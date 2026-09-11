import io, json, urllib.error

import pytest

from publishers import kie


def _resp(payload):
    class R:
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def read(self): return json.dumps(payload).encode()
    return R()


def test_api_key_missing(monkeypatch):
    monkeypatch.delenv("KIE_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="KIE_API_KEY not set"):
        kie.api_key()
    ok, info = kie.verify_key()
    assert ok is False and "not set" in info


def test_api_key_stripped(monkeypatch):
    monkeypatch.setenv("KIE_API_KEY", "  k-123 \n")
    assert kie.api_key() == "k-123"


def test_credits_sends_bearer_and_parses(monkeypatch):
    monkeypatch.setenv("KIE_API_KEY", "k-123")
    seen = {}

    def fake_open(req, timeout=None):
        seen["url"] = req.full_url
        seen["auth"] = req.get_header("Authorization")
        return _resp({"code": 200, "msg": "success", "data": 42})

    monkeypatch.setattr(kie.urllib.request, "urlopen", fake_open)
    assert kie.credits() == 42
    assert seen["url"] == "https://api.kie.ai/api/v1/chat/credit"
    assert seen["auth"] == "Bearer k-123"
    assert kie.verify_key() == (True, "valid; 42 credits remaining")


def test_api_level_error_is_reported_without_key(monkeypatch):
    monkeypatch.setenv("KIE_API_KEY", "k-secret")
    monkeypatch.setattr(kie.urllib.request, "urlopen",
                        lambda req, timeout=None: _resp({"code": 401, "msg": "unauthorized"}))
    ok, info = kie.verify_key()
    assert ok is False
    assert "401" in info and "unauthorized" in info
    assert "k-secret" not in info


def test_http_error_is_reported(monkeypatch):
    monkeypatch.setenv("KIE_API_KEY", "k-123")

    def boom(req, timeout=None):
        raise urllib.error.HTTPError(req.full_url, 403, "Forbidden", {}, io.BytesIO(b'{"msg":"no"}'))

    monkeypatch.setattr(kie.urllib.request, "urlopen", boom)
    ok, info = kie.verify_key()
    assert ok is False and "HTTP 403" in info
