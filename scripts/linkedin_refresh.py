#!/usr/bin/env python3
"""Silent LinkedIn token refresh via Supabase-stored refresh_token.
Usage:
  python3 scripts/linkedin_refresh.py --seed   # write env tokens into Supabase once
  python3 scripts/linkedin_refresh.py          # refresh if expiring within REFRESH_BEFORE_DAYS
Requires: SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, LINKEDIN_CLIENT_ID, LINKEDIN_CLIENT_SECRET.
"""
import os, sys, json, time, datetime, subprocess
import urllib.request, urllib.parse, urllib.error
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from publishers import queue

CID = os.environ.get("LINKEDIN_CLIENT_ID", "")
CSECRET = os.environ.get("LINKEDIN_CLIENT_SECRET", "")
BEFORE_DAYS = float(os.environ.get("REFRESH_BEFORE_DAYS", "14"))
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"


def _exchange(refresh_token):
    data = urllib.parse.urlencode({
        "grant_type": "refresh_token", "refresh_token": refresh_token,
        "client_id": CID, "client_secret": CSECRET}).encode()
    req = urllib.request.Request("https://www.linkedin.com/oauth/v2/accessToken", data=data,
        headers={"Content-Type": "application/x-www-form-urlencoded", "User-Agent": UA}, method="POST")
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read().decode())


def _sync_github_secret(name, value):
    repo = os.environ.get("GITHUB_REPOSITORY", "")
    if not value or not repo or not os.environ.get("GH_TOKEN"):
        return False
    result = subprocess.run(["gh", "secret", "set", name, "--repo", repo],
                            input=value, text=True, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, timeout=60)
    if result.returncode != 0:
        raise RuntimeError(f"could not sync {name}: {result.stderr[:160]}")
    return True


def _save(access, refresh, expires_in, sync_github=False):
    exp = datetime.datetime.utcfromtimestamp(time.time() + int(expires_in)).isoformat() + "Z"
    queue.upsert_oauth("linkedin", access_token=access, refresh_token=refresh,
                       expires_at=exp, updated_at=datetime.datetime.utcnow().isoformat() + "Z")
    synced_access = _sync_github_secret("LINKEDIN_ACCESS_TOKEN", access) if sync_github else False
    synced_refresh = (_sync_github_secret("LINKEDIN_REFRESH_TOKEN", refresh)
                      if sync_github and refresh else False)
    print(f"saved linkedin token, expires_at={exp}, "
          f"github_access={synced_access}, github_refresh={synced_refresh}")


def seed():
    a = os.environ.get("LINKEDIN_ACCESS_TOKEN"); r = os.environ.get("LINKEDIN_REFRESH_TOKEN")
    if not a:
        print("no LINKEDIN_ACCESS_TOKEN to seed"); return 1
    # access tokens ~60d; we don't know exact issue time, assume ~55d remaining
    _save(a, r or "", 55 * 86400)
    print("seeded. refresh_token present:", bool(r)); return 0


def _token_is_live(access):
    """Whether LinkedIn itself still honours the stored access token.

    `expires_at` is not proof of validity: LinkedIn revokes tokens on re-auth,
    and --seed only *guesses* the expiry (now + 55d). On 2026-08-13 the stored
    token introspected as inactive while expires_at still read 56 days out, so
    the "still fresh" shortcut skipped the refresh every night and all three
    LinkedIn channels stopped publishing silently. Ask LinkedIn, don't assume.
    """
    if not access:
        return False
    try:
        from publishers import linkedin
        info = linkedin.introspect_token(access)
    except Exception as e:
        print(f"could not introspect stored token ({e}) — refreshing to be safe")
        return False
    if info.get("active") in (True, "true"):
        return True
    print("stored token introspects as INACTIVE — refreshing regardless of expires_at")
    return False


def refresh_advocates():
    """Keep the employee-advocacy tokens alive too.

    These live in their own table and were never covered by this job: the two
    connected advocates were both dated to expire 2026-08-29, after which the
    advocacy channels would have gone silent with no alert and no way back
    except asking each person to click her connect link again.
    """
    failures = 0
    try:
        rows = queue.list_advocates()
    except Exception as e:
        print(f"could not list advocates: {e}")
        return 1
    for row in rows:
        account = row.get("account", "?")
        if account == "li_main_callback":
            continue  # staging row for the shared credential, not a person
        left = None
        if row.get("expires_at"):
            try:
                left = (datetime.datetime.fromisoformat(
                    row["expires_at"].replace("Z", "+00:00"))
                    - datetime.datetime.now(datetime.timezone.utc)).total_seconds() / 86400
            except Exception:
                pass
        if _token_is_live(row.get("access_token")) and (left is None or left > BEFORE_DAYS):
            print(f"{account}: still valid ({left:.1f}d left)" if left is not None
                  else f"{account}: still valid")
            continue
        if not row.get("refresh_token"):
            print(f"ACTION NEEDED: {account} needs to reconnect — token unusable "
                  "and no refresh_token stored")
            failures += 1
            continue
        try:
            t = _exchange(row["refresh_token"])
        except urllib.error.HTTPError as e:
            print(f"ACTION NEEDED: {account} refresh failed "
                  f"({e.code} {e.read().decode()[:120]}) — she must reconnect")
            failures += 1
            continue
        if not t.get("access_token"):
            print(f"ACTION NEEDED: {account} refresh returned no access_token")
            failures += 1
            continue
        exp = datetime.datetime.utcfromtimestamp(
            time.time() + int(t.get("expires_in", 5184000))).isoformat() + "Z"
        queue.update_advocate(account,
                              access_token=t["access_token"],
                              refresh_token=t.get("refresh_token", row["refresh_token"]),
                              expires_at=exp)
        print(f"{account}: refreshed, expires_at={exp}")
    return 1 if failures else 0


def main():
    if "--seed" in sys.argv:
        return seed()
    if "--advocates-only" in sys.argv:
        return refresh_advocates()
    # The advocates are refreshed on every run whatever the shared token does —
    # a dead company token must not mask employee credentials quietly expiring.
    print("— shared credential —")
    rc = _refresh_shared()
    print("— advocate credentials —")
    return max(rc, refresh_advocates())


def _refresh_shared():
    row = queue.get_oauth("linkedin")
    if not row:
        print("no linkedin token stored at all — run --seed first"); return 1

    # Days left on the current access token (if known).
    exp = row.get("expires_at")
    left = None
    if exp:
        try:
            left = (datetime.datetime.fromisoformat(exp.replace("Z", "+00:00")) -
                    datetime.datetime.now(datetime.timezone.utc)).total_seconds() / 86400
            print(f"days_left={left:.1f}")
        except Exception:
            pass

    live = _token_is_live(row.get("access_token"))
    fresh = live and (left is None or left > BEFORE_DAYS)

    if not row.get("refresh_token"):
        # No refresh_token => cannot auto-refresh. Only a problem once the access
        # token is actually unusable. While it still works, succeed quietly so
        # the daily job doesn't spam false failures.
        if fresh:
            print("no refresh_token, but access token still works — nothing to do "
                  "(re-auth with offline_access scope to enable auto-refresh)")
            return 0
        reason = ("was revoked" if not live else f"expires in {left:.1f}d")
        print(f"ACTION NEEDED: LinkedIn access token {reason} and no refresh_token "
              "is stored. Re-authorize the app (offline_access scope) and run "
              "--seed with the new tokens.")
        return 1

    if fresh:
        print("token still fresh; no refresh needed"); return 0
    try:
        t = _exchange(row["refresh_token"])
    except urllib.error.HTTPError as e:
        print("refresh failed:", e.code, e.read().decode()[:200]); return 1
    if not t.get("access_token"):
        print("no access_token in refresh response:", t); return 1
    _save(t["access_token"], t.get("refresh_token", row["refresh_token"]),
          t.get("expires_in", 5184000), sync_github=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
