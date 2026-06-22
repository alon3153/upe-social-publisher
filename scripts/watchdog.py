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
    issues = check_runway() + check_failures() + check_backlog()
    if not issues:
        print("✅ watchdog: all healthy (runway ok, no failures, no backlog)")
        return 0
    body = "מערכת הסושיאל זיהתה נושאים שדורשים תשומת לב:\n\n" + "\n".join(issues)
    print(body)
    send_graph(f"🐶 UPE Watchdog — {len(issues)} נושאים", body)
    return 0


if __name__ == "__main__":
    sys.exit(main())
