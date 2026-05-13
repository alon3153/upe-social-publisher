"""TikTok Content Posting API publisher (v2).

Implements:
- OAuth 2.0 user token exchange + refresh
- Inbox upload (video.upload scope, no app audit required)
- Direct post (video.publish scope, requires app audit)
- FILE_UPLOAD chunked upload flow
- Publish status polling

Docs: https://developers.tiktok.com/doc/content-posting-api-reference-upload-video
"""

import os
import time
import requests
from pathlib import Path
from typing import Tuple, Optional

from publishers.safe import scrub, with_retry

OAUTH_AUTHORIZE_URL = "https://www.tiktok.com/v2/auth/authorize/"
OAUTH_TOKEN_URL = "https://open.tiktokapis.com/v2/oauth/token/"
INBOX_INIT_URL = "https://open.tiktokapis.com/v2/post/publish/inbox/video/init/"
DIRECT_POST_INIT_URL = "https://open.tiktokapis.com/v2/post/publish/video/init/"
STATUS_FETCH_URL = "https://open.tiktokapis.com/v2/post/publish/status/fetch/"

DEFAULT_TIMEOUT = 60
STATUS_POLL_INTERVAL = 5
STATUS_POLL_MAX = 60   # up to 5 min


class TikTokError(Exception):
    pass


def build_authorize_url(client_key: str, redirect_uri: str, scope: str, state: str) -> str:
    """Build the TikTok OAuth authorize URL."""
    from urllib.parse import urlencode
    params = {
        "client_key": client_key,
        "response_type": "code",
        "scope": scope,
        "redirect_uri": redirect_uri,
        "state": state,
    }
    return f"{OAUTH_AUTHORIZE_URL}?{urlencode(params)}"


def exchange_code_for_token(client_key: str, client_secret: str, code: str,
                            redirect_uri: str) -> dict:
    """Exchange authorization code for access + refresh tokens."""
    r = requests.post(
        OAUTH_TOKEN_URL,
        data={
            "client_key": client_key,
            "client_secret": client_secret,
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": redirect_uri,
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=DEFAULT_TIMEOUT,
    )
    body = r.json()
    if r.status_code != 200 or "access_token" not in body:
        raise TikTokError(f"Token exchange failed HTTP {r.status_code}: {scrub(body)}")
    return body


def refresh_access_token(client_key: str, client_secret: str, refresh_token: str) -> dict:
    """Refresh expired access token using refresh_token."""
    r = requests.post(
        OAUTH_TOKEN_URL,
        data={
            "client_key": client_key,
            "client_secret": client_secret,
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=DEFAULT_TIMEOUT,
    )
    body = r.json()
    if r.status_code != 200 or "access_token" not in body:
        raise TikTokError(f"Token refresh failed HTTP {r.status_code}: {scrub(body)}")
    return body


def init_inbox_upload(access_token: str, video_size: int,
                      chunk_size: int, total_chunk_count: int) -> Tuple[str, str]:
    """Initialize a FILE_UPLOAD inbox upload. Returns (publish_id, upload_url)."""
    r = requests.post(
        INBOX_INIT_URL,
        json={
            "source_info": {
                "source": "FILE_UPLOAD",
                "video_size": video_size,
                "chunk_size": chunk_size,
                "total_chunk_count": total_chunk_count,
            }
        },
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json; charset=UTF-8",
        },
        timeout=DEFAULT_TIMEOUT,
    )
    body = r.json()
    if r.status_code != 200:
        raise TikTokError(f"Inbox init failed HTTP {r.status_code}: {scrub(body)}")
    data = body.get("data", {})
    publish_id = data.get("publish_id")
    upload_url = data.get("upload_url")
    if not publish_id or not upload_url:
        raise TikTokError(f"Missing publish_id/upload_url in init response: {scrub(body)}")
    return publish_id, upload_url


def init_direct_post(access_token: str, title: str, video_size: int,
                     chunk_size: int, total_chunk_count: int,
                     privacy_level: str = "SELF_ONLY",
                     disable_duet: bool = False,
                     disable_comment: bool = False,
                     disable_stitch: bool = False,
                     auto_add_music: bool = False) -> Tuple[str, str]:
    """Initialize a Direct Post (requires video.publish + app audit).
    privacy_level: PUBLIC_TO_EVERYONE | MUTUAL_FOLLOW_FRIENDS | FOLLOWER_OF_CREATOR | SELF_ONLY
    """
    r = requests.post(
        DIRECT_POST_INIT_URL,
        json={
            "post_info": {
                "title": title[:2200],
                "privacy_level": privacy_level,
                "disable_duet": disable_duet,
                "disable_comment": disable_comment,
                "disable_stitch": disable_stitch,
                "auto_add_music": auto_add_music,
            },
            "source_info": {
                "source": "FILE_UPLOAD",
                "video_size": video_size,
                "chunk_size": chunk_size,
                "total_chunk_count": total_chunk_count,
            },
        },
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json; charset=UTF-8",
        },
        timeout=DEFAULT_TIMEOUT,
    )
    body = r.json()
    if r.status_code != 200:
        raise TikTokError(f"Direct post init failed HTTP {r.status_code}: {scrub(body)}")
    data = body.get("data", {})
    publish_id = data.get("publish_id")
    upload_url = data.get("upload_url")
    if not publish_id or not upload_url:
        raise TikTokError(f"Missing publish_id/upload_url: {scrub(body)}")
    return publish_id, upload_url


def upload_chunks(upload_url: str, video_path: Path, chunk_size: int,
                  content_type: str = "video/mp4") -> None:
    """PUT video in chunks to the TikTok upload_url."""
    total_size = video_path.stat().st_size
    with video_path.open("rb") as f:
        offset = 0
        while offset < total_size:
            chunk = f.read(chunk_size)
            this_chunk_size = len(chunk)
            first = offset
            last = offset + this_chunk_size - 1
            content_range = f"bytes {first}-{last}/{total_size}"
            r = requests.put(
                upload_url,
                data=chunk,
                headers={
                    "Content-Type": content_type,
                    "Content-Length": str(this_chunk_size),
                    "Content-Range": content_range,
                },
                timeout=DEFAULT_TIMEOUT * 3,
            )
            if r.status_code not in (200, 201, 206):
                raise TikTokError(
                    f"Chunk upload failed HTTP {r.status_code} for range {content_range}: "
                    f"{scrub(r.text[:300])}"
                )
            offset += this_chunk_size


def fetch_publish_status(access_token: str, publish_id: str) -> dict:
    """Fetch the publish status."""
    r = requests.post(
        STATUS_FETCH_URL,
        json={"publish_id": publish_id},
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json; charset=UTF-8",
        },
        timeout=DEFAULT_TIMEOUT,
    )
    body = r.json()
    if r.status_code != 200:
        raise TikTokError(f"Status fetch failed HTTP {r.status_code}: {scrub(body)}")
    return body.get("data", {})


def wait_for_publish(access_token: str, publish_id: str,
                     terminal_statuses=("SEND_TO_USER_INBOX", "PUBLISH_COMPLETE")) -> dict:
    """Poll status until terminal state or timeout."""
    last = None
    for _ in range(STATUS_POLL_MAX):
        time.sleep(STATUS_POLL_INTERVAL)
        last = fetch_publish_status(access_token, publish_id)
        status = last.get("status")
        if status in terminal_statuses:
            return last
        if status in ("FAILED",):
            raise TikTokError(f"Publish failed: {scrub(last)}")
    raise TikTokError(f"Publish did not complete in {STATUS_POLL_INTERVAL * STATUS_POLL_MAX}s, last={scrub(last)}")


def upload_video_to_inbox(access_token: str, video_path: Path) -> dict:
    """Full inbox flow: init → upload chunks → poll → return final status.
    Resulting draft appears in the user's TikTok app inbox for manual completion.
    """
    if not video_path.exists():
        raise TikTokError(f"Video file not found: {video_path}")
    video_size = video_path.stat().st_size

    # Strategy: single chunk if file ≤ 64MB, else split
    MAX_SINGLE_CHUNK = 64 * 1024 * 1024
    if video_size <= MAX_SINGLE_CHUNK:
        chunk_size = video_size
        total_chunks = 1
    else:
        chunk_size = 10 * 1024 * 1024  # 10MB chunks
        total_chunks = (video_size + chunk_size - 1) // chunk_size

    print(f"📤 Init inbox upload — size={video_size}B chunks={total_chunks} chunk_size={chunk_size}")
    publish_id, upload_url = init_inbox_upload(access_token, video_size, chunk_size, total_chunks)
    print(f"📦 publish_id: {publish_id}")

    print(f"⬆️  Uploading chunks…")
    upload_chunks(upload_url, video_path, chunk_size)
    print(f"✅ Upload complete, polling status…")

    return wait_for_publish(access_token, publish_id, terminal_statuses=("SEND_TO_USER_INBOX",))


def direct_post_video(access_token: str, video_path: Path, title: str,
                      privacy_level: str = "SELF_ONLY") -> dict:
    """Full direct-post flow (requires video.publish + audited app)."""
    if not video_path.exists():
        raise TikTokError(f"Video file not found: {video_path}")
    video_size = video_path.stat().st_size

    MAX_SINGLE_CHUNK = 64 * 1024 * 1024
    if video_size <= MAX_SINGLE_CHUNK:
        chunk_size = video_size
        total_chunks = 1
    else:
        chunk_size = 10 * 1024 * 1024
        total_chunks = (video_size + chunk_size - 1) // chunk_size

    print(f"📤 Init direct post — privacy={privacy_level}")
    publish_id, upload_url = init_direct_post(
        access_token, title, video_size, chunk_size, total_chunks,
        privacy_level=privacy_level,
    )
    print(f"📦 publish_id: {publish_id}")

    print(f"⬆️  Uploading chunks…")
    upload_chunks(upload_url, video_path, chunk_size)
    print(f"✅ Upload complete, polling status…")

    return wait_for_publish(access_token, publish_id, terminal_statuses=("PUBLISH_COMPLETE",))
