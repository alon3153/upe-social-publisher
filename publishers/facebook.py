"""Facebook Pages publisher via Graph API v22.0."""

import os
import json
import requests
from typing import List, Optional, Tuple

from publishers.safe import scrub, with_retry

GRAPH_API = "https://graph.facebook.com/v22.0"
TIMEOUT = 60


class FacebookPublishError(Exception):
    pass


@with_retry(max_attempts=3, base_delay=2.0)
def _post_photo(url: str, page_token: str, caption: str, image_path: str) -> requests.Response:
    with open(image_path, "rb") as img:
        return requests.post(
            url,
            data={"caption": caption, "access_token": page_token},
            files={"source": img},
            timeout=TIMEOUT,
        )


@with_retry(max_attempts=3, base_delay=2.0)
def _post_feed(url: str, page_token: str, message: str) -> requests.Response:
    return requests.post(
        url,
        data={"message": message, "access_token": page_token},
        timeout=TIMEOUT,
    )


def post_to_page(
    page_id: str,
    page_token: str,
    text: str,
    image_path: Optional[str] = None,
) -> Tuple[bool, str]:
    if not page_id or not page_token:
        raise FacebookPublishError("page_id and page_token are required")

    if image_path and os.path.exists(image_path):
        url = f"{GRAPH_API}/{page_id}/photos"
        r = _post_photo(url, page_token, text, image_path)
    else:
        url = f"{GRAPH_API}/{page_id}/feed"
        r = _post_feed(url, page_token, text)

    try:
        body = r.json()
    except Exception:
        body = {"raw": r.text}

    if r.status_code != 200:
        err = body.get("error", {}) if isinstance(body, dict) else {}
        msg = err.get("message", body) if err else body
        raise FacebookPublishError(f"HTTP {r.status_code}: {scrub(msg)}")

    post_id = body.get("post_id") or body.get("id")
    if not post_id:
        raise FacebookPublishError(f"No post_id in response: {scrub(body)}")
    return True, post_id


def verify_token(page_id: str, page_token: str) -> Tuple[bool, str]:
    """Quick check that token is valid. Returns (ok, page_name_or_error)."""
    r = requests.get(
        f"{GRAPH_API}/{page_id}",
        params={"fields": "name,id", "access_token": page_token},
        timeout=10,
    )
    if r.status_code != 200:
        return False, f"HTTP {r.status_code}: {scrub(r.text[:200])}"
    data = r.json()
    return True, data.get("name", page_id)


def get_token_expiry(page_token: str) -> Optional[int]:
    """Return UNIX timestamp when this token expires, or None if non-expiring/unknown."""
    r = requests.get(
        f"{GRAPH_API}/debug_token",
        params={"input_token": page_token, "access_token": page_token},
        timeout=10,
    )
    if r.status_code != 200:
        return None
    data = r.json().get("data", {})
    expires_at = data.get("expires_at")
    if expires_at == 0:
        return None  # never expires
    return expires_at


@with_retry(max_attempts=3, base_delay=2.0)
def _upload_unpublished(page_id: str, page_token: str, image_path: str) -> requests.Response:
    with open(image_path, "rb") as img:
        return requests.post(
            f"{GRAPH_API}/{page_id}/photos",
            data={"published": "false", "access_token": page_token},
            files={"source": img},
            timeout=TIMEOUT,
        )


def post_carousel_to_page(
    page_id: str,
    page_token: str,
    text: str,
    image_paths: List[str],
) -> Tuple[bool, str]:
    """Multi-photo post via attached_media (FB carousel-style)."""
    if not page_id or not page_token:
        raise FacebookPublishError("page_id and page_token are required")
    if not image_paths:
        raise FacebookPublishError("at least one image required for carousel")

    media_fbids = []
    for path in image_paths:
        if not os.path.exists(path):
            raise FacebookPublishError(f"image not found: {os.path.basename(path)}")
        r = _upload_unpublished(page_id, page_token, path)
        try:
            body = r.json()
        except Exception:
            body = {"raw": r.text}
        if r.status_code != 200:
            err = body.get("error", {}) if isinstance(body, dict) else {}
            raise FacebookPublishError(f"upload failed for {os.path.basename(path)}: HTTP {r.status_code}: {scrub(err.get('message', body))}")
        fbid = body.get("id")
        if not fbid:
            raise FacebookPublishError(f"no id returned for {os.path.basename(path)}: {scrub(body)}")
        media_fbids.append(fbid)

    attached = json.dumps([{"media_fbid": fbid} for fbid in media_fbids])
    r = requests.post(
        f"{GRAPH_API}/{page_id}/feed",
        data={"message": text, "attached_media": attached, "access_token": page_token},
        timeout=TIMEOUT,
    )
    try:
        body = r.json()
    except Exception:
        body = {"raw": r.text}
    if r.status_code != 200:
        err = body.get("error", {}) if isinstance(body, dict) else {}
        raise FacebookPublishError(f"feed post failed: HTTP {r.status_code}: {scrub(err.get('message', body))}")

    post_id = body.get("post_id") or body.get("id")
    if not post_id:
        raise FacebookPublishError(f"no post_id in response: {scrub(body)}")
    return True, post_id


def publish_carousel(account_key: str, text: str, image_paths: List[str]) -> dict:
    page_id = os.environ.get(f"FB_{account_key.upper()}_PAGE_ID")
    page_token = os.environ.get(f"FB_{account_key.upper()}_PAGE_TOKEN")
    if not page_id or not page_token:
        return {"success": False, "account": account_key,
                "error": f"Missing FB_{account_key.upper()}_PAGE_ID or _PAGE_TOKEN"}
    try:
        ok, post_id = post_carousel_to_page(page_id, page_token, text, image_paths)
        return {"success": ok, "account": account_key, "page_id": page_id, "post_id": post_id}
    except FacebookPublishError as e:
        return {"success": False, "account": account_key, "error": scrub(e)}
    except Exception as e:
        return {"success": False, "account": account_key, "error": f"Unexpected: {scrub(e)}"}


def publish_post(account_key: str, text: str, image_path: Optional[str] = None) -> dict:
    page_id = os.environ.get(f"FB_{account_key.upper()}_PAGE_ID")
    page_token = os.environ.get(f"FB_{account_key.upper()}_PAGE_TOKEN")

    if not page_id or not page_token:
        return {
            "success": False,
            "account": account_key,
            "error": f"Missing FB_{account_key.upper()}_PAGE_ID or FB_{account_key.upper()}_PAGE_TOKEN env var",
        }

    try:
        ok, post_id = post_to_page(page_id, page_token, text, image_path)
        return {
            "success": ok,
            "account": account_key,
            "page_id": page_id,
            "post_id": post_id,
        }
    except FacebookPublishError as e:
        return {"success": False, "account": account_key, "error": scrub(e)}
    except Exception as e:
        return {"success": False, "account": account_key, "error": f"Unexpected: {scrub(e)}"}
