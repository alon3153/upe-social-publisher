"""Facebook Pages publisher via Graph API v22.0."""

import os
import requests
from typing import Optional, Tuple

GRAPH_API = "https://graph.facebook.com/v22.0"
TIMEOUT = 60


class FacebookPublishError(Exception):
    pass


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
        with open(image_path, "rb") as img:
            r = requests.post(
                url,
                data={"caption": text, "access_token": page_token},
                files={"source": img},
                timeout=TIMEOUT,
            )
    else:
        url = f"{GRAPH_API}/{page_id}/feed"
        r = requests.post(
            url,
            data={"message": text, "access_token": page_token},
            timeout=TIMEOUT,
        )

    try:
        body = r.json()
    except Exception:
        body = {"raw": r.text}

    if r.status_code != 200:
        err = body.get("error", {}) if isinstance(body, dict) else {}
        msg = err.get("message", body) if err else body
        raise FacebookPublishError(f"HTTP {r.status_code}: {msg}")

    post_id = body.get("post_id") or body.get("id")
    if not post_id:
        raise FacebookPublishError(f"No post_id in response: {body}")
    return True, post_id


def verify_token(page_id: str, page_token: str) -> Tuple[bool, str]:
    url = f"{GRAPH_API}/{page_id}"
    r = requests.get(
        url,
        params={"fields": "name,id", "access_token": page_token},
        timeout=10,
    )
    if r.status_code != 200:
        return False, f"HTTP {r.status_code}: {r.text[:200]}"
    data = r.json()
    return True, data.get("name", page_id)


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
        return {"success": False, "account": account_key, "error": str(e)}
    except Exception as e:
        return {"success": False, "account": account_key, "error": f"Unexpected: {e}"}
