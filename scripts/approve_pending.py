#!/usr/bin/env python3
"""Approve pending approval rows on Alon's behalf (he confirmed in chat).
Flips status pending -> approved so the 'Publish Approved' run picks them up.

Usage: python3 scripts/approve_pending.py [day]
  day   only approve rows for this content day (omit = all pending)
"""
import os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from publishers import queue


def main():
    day = sys.argv[1] if len(sys.argv) > 1 else None
    params = {"select": "id,day,network,account,status", "status": "eq.pending"}
    if day:
        params["day"] = f"eq.{int(day)}"
    rows = queue._req("GET", "post_approvals", params=params)
    if not rows:
        print(f"No pending rows{f' for day {day}' if day else ''}.")
        return 0
    ok = 0
    for r in rows:
        try:
            queue.mark(r["id"], status="approved")
            ok += 1
            print(f"approved id={r['id']} day={r.get('day')} {r.get('network')}/{r.get('account')}")
        except Exception as e:
            print(f"ERR id={r['id']}: {e}")
    print(f"Approved {ok}/{len(rows)} pending row(s){f' for day {day}' if day else ''}.")
    return 0 if ok == len(rows) else 1


if __name__ == "__main__":
    sys.exit(main())
