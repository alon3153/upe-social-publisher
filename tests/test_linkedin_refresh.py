import importlib.util
import sys
import types
from pathlib import Path


ROOT = Path(__file__).parents[1]
SCRIPT = ROOT / "scripts" / "linkedin_refresh.py"


def _load_module():
    sys.path.insert(0, str(ROOT))
    spec = importlib.util.spec_from_file_location("linkedin_refresh", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _stub_introspection(monkeypatch, active):
    """Stand in for publishers.linkedin, which _token_is_live imports lazily."""
    stub = types.ModuleType("publishers.linkedin")
    stub.introspect_token = lambda token: {"active": active}
    monkeypatch.setitem(sys.modules, "publishers.linkedin", stub)


def test_revoked_token_refreshes_even_with_a_distant_expiry(monkeypatch, capsys):
    """The Aug-13 outage: active=False while expires_at still read 56 days out."""
    refresher = _load_module()
    _stub_introspection(monkeypatch, active=False)
    monkeypatch.setattr(refresher.queue, "get_oauth", lambda provider: {
        "access_token": "revoked", "refresh_token": "refresh-me",
        "expires_at": "2099-01-01T00:00:00Z"})

    exchanged = []
    monkeypatch.setattr(refresher, "_exchange", lambda rt: exchanged.append(rt) or {
        "access_token": "fresh", "refresh_token": "next", "expires_in": 5184000})
    saved = []
    monkeypatch.setattr(refresher, "_save", lambda *a, **kw: saved.append(a))

    assert refresher.main() == 0
    assert exchanged == ["refresh-me"]
    assert saved and saved[0][0] == "fresh"
    assert "INACTIVE" in capsys.readouterr().out


def test_live_token_with_a_distant_expiry_is_left_alone(monkeypatch, capsys):
    refresher = _load_module()
    _stub_introspection(monkeypatch, active=True)
    monkeypatch.setattr(refresher.queue, "get_oauth", lambda provider: {
        "access_token": "good", "refresh_token": "refresh-me",
        "expires_at": "2099-01-01T00:00:00Z"})
    monkeypatch.setattr(refresher, "_exchange", lambda rt: pytest_fail())

    assert refresher.main() == 0
    assert "no refresh needed" in capsys.readouterr().out


def test_revoked_token_without_refresh_token_fails_loudly(monkeypatch, capsys):
    refresher = _load_module()
    _stub_introspection(monkeypatch, active=False)
    monkeypatch.setattr(refresher.queue, "get_oauth", lambda provider: {
        "access_token": "revoked", "refresh_token": "",
        "expires_at": "2099-01-01T00:00:00Z"})

    assert refresher.main() == 1
    assert "ACTION NEEDED" in capsys.readouterr().out


def pytest_fail():
    raise AssertionError("a live token must not be exchanged")
