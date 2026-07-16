#!/usr/bin/env python3
"""
UPE Autonomy Watchdog — daily cross-channel health check for the social/content
engine. Emails Alon (via Microsoft Graph, Focused Inbox) ONLY when something needs
attention; silent when everything is healthy.

Covers the silent-failure gaps that publishing/token jobs don't:
  1. Content-bank RUNWAY  — days of pre-written posts left before the bank runs dry
  2. PUBLISH FAILURES     — posts that errored in the last N days (e.g. token/scope)
  3. APPROVAL BACKLOG     — posts stuck pending (emails sent but never approved)

Exit 0 always (a watchdog must not fail the schedule); it reports via email.
"""
import os, re, sys, glob, datetime, json, urllib.request, urllib.parse, urllib.error

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from publishers import queue

TO = os.environ.get("APPROVAL_TO") or "alon@upe.co.il"
RUNWAY_WARN_DAYS = int(os.environ.get("RUNWAY_WARN_DAYS", "21"))
FAIL_LOOKBACK_DAYS = int(os.environ.get("FAIL_LOOKBACK_DAYS", "3"))
BACKLOG_AGE_DAYS = int(os.environ.get("BACKLOG_AGE_DAYS", "2"))


def _iso(days_ago):
    return (datetime.datetime.utcnow() - datetime.timedelta(days=days_ago)).strftime("%Y-%m-%dT%H:%M:%S")


def check_runway():
    days = []
    for f in glob.glob(os.path.join(ROOT, "content", "days", "*day*.json")):
        m = re.search(r"day(\d+)", os.path.basename(f))
        if m:
            days.append(int(m.group(1)))
    if not days:
        return ["⚠️ בנק התוכן: לא נמצאו קבצי content/days — הפרסום ייעצר!"]
    max_day = max(set(days))
    try:
        pub = queue.published_days()
        # ignore junk/test day numbers (e.g. 9001x) outside the real bank range
        real = [d for d in pub if 1 <= d <= max_day]
        last_pub = max(real) if real else 0
    except Exception as e:
        return [f"⚠️ לא ניתן לקרוא published_days מ-Supabase: {e}"]
    runway = max_day - last_pub
    if runway <= RUNWAY_WARN_DAYS:
        return [f"🔴 בנק הפוסטים אוזל: {runway} ימים נותרו (פורסם עד יום {last_pub}, בנק עד יום {max_day}). צריך לחדש את הבנק."]
    return []


def check_failures():
    try:
        rows = queue._req("GET", "post_approvals", params={
            "select": "day,network,account,lang,error,created_at",
            "status": "eq.failed", "created_at": f"gte.{_iso(FAIL_LOOKBACK_DAYS)}",
            "order": "created_at.desc"})
    except Exception as e:
        return [f"⚠️ לא ניתן לבדוק כשלי פרסום: {e}"]
    if not rows:
        return []
    lines = [f"🔴 {len(rows)} כשלי פרסום ב-{FAIL_LOOKBACK_DAYS} הימים האחרונים:"]
    for r in rows[:10]:
        err = (r.get("error") or "")[:90]
        lines.append(f"   · יום {r.get('day')} {r.get('network')}/{r.get('account')} — {err}")
    return lines


def check_backlog():
    try:
        rows = queue._req("GET", "post_approvals", params={
            "select": "day,scheduled_date", "status": "eq.pending",
            "scheduled_date": f"lte.{(datetime.date.today() - datetime.timedelta(days=BACKLOG_AGE_DAYS)).isoformat()}"})
    except Exception as e:
        return [f"⚠️ לא ניתן לבדוק פקק אישורים: {e}"]
    if not rows:
        return []
    days = sorted({int(r["day"]) for r in rows if r.get("day") is not None})
    return [f"🟠 {len(rows)} פוסטים תקועים בהמתנה לאישור מעל {BACKLOG_AGE_DAYS} ימים (ימים: {days}). אשר/דחה במייל היומי."]


def check_duplicates():
    """Same day+network+account+lang alive more than once (pending/approved) — a
    re-enqueue bug symptom; one approve_all click then publishes twice. Keyed on
    ACCOUNT too: the 3 HE LinkedIn advocates legitimately share (day,network,lang)
    with distinct accounts — that is by design, not a duplicate."""
    try:
        rows = queue._req("GET", "post_approvals", params={
            "select": "day,network,account,lang", "status": "in.(pending,approved)"})
    except Exception as e:
        return [f"⚠️ לא ניתן לבדוק שכפולים בתור: {e}"]
    counts = {}
    for r in rows:
        k = (r.get("day"), r.get("network"), r.get("account"), r.get("lang"))
        counts[k] = counts.get(k, 0) + 1
    dups = {k: v for k, v in counts.items() if v > 1 and k[0] is not None}
    if not dups:
        return []
    days = sorted({k[0] for k in dups})
    return [f"🔴 שכפול בתור האישורים: {len(dups)} צירופי יום/רשת/שפה חיים יותר מפעם אחת (ימים: {days}). "
            f"סכנת פרסום כפול — לדחות (reject) את הסט הישן לפני אישור/פרסום."]


def check_workflows():
    """Catch WORKFLOW-LEVEL failures (GitHub Actions run conclusions) — the gap
    that let the approval email die quietly for days: the run crashed BEFORE any
    row was inserted, so there were zero failed/pending rows and runway looked
    fine. This checks the run conclusions directly."""
    token = os.environ.get("GITHUB_TOKEN", "")
    repo = os.environ.get("GITHUB_REPOSITORY", "alon3153/upe-social-publisher")
    if not token:
        print("check_workflows: no GITHUB_TOKEN — skipping workflow-run check")
        return []
    # workflow file -> (label, max hours since last run before "silent")
    # NOTE: daily-publish.yml is legacy (retired ~2026-05-29) — FB/IG now publish
    # through publish-approved.yml (handles all networks). Do not monitor it.
    critical = {
        "approval-email.yml":   ("מייל אישור יומי", 26),
        "publish-approved.yml": ("פרסום מאושרים (כל הרשתות)", 5),
        "daily-council.yml":    ("מועצת שיווק יומית", 26),
        "aeo-daily.yml":        ("AEO יומי", 26),
    }
    bad = {"failure", "cancelled", "timed_out", "startup_failure"}
    now = datetime.datetime.now(datetime.timezone.utc)
    issues = []
    for wf, (label, max_age_h) in critical.items():
        try:
            req = urllib.request.Request(
                f"https://api.github.com/repos/{repo}/actions/workflows/{wf}/runs?per_page=1",
                headers={"Authorization": f"Bearer {token}",
                         "Accept": "application/vnd.github+json",
                         "User-Agent": "upe-watchdog/1.0"})
            with urllib.request.urlopen(req, timeout=30) as r:
                runs = json.loads(r.read().decode()).get("workflow_runs") or []
        except Exception as e:
            issues.append(f"⚠️ לא ניתן לבדוק את {label} ({wf}): {e}")
            continue
        if not runs:
            issues.append(f"🔴 {label} ({wf}) — אין ריצות כלל")
            continue
        run = runs[0]
        concl, status = run.get("conclusion"), run.get("status")
        created = run.get("created_at", "1970-01-01T00:00:00Z")
        age_h = (now - datetime.datetime.fromisoformat(created.replace("Z", "+00:00"))).total_seconds() / 3600.0
        url = run.get("html_url", "")
        if status == "completed" and concl in bad:
            issues.append(f"🔴 {label} — הריצה האחרונה נכשלה ({concl}). {url}")
        elif age_h > max_age_h:
            issues.append(f"🔴 {label} — אין ריצה מזה {age_h:.0f} שעות (סף {max_age_h}). ה-cron אולי מת. {url}")
    return issues


def send_graph(subject, body_text):
    tenant = os.environ.get("MS_GRAPH_TENANT_ID"); cid = os.environ.get("MS_GRAPH_CLIENT_ID")
    secret = os.environ.get("MS_GRAPH_CLIENT_SECRET"); sender = os.environ.get("MS_GRAPH_FROM")
    if not all([tenant, cid, secret, sender]):
        print("graph creds missing — printing instead:\n", body_text); return False
    try:
        tok = urllib.parse.urlencode({"client_id": cid, "client_secret": secret,
            "scope": "https://graph.microsoft.com/.default", "grant_type": "client_credentials"}).encode()
        with urllib.request.urlopen(urllib.request.Request(
                f"https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token", data=tok,
                headers={"Content-Type": "application/x-www-form-urlencoded"}), timeout=30) as r:
            access = json.loads(r.read().decode()).get("access_token")
        html = ('<html dir="rtl" lang="he"><body style="font-family:Arial;direction:rtl;text-align:right;font-size:14px;">'
                + "".join(f"<div>{l}</div>" for l in body_text.split("\n"))
                + '<p style="color:#FBCE0A;"><b>uproduction</b> watchdog</p></body></html>')
        payload = json.dumps({"message": {"subject": subject,
            "body": {"contentType": "HTML", "content": html},
            "toRecipients": [{"emailAddress": {"address": TO}}]}, "saveToSentItems": True}).encode()
        with urllib.request.urlopen(urllib.request.Request(
                f"https://graph.microsoft.com/v1.0/users/{sender}/sendMail", data=payload,
                headers={"Authorization": f"Bearer {access}", "Content-Type": "application/json"}), timeout=30) as r:
            print("alert emailed via graph", r.status); return True
    except Exception as e:
        print("graph send failed:", e); return False


def main():
    # Immediate mode: called from an if:failure() step so a crashing workflow
    # alerts within seconds, not at the next 13:00 watchdog sweep.
    if len(sys.argv) > 2 and sys.argv[1] == "--immediate":
        msg = sys.argv[2]
        print("immediate alert:", msg)
        send_graph(f"🚨 UPE Watchdog — {msg}",
                   f"ריצת workflow נכשלה זה עתה:\n\n🔴 {msg}\n\n"
                   f"בדוק את ה-Actions ב-{os.environ.get('GITHUB_REPOSITORY','upe-social-publisher')} וטפל — זה חוסם פרסום.")
        return 0
    issues = (check_workflows() + check_runway() + check_failures()
              + check_backlog() + check_duplicates())
    if not issues:
        print("✅ watchdog: all healthy (runway ok, no failures, no backlog)")
        return 0
    body = "מערכת הסושיאל זיהתה נושאים שדורשים תשומת לב:\n\n" + "\n".join(issues)
    print(body)
    send_graph(f"🐶 UPE Watchdog — {len(issues)} נושאים", body)
    return 0


if __name__ == "__main__":
    sys.exit(main())
