"""Secrets must never reach the AEO history / reports (GitHub secret-scanning alert #1)."""
import io, json, urllib.error
import scripts.aeo_models as m
import scripts.aeo_probe as probe

# Synthetic, obviously fake values built at runtime (no real-looking literal in the repo).
FAKE_AQ = "AQ." + "Zz" * 20
FAKE_AIZA = "AIza" + "Y" * 35
FAKE_SK = "sk-proj-" + "x1" * 15
FAKE_BEARER = "Bearer " + "t0k" * 10


def test_redact_masks_all_patterns():
    raw = (f"HTTP 402 from https://generativelanguage.googleapis.com/v1beta/models/g:generateContent?key={FAKE_AQ}: "
           f"{FAKE_AIZA} {FAKE_SK} Authorization: {FAKE_BEARER} https://x.test/?a=1&access_token=" + "abcd" + "efgh123")
    out = m.redact(raw)
    for secret in (FAKE_AQ, FAKE_AIZA, FAKE_SK, "t0kt0kt0k", "abcdefgh123"):
        assert secret not in out
    assert m.find_secrets(out) == []
    assert "HTTP 402" in out  # the useful part of the error survives


def test_find_secrets_never_returns_value():
    hits = m.find_secrets(f"x {FAKE_AQ} y")
    assert hits and all(FAKE_AQ not in h for h in hits)


def test_gemini_key_sent_in_header_not_url(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", FAKE_AQ)
    seen = {}

    def fake_http(url, data, headers):
        seen["url"], seen["headers"] = url, headers
        return json.dumps({"candidates": [{"content": {"parts": [{"text": "ok"}]}}]})

    assert m.ask("gemini", "hi", _http=fake_http) == "ok"
    assert FAKE_AQ not in seen["url"] and "key=" not in seen["url"]
    assert seen["headers"].get("x-goog-api-key") == FAKE_AQ


def test_post_http_error_is_redacted(monkeypatch):
    def boom(req, timeout=0):
        raise urllib.error.HTTPError(req.full_url, 402, "pay", {}, io.BytesIO(b'{"error": "no credit"}'))
    monkeypatch.setattr(m.urllib.request, "urlopen", boom)
    try:
        m._post(f"https://example.test/v1?key={FAKE_AQ}", b"{}", {})
    except RuntimeError as e:
        assert FAKE_AQ not in str(e) and "402" in str(e)
    else:
        raise AssertionError("expected RuntimeError")


def test_append_history_never_writes_secret(tmp_path):
    path = tmp_path / "aeo_daily_history.json"
    scorecard = {"date": "2026-11-04", "errors": [f"gemini/q1: RuntimeError: HTTP 402 from https://g.test/x?key={FAKE_AQ}: boom"]}
    probe.append_history(scorecard, path)
    text = path.read_text()
    assert FAKE_AQ not in text and m.find_secrets(text) == []


def test_check_no_secrets_cli(tmp_path):
    import scripts.check_no_secrets as chk
    clean, dirty = tmp_path / "clean.json", tmp_path / "dirty.json"
    clean.write_text('{"errors": ["HTTP 402 from https://g.test/x?key=[REDACTED]"]}')
    dirty.write_text(json.dumps({"errors": [f"?key={FAKE_AQ}"]}))
    assert chk.main([str(clean)]) == 0
    assert chk.main([str(dirty)]) == 1


def test_no_false_positive_on_url_slugs():
    assert m.find_secrets("https://x.test/event-risk-management-guide-2026") == []
    assert m.find_secrets("10-questions-to-ask-before-booking") == []
