"""Content loader — finds day-N content JSON + matching branded image."""

import os
import json
import glob
import re
from datetime import date
from typing import Optional, Iterable

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONTENT_DAYS_DIR = os.environ.get("CONTENT_DAYS_DIR", os.path.join(ROOT, "content", "days"))
CONTENT_IMAGES_DIR = os.environ.get("CONTENT_IMAGES_DIR", os.path.join(ROOT, "content", "images"))
IMAGE_BASE_URL = os.environ.get("IMAGE_BASE_URL", "").rstrip("/")


def load_all_content() -> dict:
    result = {}
    for f in glob.glob(os.path.join(CONTENT_DAYS_DIR, "*.json")):
        try:
            data = json.load(open(f, encoding="utf-8"))
        except Exception:
            continue
        day = data.get("day")
        if day is None:
            m = re.search(r"day(\d+)", os.path.basename(f))
            day = int(m.group(1)) if m else None
        if day is None:
            continue
        result[int(day)] = {"file": f, "data": data}
    return dict(sorted(result.items()))


def get_day(day: int) -> Optional[dict]:
    return load_all_content().get(day)


def get_today_day(today: Optional[date] = None) -> Optional[int]:
    today = today or date.today()
    for day_num, entry in load_all_content().items():
        if entry["data"].get("date") == today.isoformat():
            return day_num
    return None


def find_image_path(day: int) -> Optional[str]:
    if not os.path.isdir(CONTENT_IMAGES_DIR):
        return None
    for pat in (f"day{day}_*.png", f"day{day}_*.jpg", f"day{day}_*.jpeg"):
        matches = sorted(glob.glob(os.path.join(CONTENT_IMAGES_DIR, pat)))
        if matches:
            return matches[0]
    return None


def find_image_url(day: int) -> Optional[str]:
    """Public URL for the day's image — required by Instagram Graph API."""
    if not IMAGE_BASE_URL:
        return None
    path = find_image_path(day)
    if not path:
        return None
    return f"{IMAGE_BASE_URL}/content/images/{os.path.basename(path)}"


def get_next_pending_day(content: dict, published_per_account: dict, account: str) -> Optional[int]:
    """Lowest day number that has not been successfully published to this account."""
    published = published_per_account.get(account, set())
    for day in content.keys():
        if day not in published:
            return day
    return None


def extract_text(day_data: dict, platform: str) -> Optional[str]:
    block = day_data.get(platform)
    if isinstance(block, dict):
        return block.get("text")
    if isinstance(block, str):
        return block
    return None


def days_with_image(content: dict) -> list:
    return [d for d in content if find_image_path(d) or find_carousel_paths(d)]


def find_carousel_paths(day: int) -> Optional[list]:
    """Return list of carousel slide paths if day's content has carousel field, else None."""
    entry = get_day(day) if isinstance(day, int) else None
    if not entry:
        return None
    return _carousel_paths_from_data(entry["data"])


def _carousel_paths_from_data(data: dict) -> Optional[list]:
    carousel = data.get("carousel")
    if not carousel:
        return None
    img_dir = carousel.get("image_dir", "")
    slides = carousel.get("slides", [])
    if not slides:
        return None
    paths = []
    for s in slides:
        path = os.path.join(CONTENT_IMAGES_DIR, img_dir, s) if img_dir else os.path.join(CONTENT_IMAGES_DIR, s)
        if not os.path.exists(path):
            return None
        paths.append(path)
    return paths


def find_carousel_urls(data: dict) -> Optional[list]:
    """Return list of public URLs for carousel slides."""
    if not IMAGE_BASE_URL:
        return None
    carousel = data.get("carousel")
    if not carousel:
        return None
    img_dir = carousel.get("image_dir", "")
    slides = carousel.get("slides", [])
    if not slides:
        return None
    base = f"{IMAGE_BASE_URL}/content/images"
    if img_dir:
        return [f"{base}/{img_dir}/{s}" for s in slides]
    return [f"{base}/{s}" for s in slides]


def get_carousel_paths_for_data(data: dict) -> Optional[list]:
    """Public: get carousel paths directly from day data dict."""
    return _carousel_paths_from_data(data)
