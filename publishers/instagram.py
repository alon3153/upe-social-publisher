"""Instagram Business publisher via Graph API v22.0.

Flow:
  1. POST /{ig-user-id}/media  → container_id (with image_url + caption)
  2. POST /{ig-user-id}/media_publish  → publishes container

Requires IG Business or Creator account linked to a Facebook Page.
"""

import os
import time
import requests
from typing import Tuple

GRAPH_API = "https://graph.facebook.com/v22.0"
TIMEOUT = 60
CONTAINER_POLL_INTERVAL = 3
CONTAINER_POLL_MAX = 10


class InstagramPublishError(Exception):
    pass


def _post(url: str, data: dict) -> dict:
    r = requests.post(url, data=data, timeout=TIMEOUT)
    try:
        body = r.json()
    except Exception:
        body = {"raw": r.text}
    if r.status_code != 200:
        err = body.get("error", {}) if isinstance(body, dict) else {}
        msg = err.get("message", body) if err else body
        raise InstagramPublishError(f"HTTP {r.status_code}: {msg}")
    return body


def _wait_container_ready(container_id: str, access_token: str) -> None:
    url = f"{GRAPH_API}/{container_id}"
    for _ in range(CONTAINER_POLL_MAX):
        r = requests.get(url, params={"fields": "status_code", "access_token": access_token}, timeout=15)
        if r.status_code == 200:
            status = r.json().get("status_code")
            if status == "FINISHED":
                return
            if status == "ERROR":
                raise InstagramPublishError(f"Container processing failed: {r.json()}")
        time.sleep(CONTAINER_POLL_INTERVAL)
    # Best-effort: proceed to publish anyway (most images are FINISHED instantly)


def post_to_account(
    ig_user_id: str,
    access_token: str,
    caption: str,
    image_url: str,
) -> Tuple[bool, str]:
    if not ig_user_id or not access_token:
        raise InstagramPublishError("ig_user_id and access_token are required")
    if not image_url:
        raise InstagramPublishError("image_url is required (Instagram does not support text-only posts)")
    if not image_url.startswith("https://"):
        raise InstagramPublishError(f"image_url must be HTTPS, got: {image_url}")

    container = _post(
        f"{GRAPH_API}/{ig_user_id}/media",
        {"image_url": image_url, "caption": caption, "access_token": access_token},
    )
    container_id = container.get("id")
    if not container_id:
        raise InstagramPublishError(f"No container id in response: {container}")

    _wait_container_ready(container_id, access_token)

    result = _post(
        f"{GRAPH_API}/{ig_user_id}/media_publish",
        {"creation_id": container_id, "access_token": access_token},
    )
    media_id = result.get("id")
    if not media_id:
        raise InstagramPublishError(f"No media id in publish response: {result}")
    return True, media_id


def verify_account(ig_user_id: str, access_token: str) -> Tuple[bool, str]:
    r = requests.get(
        f"{GRAPH_API}/{ig_user_id}",
        params={"fields": "username,id", "access_token": access_token},
        timeout=10,
    )
    if r.status_code != 200:
        return False, f"HTTP {r.status_code}: {r.text[:200]}"
    return True, r.json().get("username", ig_user_id)


def publish_post(account_key: str, caption: str, image_url: str) -> dict:
    ig_user_id = os.environ.get(f"IG_{account_key.upper()}_USER_ID")
    access_token = os.environ.get(f"IG_{account_key.upper()}_ACCESS_TOKEN")

    if not ig_user_id or not access_token:
        return {
            "success": False,
            "account": account_key,
            "error": f"Missing IG_{account_key.upper()}_USER_ID or IG_{account_key.upper()}_ACCESS_TOKEN",
        }

    try:
        ok, media_id = post_to_account(ig_user_id, access_token, caption, image_url)
        return {
            "success": ok,
            "account": account_key,
            "ig_user_id": ig_user_id,
            "post_id": media_id,
        }
    except InstagramPublishError as e:
        return {"success": False, "account": account_key, "error": str(e)}
    except Exception as e:
        return {"success": False, "account": account_key, "error": f"Unexpected: {e}"}
