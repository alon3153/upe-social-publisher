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
from publishers import queue, linkedin

TO = os.environ.get("APPROVAL_TO") or "alon@upe.co.il"
RUNWAY_WARN_DAYS = int(os.environ.get("RUNWAY_WARN_DAYS", "21"))
FAIL_LOOKBACK_DAYS = int(os.environ.get("FAIL_LOOKBACK_DAYS", "3"))
BACKLOG_AGE_DAYS = int(os.environ.get("BACKLOG_AGE_DAYS", "2"))
LI_AUTH_ERROR_MARKERS = (
    "http 401", "http 403", "not authorized", "organizationugcauthorizations",
    "missing scope", "identity mismatch", "no approved posting role",
    "advocate not connected", "auth_blocked",
)


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
    auth_rows = [r for r in rows if r.get("network") == "linkedin" and
                 any(m in (r.get("error") or "").lower() for m in LI_AUTH_ERROR_MARKERS)]
    other_rows = [r for r in rows if r not in auth_rows]
    lines = []
    if auth_rows:
        days = sorted({r.get("day") for r in auth_rows if r.get("day") is not None})
        lines.append(f"🟠 {len(auth_rows)} פוסטי LinkedIn מושהים עד תיקון ההרשאה "
                     f"(ימים: {days}). הם יוחזרו אוטומטית לתור לאחר חיבור תקין.")
    if other_rows:
        lines.append(f"🔴 {len(other_rows)} כשלי פרסום אחרים ב-{FAIL_LOOKBACK_DAYS} הימים האחרונים:")
    for r in other_rows[:10]:
        err = (r.get("error") or "")[:90]
        lines.append(f"   · יום {r.get('day')} {r.get('network')}/{r.get('account')} — {err}")
    return lines


def connect_link(fn_base, slug):
    """Return (url, works). A reconnect link that 404s on its own slug is worse
    than no link: it was emailed for weeks, and the advocate who clicked it got
    'לינק לא תקין' — the failure looked like her fault. A healthy link 302s to
    linkedin.com; anything else means the deployed function does not know the slug."""
    if not fn_base.startswith("http"):
        return "", False
    url = f"{fn_base}?advocate={slug}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "upe-watchdog/1.0"})
        class _NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, *a, **kw):
                return None
        opener = urllib.request.build_opener(_NoRedirect)
        with opener.open(req, timeout=20) as r:
            return url, False  # a 200 here is the function's own error page
    except urllib.error.HTTPError as e:
        loc = e.headers.get("Location", "") if e.headers else ""
        return url, e.code in (301, 302, 303, 307) and "linkedin.com" in loc
    except Exception:
        return url, True  # network trouble is not evidence the link is broken


def check_linkedin_auth():
    """Validate usable write authorization, not merely token expiration."""
    issues = []
    try:
        token = linkedin._token()
    except Exception as e:
        return [f"🔴 LinkedIn: לא ניתן לטעון טוקן פרסום: {e}"]

    shared_targets = [
        ("הפרופיל האישי של אלון", "member", os.environ.get("LINKEDIN_MEMBER_URN", "")),
        ("עמוד החברה באנגלית", "organization", os.environ.get("LINKEDIN_ORG_URN", "")),
        ("עמוד החברה בספרד", "organization", os.environ.get("LINKEDIN_ORG_URN_SPAIN", "")),
    ]
    for label, kind, urn in shared_targets:
        if not urn:
            issues.append(f"🔴 LinkedIn — {label}: חסר URN בהגדרות")
            continue
        auth = (linkedin.preflight(token=token, member_urn_expected=urn)
                if kind == "member" else linkedin.preflight(token=token, org_urn=urn))
        if not auth.get("ok"):
            issues.append(f"🔴 LinkedIn — {label}: {auth.get('code')} — {auth.get('message')}")

    fn_base = os.environ.get("SUPABASE_URL", "").rstrip("/") + "/functions/v1/linkedin-oauth"
    # The slug must be one the DEPLOYED edge function knows — 'daniel' is not
    # 'danielle', and the deployed build lagged the repo by two months, so both
    # links in this alert led to "לינק לא תקין". connect_link() proves each one.
    required_advocates = {
        "li_danielle": ("דניאל", "danielle"),
        "li_dorin": ("דורין", "dorin"),
    }
    try:
        advocates = {r.get("account"): r for r in queue.list_advocates()}
    except Exception as e:
        issues.append(f"⚠️ LinkedIn — לא ניתן לבדוק חיבורי צוות: {e}")
        return issues
    alon_urn = os.environ.get("LINKEDIN_MEMBER_URN", "")
    for account, (display, slug) in required_advocates.items():
        row = advocates.get(account)
        reconnect, link_ok = connect_link(fn_base, slug)
        if reconnect and not link_ok:
            issues.append(f"🔴 LinkedIn — לינק החיבור של {display} שבור (הפונקציה שפרוסה לא מכירה "
                          f"'{slug}'). אין טעם לשלוח לה אותו. פריסה מחדש: "
                          f"supabase functions deploy linkedin-oauth --project-ref <ref>")
        if row is None:
            # No row at all = never onboarded, not a connection that broke. The
            # distinction decides what Alon does: chase HER to click the link once,
            # or drop her from the roster — not "reconnect something that worked".
            issues.append(f"🔴 LinkedIn — {display} מעולם לא התחברה (אין רשומה כלל). "
                          f"רק היא יכולה ללחוץ, מהמכשיר שלה: {reconnect}")
            continue
        if not row.get("access_token") or not row.get("member_urn"):
            issues.append(f"🔴 LinkedIn — החיבור של {display} נשבר. חיבור מחדש: {reconnect}")
            continue
        # A connect link is a plain URL: whoever opens it authorizes THEIR OWN
        # profile. If Alon clicks an advocate's link to "help", the row stores
        # his URN and preflight still passes — the advocacy channel then quietly
        # posts a second time as Alon instead of reaching her audience.
        if alon_urn and row.get("member_urn") == alon_urn:
            issues.append(f"🔴 LinkedIn — החיבור של {display} מצביע על הפרופיל של אלון "
                          f"(מישהו אחר לחץ על הלינק). {display} צריכה ללחוץ בעצמה: {reconnect}")
            continue
        auth = linkedin.preflight(token=row["access_token"],
                                  member_urn_expected=row["member_urn"])
        if not auth.get("ok"):
            issues.append(f"🔴 LinkedIn — החיבור של {display} אינו מורשה: "
                          f"{auth.get('code')} — {auth.get('message')}. חיבור מחדש: {reconnect}")
    issues += check_idle_advocates(advocates)
    return issues


def check_idle_advocates(advocates):
    """An advocate who connected but is not on the publishing roster posts nothing,
    forever, and nothing reports it: the daily email silently skips accounts it
    doesn't list. Rosters live in four files and drift apart, so compare the two
    that matter — connected vs. actually enqueued."""
    try:
        publishing = {a for _, a, _, _ in _daily_email().ACCOUNTS}
    except Exception as e:
        return [f"⚠️ LinkedIn — לא ניתן לבדוק אילו שגרירים מקבלים פוסטים: {e}"]
    idle = [acc for acc, row in advocates.items()
            if row.get("access_token") and row.get("member_urn") and acc not in publishing]
    if not idle:
        return []
    return [f"🟠 LinkedIn — {', '.join(sorted(idle))} מחובר/ת אך לא מקבל/ת פוסטים כלל "
            f"(לא ברשימת ACCOUNTS ב-daily_email). להוסיף או לנתק."]


def _daily_email():
    """daily_email is a script, not a package module — load it by path."""
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "daily_email", os.path.join(ROOT, "scripts", "daily_email.py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


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
    """Same day+network+account+lang alive more than once — a re-enqueue bug
    symptom; one approve_all click then publishes twice. Keyed on ACCOUNT too:
    the 3 HE LinkedIn advocates legitimately share (day,network,lang) with
    distinct accounts — that is by design, not a duplicate.

    SELF-HEALING (per the Iron Rule 'reject the old set before publishing'):
      · A copy already `published` under a key → any still-live copy of the same
        key would double-post → auto-reject the live copies (the system never
        intentionally republishes a day: pick_next_day skips published days).
      · Two live copies (different dates) → keep one, auto-reject the stale
        `pending` copies. Keeper preference: an `approved` row (Alon acted on it)
        wins over `pending`; among same status, newest scheduled_date wins.
      · Never silently undo an approval we can't supersede: two `approved` copies
        of one key = genuine double-approve → alert for human handling, no auto-act."""
    try:
        rows = queue._req("GET", "post_approvals", params={
            "select": "id,day,network,account,lang,status,scheduled_date,created_at",
            "status": "in.(pending,approved,published)"})
    except Exception as e:
        return [f"⚠️ לא ניתן לבדוק שכפולים בתור: {e}"]
    groups = {}
    for r in rows:
        if r.get("day") is None:
            continue
        k = (r["day"], r.get("network"), r.get("account"), r.get("lang"))
        groups.setdefault(k, []).append(r)

    def _reject(r, why):
        queue.mark(r["id"], status="rejected", error=f"auto-rejected: {why} (watchdog)")

    auto, unresolved = [], []
    for k, grp in groups.items():
        if len(grp) < 2:
            continue
        published = [r for r in grp if r.get("status") == "published"]
        live = [r for r in grp if r.get("status") in ("pending", "approved")]
        try:
            if published:
                # content already went out under this key — any live copy re-posts it
                for r in live:
                    _reject(r, "duplicate of an already-published post")
                    auto.append((k, r.get("scheduled_date")))
                continue
            if len(live) < 2:
                continue
            # keeper: approved beats pending; then newest scheduled_date/created_at
            live.sort(key=lambda r: (1 if r.get("status") == "approved" else 0,
                                     r.get("scheduled_date") or "", r.get("created_at") or ""))
            keeper = live[-1]
            for r in live[:-1]:
                if r.get("status") == "pending":
                    _reject(r, f"stale duplicate; kept {keeper.get('scheduled_date')}")
                    auto.append((k, r.get("scheduled_date")))
                else:  # a second approved copy — don't silently discard Alon's click
                    unresolved.append(
                        f"🔴 יום {k[0]} {k[1]}/{k[2]}/{k[3]} — שני עותקים מאושרים (double-approve). "
                        f"סכנת פרסום כפול — טיפול ידני נדרש.")
        except Exception as e:
            unresolved.append(f"🔴 יום {k[0]} {k[1]}/{k[2]} — כשל בטיפול אוטומטי בכפילות: {e}")

    out = []
    if auto:
        days = sorted({k[0] for k, _ in auto})
        out.append(f"🟢 שכפולים בתור טופלו אוטומטית: {len(auto)} עותקים ישנים נדחו "
                   f"(ימים: {days}). נשמר העותק העדכני בכל צירוף — אין סכנת פרסום כפול.")
    out.extend(unresolved)
    return out


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
    issues = (check_workflows() + check_runway() + check_linkedin_auth() + check_failures()
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
