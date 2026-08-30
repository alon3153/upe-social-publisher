"""External-citation pipeline: the state machine for third-party authority actions.

States: drafted -> awaiting_founder -> submitted -> live -> verified_cited
        (any state may also terminate in closed_no_recontact — a deliberate decision to
         stop pursuing a channel; it never nags and never re-crawls)
- verify() crawls target_url for items in awaiting_founder/submitted/live and advances
  them automatically when the page exists and mentions Uproduction (no founder click
  needed) — so a submission Alon completed outside the pipeline stops being nagged.
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
            "live": "באוויר", "verified_cited": "מאומת ✓",
            # terminal, deliberate: a channel we decided NOT to contact again. Distinct
            # from "pending" — the four press pitches sat as open items for 55 days while
            # the same email had already gone out 4-5 times to each editor.
            "closed_no_recontact": "סגור — לא לפנות שוב"}


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
    # Directory/entity hosts (Crunchbase, Clutch, G2, Cvent) bot-block plain
    # urllib with a 403, which would make the citation gate permanently
    # unreachable. Fall back to the keyless r.jina.ai reader (same technique the
    # digital-maintenance doctor uses) so a live profile can still be verified.
    req = urllib.request.Request(url, headers=UA)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.read().decode("utf-8", errors="replace")
    except Exception:
        proxied = "https://r.jina.ai/" + url
        req2 = urllib.request.Request(proxied, headers=UA)
        with urllib.request.urlopen(req2, timeout=45) as r:
            return r.read().decode("utf-8", errors="replace")


# A brand-slugged URL echoes its own path inside a bot-challenge page, so the naive
# substring test made any blocked page "verify" itself: themanifest.com/company/
# uproduction-events returned a Cloudflare interstitial containing three literal
# "uproduction" hits and no profile. r.jina.ai serves challenge HTML with HTTP 200, so
# the status code cannot catch it either.
_BLOCK_MARKERS = (
    "just a moment", "enable javascript and cookies", "cf-browser-verification",
    "cf_chl_opt", "__cf_chl", "checking your browser", "attention required",
    "datadome", "captcha-delivery", "px-captcha", "access denied",
    "sorry, you have been blocked", "request unsuccessful",
)


def is_block_page(html):
    """Marker-based only. A length heuristic was tempting but wrong: it would reject
    legitimately terse pages, and a real challenge page always carries one of these."""
    low = (html or "").lower()
    return any(m in low for m in _BLOCK_MARKERS)


def _mentions_us(html):
    """True only when the page really carries our name — never off a challenge page."""
    if is_block_page(html):
        return False
    low = (html or "").lower()
    return "uproduction" in low or "upe.co.il" in low


# Terminal items were never re-examined, so the board could not notice a profile going
# down -- or a real review landing. The first verified Clutch review (13.08.2026) sat
# unnoticed while the weekly email kept reporting "0 reviews".
REVERIFY_DAYS = 14


def verify(data=None, path=None, fetch=_fetch, today=None):
    """Advance submitted->live->verified_cited by crawling target_url.
    live = the page responds; verified_cited = it mentions Uproduction/upe.co.il.

    awaiting_founder items are crawled too, but only ever jump straight to
    verified_cited: Alon regularly completes a submission outside this pipeline
    (Clutch, G2 and the LinkedIn articles all went live in July 2026 while their
    items sat here), and without this the daily email nags him forever for work
    already done. A merely-reachable page proves nothing for these — a directory
    homepage responds whether or not we are listed — so a live page that does not
    mention us leaves the item exactly where it was.
    """
    data = data or load(path)
    today = today or datetime.date.today().isoformat()
    changed = []
    for item in data["items"]:
        if not item.get("target_url"):
            # Nothing to crawl. Seven of twelve items were in this state, including
            # entity_wikidata -- skipped here before any fetch, so it could never advance
            # and nagged Alon daily for 30 days about work finished on 08.08. Mark it as
            # needing a human check-off instead of pretending it is pending automation.
            item["unverifiable"] = True
            continue
        item["unverifiable"] = False
        if item["state"] == "verified_cited" and not _due_reverify(item, today):
            continue
        if item["state"] not in ("awaiting_founder", "submitted", "live", "verified_cited"):
            continue
        try:
            html = fetch(item["target_url"])
        except Exception:
            continue  # unreachable today — retry next run
        if is_block_page(html):
            item["last_check"] = today
            item["last_check_result"] = "blocked"
            continue  # a bot wall is not evidence either way
        cited = _mentions_us(html)
        item["last_check"] = today
        item["last_check_result"] = "cited" if cited else "reachable"
        if item["state"] == "awaiting_founder" and not cited:
            continue  # cannot conclude the founder acted; keep nagging
        if item["state"] == "verified_cited":
            if not cited:  # a profile that disappeared must not stay green
                item["state"], item["since"] = "live", today
                changed.append(f'{item["id"]} → live (no longer mentions us)')
            continue
        new_state = "verified_cited" if cited else "live"
        if new_state != item["state"]:
            item["state"], item["since"] = new_state, today
            changed.append(f'{item["id"]} → {new_state}')
    if changed:
        save(data, path)
    return changed


def _due_reverify(item, today):
    last = item.get("last_check") or item.get("since")
    if not last:
        return True
    try:
        d = (datetime.date.fromisoformat(today) - datetime.date.fromisoformat(last[:10])).days
    except ValueError:
        return True
    return d >= REVERIFY_DAYS


PRESS_FOLLOWUP_DAYS = (5, 10)
STALE_NAG_DAYS = 14


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
            if item.get("unverifiable") and days > STALE_NAG_DAYS:
                # No target_url means nothing will ever clear this automatically. After a
                # fortnight, stop asserting it is outstanding and ask for a human answer.
                out.append(f'❓ {item["title"]} — לא ניתן לאימות אוטומטי (אין URL). '
                           f'ממתין {days} ימים — לאשר ידנית שבוצע, או להוסיף כתובת לאימות.')
            else:
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
