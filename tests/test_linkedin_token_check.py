import importlib.util
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "scripts" / "linkedin_token_check.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("linkedin_token_check", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_inactive_token_alerts_without_emitting_replacement_token(monkeypatch, capsys):
    monitor = _load_module()
    monkeypatch.setattr(monitor, "CID", "client-id")
    monkeypatch.setattr(monitor, "CSECRET", "client-secret")
    monkeypatch.setattr(monitor, "TOKEN", "expired-token")
    monkeypatch.setattr(monitor, "introspect", lambda token=None: {"active": False})

    alerts = []
    monkeypatch.setattr(
        monitor,
        "email",
        lambda subject, html: alerts.append((subject, html)),
    )

    assert monitor.main() == 0
    assert len(alerts) == 1
    assert "הטוקן לא תקף" in alerts[0][0]
    assert "ACCESS_TOKEN=" not in capsys.readouterr().out
    assert not hasattr(monitor, "refresh")


def test_healthy_token_does_not_email(monkeypatch):
    monitor = _load_module()
    monkeypatch.setattr(monitor, "CID", "client-id")
    monkeypatch.setattr(monitor, "CSECRET", "client-secret")
    monkeypatch.setattr(monitor, "TOKEN", "healthy-token")
    monkeypatch.setattr(
        monitor,
        "introspect",
        lambda token=None: {
            "active": True,
            "expires_at": monitor.time.time() + 60 * 86400,
            "scope": "w_member_social w_organization_social",
        },
    )

    alerts = []
    monkeypatch.setattr(monitor, "email", lambda *args: alerts.append(args))

    assert monitor.main() == 0
    assert alerts == []


def test_active_token_missing_write_scopes_alerts(monkeypatch):
    monitor = _load_module()
    monkeypatch.setattr(monitor, "CID", "client-id")
    monkeypatch.setattr(monitor, "CSECRET", "client-secret")
    monkeypatch.setattr(monitor, "TOKEN", "active-but-useless")
    monkeypatch.setattr(
        monitor,
        "introspect",
        lambda token=None: {
            "active": True,
            "expires_at": monitor.time.time() + 60 * 86400,
            "scope": "openid profile",
        },
    )
    alerts = []
    monkeypatch.setattr(monitor, "email", lambda *args: alerts.append(args))

    assert monitor.main() == 0
    assert len(alerts) == 1
    assert "w_member_social" in alerts[0][0]
    assert "w_organization_social" in alerts[0][0]
