#!/usr/bin/env python3
"""
Token health check — call /debug_token for each account and report:
  - Token valid?
  - Expiration date (UNIX → human)
  - Days until expiry

Exit codes:
  0 = all tokens healthy
  1 = at least one token expires in <14 days
  2 = at least one token is already invalid

Usage:
  python3 scripts/check_tokens.py            # human-readable
  python3 scripts/check_tokens.py --json     # machine-readable
"""

import os
import sys
import json
import argparse
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from publishers.facebook import verify_token as fb_verify, get_token_expiry as fb_expiry
from publishers.instagram import verify_account as ig_verify, get_token_expiry as ig_expiry

WARN_DAYS = 14

ACCOUNTS = [
    ("facebook",  "uproductionevents",  "FB_UPRODUCTIONEVENTS_PAGE_ID",   "FB_UPRODUCTIONEVENTS_PAGE_TOKEN"),
    ("facebook",  "uproduction_spain",  "FB_UPRODUCTION_SPAIN_PAGE_ID",   "FB_UPRODUCTION_SPAIN_PAGE_TOKEN"),
    ("instagram", "uproductionevents",  "IG_UPRODUCTIONEVENTS_USER_ID",   "IG_UPRODUCTIONEVENTS_ACCESS_TOKEN"),
    ("instagram", "uproduction_spain",  "IG_UPRODUCTION_SPAIN_USER_ID",   "IG_UPRODUCTION_SPAIN_ACCESS_TOKEN"),
]


def check_one(platform: str, name: str, id_env: str, token_env: str) -> dict:
    pid = os.environ.get(id_env)
    token = os.environ.get(token_env)
    if not pid or not token:
        return {"platform": platform, "name": name, "ok": False, "error": f"Missing {id_env}/{token_env}"}

    if platform == "facebook":
        ok, info = fb_verify(pid, token)
        expires_at = fb_expiry(token)
    else:
        ok, info = ig_verify(pid, token)
        expires_at = ig_expiry(token)

    out = {"platform": platform, "name": name, "ok": ok, "info": info}
    if not ok:
        out["error"] = info
        return out

    if expires_at is None:
        out["expires_at"] = "never"
        out["days_remaining"] = None
    else:
        out["expires_at"] = datetime.fromtimestamp(expires_at, tz=timezone.utc).isoformat()
        days = (expires_at - datetime.now(tz=timezone.utc).timestamp()) / 86400
        out["days_remaining"] = round(days, 1)
    return out


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--json", action="store_true", help="JSON output")
    args = p.parse_args()

    results = [check_one(*a) for a in ACCOUNTS]

    invalid = [r for r in results if not r.get("ok")]
    expiring = [r for r in results if r.get("ok") and isinstance(r.get("days_remaining"), (int, float)) and r["days_remaining"] < WARN_DAYS]

    if args.json:
        print(json.dumps({"results": results, "invalid": invalid, "expiring_soon": expiring}, indent=2))
    else:
        print("=" * 70)
        print("UPE Social Publisher — Token Health Check")
        print("=" * 70)
        for r in results:
            mark = "✅" if r.get("ok") else "❌"
            line = f"{mark} {r['platform']:10s} {r['name']:25s}"
            if r.get("ok"):
                line += f"  → {r['info']:30s}  expires: {r.get('expires_at')}"
                if r.get("days_remaining") is not None:
                    line += f" ({r['days_remaining']}d)"
            else:
                line += f"  → ERROR: {r.get('error', '?')}"
            print(line)
        print()
        if invalid:
            print(f"❌ {len(invalid)} INVALID token(s)")
        if expiring:
            print(f"⚠️  {len(expiring)} token(s) expire within {WARN_DAYS} days")
        if not invalid and not expiring:
            print(f"✅ All tokens healthy")

    if invalid:
        return 2
    if expiring:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
