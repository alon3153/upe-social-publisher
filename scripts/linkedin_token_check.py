#!/usr/bin/env python3
"""LinkedIn token monitor: introspect the access token; if it is invalid or expires
within EXPIRY_WARN_DAYS, email Alon to re-auth. Optionally auto-refresh if a
LINKEDIN_REFRESH_TOKEN is present (LinkedIn 365-day refresh flow)."""
import os, sys, json, time, urllib.request, urllib.parse, urllib.error

CID = os.environ.get("LINKEDIN_CLIENT_ID", "")
CSECRET = os.environ.get("LINKEDIN_CLIENT_SECRET", "")
TOKEN = os.environ.get("LINKEDIN_ACCESS_TOKEN", "")
REFRESH = os.environ.get("LINKEDIN_REFRESH_TOKEN", "")
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


def introspect():
    return _post("https://www.linkedin.com/oauth/v2/introspectToken",
                 {"client_id": CID, "client_secret": CSECRET, "token": TOKEN})


def refresh():
    if not REFRESH:
        return None
    return _post("https://www.linkedin.com/oauth/v2/accessToken",
                 {"grant_type": "refresh_token", "refresh_token": REFRESH,
                  "client_id": CID, "client_secret": CSECRET})


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
    if not (CID and CSECRET and TOKEN):
        print("missing LINKEDIN_* env"); return 1
    try:
        info = introspect()
    except urllib.error.HTTPError as e:
        info = {"active": False, "error": f"{e.code} {e.read().decode()[:120]}"}
    active = info.get("active") in (True, "true")
    exp = info.get("expires_at")
    days_left = round((exp - time.time()) / 86400, 1) if isinstance(exp, (int, float)) else None
    print(f"active={active} expires_at={exp} days_left={days_left}")

    if active and (days_left is None or days_left > WARN_DAYS):
        print("token healthy"); return 0

    # try silent refresh first
    if REFRESH:
        try:
            t = refresh()
            if t and t.get("access_token"):
                print("REFRESHED. New access_token obtained (update LINKEDIN_ACCESS_TOKEN secret).")
                print("NEW_ACCESS_TOKEN=" + t["access_token"])
                if t.get("refresh_token"):
                    print("NEW_REFRESH_TOKEN=" + t["refresh_token"])
                email("✅ LinkedIn token חודש אוטומטית",
                      reauth_html("הטוקן חודש — אמת שה-secret עודכן."))
                return 0
        except Exception as e:
            print("refresh failed:", e)

    reason = "הטוקן לא תקף" if not active else f"הטוקן פג בעוד {days_left} ימים"
    email(f"⚠️ LinkedIn token — {reason}", reauth_html(reason))
    return 0


if __name__ == "__main__":
    sys.exit(main())
