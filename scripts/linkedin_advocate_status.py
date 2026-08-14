#!/usr/bin/env python3
"""Read-only report: can each LinkedIn advocate actually publish, and as whom?

Two other places already answer "is this advocate connected" — daily_email's
connected_advocates() and watchdog's check_linkedin_auth() — and on 14.08 they
disagreed with each other (approval email skipped li_dorin as not connected
07:57; the watchdog passed her 08:15) with no way to see the underlying row.
This prints the row so the disagreement is resolvable in one run.

Never prints tokens — only whether one is present, and the identity it writes as.
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from publishers import queue, linkedin

ADVOCATES = {"li_danielle": "דניאל", "li_dorin": "דורין", "li_natalia": "נטליה"}


def main():
    alon_urn = os.environ.get("LINKEDIN_MEMBER_URN", "")
    print(f"Alon's own member URN: {alon_urn or '(LINKEDIN_MEMBER_URN not set)'}")

    rows = {r.get("account"): r for r in queue.list_advocates()}
    print(f"rows in linkedin_advocate_tokens: {sorted(rows)}\n")

    problems = 0
    for account, display in ADVOCATES.items():
        row = rows.get(account)
        if not row:
            print(f"{account:<14} {display:<8} NO ROW — never connected")
            problems += 1
            continue
        urn = row.get("member_urn") or ""
        has_token = bool(row.get("access_token"))
        note = ""
        if urn and urn == alon_urn:
            note = "  ⚠️ THIS IS ALON'S OWN PROFILE — the wrong person clicked her link"
            problems += 1
        print(f"{account:<14} {display:<8} urn={urn or '(none)'} "
              f"token={'yes' if has_token else 'NO'} "
              f"expires_at={row.get('expires_at')}{note}")

        if not (has_token and urn):
            problems += 1
            continue
        auth = linkedin.preflight(token=row["access_token"], member_urn_expected=urn)
        print(f"{'':<14} preflight: {auth.get('code')} — {auth.get('message')} "
              f"scopes={auth.get('scopes')}")
        if not auth.get("ok"):
            problems += 1

    print(f"\nproblems: {problems}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
