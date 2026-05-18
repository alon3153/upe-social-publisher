#!/usr/bin/env python3
"""Publish Boaz & Co. Law Firm — Italy Incentive Reel to TikTok @alonouaknine.

Inbox mode (video.upload scope) — uploads draft, caption auto-copied
to clipboard for Alon to paste in the TikTok app.
"""
import os
import sys
import argparse
import subprocess
import platform
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

VIDEO_PATH = ROOT / "content/videos/boaz_italy_v2_9x16.mp4"

CAPTION = """ספויילר: זה לא פגישה במשרד 🇮🇹

ככה משרד עו"ד בועז ושות' מתגמל את הצוות —
אינסטיב באיטליה. רק זיכרונות, אפס מצגות.

הפקה: @alonouaknine
Uproduction Events
from business to pleasure 🎯

#fyp #foryou #foryoupage #אינסטיב #משרדעורכידין #איטליה #טיולעבודה #הפקתאירועים #ישראל #incentivetravel #lawfirmlife #italytrip #corporateevents #eventproduction #uproductionevents #upe #fomo #travelreels #italytravel #lawyers"""


def copy_to_clipboard(text: str) -> bool:
    try:
        if platform.system() == "Darwin":
            subprocess.run(["pbcopy"], input=text.encode("utf-8"), check=True)
        elif platform.system() == "Linux":
            subprocess.run(["xclip", "-selection", "clipboard"],
                           input=text.encode("utf-8"), check=True)
        elif platform.system() == "Windows":
            subprocess.run(["clip"], input=text.encode("utf-16le"), check=True)
        else:
            return False
        return True
    except Exception:
        return False


def try_refresh_and_retry(error_msg):
    print(f"⚠️  Token may be expired ({error_msg}). Refreshing…")
    client_key = os.environ["TIKTOK_CLIENT_KEY"]
    client_secret = os.environ["TIKTOK_CLIENT_SECRET"]
    refresh_token = os.environ["TIKTOK_REFRESH_TOKEN"]
    tokens = refresh_access_token(client_key, client_secret, refresh_token)
    new_access = tokens["access_token"]
    new_refresh = tokens.get("refresh_token", refresh_token)
    env_path = ROOT / ".env"
    lines = env_path.read_text().splitlines()
    new_lines, keys_done = [], set()
    for line in lines:
        if line.startswith("TIKTOK_ACCESS_TOKEN="):
            new_lines.append(f"TIKTOK_ACCESS_TOKEN={new_access}"); keys_done.add("TIKTOK_ACCESS_TOKEN")
        elif line.startswith("TIKTOK_REFRESH_TOKEN="):
            new_lines.append(f"TIKTOK_REFRESH_TOKEN={new_refresh}"); keys_done.add("TIKTOK_REFRESH_TOKEN")
        else:
            new_lines.append(line)
    if "TIKTOK_ACCESS_TOKEN" not in keys_done:
        new_lines.append(f"TIKTOK_ACCESS_TOKEN={new_access}")
    if "TIKTOK_REFRESH_TOKEN" not in keys_done:
        new_lines.append(f"TIKTOK_REFRESH_TOKEN={new_refresh}")
    env_path.write_text("\n".join(new_lines) + "\n")
    print("✅ Refreshed access token")
    return new_access


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--direct", action="store_true")
    parser.add_argument("--privacy", default="PUBLIC_TO_EVERYONE")
    args = parser.parse_args()

    if not VIDEO_PATH.exists():
        print(f"❌ Video not found: {VIDEO_PATH}")
        sys.exit(1)

    access_token = os.environ.get("TIKTOK_ACCESS_TOKEN")
    if not access_token:
        print("❌ No TIKTOK_ACCESS_TOKEN in .env — run scripts/tiktok_oauth.py first")
        sys.exit(1)

    print(f"🎬 Video: {VIDEO_PATH.name} ({VIDEO_PATH.stat().st_size:,}B)")
    print(f"📝 Caption: {len(CAPTION)} chars")
    print(f"🎯 Mode: {'DIRECT POST' if args.direct else 'INBOX (draft)'}")

    if not args.direct:
        if copy_to_clipboard(CAPTION):
            print("📋 Caption copied to clipboard — paste in TikTok app")
        else:
            print("⚠️  Could not copy to clipboard — caption printed below")
            print(f"---\n{CAPTION}\n---")
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

    print(f"\n🎉 SUCCESS!")
    print(f"   status: {result.get('status')}")
    if args.direct:
        print(f"\n📲 Check your TikTok feed @alonouaknine — the post is live!")
    else:
        print(f"\n📲 Open TikTok app → Inbox/Notifications — your draft is waiting.")
        print(f"   Tap it → review → paste caption (Cmd/⌘V) → 'Post'")


if __name__ == "__main__":
    main()
