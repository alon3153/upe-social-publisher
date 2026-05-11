"""Instagram Business publisher via Graph API v22.0.

Flow:
  1. POST /{ig-user-id}/media  → container_id (with image_url + caption)
  2. POST /{ig-user-id}/media_publish  → publishes container

Requires IG Business or Creator account linked to a Facebook Page.
"""

import os
import time
import requests
from typing import Tuple, Optional

from publishers.safe import scrub, with_retry

GRAPH_API = "https://graph.facebook.com/v22.0"
TIMEOUT = 60
CONTAINER_POLL_INTERVAL = 3
CONTAINER_POLL_MAX = 10


class InstagramPublishError(Exception):
    pass


@with_retry(max_attempts=3, base_delay=2.0)
def _request_post(url: str, data: dict) -> requests.Response:
    return requests.post(url, data=data, timeout=TIMEOUT)


def _post(url: str, data: dict) -> dict:
    r = _request_post(url, data)
    try:
        body = r.json()
    except Exception:
        body = {"raw": r.text}
    if r.status_code != 200:
        err = body.get("error", {}) if isinstance(body, dict) else {}
        msg = err.get("message", body) if err else body
        raise InstagramPublishError(f"HTTP {r.status_code}: {scrub(msg)}")
    return body


def _wait_container_ready(container_id: str, access_token: str) -> None:
    """Poll until container is FINISHED or ERROR. Raise on ERROR or timeout."""
    url = f"{GRAPH_API}/{container_id}"
    last_status = None
    for _ in range(CONTAINER_POLL_MAX):
        r = requests.get(url, params={"fields": "status_code", "access_token": access_token}, timeout=15)
        if r.status_code == 200:
            last_status = r.json().get("status_code")
            if last_status == "FINISHED":
                return
            if last_status == "ERROR":
                raise InstagramPublishError(f"Container processing failed: {scrub(r.json())}")
        time.sleep(CONTAINER_POLL_INTERVAL)
    raise InstagramPublishError(f"Container did not finish processing in {CONTAINER_POLL_INTERVAL * CONTAINER_POLL_MAX}s (last status: {last_status})")


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
        raise InstagramPublishError(f"No container id in response: {scrub(container)}")

    _wait_container_ready(container_id, access_token)

    result = _post(
        f"{GRAPH_API}/{ig_user_id}/media_publish",
        {"creation_id": container_id, "access_token": access_token},
    )
    media_id = result.get("id")
    if not media_id:
        raise InstagramPublishError(f"No media id in publish response: {scrub(result)}")
    return True, media_id


def verify_account(ig_user_id: str, access_token: str) -> Tuple[bool, str]:
    r = requests.get(
        f"{GRAPH_API}/{ig_user_id}",
        params={"fields": "username,id", "access_token": access_token},
        timeout=10,
    )
    if r.status_code != 200:
        return False, f"HTTP {r.status_code}: {scrub(r.text[:200])}"
    return True, r.json().get("username", ig_user_id)


def get_token_expiry(access_token: str) -> Optional[int]:
    """Return UNIX timestamp when this token expires, or None if non-expiring/unknown."""
    r = requests.get(
        f"{GRAPH_API}/debug_token",
        params={"input_token": access_token, "access_token": access_token},
        timeout=10,
    )
    if r.status_code != 200:
        return None
    data = r.json().get("data", {})
    expires_at = data.get("expires_at")
    if expires_at == 0:
        return None
    return expires_at


def publish_post(account_key: str, caption: str, image_url: str) -> dict:
    env_suffix = account_key.upper().removeprefix("IG_")
    ig_user_id = os.environ.get(f"IG_{env_suffix}_USER_ID")
    access_token = os.environ.get(f"IG_{env_suffix}_ACCESS_TOKEN")

    if not ig_user_id or not access_token:
        return {
            "success": False,
            "account": account_key,
            "error": f"Missing IG_{env_suffix}_USER_ID or IG_{env_suffix}_ACCESS_TOKEN",
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
        return {"success": False, "account": account_key, "error": scrub(e)}
    except Exception as e:
        return {"success": False, "account": account_key, "error": f"Unexpected: {scrub(e)}"}
