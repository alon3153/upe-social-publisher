#!/usr/bin/env python3
"""
KIE API key health check — validates KIE_API_KEY against kie.ai and reports
remaining credits.

Exit codes:
  0 = key valid
  1 = key missing, invalid, or KIE unreachable

Usage:
  python3 scripts/kie_check.py          # human-readable
  python3 scripts/kie_check.py --json   # machine-readable
"""
import os, sys, json, argparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from publishers import kie


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    ok, info = kie.verify_key()
    if args.json:
        print(json.dumps({"service": "kie", "ok": ok, "info": info}))
    else:
        print(f"{'OK  ' if ok else 'FAIL'} kie: {info}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
