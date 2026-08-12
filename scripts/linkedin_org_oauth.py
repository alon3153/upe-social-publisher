#!/usr/bin/env python3
"""LinkedIn COMPANY-PAGE OAuth — get an org-scoped token + discover the org URN.

WHY: the daily publisher currently posts to Alon's personal profile because the
stored token only has `w_member_social`. Posting to the Uproduction company page
needs `w_organization_social` and the page's organization URN.

PREREQUISITES (one-time, in the LinkedIn Developer app):
  1. App → Products → request **Community Management API** (grants
     w_organization_social / r_organization_social / rw_organization_admin).
  2. You must be an **ADMIN** of the Uproduction LinkedIn company page.
  3. App → Auth → add an authorized **Redirect URL** and set it below
     (env LINKEDIN_REDIRECT_URI), e.g.
     https://alon3153.github.io/upe-social-publisher/linkedin-callback.html

USAGE:
  export LINKEDIN_CLIENT_ID=...        # from the app (Auth tab)
  export LINKEDIN_CLIENT_SECRET=...
  export LINKEDIN_REDIRECT_URI=...     # must exactly match the app's redirect
  # to also save the token to Supabase:
  export SUPABASE_URL=... SUPABASE_SERVICE_ROLE_KEY=...
  python3 scripts/linkedin_org_oauth.py --authorize-url
  -> opens the browser, you authorize, LinkedIn redirects with ?code=... in the
     address bar. The GitHub re-auth workflow exchanges the one-time code,
     validates every target, and updates Supabase + GitHub Secrets without ever
     printing a token.
"""
import os, sys, json, time, secrets, datetime, subprocess
import urllib.parse, urllib.request, urllib.error, webbrowser

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

CID = os.environ.get("LINKEDIN_CLIENT_ID", "")
CSECRET = os.environ.get("LINKEDIN_CLIENT_SECRET", "")
REDIRECT = os.environ.get("LINKEDIN_REDIRECT_URI",
                          "https://alon3153.github.io/upe-social-publisher/linkedin-callback.html")
SCOPES = "w_organization_social r_organization_social rw_organization_admin w_member_social openid profile"
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"


def authorize_url():
    q = urllib.parse.urlencode({
        "response_type": "code", "client_id": CID, "redirect_uri": REDIRECT,
        "scope": SCOPES, "state": secrets.token_hex(8)})
    return "https://www.linkedin.com/oauth/v2/authorization?" + q


def exchange(code):
    data = urllib.parse.urlencode({
        "grant_type": "authorization_code", "code": code, "redirect_uri": REDIRECT,
        "client_id": CID, "client_secret": CSECRET}).encode()
    req = urllib.request.Request("https://www.linkedin.com/oauth/v2/accessToken", data=data,
        headers={"Content-Type": "application/x-www-form-urlencoded", "User-Agent": UA}, method="POST")
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read().decode())


def discover_org(token):
    """Find organizations where the member is an ADMINISTRATOR."""
    url = ("https://api.linkedin.com/v2/organizationAcls"
           "?q=roleAssignee&role=ADMINISTRATOR&state=APPROVED&projection="
           "(elements*(organization~(localizedName)))")
    req = urllib.request.Request(url, headers={
        "Authorization": f"Bearer {token}", "User-Agent": UA,
        "X-Restli-Protocol-Version": "2.0.0"})
    try:
        with urllib.request.urlopen(req) as r:
            data = json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        print(f"  (could not auto-list orgs: {e.code} {e.read().decode()[:160]})")
        return []
    out = []
    for el in data.get("elements", []):
        org = el.get("organization", "")
        name = (el.get("organization~", {}) or {}).get("localizedName", "?")
        out.append((org, name))
    return out


def validate_token(access):
    """Prove the token can post as Alon and to both configured company pages."""
    from publishers import linkedin
    member = os.environ.get("LINKEDIN_MEMBER_URN", "")
    org_en = os.environ.get("LINKEDIN_ORG_URN", "")
    org_es = os.environ.get("LINKEDIN_ORG_URN_SPAIN", "")
    missing_config = [name for name, value in (
        ("LINKEDIN_MEMBER_URN", member), ("LINKEDIN_ORG_URN", org_en),
        ("LINKEDIN_ORG_URN_SPAIN", org_es)) if not value]
    if missing_config:
        return False, ["missing target config: " + ", ".join(missing_config)]
    checks = [
        ("member", linkedin.preflight(token=access, member_urn_expected=member)),
        ("english org", linkedin.preflight(token=access, org_urn=org_en)),
        ("spain org", linkedin.preflight(token=access, org_urn=org_es)),
    ]
    errors = [f"{label}: {result.get('code')} — {result.get('message')}"
              for label, result in checks if not result.get("ok")]
    return not errors, errors


def _sync_github_secret(name, value):
    """Update a repository secret through gh; the value travels only on stdin."""
    repo = os.environ.get("GITHUB_REPOSITORY", "")
    if not value or not repo or not os.environ.get("GH_TOKEN"):
        return False
    result = subprocess.run(
        ["gh", "secret", "set", name, "--repo", repo], input=value,
        text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60,
    )
    if result.returncode != 0:
        raise RuntimeError(f"could not update GitHub secret {name}: {result.stderr[:160]}")
    return True


def persist_token(tok):
    access = tok["access_token"]
    refresh = tok.get("refresh_token", "")
    expires = int(tok.get("expires_in", 5184000))
    exp = datetime.datetime.utcfromtimestamp(time.time() + expires).isoformat() + "Z"
    from publishers import queue
    queue.upsert_oauth("linkedin", access_token=access, refresh_token=refresh,
                       expires_at=exp, updated_at=datetime.datetime.utcnow().isoformat() + "Z")
    github_access = _sync_github_secret("LINKEDIN_ACCESS_TOKEN", access)
    github_refresh = _sync_github_secret("LINKEDIN_REFRESH_TOKEN", refresh) if refresh else False
    print(f"✅ saved authorized LinkedIn credential (expires_at={exp}; "
          f"github_access={github_access}; github_refresh={github_refresh})")


def main():
    if not CID:
        print("Set LINKEDIN_CLIENT_ID first."); return 1
    url = authorize_url()
    if "--authorize-url" in sys.argv:
        print(url)
        return 0
    if not CSECRET:
        print("Set LINKEDIN_CLIENT_SECRET first."); return 1

    code = os.environ.get("LINKEDIN_AUTH_CODE", "").strip()
    if not code:
        print("\n1) Authorize in the browser (opening now). If it doesn't open, visit:\n")
        print(url, "\n")
        try:
            webbrowser.open(url)
        except Exception:
            pass
        print(f"2) After approving, the browser lands on {REDIRECT}?code=...&state=...")
        code = input("3) Paste the one-time `code` value here: ").strip()
    if not code:
        print("no code provided"); return 1

    tok = exchange(code)
    access = tok.get("access_token")
    if not access:
        print("token exchange failed:", tok); return 1
    ok, errors = validate_token(access)
    if not ok:
        print("authorization rejected; existing credentials were NOT changed:")
        for error in errors:
            print(" -", error)
        return 1
    if not (os.environ.get("SUPABASE_URL") and os.environ.get("SUPABASE_SERVICE_ROLE_KEY")):
        print("SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY missing; token was NOT persisted")
        return 1
    persist_token(tok)
    return 0


if __name__ == "__main__":
    sys.exit(main())
