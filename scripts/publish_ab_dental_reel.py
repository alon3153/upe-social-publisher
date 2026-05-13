#!/usr/bin/env python3
"""One-off: publish the AB Dental Gala Reel to @uproductionevents with optimized viral copy."""
import os
import sys
import time
import requests
from pathlib import Path
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env")

from publishers.safe import scrub

GRAPH_API = "https://graph.facebook.com/v22.0"
VIDEO_URL = "https://raw.githubusercontent.com/alon3153/upe-social-publisher/main/content/videos/ab_dental_gala_reel.mp4"

CAPTION = """איך לוקחים אירוע ארגוני… והופכים אותו לזיכרון של פעם בחיים? 🌊

ערב הגאלה של AB Dental — אי שם בלב הים.
תאורה. מוזיקה. אוכל. אנשים. רגעים שלא נשכחים.

זה לא רק אירוע — זאת חוויה שמלווה את הצוות שנים קדימה.

✨ הפקה ועיצוב חוויה: Uproduction Events
🎯 from business to pleasure
🌐 www.upe.co.il

עוד מהעולם של @alon.ouaknine

שמרו 💾 | שתפו 📤 | תייגו את מי שצריך לראות 👇

#AbDental #UproductionEvents #CorporateEvents #IncentiveTravel #GalaNight #CruiseEvent #EventProduction #LuxuryEvents #B2BEvents #הפקתאירועים #אירועיחברה #ניהולאירועים #אירועיםעסקיים #ישראל #גאלה"""

# Pick a strong frame ~5s in as the cover (skip loading/intro frames)
THUMB_OFFSET_MS = 5000


def publish_reel_with_thumb(ig_user_id, access_token, caption, video_url, thumb_offset_ms):
    """Custom reel publish with thumb_offset for better cover frame."""
    # Step 1: Create container with REELS + thumb_offset
    r = requests.post(
        f"{GRAPH_API}/{ig_user_id}/media",
        data={
            "media_type": "REELS",
            "video_url": video_url,
            "caption": caption,
            "share_to_feed": "true",
            "thumb_offset": str(thumb_offset_ms),
            "access_token": access_token,
        },
        timeout=60,
    )
    body = r.json()
    if r.status_code != 200:
        raise RuntimeError(f"Container creation failed HTTP {r.status_code}: {scrub(body)}")
    container_id = body.get("id")
    if not container_id:
        raise RuntimeError(f"No container id: {scrub(body)}")
    print(f"📦 Container: {container_id}")

    # Step 2: Poll until FINISHED
    print("⏳ Waiting for reels processing", end="", flush=True)
    last_status = None
    for i in range(60):
        time.sleep(5)
        rr = requests.get(
            f"{GRAPH_API}/{container_id}",
            params={"fields": "status_code,status", "access_token": access_token},
            timeout=15,
        )
        if rr.status_code == 200:
            data = rr.json()
            last_status = data.get("status_code")
            if last_status == "FINISHED":
                print(" ✅")
                break
            if last_status == "ERROR":
                raise RuntimeError(f"Reel processing ERROR: {scrub(data)}")
        print(".", end="", flush=True)
    else:
        raise RuntimeError(f"Reels container did not finish in 5 min (last={last_status})")

    # Step 3: Publish
    rp = requests.post(
        f"{GRAPH_API}/{ig_user_id}/media_publish",
        data={"creation_id": container_id, "access_token": access_token},
        timeout=60,
    )
    pbody = rp.json()
    if rp.status_code != 200:
        raise RuntimeError(f"Publish HTTP {rp.status_code}: {scrub(pbody)}")
    media_id = pbody.get("id")
    if not media_id:
        raise RuntimeError(f"No media id in publish: {scrub(pbody)}")
    return media_id


if __name__ == "__main__":
    ig_user_id = os.environ.get("IG_UPRODUCTIONEVENTS_USER_ID")
    access_token = os.environ.get("IG_UPRODUCTIONEVENTS_ACCESS_TOKEN")
    if not ig_user_id or not access_token:
        print("❌ Missing IG credentials in .env")
        sys.exit(1)

    print(f"🎬 Video: {VIDEO_URL}")
    print(f"🎯 Account: @uproductionevents (ig_user_id={ig_user_id})")
    print(f"📸 Thumb offset: {THUMB_OFFSET_MS}ms")
    print(f"📝 Caption length: {len(CAPTION)} chars")
    print()

    try:
        media_id = publish_reel_with_thumb(
            ig_user_id, access_token, CAPTION, VIDEO_URL, THUMB_OFFSET_MS
        )
        print(f"\n🎉 PUBLISHED! media_id: {media_id}")

        # Fetch permalink
        rl = requests.get(
            f"{GRAPH_API}/{media_id}",
            params={"fields": "permalink,media_type,media_url", "access_token": access_token},
            timeout=15,
        )
        if rl.status_code == 200:
            data = rl.json()
            print(f"🔗 Permalink: {data.get('permalink')}")
            print(f"📹 Type: {data.get('media_type')}")
    except Exception as e:
        print(f"\n❌ FAILED: {e}")
        sys.exit(1)
