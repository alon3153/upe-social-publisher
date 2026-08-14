import importlib.util
import sys
from pathlib import Path


ROOT = Path(__file__).parents[1]
SCRIPT = ROOT / "scripts" / "resend_pending.py"


def _load_module():
    sys.path.insert(0, str(ROOT))
    spec = importlib.util.spec_from_file_location("resend_pending", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_reminder_offers_one_approve_all_button_per_day(monkeypatch):
    """14.08: the reminder had per-post buttons only, so a single click left 8 of
    9 rows pending while Alon reported the batch approved."""
    resend = _load_module()
    monkeypatch.setattr(sys, "argv", ["resend_pending.py"])
    rows = [
        {"id": 1, "day": 103, "network": "facebook", "account": "fb", "lang": "en",
         "token": "tok-103", "status": "pending"},
        {"id": 2, "day": 103, "network": "linkedin", "account": "li_personal",
         "lang": "he", "token": "tok-103b", "status": "pending"},
        {"id": 3, "day": 104, "network": "linkedin", "account": "li_spain",
         "lang": "es", "token": "tok-104", "status": "pending"},
    ]
    monkeypatch.setattr(resend.queue, "_req", lambda *a, **kw: rows)

    sent = {}
    daily = resend._load_daily()
    monkeypatch.setattr(daily, "post_card", lambda r: f"<card {r['id']}>")
    monkeypatch.setattr(daily, "send_graph_html",
                        lambda subj, html: sent.update(subject=subj, html=html) or (True, "202"))
    monkeypatch.setattr(resend, "_load_daily", lambda: daily)

    assert resend.main() == 0

    html = sent["html"]
    assert "action=approve_all&day=103&token=tok-103" in html
    assert "action=approve_all&day=104&token=tok-104" in html
    assert "אשר הכל (2 פוסטים)" in html   # day 103
    assert "אשר הכל (1 פוסטים)" in html   # day 104
    for card in ("<card 1>", "<card 2>", "<card 3>"):
        assert card in html
