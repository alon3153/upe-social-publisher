#!/usr/bin/env python3
"""Read-only: what is in the approval queue, and what is blocking each row.

The watchdog reports counts ("8 posts stuck pending") but never which rows or
why, so every recurrence has meant guessing whether Alon's approve clicks
registered, whether a day was enqueued twice, or whether publishing failed after
approval. Prints the rows.

Usage: approval_queue_status.py [day]
"""
import os
import sys
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from publishers import queue


def main():
    day = sys.argv[1] if len(sys.argv) > 1 else ""

    params = {"select": "id,day,network,account,lang,status,approved_at,"
                        "published_at,post_id,error",
              "order": "day.desc,network.asc", "limit": "200"}
    if day:
        params["day"] = f"eq.{day}"
    else:
        params["status"] = "in.(pending,approved,failed)"
    rows = queue._req("GET", "post_approvals", params=params)

    print(f"rows: {len(rows)}")
    print("by status:", dict(Counter(r.get("status") for r in rows)))
    print("by day:", dict(Counter(r.get("day") for r in rows)))
    print()

    for r in rows:
        line = (f"day{r.get('day'):<5} {str(r.get('network')):<10} "
                f"{str(r.get('account')):<22} {str(r.get('lang')):<3} "
                f"{str(r.get('status')):<10}")
        if r.get("approved_at"):
            line += f" approved={r['approved_at'][:19]}"
        if r.get("published_at"):
            line += f" published={r['published_at'][:19]}"
        if r.get("error"):
            line += f"\n{'':<20}error: {str(r['error'])[:160]}"
        print(line)
    return 0


if __name__ == "__main__":
    sys.exit(main())
