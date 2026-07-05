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
