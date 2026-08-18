import importlib.util
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _load():
    spec = importlib.util.spec_from_file_location(
        "daily_email", os.path.join(ROOT, "scripts", "daily_email.py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


daily = _load()


def _pending(day, network="facebook"):
    return {"id": f"{day}-{network}", "token": f"tok{day}", "day": day,
            "network": network, "account": "uproductionevents", "lang": "en",
            "caption": "text", "image_url": "http://img/x.jpg",
            "scheduled_date": "2026-08-15"}


def test_carryover_excludes_todays_new_day(monkeypatch):
    rows = [_pending(107), _pending(110)]
    monkeypatch.setattr(daily.queue, "_req", lambda *a, **k: rows)

    out = daily.carryover_pending(exclude_day=110)

    assert [r["day"] for r in out] == [107]


def test_carryover_survives_a_supabase_error(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("supabase down")
    monkeypatch.setattr(daily.queue, "_req", boom)

    assert daily.carryover_pending() == []


def test_carryover_html_has_one_approve_all_per_day():
    html = daily.carryover_html([_pending(107), _pending(107, "instagram"), _pending(105)])

    assert html.count("action=approve_all") == 2
    assert "day=107" in html and "day=105" in html
    assert "יום 107 — 2 פוסטים" in html


def test_digest_appends_stuck_posts_to_the_daily_email():
    fresh = [_pending(111)]
    html = daily.email_html_digest(111, "http://approve/all", fresh, carry=[_pending(107)])

    assert "תקועים מימים קודמים" in html
    assert "day=107" in html


def test_no_new_day_still_emails_the_stuck_ones(monkeypatch):
    sent = {}
    monkeypatch.setattr(daily, "carryover_pending", lambda *a, **k: [_pending(107)])
    monkeypatch.setattr(daily, "pick_next_day", lambda: None)
    monkeypatch.setattr(daily, "send_graph_html",
                        lambda subj, html: (sent.update(subj=subj, html=html), (True, "202"))[1])

    assert daily.main() == 0
    assert "107" in sent["subj"]
    assert "action=approve_all" in sent["html"]


def test_no_new_day_and_nothing_stuck_sends_nothing(monkeypatch):
    monkeypatch.setattr(daily, "carryover_pending", lambda *a, **k: [])
    monkeypatch.setattr(daily, "pick_next_day", lambda: None)
    monkeypatch.setattr(daily, "send_graph_html",
                        lambda *a, **k: (_ for _ in ()).throw(AssertionError("must not email")))

    assert daily.main() == 0
