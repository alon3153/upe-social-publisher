#!/usr/bin/env python3
"""Silent LinkedIn token refresh via Supabase-stored refresh_token.
Usage:
  python3 scripts/linkedin_refresh.py --seed   # write env tokens into Supabase once
  python3 scripts/linkedin_refresh.py          # refresh if expiring within REFRESH_BEFORE_DAYS
Requires: SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, LINKEDIN_CLIENT_ID, LINKEDIN_CLIENT_SECRET.
"""
import os, sys, json, time, datetime, urllib.request, urllib.parse, urllib.error
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


def _save(access, refresh, expires_in):
    exp = datetime.datetime.utcfromtimestamp(time.time() + int(expires_in)).isoformat() + "Z"
    queue.upsert_oauth("linkedin", access_token=access, refresh_token=refresh,
                       expires_at=exp, updated_at=datetime.datetime.utcnow().isoformat() + "Z")
    print(f"saved linkedin token, expires_at={exp}")


def seed():
    a = os.environ.get("LINKEDIN_ACCESS_TOKEN"); r = os.environ.get("LINKEDIN_REFRESH_TOKEN")
    if not a:
        print("no LINKEDIN_ACCESS_TOKEN to seed"); return 1
    # access tokens ~60d; we don't know exact issue time, assume ~55d remaining
    _save(a, r or "", 55 * 86400)
    print("seeded. refresh_token present:", bool(r)); return 0


def main():
    if "--seed" in sys.argv:
        return seed()
    row = queue.get_oauth("linkedin")
    if not row or not row.get("refresh_token"):
        print("no refresh_token stored — cannot auto-refresh (provide one + --seed)"); return 1
    exp = row.get("expires_at")
    if exp:
        try:
            left = (datetime.datetime.fromisoformat(exp.replace("Z", "+00:00")) -
                    datetime.datetime.now(datetime.timezone.utc)).total_seconds() / 86400
            print(f"days_left={left:.1f}")
            if left > BEFORE_DAYS:
                print("token still fresh; no refresh needed"); return 0
        except Exception:
            pass
    try:
        t = _exchange(row["refresh_token"])
    except urllib.error.HTTPError as e:
        print("refresh failed:", e.code, e.read().decode()[:200]); return 1
    if not t.get("access_token"):
        print("no access_token in refresh response:", t); return 1
    _save(t["access_token"], t.get("refresh_token", row["refresh_token"]), t.get("expires_in", 5184000))
    return 0


if __name__ == "__main__":
    sys.exit(main())
