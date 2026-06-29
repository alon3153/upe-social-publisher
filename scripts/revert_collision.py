#!/usr/bin/env python3
"""Revert the two pre-existing alon3153 rows (days 9002, 9003) that were
wrongly flipped to approved by an approve-by-day collision. Restore to pending.
Targets explicit row IDs only — does NOT touch the brand-film li_* rows or the
already-approved 9001/alon3153 row."""
import os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from publishers import queue

REVERT_IDS = ["7b07791c-9229-402d-8eb0-beb688caf1c1",  # day 9002 alon3153
              "eb3c7fae-d846-4ab7-9129-fb3d3ce43751"]  # day 9003 alon3153

for rid in REVERT_IDS:
    res = queue._req("PATCH", "post_approvals", params={"id": f"eq.{rid}"},
                     body={"status": "pending"}, prefer="return=representation")
    print("reverted", [(r["day"], r["account"], r["status"]) for r in (res or [])])

# final state of the 6 rows
rows = queue._req("GET", "post_approvals",
                  params={"select": "day,account,status", "day": "in.(9001,9002,9003)", "order": "day.asc"})
print("FINAL:", [(r["day"], r["account"], r["status"]) for r in rows])
