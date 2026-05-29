#!/usr/bin/env python3
"""LinkedIn integration check.

Default: verify the token + author URN resolve (no posting).
With --post and a --day, publishes a real test post to the configured page
(use only when you intend to publish).

Env: LINKEDIN_ACCESS_TOKEN, LINKEDIN_ORG_ID (or LINKEDIN_PERSON_ID)
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from publishers import linkedin
from publishers.content import find_image_path, get_day, extract_text


def main():
    ok, info = linkedin.verify_token()
    mark = "✅" if ok else "❌"
    print(f"{mark} LinkedIn token/author: {info}")
    if not ok:
        return 2

    if "--post" in sys.argv:
        day = None
        if "--day" in sys.argv:
            day = int(sys.argv[sys.argv.index("--day") + 1])
        if day is None:
            print("Provide --day N to test-post")
            return 1
        entry = get_day(day)
        if not entry:
            print(f"No content for day {day}")
            return 1
        text = extract_text(entry["data"], "linkedin") or extract_text(entry["data"], "facebook")
        path = find_image_path(day)
        print(f"Posting day {day} (image={'yes' if path else 'no'})…")
        res = linkedin.publish_post("li_uproductionevents", text, path)
        print(res)
        return 0 if res.get("success") else 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
