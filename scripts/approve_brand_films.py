#!/usr/bin/env python3
"""Flip the 3 brand-film LinkedIn rows (days 9001-9003) from pending → approved
in the Supabase post_approvals queue, so publish_approved.py posts them on the
next run. Requires SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY."""
import os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from publishers import queue

DAYS = [9001, 9002, 9003]

def main():
    # show current state
    rows = queue._req("GET", "post_approvals",
                      params={"select": "id,day,network,account,status", "day": "in.(9001,9002,9003)"})
    print("before:", [(r["day"], r["account"], r["status"]) for r in rows])
    # approve
    res = queue._req("PATCH", "post_approvals",
                     params={"day": "in.(9001,9002,9003)"},
                     body={"status": "approved"}, prefer="return=representation")
    print(f"approved {len(res) if isinstance(res, list) else '?'} rows:",
          [(r["day"], r["account"], r["status"]) for r in (res or [])])

main()
