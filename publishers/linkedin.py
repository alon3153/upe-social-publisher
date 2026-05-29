"""LinkedIn publisher via the versioned Posts API (rest/posts + rest/images).

Posts an image + text to a LinkedIn Company Page (organization) or, as a
fallback, to a member profile.

Env:
  LINKEDIN_ACCESS_TOKEN   member token with w_organization_social (+ r_organization_admin)
  LINKEDIN_ORG_ID         numeric organization id  -> author = urn:li:organization:<id>
  LINKEDIN_PERSON_ID      numeric/sub person id     -> author = urn:li:person:<id> (used only if no ORG_ID)
  LINKEDIN_VERSION        API version header, default 202401

Docs: https://learn.microsoft.com/en-us/linkedin/marketing/community-management/shares/posts-api
"""

import os
import requests
from typing import Optional, Tuple

from publishers.safe import scrub, with_retry

REST_BASE = "https://api.linkedin.com/rest"
TIMEOUT = 60
DEFAULT_VERSION = "202401"

# Characters LinkedIn requires to be escaped inside the `commentary` field.
_ESCAPE_CHARS = set(r"\|{}@[]()<>#*_~")


class LinkedInPublishError(Exception):
    pass


def _version() -> str:
    return os.environ.get("LINKEDIN_VERSION", DEFAULT_VERSION)


def _headers(token: str, extra: Optional[dict] = None) -> dict:
    h = {
        "Authorization": f"Bearer {token}",
        "LinkedIn-Version": _version(),
        "X-Restli-Protocol-Version": "2.0.0",
    }
    if extra:
        h.update(extra)
    return h


def _author_urn() -> Optional[str]:
    org = os.environ.get("LINKEDIN_ORG_ID")
    if org:
        org = org.strip()
        if org.startswith("urn:"):
            return org
        return f"urn:li:organization:{org}"
    person = os.environ.get("LINKEDIN_PERSON_ID")
    if person:
        person = person.strip()
        if person.startswith("urn:"):
            return person
        return f"urn:li:person:{person}"
    return None


def escape_commentary(text: str) -> str:
    """Escape the reserved little-text characters required by the Posts API commentary field."""
    out = []
    for ch in text:
        if ch in _ESCAPE_CHARS:
            out.append("\\" + ch)
        else:
            out.append(ch)
    return "".join(out)


@with_retry(max_attempts=3, base_delay=2.0)
def _init_upload(token: str, author: str) -> requests.Response:
    return requests.post(
        f"{REST_BASE}/images?action=initializeUpload",
        headers=_headers(token, {"Content-Type": "application/json"}),
        json={"initializeUploadRequest": {"owner": author}},
        timeout=TIMEOUT,
    )


@with_retry(max_attempts=3, base_delay=2.0)
def _put_bytes(upload_url: str, token: str, data: bytes) -> requests.Response:
    # LinkedIn upload URL accepts the image bytes via PUT with the bearer token.
    return requests.put(
        upload_url,
        headers={"Authorization": f"Bearer {token}"},
        data=data,
        timeout=TIMEOUT,
    )


@with_retry(max_attempts=3, base_delay=2.0)
def _create_post(token: str, payload: dict) -> requests.Response:
    return requests.post(
        f"{REST_BASE}/posts",
        headers=_headers(token, {"Content-Type": "application/json"}),
        json=payload,
        timeout=TIMEOUT,
    )


def _upload_image(token: str, author: str, image_path: str) -> str:
    """Initialize + upload an image, returning its urn:li:image:... id."""
    r = _init_upload(token, author)
    if r.status_code not in (200, 201):
        raise LinkedInPublishError(f"image init HTTP {r.status_code}: {scrub(r.text[:300])}")
    value = (r.json() or {}).get("value", {})
    upload_url = value.get("uploadUrl")
    image_urn = value.get("image")
    if not upload_url or not image_urn:
        raise LinkedInPublishError(f"image init missing uploadUrl/image: {scrub(r.text[:300])}")
    with open(image_path, "rb") as fh:
        up = _put_bytes(upload_url, token, fh.read())
    if up.status_code not in (200, 201):
        raise LinkedInPublishError(f"image upload HTTP {up.status_code}: {scrub(up.text[:200])}")
    return image_urn


def post_to_linkedin(token: str, author: str, text: str, image_path: Optional[str] = None) -> Tuple[bool, str]:
    if not token or not author:
        raise LinkedInPublishError("access token and author URN are required")

    payload = {
        "author": author,
        "commentary": escape_commentary(text),
        "visibility": "PUBLIC",
        "distribution": {
            "feedDistribution": "MAIN_FEED",
            "targetEntities": [],
            "thirdPartyDistributionChannels": [],
        },
        "lifecycleState": "PUBLISHED",
        "isReshareDisabledByAuthor": False,
    }

    if image_path and os.path.exists(image_path):
        image_urn = _upload_image(token, author, image_path)
        payload["content"] = {"media": {"id": image_urn, "altText": "Uproduction Events"}}

    r = _create_post(token, payload)
    if r.status_code not in (200, 201):
        raise LinkedInPublishError(f"post HTTP {r.status_code}: {scrub(r.text[:300])}")
    post_id = r.headers.get("x-restli-id") or r.headers.get("x-linkedin-id")
    if not post_id:
        try:
            post_id = (r.json() or {}).get("id", "")
        except Exception:
            post_id = ""
    return True, post_id or "posted"


def verify_token() -> Tuple[bool, str]:
    """Confirm the token + author resolve. Returns (ok, org_name_or_error)."""
    token = os.environ.get("LINKEDIN_ACCESS_TOKEN")
    author = _author_urn()
    if not token:
        return False, "Missing LINKEDIN_ACCESS_TOKEN"
    if not author:
        return False, "Missing LINKEDIN_ORG_ID (or LINKEDIN_PERSON_ID)"
    if author.startswith("urn:li:organization:"):
        org_id = author.rsplit(":", 1)[-1]
        r = requests.get(
            f"{REST_BASE}/organizations/{org_id}",
            headers=_headers(token),
            params={"fields": "localizedName,id"},
            timeout=10,
        )
        if r.status_code != 200:
            return False, f"HTTP {r.status_code}: {scrub(r.text[:200])}"
        return True, (r.json() or {}).get("localizedName", author)
    # member token: lightweight userinfo check
    r = requests.get("https://api.linkedin.com/v2/userinfo",
                     headers={"Authorization": f"Bearer {token}"}, timeout=10)
    if r.status_code != 200:
        return False, f"HTTP {r.status_code}: {scrub(r.text[:200])}"
    return True, (r.json() or {}).get("name", author)


def publish_post(account_key: str, text: str, image_path: Optional[str] = None) -> dict:
    """Match the facebook/instagram publisher interface.

    `account_key` is accepted for parity but LinkedIn targets a single page
    resolved from env (LINKEDIN_ORG_ID / LINKEDIN_PERSON_ID).
    """
    token = os.environ.get("LINKEDIN_ACCESS_TOKEN")
    author = _author_urn()
    if not token:
        return {"success": False, "account": account_key, "error": "Missing LINKEDIN_ACCESS_TOKEN"}
    if not author:
        return {"success": False, "account": account_key,
                "error": "Missing LINKEDIN_ORG_ID (or LINKEDIN_PERSON_ID)"}
    try:
        ok, post_id = post_to_linkedin(token, author, text, image_path)
        return {"success": ok, "account": account_key, "author": author, "post_id": post_id}
    except LinkedInPublishError as e:
        return {"success": False, "account": account_key, "error": scrub(e)}
    except Exception as e:
        return {"success": False, "account": account_key, "error": f"Unexpected: {scrub(e)}"}
