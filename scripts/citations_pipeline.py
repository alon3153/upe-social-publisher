"""External-citation pipeline: the state machine for third-party authority actions.

States: drafted -> awaiting_founder -> submitted -> live -> verified_cited
- verify() crawls target_url for items in submitted/live and advances them
  automatically when the page exists and mentions Uproduction (no founder click needed).
- overdue_reminders() lists awaiting_founder items older than REMIND_HOURS for
  the daily email nag.
- digest_html() renders the weekly one-look approval digest (RTL Hebrew).
"""
import json, datetime, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
STATE = ROOT.parent / "state" / "citations.json"
REMIND_HOURS = 72
UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) upe-citation-verifier"}

STATE_HE = {"drafted": "טיוטה", "awaiting_founder": "ממתין לאלון", "submitted": "הוגש",
            "live": "באוויר", "verified_cited": "מאומת ✓"}


def load(path=None):
    p = Path(path) if path else STATE
    return json.loads(p.read_text(encoding="utf-8"))


def save(data, path=None):
    p = Path(path) if path else STATE
    data["updated"] = datetime.date.today().isoformat()
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def verified_count(data=None):
    data = data or load()
    return sum(1 for i in data["items"] if i["state"] == "verified_cited")


def _fetch(url):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", errors="replace")


def verify(data=None, path=None, fetch=_fetch, today=None):
    """Advance submitted->live->verified_cited by crawling target_url.
    live = the page responds; verified_cited = it mentions Uproduction/upe.co.il."""
    data = data or load(path)
    today = today or datetime.date.today().isoformat()
    changed = []
    for item in data["items"]:
        if item["state"] not in ("submitted", "live") or not item.get("target_url"):
            continue
        try:
            html = fetch(item["target_url"]).lower()
        except Exception:
            continue  # unreachable today — retry next run
        new_state = "verified_cited" if ("uproduction" in html or "upe.co.il" in html) else "live"
        if new_state != item["state"]:
            item["state"], item["since"] = new_state, today
            changed.append(f'{item["id"]} → {new_state}')
    if changed:
        save(data, path)
    return changed


PRESS_FOLLOWUP_DAYS = (5, 10)


def overdue_reminders(data=None, now=None):
    """Daily-email nags: awaiting_founder items older than REMIND_HOURS, plus
    day-5/day-10 follow-up prompts for press pitches that were sent (submitted)."""
    try:
        data = data or load()
    except FileNotFoundError:
        return []
    now = now or datetime.datetime.now()
    out = []
    for item in data["items"]:
        since = datetime.datetime.fromisoformat(item["since"])
        hours = (now - since).total_seconds() / 3600
        days = int(hours // 24)
        if item["state"] == "awaiting_founder" and hours >= REMIND_HOURS:
            out.append(f'{item["title"]} — {item["action"]} (ממתין {days} ימים)')
        elif (item["state"] == "submitted" and item.get("kind") == "press"
              and days in PRESS_FOLLOWUP_DAYS
              and days not in item.get("followups_handled", [])):
            out.append(f'📨 follow-up לפיץ\' {item["title"]} — יום {days} ללא מענה, שלח תזכורת')
    return out


def digest_html(data=None):
    """Weekly approval digest: everything pending, one look, ~2 minutes."""
    data = data or load()
    waiting = [i for i in data["items"] if i["state"] == "awaiting_founder"]
    other = [i for i in data["items"] if i["state"] != "awaiting_founder"]
    v = verified_count(data)

    def row(i):
        url = f' <span dir="ltr">{i["target_url"]}</span>' if i.get("target_url") else ""
        return (f'<tr><td dir="rtl" style="padding:4px 8px;">{i["title"]}</td>'
                f'<td dir="rtl" style="padding:4px 8px;">{STATE_HE.get(i["state"], i["state"])}</td>'
                f'<td dir="rtl" style="padding:4px 8px;">{i["action"]}{url}</td></tr>')

    head = ('<tr><th dir="rtl" style="padding:4px 8px;">פעולה</th>'
            '<th dir="rtl" style="padding:4px 8px;">מצב</th>'
            '<th dir="rtl" style="padding:4px 8px;">מה צריך</th></tr>')
    gate_note = ("" if v >= 3 else
                 f'<p dir="rtl" style="color:#946200;">🔒 יצירת עמודי תוכן חדשים מושהית עד 3 ציטוטים חיצוניים מאומתים (כרגע {v}).</p>')
    return (f'<h3 dir="rtl">📮 דיגסט ציטוטים חיצוניים — ממתין לך ({len(waiting)})</h3>'
            f'<table dir="rtl" style="border-collapse:collapse;border:1px solid #ddd;">{head}'
            + "".join(row(i) for i in waiting) + "</table>"
            + (f'<h4 dir="rtl">בתהליך/מאומת</h4>'
               f'<table dir="rtl" style="border-collapse:collapse;border:1px solid #ddd;">{head}'
               + "".join(row(i) for i in other) + "</table>" if other else "")
            + gate_note)


def summary_line(data=None):
    try:
        data = data or load()
    except FileNotFoundError:
        return ""
    c = {}
    for i in data["items"]:
        c[i["state"]] = c.get(i["state"], 0) + 1
    return " · ".join(f"{STATE_HE.get(k, k)}: {v}" for k, v in c.items())
