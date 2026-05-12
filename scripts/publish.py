#!/usr/bin/env python3
"""
UPE Social Publisher — Facebook + Instagram via Graph API.

Usage:
  python3 scripts/publish.py                  # publish today's day to all accounts
  python3 scripts/publish.py --day 20         # publish specific day
  python3 scripts/publish.py --dry-run        # preview without posting
  python3 scripts/publish.py --catchup        # publish all overdue past days
  python3 scripts/publish.py --status         # show state summary
  python3 scripts/publish.py --platform facebook  # restrict to one platform
"""

import os
import sys
import json
import argparse
from datetime import datetime, date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from publishers import facebook, instagram
from publishers.content import (
    load_all_content,
    get_day,
    get_today_day,
    extract_text,
    find_image_path,
    find_image_url,
    get_carousel_paths_for_data,
    find_carousel_urls,
)
from publishers.state import (
    load_state,
    save_state,
    mark_published,
    get_published_days,
)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPORTS_DIR = os.path.join(ROOT, "reports")

ACCOUNTS = [
    {"key": "uproductionevents",   "platform": "facebook",  "lang": "en"},
    {"key": "uproduction_spain",   "platform": "facebook",  "lang": "es"},
    {"key": "ig_uproductionevents", "platform": "instagram", "lang": "en"},
    {"key": "ig_uproduction_spain", "platform": "instagram", "lang": "es"},
    # ig_alon3153 dropped 2026-05-11: not a linked IG Business account on a managed Page.
    # Continues to be posted manually by Alon.
]


def log(msg: str) -> None:
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}", flush=True)


def write_report(day: int, results: list, content: dict) -> str:
    os.makedirs(REPORTS_DIR, exist_ok=True)
    fname = os.path.join(REPORTS_DIR, f"day{day}.txt")
    with open(fname, "w", encoding="utf-8") as f:
        f.write(f"UPE Social Publisher Report — Day {day}\n")
        f.write(f"Generated: {datetime.utcnow().isoformat()}Z\n")
        f.write(f"Theme: {content.get('theme', content.get('title', '-'))}\n")
        f.write(f"Date scheduled: {content.get('date', '-')}\n\n")
        f.write("Results:\n")
        for r in results:
            mark = "OK " if r.get("success") else "ERR"
            line = f"  [{mark}] {r.get('platform','?')} :: {r['account']}"
            if r.get("post_id"):
                line += f" → post_id={r['post_id']}"
            if r.get("error"):
                line += f" → {r['error']}"
            f.write(line + "\n")
    return fname


def _publish_one(acc: dict, day: int, data: dict, image_path: str, image_url: str, dry_run: bool) -> dict:
    platform = acc["platform"]
    text = extract_text(data, platform) or ""
    if not text:
        return {"success": False, "platform": platform, "account": acc["key"],
                "error": f"No {platform}.text in day {day}"}

    carousel_paths = get_carousel_paths_for_data(data)
    carousel_urls = find_carousel_urls(data) if carousel_paths else None
    is_carousel = bool(carousel_paths)

    # Per-platform strategy: FB can override carousel → single (slide1 only)
    fb_strategy = data.get("facebook_strategy")
    fb_use_single = platform == "facebook" and fb_strategy == "single_first_slide" and is_carousel

    if dry_run:
        if fb_use_single:
            kind = "single(from carousel[0])"
        else:
            kind = f"CAROUSEL[{len(carousel_paths)}]" if is_carousel else "single"
        log(f"  [DRY] {platform}::{acc['key']} ({acc['lang']}) — {kind} — {len(text)} chars")
        return {"success": True, "platform": platform, "account": acc["key"], "post_id": "DRY_RUN"}

    if platform == "facebook":
        if fb_use_single:
            result = facebook.publish_post(acc["key"], text, carousel_paths[0])
        elif is_carousel:
            result = facebook.publish_carousel(acc["key"], text, carousel_paths)
        else:
            result = facebook.publish_post(acc["key"], text, image_path)
    elif platform == "instagram":
        ig_key = acc["key"].replace("ig_", "")
        if is_carousel:
            if not carousel_urls:
                return {"success": False, "platform": platform, "account": acc["key"],
                        "error": "No IMAGE_BASE_URL set — IG carousel requires public URLs"}
            result = instagram.publish_carousel(ig_key, text, carousel_urls)
        else:
            if not image_url:
                return {"success": False, "platform": platform, "account": acc["key"],
                        "error": "No IMAGE_BASE_URL set — Instagram requires public image URL"}
            result = instagram.publish_post(ig_key, text, image_url)
    else:
        return {"success": False, "platform": platform, "account": acc["key"],
                "error": f"Unknown platform: {platform}"}

    result["platform"] = platform
    return result


def publish_day(day: int, dry_run: bool = False, platform_filter: str = None) -> bool:
    entry = get_day(day)
    if not entry:
        log(f"ERROR: No content for day {day}")
        return False

    data = entry["data"]
    carousel_paths = get_carousel_paths_for_data(data)
    image_path = find_image_path(day) if not carousel_paths else carousel_paths[0]
    image_url = find_image_url(day)
    if not image_path and not carousel_paths:
        log(f"ERROR: No image or carousel for day {day}")
        return False

    log(f"Day {day}: {data.get('theme', data.get('title','?'))[:80]}")
    if carousel_paths:
        log(f"  Carousel: {len(carousel_paths)} slides")
    else:
        log(f"  Image: {os.path.basename(image_path)}")
    if image_url:
        log(f"  Image URL: {image_url}")

    state = load_state()
    results = []

    for acc in ACCOUNTS:
        if platform_filter and acc["platform"] != platform_filter:
            continue
        if day in get_published_days(state, acc["key"]):
            log(f"  ⏭  {acc['platform']}::{acc['key']} — already published")
            continue

        res = _publish_one(acc, day, data, image_path, image_url, dry_run)
        results.append(res)

        if res["success"]:
            log(f"  ✅ {acc['platform']}::{acc['key']} → {res.get('post_id')}")
            if not dry_run:
                mark_published(state, day, acc["key"], res.get("post_id"), True)
        else:
            log(f"  ❌ {acc['platform']}::{acc['key']} → {res.get('error')}")
            if not dry_run:
                mark_published(state, day, acc["key"], None, False, res.get("error"))

    if not dry_run:
        save_state(state)
    report_path = write_report(day, results, data)
    log(f"Report: {report_path}")

    succeeded = sum(1 for r in results if r.get("success"))
    log(f"Day {day} summary: {succeeded}/{len(results)} posted")
    return succeeded == len(results) if results else True


def show_status() -> None:
    content = load_all_content()
    state = load_state()
    print("=" * 80)
    print("UPE Social Publisher — Status")
    print("=" * 80)
    print(f"Today: {date.today().isoformat()}")
    print(f"Last publish: {state.get('last_publish', 'never')}")
    print(f"Content days available: {len(content)}")
    print()
    header = f"{'Day':<4} {'Date':<12} {'Title':<45} " + " ".join(a['key'][:8] for a in ACCOUNTS)
    print(header)
    print("-" * len(header))
    for day_num, entry in content.items():
        data = entry["data"]
        d = data.get("date", "-")
        title = (data.get("theme") or data.get("title") or "-")[:45]
        marks = []
        pubs = state.get("publications", {}).get(str(day_num), {})
        for acc in ACCOUNTS:
            r = pubs.get(acc["key"], {})
            marks.append("✓" if r.get("success") else ("✗" if r.get("error") else "·"))
        print(f"{day_num:<4} {d:<12} {title:<45} " + "        ".join(marks))


def find_catchup_days() -> list:
    content = load_all_content()
    state = load_state()
    today = date.today()
    out = []
    for day_num, entry in content.items():
        d_str = entry["data"].get("date")
        if not d_str:
            continue
        try:
            d = datetime.fromisoformat(d_str).date()
        except ValueError:
            continue
        if d > today:
            continue
        if any(day_num not in get_published_days(state, acc["key"]) for acc in ACCOUNTS):
            out.append(day_num)
    return sorted(out)


def main() -> int:
    p = argparse.ArgumentParser(description="UPE Social Publisher")
    p.add_argument("--day", type=int, help="Specific day")
    p.add_argument("--dry-run", action="store_true", help="Preview only")
    p.add_argument("--catchup", action="store_true", help="Publish all overdue past days at once")
    p.add_argument("--status", action="store_true", help="Show status")
    p.add_argument("--platform", choices=["facebook", "instagram"], help="Restrict to platform")
    args = p.parse_args()

    if args.status:
        show_status()
        return 0

    # Verify all tokens at start unless dry-run (fail-fast on invalid tokens)
    if not args.dry_run and os.environ.get("SKIP_TOKEN_VERIFY") != "1":
        log("Verifying all account tokens before publishing…")
        from publishers.facebook import verify_token as fb_verify
        from publishers.instagram import verify_account as ig_verify
        invalid = []
        for acc in ACCOUNTS:
            if args.platform and acc["platform"] != args.platform:
                continue
            if acc["platform"] == "facebook":
                pid = os.environ.get(f"FB_{acc['key'].upper()}_PAGE_ID")
                tok = os.environ.get(f"FB_{acc['key'].upper()}_PAGE_TOKEN")
                ok, info = fb_verify(pid, tok) if (pid and tok) else (False, "missing env")
            else:
                env_suffix = acc["key"].upper().removeprefix("IG_")
                pid = os.environ.get(f"IG_{env_suffix}_USER_ID")
                tok = os.environ.get(f"IG_{env_suffix}_ACCESS_TOKEN")
                ok, info = ig_verify(pid, tok) if (pid and tok) else (False, "missing env")
            mark = "✅" if ok else "❌"
            log(f"  {mark} {acc['platform']}::{acc['key']} → {info}")
            if not ok:
                invalid.append(f"{acc['platform']}::{acc['key']}: {info}")
        if invalid:
            log(f"ABORT: {len(invalid)} token(s) invalid — refusing to publish")
            for line in invalid:
                log(f"  - {line}")
            return 2

    if args.catchup:
        days = find_catchup_days()
        log(f"Catchup: {len(days)} days — {days}")
        all_ok = True
        for d in days:
            if not publish_day(d, dry_run=args.dry_run, platform_filter=args.platform):
                all_ok = False
        return 0 if all_ok else 1

    day = args.day
    if day is None:
        # Default: next day not yet successfully published to ALL accounts (one per day)
        content = load_all_content()
        state = load_state()
        for d in content.keys():
            unpublished = [acc for acc in ACCOUNTS if d not in get_published_days(state, acc["key"])]
            if unpublished:
                day = d
                break
        if day is None:
            log("Nothing to publish — all content days are fully published")
            return 0
        log(f"Auto-selected next pending day: {day}")

    return 0 if publish_day(day, dry_run=args.dry_run, platform_filter=args.platform) else 1


if __name__ == "__main__":
    sys.exit(main())
