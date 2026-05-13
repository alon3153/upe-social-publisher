#!/usr/bin/env python3
"""Publish AB Dental Gala Reel to TikTok @alonouaknine.

Two modes:
  - INBOX (default): video.upload scope — appears as draft in user's TikTok inbox,
    user completes posting from the app. Works immediately, no app audit needed.
  - DIRECT: video.publish scope — posts directly. Requires app audit by TikTok.
    Use --direct flag to attempt this.

Caption optimized for TikTok virality:
  - Hook in first line
  - Short emoji-heavy lines
  - Mix of FYP hashtags + brand + Hebrew
  - Mention @alonouaknine
"""
import os
import sys
import argparse
from pathlib import Path
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env")

from publishers.tiktok import (
    upload_video_to_inbox,
    direct_post_video,
    refresh_access_token,
    TikTokError,
)

VIDEO_PATH = ROOT / "content/videos/ab_dental_gala_reel.mp4"

CAPTION = """ערב גאלה. בלב הים. AB Dental 🌊✨

איך לוקחים אירוע ארגוני…
והופכים אותו לזיכרון של פעם בחיים?

הפקה: @alonouaknine
Uproduction Events
from business to pleasure 🎯

#fyp #foryou #foryoupage #אירועיחברה #גאלה #קרוז #הפקתאירועים #ישראל #abdental #uproductionevents #incentivetravel #corporateevents #eventproduction #galanight #cruise #ניהולאירועים #upe"""


def get_valid_access_token():
    """Return a valid TikTok access token; auto-refresh if needed."""
    access_token = os.environ.get("TIKTOK_ACCESS_TOKEN")
    if not access_token:
        print("❌ No TIKTOK_ACCESS_TOKEN in .env — run scripts/tiktok_oauth.py first")
        sys.exit(1)
    return access_token


def try_refresh_and_retry(error_msg):
    """If access token expired, refresh and update env."""
    print(f"⚠️  Token may be expired ({error_msg}). Attempting refresh…")
    client_key = os.environ.get("TIKTOK_CLIENT_KEY")
    client_secret = os.environ.get("TIKTOK_CLIENT_SECRET")
    refresh_token = os.environ.get("TIKTOK_REFRESH_TOKEN")
    if not all([client_key, client_secret, refresh_token]):
        print("❌ Cannot refresh — missing client_key/secret or refresh_token")
        sys.exit(1)
    tokens = refresh_access_token(client_key, client_secret, refresh_token)
    new_access = tokens["access_token"]
    new_refresh = tokens.get("refresh_token", refresh_token)

    # Update .env
    env_path = ROOT / ".env"
    lines = env_path.read_text().splitlines()
    new_lines = []
    keys_done = set()
    for line in lines:
        if line.startswith("TIKTOK_ACCESS_TOKEN="):
            new_lines.append(f"TIKTOK_ACCESS_TOKEN={new_access}")
            keys_done.add("TIKTOK_ACCESS_TOKEN")
        elif line.startswith("TIKTOK_REFRESH_TOKEN="):
            new_lines.append(f"TIKTOK_REFRESH_TOKEN={new_refresh}")
            keys_done.add("TIKTOK_REFRESH_TOKEN")
        else:
            new_lines.append(line)
    if "TIKTOK_ACCESS_TOKEN" not in keys_done:
        new_lines.append(f"TIKTOK_ACCESS_TOKEN={new_access}")
    if "TIKTOK_REFRESH_TOKEN" not in keys_done:
        new_lines.append(f"TIKTOK_REFRESH_TOKEN={new_refresh}")
    env_path.write_text("\n".join(new_lines) + "\n")
    print(f"✅ Refreshed access token")
    return new_access


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--direct", action="store_true",
                        help="Direct post (requires video.publish scope + audited app)")
    parser.add_argument("--privacy", default="PUBLIC_TO_EVERYONE",
                        choices=["PUBLIC_TO_EVERYONE", "MUTUAL_FOLLOW_FRIENDS",
                                 "FOLLOWER_OF_CREATOR", "SELF_ONLY"])
    args = parser.parse_args()

    if not VIDEO_PATH.exists():
        print(f"❌ Video not found: {VIDEO_PATH}")
        sys.exit(1)

    access_token = get_valid_access_token()

    print(f"🎬 Video: {VIDEO_PATH.name} ({VIDEO_PATH.stat().st_size:,}B)")
    print(f"📝 Caption: {len(CAPTION)} chars")
    print(f"🎯 Mode: {'DIRECT POST' if args.direct else 'INBOX (draft)'}")
    if args.direct:
        print(f"🔒 Privacy: {args.privacy}")
    print()

    def do_upload(token):
        if args.direct:
            return direct_post_video(token, VIDEO_PATH, CAPTION, privacy_level=args.privacy)
        return upload_video_to_inbox(token, VIDEO_PATH)

    try:
        result = do_upload(access_token)
    except TikTokError as e:
        msg = str(e)
        if "access_token_invalid" in msg or "401" in msg or "expired" in msg.lower():
            access_token = try_refresh_and_retry(msg)
            result = do_upload(access_token)
        else:
            print(f"\n❌ TikTok error: {e}")
            sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        sys.exit(1)

    print(f"\n🎉 SUCCESS!")
    print(f"   status: {result.get('status')}")
    if args.direct:
        print(f"   share_url: {result.get('publicaly_available_post_id')}")
        print(f"\n📲 Check your TikTok feed @alonouaknine — the post is live!")
    else:
        print(f"\n📲 Open TikTok app → Inbox/Notifications — your draft is waiting.")
        print(f"   Tap it → review → 'Post' to publish to your followers.")


if __name__ == "__main__":
    main()
