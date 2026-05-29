#!/usr/bin/env python3
"""Publish a Sofia presenter Reel (video) to one or more IG accounts.

Reads IG_<ACCOUNT>_USER_ID / IG_<ACCOUNT>_ACCESS_TOKEN from env (GitHub secrets).
Video must be a public HTTPS URL (raw.githubusercontent.com works).

Usage:
  python3 scripts/publish_sofia_reel.py \
    --accounts uproduction_spain \
    --video-url https://raw.githubusercontent.com/alon3153/upe-social-publisher/main/content/sofia/videos/sofia_barcelona_01.mp4 \
    --caption-file content/sofia/captions/barcelona_01.txt
"""
import argparse, sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from publishers import instagram


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--accounts", required=True,
                    help="comma-separated IG account keys, e.g. uproduction_spain,uproductionevents")
    ap.add_argument("--video-url", required=True)
    ap.add_argument("--caption-file", required=True)
    a = ap.parse_args()

    caption = open(a.caption_file, encoding="utf-8").read().strip()
    accounts = [x.strip() for x in a.accounts.split(",") if x.strip()]

    print(f"Publishing Sofia Reel to: {accounts}")
    print(f"Video: {a.video_url}")
    results, failed = [], False
    for acc in accounts:
        print(f"\n-> {acc} ...", flush=True)
        res = instagram.publish_reel(acc, caption, a.video_url, share_to_feed=True)
        results.append(res)
        if res.get("success"):
            print(f"   OK  post_id={res.get('post_id')}")
        else:
            failed = True
            print(f"   FAIL {res.get('error')}")

    print("\n=== SUMMARY ===")
    for r in results:
        print(f"  {r['account']}: {'OK ' + str(r.get('post_id')) if r.get('success') else 'FAIL ' + str(r.get('error'))}")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
