"""Read-only checks for a Meta post that may already be live after a server error.

These helpers never publish. A lookup failure raises ExistenceCheckError with
an HTTP status or exception type only — not the response body.
"""
import datetime
import re

import requests

from publishers.facebook import GRAPH_API as FB_GRAPH
from publishers.instagram import GRAPH_API as IG_GRAPH

CAPTION_PREFIX_LEN = 80
_GRAPH_OFFSET = re.compile(r"([+-]\d{2})(\d{2})$")


class ExistenceCheckError(Exception):
    pass


def caption_prefix(text):
    collapsed = " ".join((text or "").split())
    return collapsed[:CAPTION_PREFIX_LEN]


def parse_graph_time(value):
    if not isinstance(value, str) or not value:
        return None
    text = value.strip().replace("Z", "+00:00")
    text = _GRAPH_OFFSET.sub(r"\1:\2", text)
    try:
        parsed = datetime.datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=datetime.timezone.utc)
    return parsed.astimezone(datetime.timezone.utc)


def attempt_window(started_at, now=None, slack_seconds=120):
    """Inclusive window around one publish attempt, with a little clock slack."""
    now = now or datetime.datetime.now(datetime.timezone.utc)
    if started_at.tzinfo is None:
        started_at = started_at.replace(tzinfo=datetime.timezone.utc)
    else:
        started_at = started_at.astimezone(datetime.timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=datetime.timezone.utc)
    else:
        now = now.astimezone(datetime.timezone.utc)
    return (started_at - datetime.timedelta(seconds=slack_seconds),
            now + datetime.timedelta(seconds=30))


def _in_window(moment, start, end):
    return moment is not None and start <= moment <= end


def _call(get, url, params):
    try:
        response = get(url, params=params, timeout=20)
    except Exception as exc:
        raise ExistenceCheckError(type(exc).__name__) from None
    if getattr(response, "status_code", None) != 200:
        code = getattr(response, "status_code", "error")
        raise ExistenceCheckError(f"HTTP {code}")
    try:
        body = response.json()
    except Exception as exc:
        raise ExistenceCheckError(type(exc).__name__) from None
    if not isinstance(body, dict):
        raise ExistenceCheckError("invalid response")
    return body


def find_facebook_post(page_id, token, caption, start, end, get=None):
    """Page post id created in the attempt window whose message starts with the caption."""
    prefix = caption_prefix(caption)
    if not page_id or not token or not prefix:
        raise ExistenceCheckError("missing lookup input")
    get = get or requests.get
    body = _call(get, f"{FB_GRAPH}/{page_id}/posts", {
        "fields": "id,message,created_time",
        "since": str(int(start.timestamp())),
        "until": str(int(end.timestamp())),
        "limit": "25",
        "access_token": token,
    })
    data = body.get("data") or []
    if not isinstance(data, list):
        raise ExistenceCheckError("invalid response")
    found = []
    for post in data:
        if not isinstance(post, dict) or not post.get("id"):
            continue
        message = " ".join(str(post.get("message") or "").split())
        created = parse_graph_time(post.get("created_time"))
        if message.startswith(prefix) and _in_window(created, start, end):
            found.append((created, str(post["id"])))
    if not found:
        return None
    found.sort()
    return found[-1][1]


def find_instagram_media(ig_user_id, token, caption, start, end, container_id=None, get=None):
    """Recent media whose caption matches, or whose id is the container from this attempt."""
    prefix = caption_prefix(caption)
    if not ig_user_id or not token or not (prefix or container_id):
        raise ExistenceCheckError("missing lookup input")
    get = get or requests.get
    body = _call(get, f"{IG_GRAPH}/{ig_user_id}/media", {
        "fields": "id,caption,timestamp",
        "limit": "20",
        "access_token": token,
    })
    data = body.get("data") or []
    if not isinstance(data, list):
        raise ExistenceCheckError("invalid response")
    caption_hits = []
    for media in data:
        if not isinstance(media, dict) or not media.get("id"):
            continue
        media_id = str(media["id"])
        if container_id and media_id == str(container_id):
            return media_id
        text = " ".join(str(media.get("caption") or "").split())
        created = parse_graph_time(media.get("timestamp"))
        if prefix and text.startswith(prefix) and _in_window(created, start, end):
            caption_hits.append((created, media_id))
    if not caption_hits:
        return None
    caption_hits.sort()
    return caption_hits[-1][1]
