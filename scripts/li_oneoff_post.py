#!/usr/bin/env python3
"""One-off LinkedIn post to a specific org/page using the stored token.
Caption is passed base64-encoded in LI_CAPTION_B64; target org in LI_ORG_URN
(empty -> personal profile). Used for verification posts; not part of the cron."""
import os, sys, base64
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from publishers import linkedin


def main():
    cap = base64.b64decode(os.environ.get("LI_CAPTION_B64", "")).decode("utf-8")
    org = os.environ.get("LI_ORG_URN") or None
    img = os.environ.get("LI_IMAGE_URL") or None
    if not cap.strip():
        print("no caption"); return 1
    print(f"posting to org={org or 'PERSONAL'} ({len(cap)} chars)")
    res = linkedin.publish_post(cap, image_url=img, org_urn=org)
    print(res)
    return 0 if res.get("success") else 1


if __name__ == "__main__":
    sys.exit(main())
