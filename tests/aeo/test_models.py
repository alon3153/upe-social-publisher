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
