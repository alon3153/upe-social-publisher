#!/usr/bin/env python3
"""Prove against the LIVE approve function that approve_all cannot revive a reject.

Regression test for the 14.08.2026 bug: approve_all filtered out published and
approved rows but not `rejected`, so one batch click re-approved posts Alon had
declined. The function is deployed separately from this repo, so a passing unit
test would prove nothing — this exercises the real endpoint.

Safe by construction: it only calls approve_all, which by design touches pending
rows only, and it reports rather than repairs.

Usage: verify_approve_all.py <day>
"""
import os
import sys
import urllib.request
import urllib.error

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from publishers import queue

FN = os.environ.get("SUPABASE_URL", "").rstrip("/") + "/functions/v1/approve"
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"


def statuses(day):
    rows = queue._req("GET", "post_approvals", params={
        "select": "id,account,status", "day": f"eq.{day}", "order": "id.asc"})
    return {r["id"]: r for r in rows}


def main():
    day = sys.argv[1]
    before = statuses(day)
    if not before:
        print(f"day {day}: no rows — nothing to verify")
        return 1
    rejected_before = {i for i, r in before.items() if r["status"] == "rejected"}
    print(f"day {day} before: "
          f"{[(r['account'], r['status']) for r in before.values()]}")
    if not rejected_before:
        print("no rejected row on this day — cannot prove the fix here")
        return 1

    token = next(iter(queue._req("GET", "post_approvals", params={
        "select": "token", "day": f"eq.{day}", "limit": "1"})))["token"]
    req = urllib.request.Request(f"{FN}?action=approve_all&day={day}&token={token}",
                                 headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req) as r:
            print(f"approve_all returned HTTP {r.status}")
    except urllib.error.HTTPError as e:
        print(f"approve_all returned HTTP {e.code}")

    after = statuses(day)
    print(f"day {day} after:  "
          f"{[(r['account'], r['status']) for r in after.values()]}")

    revived = sorted(i for i in rejected_before if after.get(i, {}).get("status") != "rejected")
    if revived:
        print(f"\n❌ FAIL — approve_all revived rejected row(s): {revived}")
        print("the deployed function still filters on != approved/published")
        return 1
    print(f"\n✅ PASS — {len(rejected_before)} rejected row(s) stayed rejected")
    return 0


if __name__ == "__main__":
    sys.exit(main())
