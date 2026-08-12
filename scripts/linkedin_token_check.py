#!/usr/bin/env python3
"""LinkedIn token monitor: introspect the access token; if it is invalid or expires
within EXPIRY_WARN_DAYS, email Alon to re-auth.

Token rotation is deliberately not attempted here. A GitHub Actions job cannot
safely persist a rotated repository secret, and printing the replacement token
would expose it in the job log. The separate refresh workflow persists tokens in
Supabase for the publisher; this monitor owns only the manual re-auth alert.
"""
import os, sys, json, time, urllib.request, urllib.parse, urllib.error

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from publishers import queue, linkedin

CID = os.environ.get("LINKEDIN_CLIENT_ID", "")
CSECRET = os.environ.get("LINKEDIN_CLIENT_SECRET", "")
TOKEN = os.environ.get("LINKEDIN_ACCESS_TOKEN", "")
RESEND_KEY = os.environ.get("RESEND_API_KEY", "")
RESEND_FROM = os.environ.get("RESEND_FROM") or "uproduction <onboarding@resend.dev>"
TO = os.environ.get("APPROVAL_TO") or "alon@upe.co.il"
WARN_DAYS = int(os.environ.get("EXPIRY_WARN_DAYS", "7"))
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"


def _post(url, fields):
    data = urllib.parse.urlencode(fields).encode()
    req = urllib.request.Request(url, data=data, headers={
        "Content-Type": "application/x-www-form-urlencoded", "User-Agent": UA}, method="POST")
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read().decode())


def current_token():
    """Monitor the same Supabase token the publisher actually uses."""
    if os.environ.get("SUPABASE_URL") and os.environ.get("SUPABASE_SERVICE_ROLE_KEY"):
        try:
            row = queue.get_oauth("linkedin")
            if row and row.get("access_token"):
                return row["access_token"]
        except Exception as e:
            print(f"warn: could not load Supabase LinkedIn token: {e}")
    return TOKEN


def introspect(token=None):
    return _post("https://www.linkedin.com/oauth/v2/introspectToken",
                 {"client_id": CID, "client_secret": CSECRET, "token": token or TOKEN})


def email(subject, html):
    if not RESEND_KEY:
        print("no RESEND_API_KEY"); return
    body = json.dumps({"from": RESEND_FROM, "to": [TO], "subject": subject, "html": html}).encode()
    req = urllib.request.Request("https://api.resend.com/emails", data=body, headers={
        "Authorization": f"Bearer {RESEND_KEY}", "Content-Type": "application/json", "User-Agent": UA})
    try:
        urllib.request.urlopen(req); print("alert emailed")
    except urllib.error.HTTPError as e:
        print("email err", e.code, e.read().decode()[:160])


def reauth_html(reason):
    return ("<html dir=\"rtl\" lang=\"he\"><body style=\"font-family:Arial;direction:rtl;text-align:right;\">"
            f"<h2 style=\"color:#e0533d;\">⚠️ טוקן LinkedIn דורש חידוש</h2>"
            f"<p>{reason}</p>"
            "<p>הטוקן הזה מפרסם לעמוד החברה (אנגלי + ספרד) ולפרופיל האישי. "
            "כדי לחדש — תגיד ל-UPE \"חדש את טוקן הלינקדאין\" ואני מריץ את ה-OAuth דרך הדפדפן המחובר "
            "(app <b>78nrl43hscor4q</b>, scopes: w_organization_social r_organization_social "
            "rw_organization_admin w_member_social) ומעדכן את ה-secret <b>LINKEDIN_ACCESS_TOKEN</b> אוטומטית. "
            "לוקח דקה.</p>"
            "<p style=\"color:#FBCE0A;\"><b>uproduction</b> from business to pleasure</p></body></html>")


def main():
    token = current_token()
    if not (CID and CSECRET and token):
        print("missing LINKEDIN_* env"); return 1
    try:
        info = introspect(token)
    except urllib.error.HTTPError as e:
        info = {"active": False, "error": f"{e.code} {e.read().decode()[:120]}"}
    active = info.get("active") in (True, "true")
    exp = info.get("expires_at")
    days_left = round((exp - time.time()) / 86400, 1) if isinstance(exp, (int, float)) else None
    print(f"active={active} expires_at={exp} days_left={days_left}")

    auth_problems = []
    scopes = linkedin._scope_set(info)
    missing = sorted({"w_member_social", "w_organization_social"} - scopes)
    if active and missing:
        auth_problems.append("חסרות הרשאות כתיבה: " + ", ".join(missing))

    member = os.environ.get("LINKEDIN_MEMBER_URN", "")
    org_en = os.environ.get("LINKEDIN_ORG_URN", "")
    org_es = os.environ.get("LINKEDIN_ORG_URN_SPAIN", "")
    if active and not missing:
        targets = [
            ("הפרופיל האישי", linkedin.preflight(token=token, member_urn_expected=member)) if member else None,
            ("עמוד החברה באנגלית", linkedin.preflight(token=token, org_urn=org_en)) if org_en else None,
            ("עמוד החברה בספרד", linkedin.preflight(token=token, org_urn=org_es)) if org_es else None,
        ]
        for item in targets:
            if item and not item[1].get("ok"):
                auth_problems.append(f"{item[0]}: {item[1].get('code')} — {item[1].get('message')}")

    if active and not auth_problems and (days_left is None or days_left > WARN_DAYS):
        print("token healthy and authorized"); return 0

    if not active:
        reason = "הטוקן לא תקף"
    elif auth_problems:
        reason = "; ".join(auth_problems)
    else:
        reason = f"הטוקן פג בעוד {days_left} ימים"
    print(f"authorization unhealthy: {reason}")
    email(f"⚠️ LinkedIn token — {reason}", reauth_html(reason))
    return 0


if __name__ == "__main__":
    sys.exit(main())
