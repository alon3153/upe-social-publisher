#!/usr/bin/env python3
"""Reject duplicate live copies of the same post so a day cannot publish twice.

The watchdog detects two *approved* copies of one (day, network, account, lang)
but deliberately refuses to auto-act: un-approving something Alon approved is his
call, not the system's. This is the companion tool for when he makes that call.

Dry-run by default. Keeps exactly one copy per key — preferring the newest
scheduled_date, then the highest id — and rejects the rest.

Usage: dedupe_approved.py [--apply] [day]
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from publishers import queue

LIVE = ("pending", "approved")


def main():
    args = [a for a in sys.argv[1:] if a != "--apply"]
    apply_changes = "--apply" in sys.argv
    day = args[0] if args else None

    params = {"select": "id,day,network,account,lang,status,scheduled_date",
              "status": f"in.({','.join(LIVE)})"}
    if day:
        params["day"] = f"eq.{int(day)}"
    rows = queue._req("GET", "post_approvals", params=params)

    groups = {}
    for r in rows:
        if r.get("day") is None:
            continue
        key = (r["day"], r.get("network"), r.get("account"), r.get("lang"))
        groups.setdefault(key, []).append(r)

    dupes = {k: v for k, v in groups.items() if len(v) > 1}
    if not dupes:
        print("No duplicate live rows.")
        return 0

    rejected = 0
    for key, copies in sorted(dupes.items()):
        copies.sort(key=lambda r: ((r.get("scheduled_date") or ""), r["id"]))
        keep, drop = copies[-1], copies[:-1]
        print(f"day{key[0]} {key[1]}/{key[2]}/{key[3]}: "
              f"{len(copies)} live copies — keeping id={keep['id']} "
              f"({keep['status']}), rejecting {[d['id'] for d in drop]}")
        for d in drop:
            if not apply_changes:
                continue
            try:
                queue.mark(d["id"], status="rejected")
                rejected += 1
            except Exception as e:
                print(f"  ERR id={d['id']}: {e}")

    if not apply_changes:
        print("\nDRY RUN — nothing changed. Re-run with --apply to reject the extras.")
    else:
        print(f"\nrejected {rejected} duplicate row(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
