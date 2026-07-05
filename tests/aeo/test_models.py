import importlib


def load(monkeypatch, env):
    for k in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY", "GEMINI_API_KEY"):
        monkeypatch.delenv(k, raising=False)
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    import scripts.aeo_models as m
    return importlib.reload(m)


def test_available_models_claude_only(monkeypatch):
    m = load(monkeypatch, {"ANTHROPIC_API_KEY": "x"})
    assert m.available_models() == ["claude"]


def test_available_models_all(monkeypatch):
    m = load(monkeypatch, {"ANTHROPIC_API_KEY": "x", "OPENAI_API_KEY": "y", "GEMINI_API_KEY": "z"})
    assert set(m.available_models()) == {"claude", "chatgpt", "gemini"}


def test_ask_claude_parses_text(monkeypatch):
    import json
    m = load(monkeypatch, {"ANTHROPIC_API_KEY": "x"})

    def fake_http(url, data, headers):
        assert "api.anthropic.com" in url
        assert headers["x-api-key"] == "x"
        return json.dumps({"content": [{"type": "text", "text": "hello world"}]})

    out = m.ask("claude", "hi", _http=fake_http)
    assert out == "hello world"


def test_ask_claude_grounded_adds_web_search_tool(monkeypatch):
    import json
    m = load(monkeypatch, {"ANTHROPIC_API_KEY": "x"})

    def fake_http(url, data, headers):
        body = json.loads(data)
        assert body["tools"][0]["type"] == "web_search_20250305"
        return json.dumps({"content": [{"type": "text", "text": "grounded"}]})

    assert m.ask("claude", "hi", _http=fake_http, grounded=True) == "grounded"


def test_ask_chatgpt_grounded_uses_search_model(monkeypatch):
    import json
    m = load(monkeypatch, {"OPENAI_API_KEY": "y"})

    def fake_http(url, data, headers):
        body = json.loads(data)
        assert body["model"] == "gpt-4o-search-preview"
        assert "web_search_options" in body
        return json.dumps({"choices": [{"message": {"content": "grounded"}}]})

    assert m.ask("chatgpt", "hi", _http=fake_http, grounded=True) == "grounded"


def test_ask_gemini_grounded_adds_google_search_tool(monkeypatch):
    import json
    m = load(monkeypatch, {"GEMINI_API_KEY": "z"})

    def fake_http(url, data, headers):
        body = json.loads(data)
        assert body["tools"] == [{"google_search": {}}]
        return json.dumps({"candidates": [{"content": {"parts": [{"text": "grounded"}]}}]})

    assert m.ask("gemini", "hi", _http=fake_http, grounded=True) == "grounded"


def test_grounded_falls_back_to_plain_on_error(monkeypatch):
    import json
    m = load(monkeypatch, {"ANTHROPIC_API_KEY": "x"})
    calls = []

    def fake_http(url, data, headers):
        body = json.loads(data)
        calls.append("grounded" if "tools" in body else "plain")
        if "tools" in body:
            raise RuntimeError("HTTP 400: tool not enabled")
        return json.dumps({"content": [{"type": "text", "text": "fallback"}]})

    assert m.ask("claude", "hi", _http=fake_http, grounded=True) == "fallback"
    assert calls == ["grounded", "plain"]


def test_gemini_joins_multiple_parts(monkeypatch):
    import json
    m = load(monkeypatch, {"GEMINI_API_KEY": "z"})

    def fake_http(url, data, headers):
        return json.dumps({"candidates": [{"content": {"parts": [{"text": "a "}, {"text": "b"}]}}]})

    assert m.ask("gemini", "hi", _http=fake_http) == "a b"
