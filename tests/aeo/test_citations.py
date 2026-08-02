import json, datetime
import scripts.citations_pipeline as cp


def _data():
    return {"items": [
        {"id": "a", "title": "A", "state": "awaiting_founder", "since": "2026-07-01",
         "action": "do", "target_url": "", "kind": "press"},
        {"id": "b", "title": "B", "state": "submitted", "since": "2026-07-01",
         "action": "do", "target_url": "https://x.com/p", "kind": "directory"},
        {"id": "c", "title": "C", "state": "live", "since": "2026-07-01",
         "action": "do", "target_url": "https://y.com/p", "kind": "directory"},
    ]}


def test_verify_advances_states(tmp_path):
    p = tmp_path / "citations.json"
    p.write_text(json.dumps(_data()), encoding="utf-8")

    def fetch(url):
        return "About Uproduction Events" if "y.com" in url else "<html>directory page</html>"

    changed = cp.verify(path=str(p), fetch=fetch, today="2026-07-05")
    data = json.loads(p.read_text())
    states = {i["id"]: i["state"] for i in data["items"]}
    assert states["b"] == "live" and states["c"] == "verified_cited"
    assert len(changed) == 2


def test_verify_self_heals_awaiting_founder_already_live(tmp_path):
    """A submission Alon completed outside the pipeline must stop nagging by itself."""
    d = _data()
    d["items"][0]["target_url"] = "https://dir.com/uproduction"
    p = tmp_path / "citations.json"
    p.write_text(json.dumps(d), encoding="utf-8")

    changed = cp.verify(path=str(p), fetch=lambda u: "Uproduction Events profile",
                        today="2026-07-31")
    states = {i["id"]: i["state"] for i in json.loads(p.read_text())["items"]}
    assert states["a"] == "verified_cited"
    assert "a → verified_cited" in changed


def test_verify_keeps_nagging_when_directory_page_lacks_us(tmp_path):
    """A reachable directory homepage proves nothing — the item must stay awaiting."""
    d = _data()
    d["items"][0]["target_url"] = "https://www.g2.com"
    p = tmp_path / "citations.json"
    p.write_text(json.dumps(d), encoding="utf-8")

    changed = cp.verify(path=str(p), fetch=lambda u: "<html>G2 home</html>",
                        today="2026-07-31")
    states = {i["id"]: i["state"] for i in json.loads(p.read_text())["items"]}
    assert states["a"] == "awaiting_founder"
    assert not any(c.startswith("a →") for c in changed)


def test_verified_count_and_overdue():
    d = _data()
    d["items"][2]["state"] = "verified_cited"
    assert cp.verified_count(d) == 1
    now = datetime.datetime(2026, 7, 5, 12, 0)
    rem = cp.overdue_reminders(d, now=now)
    assert len(rem) == 1 and "A" in rem[0]


def test_digest_html_renders_gate_note():
    html = cp.digest_html(_data())
    assert "דיגסט" in html and "מושהית" in html


def test_verify_survives_fetch_errors(tmp_path):
    p = tmp_path / "citations.json"
    p.write_text(json.dumps(_data()), encoding="utf-8")

    def fetch(url):
        raise RuntimeError("timeout")

    assert cp.verify(path=str(p), fetch=fetch) == []


def test_press_followup_reminders_day5():
    d = {"items": [{"id": "p", "title": "P", "state": "submitted", "since": "2026-07-01",
                    "action": "sent", "target_url": "", "kind": "press"}]}
    now = datetime.datetime(2026, 7, 6, 12, 0)
    rem = cp.overdue_reminders(d, now=now)
    assert len(rem) == 1 and "follow-up" in rem[0]


def test_press_followup_skipped_when_handled():
    d = {"items": [{"id": "p", "title": "P", "state": "submitted", "since": "2026-07-01",
                    "action": "sent", "target_url": "", "kind": "press",
                    "followups_handled": [5]}]}
    now = datetime.datetime(2026, 7, 6, 12, 0)
    assert cp.overdue_reminders(d, now=now) == []
    now10 = datetime.datetime(2026, 7, 11, 12, 0)
    assert len(cp.overdue_reminders(d, now=now10)) == 1
