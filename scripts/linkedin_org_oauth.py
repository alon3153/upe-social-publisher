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
  python3 scripts/linkedin_org_oauth.py
  -> opens the browser, you authorize, LinkedIn redirects with ?code=... in the
     address bar; paste that code back into the terminal.
  -> prints the access token + organization URN. Set as GitHub secrets:
       LINKEDIN_ACCESS_TOKEN  (refreshed value)
       LINKEDIN_ORG_URN       (e.g. urn:li:organization:12345678)
"""
import os, sys, json, time, secrets, datetime, urllib.parse, urllib.request, urllib.error, webbrowser

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


def main():
    if not CID or not CSECRET:
        print("Set LINKEDIN_CLIENT_ID and LINKEDIN_CLIENT_SECRET first."); return 1
    url = authorize_url()
    print("\n1) Authorize in the browser (opening now). If it doesn't open, visit:\n")
    print(url, "\n")
    try:
        webbrowser.open(url)
    except Exception:
        pass
    print(f"2) After approving, the browser lands on {REDIRECT}?code=...&state=...")
    code = input("3) Paste the `code` value here: ").strip()
    if not code:
        print("no code provided"); return 1

    tok = exchange(code)
    access = tok.get("access_token")
    if not access:
        print("token exchange failed:", tok); return 1
    print("\n✅ access_token obtained (expires_in:", tok.get("expires_in"), "s)")

    orgs = discover_org(access)
    if orgs:
        print("\nOrganizations you administer:")
        for org, name in orgs:
            print(f"   {org}   {name}")
        org_urn = orgs[0][0]
    else:
        org_urn = input("\nCould not auto-detect. Paste org URN (urn:li:organization:NNN): ").strip()

    # optionally persist to Supabase (same row the publisher reads)
    if os.environ.get("SUPABASE_URL") and os.environ.get("SUPABASE_SERVICE_ROLE_KEY"):
        try:
            from publishers import queue
            exp = datetime.datetime.utcfromtimestamp(time.time() + int(tok.get("expires_in", 5184000))).isoformat() + "Z"
            queue.upsert_oauth("linkedin", access_token=access,
                               refresh_token=tok.get("refresh_token", ""),
                               expires_at=exp,
                               updated_at=datetime.datetime.utcnow().isoformat() + "Z")
            print("\n✅ token saved to Supabase oauth_tokens (provider=linkedin)")
        except Exception as e:
            print("  (Supabase save skipped:", e, ")")

    print("\n=== SET THESE GITHUB SECRETS ===")
    print("LINKEDIN_ACCESS_TOKEN =", access[:12] + "…(full value above flow)")
    print("LINKEDIN_ORG_URN      =", org_urn)
    print("\nOnce LINKEDIN_ORG_URN is set, the publisher posts to the company page automatically.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
