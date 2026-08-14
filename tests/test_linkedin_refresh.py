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
    """Stand in for publishers.linkedin, which _token_is_live imports lazily.

    `from publishers import linkedin` reads the ATTRIBUTE on the publishers
    package, so patching sys.modules is not enough once any other test file has
    already imported the real module — it passed alone and failed in the suite.
    """
    import publishers
    stub = types.ModuleType("publishers.linkedin")
    stub.introspect_token = lambda token: {"active": active}
    monkeypatch.setattr(publishers, "linkedin", stub)
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

    assert refresher._refresh_shared() == 0
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

    assert refresher._refresh_shared() == 0
    assert "no refresh needed" in capsys.readouterr().out


def test_revoked_token_without_refresh_token_fails_loudly(monkeypatch, capsys):
    refresher = _load_module()
    _stub_introspection(monkeypatch, active=False)
    monkeypatch.setattr(refresher.queue, "get_oauth", lambda provider: {
        "access_token": "revoked", "refresh_token": "",
        "expires_at": "2099-01-01T00:00:00Z"})

    assert refresher._refresh_shared() == 1
    assert "ACTION NEEDED" in capsys.readouterr().out


def pytest_fail():
    raise AssertionError("a live token must not be exchanged")


def test_advocate_tokens_are_refreshed_before_they_expire(monkeypatch, capsys):
    """Nothing covered these until 14.08 — both advocates were due to die 29.08."""
    refresher = _load_module()
    _stub_introspection(monkeypatch, active=True)
    monkeypatch.setattr(refresher.queue, "list_advocates", lambda: [
        {"account": "li_danielle", "access_token": "old", "refresh_token": "r1",
         "expires_at": "2026-08-15T00:00:00Z"},          # inside the 14d window
        {"account": "li_natalia", "access_token": "fine", "refresh_token": "r2",
         "expires_at": "2099-01-01T00:00:00Z"},          # untouched
        {"account": "li_main_callback", "access_token": "staging",
         "refresh_token": "r3", "expires_at": "2026-08-15T00:00:00Z"},
    ])
    monkeypatch.setattr(refresher, "_exchange", lambda rt: {
        "access_token": "new", "refresh_token": "next", "expires_in": 5184000})
    updates = []
    monkeypatch.setattr(refresher.queue, "update_advocate",
                        lambda account, **f: updates.append((account, f["access_token"])))

    assert refresher.refresh_advocates() == 0
    assert updates == [("li_danielle", "new")]      # staging row is not a person
    assert "li_natalia: still valid" in capsys.readouterr().out


def test_advocate_needing_a_reconnect_is_reported_as_action_needed(monkeypatch, capsys):
    refresher = _load_module()
    _stub_introspection(monkeypatch, active=False)
    monkeypatch.setattr(refresher.queue, "list_advocates", lambda: [
        {"account": "li_dorin", "access_token": "dead", "refresh_token": "",
         "expires_at": "2099-01-01T00:00:00Z"}])

    assert refresher.refresh_advocates() == 1
    out = capsys.readouterr().out
    assert "ACTION NEEDED" in out and "li_dorin" in out


def test_main_sweeps_advocates_even_when_the_shared_credential_is_dead(monkeypatch):
    """A dead company token must not mask employee credentials quietly expiring."""
    refresher = _load_module()
    monkeypatch.setattr(refresher, "_refresh_shared", lambda: 1)
    called = []
    monkeypatch.setattr(refresher, "refresh_advocates", lambda: called.append(1) or 0)

    assert refresher.main() == 1
    assert called == [1]
