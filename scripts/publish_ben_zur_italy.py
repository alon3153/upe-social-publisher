#!/usr/bin/env python3
"""Publish Ben Zur | Corb Italy 2026 video to IG + FB + TikTok.

Targets:
  - IG Reel  → @uproductionevents     (9:16)
  - IG Reel  → @uproduction_spain     (9:16)
  - FB Video → uproductionevents page (16:9)
  - FB Video → uproduction_spain page (16:9)
  - TikTok   → @alonouaknine inbox    (9:16, draft — user posts from app)

Flags:
  --dry-run         Print plan only, do not call any API
  --skip-ig         Skip Instagram
  --skip-fb         Skip Facebook
  --skip-tiktok     Skip TikTok
  --tiktok-direct   Direct TikTok post (requires audited app); default = inbox draft
"""
import argparse
import os
import sys
import requests
from pathlib import Path
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env")

from publishers.instagram import publish_reel  # noqa: E402
from publishers.safe import scrub  # noqa: E402
from publishers.tiktok import upload_video_to_inbox, direct_post_video, TikTokError  # noqa: E402

GRAPH_API = "https://graph.facebook.com/v22.0"

REEL_VIDEO_URL = os.environ.get("BEN_ZUR_REEL_URL", "https://raw.githubusercontent.com/alon3153/upe-social-publisher/main/content/videos/ben_zur_italy_reel_9x16.mp4")
FB_VIDEO_URL   = os.environ.get("BEN_ZUR_FB_URL",   "https://raw.githubusercontent.com/alon3153/upe-social-publisher/main/content/videos/ben_zur_italy_fb_16x9.mp4")

LOCAL_REEL_PATH = ROOT / "content/videos/ben_zur_italy_reel_9x16.mp4"
LOCAL_FB_PATH   = ROOT / "content/videos/ben_zur_italy_fb_16x9.mp4"

CAPTION_REEL = """The meeting you'll still talk about in 2027.

🇮🇹 Florence × Tuscany
Designed for Ben Zur | Corb Law Offices

DM "Italy" — we'll take it from there.

#Uproduction #FromBusinessToPleasure #ExecutiveOffsite #CorporateRetreat #Italy #Tuscany #Florence #LuxuryTravel #IncentiveTravel #LeadershipDevelopment #LawFirmCulture #BoutiqueExperiences"""

CAPTION_FB = """Some companies host meetings. We design the kind of days people remember a decade later.

This May, Ben Zur | Corb Law Offices traded their boardroom for Florence and Tuscany — and what came back wasn't just rested. It was aligned.

Three quiet days. One unforgettable team.
Curated end-to-end by Uproduction.

from business → to pleasure.

→ Message us to plan yours."""

CAPTION_TIKTOK = """POV: your law firm offsite isn't in a hotel conference room.

🇮🇹 Florence. Tuscany. Three days.
Designed for Ben Zur | Corb.

Want to see how it looked? Stay till the end 👀

#fyp #foryou #foryoupage #italy #tuscany #florence #corporateretreat #executivetravel #uproduction #frombusinesstopleasure #lawyersoftiktok #lawfirm #ceolife #luxurytravel #incentivetravel #behindthescenes #travelhacks"""

IG_ACCOUNTS = ["uproductionevents", "uproduction_spain"]
FB_ACCOUNTS = ["uproductionevents", "uproduction_spain"]


# ──────────── Facebook video upload (file_url) ────────────
def fb_post_video(page_id: str, page_token: str, description: str, file_url: str) -> dict:
    r = requests.post(
        f"{GRAPH_API}/{page_id}/videos",
        data={"description": description, "file_url": file_url, "access_token": page_token},
        timeout=120,
    )
    try:
        body = r.json()
    except Exception:
        body = {"raw": r.text}
    if r.status_code != 200:
        err = body.get("error", {}) if isinstance(body, dict) else {}
        return {"success": False, "error": f"HTTP {r.status_code}: {scrub(err.get('message', body))}"}
    vid = body.get("id")
    return {"success": bool(vid), "video_id": vid, "raw": body}


def publish_fb_video(account_key: str, description: str, file_url: str) -> dict:
    key = account_key.upper()
    page_id = os.environ.get(f"FB_{key}_PAGE_ID")
    page_token = os.environ.get(f"FB_{key}_PAGE_TOKEN")
    if not page_id or not page_token:
        return {"success": False, "account": account_key, "error": f"Missing FB_{key}_PAGE_ID/_PAGE_TOKEN"}
    res = fb_post_video(page_id, page_token, description, file_url)
    res["account"] = account_key
    res["page_id"] = page_id
    return res


# ──────────── Pretty print ────────────
def banner(text):
    print(f"\n{'═' * 70}\n  {text}\n{'═' * 70}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--skip-ig", action="store_true")
    parser.add_argument("--skip-fb", action="store_true")
    parser.add_argument("--skip-tiktok", action="store_true")
    parser.add_argument("--tiktok-direct", action="store_true",
                        help="Direct TikTok post (requires audited app). Default = inbox draft.")
    args = parser.parse_args()

    # Sanity: local files exist
    if not LOCAL_REEL_PATH.exists():
        print(f"❌ Missing local Reel: {LOCAL_REEL_PATH}")
        sys.exit(1)
    if not LOCAL_FB_PATH.exists():
        print(f"❌ Missing local FB video: {LOCAL_FB_PATH}")
        sys.exit(1)

    banner("Ben Zur | Corb Italy 2026 — Multi-platform Publish")
    print(f"Reel  (9:16, IG/TikTok):  {LOCAL_REEL_PATH.name}  ({LOCAL_REEL_PATH.stat().st_size:,}B)")
    print(f"FB    (16:9, FB pages):   {LOCAL_FB_PATH.name}    ({LOCAL_FB_PATH.stat().st_size:,}B)")
    print(f"\nReel URL: {REEL_VIDEO_URL}")
    print(f"FB URL:   {FB_VIDEO_URL}")
    print(f"\nMode: {'DRY-RUN' if args.dry_run else 'LIVE'}")

    plan = []
    if not args.skip_ig:
        for acc in IG_ACCOUNTS:
            plan.append(("IG-Reel", acc))
    if not args.skip_fb:
        for acc in FB_ACCOUNTS:
            plan.append(("FB-Video", acc))
    if not args.skip_tiktok:
        plan.append(("TikTok", "alonouaknine"))

    print(f"\nPlan ({len(plan)} targets):")
    for kind, acc in plan:
        print(f"  • {kind:10s} → {acc}")

    if args.dry_run:
        print("\n✓ Dry-run only — no API calls.")
        return

    results = []

    # 1) Instagram Reels
    if not args.skip_ig:
        for acc in IG_ACCOUNTS:
            banner(f"IG Reel → @{acc}")
            r = publish_reel(account_key=acc, caption=CAPTION_REEL,
                             video_url=REEL_VIDEO_URL, share_to_feed=True)
            results.append(("IG-Reel", acc, r))
            if r.get("success"):
                pid = r.get("post_id")
                print(f"✅ Published. media_id={pid}")
            else:
                print(f"❌ {r.get('error')}")

    # 2) Facebook videos
    if not args.skip_fb:
        for acc in FB_ACCOUNTS:
            banner(f"FB Video → {acc} page")
            r = publish_fb_video(account_key=acc, description=CAPTION_FB, file_url=FB_VIDEO_URL)
            results.append(("FB-Video", acc, r))
            if r.get("success"):
                print(f"✅ Submitted. video_id={r.get('video_id')} (FB will process async)")
            else:
                print(f"❌ {r.get('error')}")

    # 3) TikTok
    if not args.skip_tiktok:
        banner(f"TikTok → @alonouaknine ({'DIRECT' if args.tiktok_direct else 'INBOX draft'})")
        tt_token = os.environ.get("TIKTOK_ACCESS_TOKEN")
        if not tt_token:
            print("❌ Missing TIKTOK_ACCESS_TOKEN — skipping. Run scripts/tiktok_oauth.py to authorize.")
            results.append(("TikTok", "alonouaknine", {"success": False, "error": "no token"}))
        else:
            try:
                if args.tiktok_direct:
                    tr = direct_post_video(tt_token, LOCAL_REEL_PATH, CAPTION_TIKTOK,
                                           privacy_level="PUBLIC_TO_EVERYONE")
                else:
                    tr = upload_video_to_inbox(tt_token, LOCAL_REEL_PATH)
                results.append(("TikTok", "alonouaknine", {"success": True, "raw": tr}))
                print(f"✅ Status: {tr.get('status')}")
                if not args.tiktok_direct:
                    print("📲 Open TikTok app → Inbox → review the draft → tap Post.")
            except TikTokError as e:
                results.append(("TikTok", "alonouaknine", {"success": False, "error": str(e)}))
                print(f"❌ {e}")
            except Exception as e:
                results.append(("TikTok", "alonouaknine", {"success": False, "error": str(e)}))
                print(f"❌ {e}")

    # ──────────── Summary ────────────
    banner("Summary")
    ok = sum(1 for _, _, r in results if r.get("success"))
    fail = len(results) - ok
    for kind, acc, r in results:
        status = "✅" if r.get("success") else "❌"
        detail = r.get("post_id") or r.get("video_id") or r.get("error") or ""
        print(f"  {status} {kind:10s} {acc:20s} {str(detail)[:80]}")
    print(f"\nTotal: {ok} ok, {fail} fail (of {len(results)})")

    if fail:
        sys.exit(1)


if __name__ == "__main__":
    main()
