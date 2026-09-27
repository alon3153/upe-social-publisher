import datetime
import json

import pytest

from publishers import instagram, safe
from publishers.meta_reconcile import (
    ExistenceCheckError, find_facebook_post, find_instagram_media,
)
from scripts import publish_approved


class _Response:
    def __init__(self, status_code, payload):
        self.status_code = status_code
        self._payload = payload
        self.text = json.dumps(payload)

    def json(self):
        return self._payload


def test_media_id_unavailable_is_transient_regardless_of_case():
    response = _Response(400, {"error": {"message": "MEDIA ID IS NOT AVAILABLE", "code": 9007}})
    assert safe.is_transient(response)
    plain = _Response(400, {"error": {"message": "The image is too small.", "code": 9004}})
    assert not safe.is_transient(plain)


def test_media_publish_retries_until_the_container_id_is_available(monkeypatch):
    sleeps = []
    publish_calls = []

    def post(url, data=None, timeout=None):
        if url.endswith("/media"):
            return _Response(200, {"id": "container-1"})
        if url.endswith("/media_publish"):
            publish_calls.append(data["creation_id"])
            if len(publish_calls) < 3:
                return _Response(400, {"error": {"message": "Media ID is not available"}})
            return _Response(200, {"id": "media-9"})
        raise AssertionError(url)

    monkeypatch.setattr(instagram.requests, "post", post)
    monkeypatch.setattr(instagram.requests, "get",
                        lambda *a, **k: _Response(200, {"status_code": "FINISHED"}))
    monkeypatch.setattr(safe.time, "sleep", lambda seconds: sleeps.append(seconds))

    ok, media_id = instagram.post_to_account(
        "ig-user", "token-secret", "caption", "https://cdn.example/a.jpg")

    assert ok is True
    assert media_id == "media-9"
    assert publish_calls == ["container-1", "container-1", "container-1"]
    assert sleeps == [2.0, 4.0]
    assert "token-secret" not in json.dumps(publish_calls)


def test_exhausted_media_publish_keeps_the_container_id(monkeypatch):
    monkeypatch.setenv("IG_UPRODUCTIONEVENTS_USER_ID", "ig-user")
    monkeypatch.setenv("IG_UPRODUCTIONEVENTS_ACCESS_TOKEN", "token-secret")

    def post(url, data=None, timeout=None):
        if url.endswith("/media"):
            return _Response(200, {"id": "container-7"})
        return _Response(400, {"error": {"message": "Media ID is not available"}})

    monkeypatch.setattr(instagram.requests, "post", post)
    monkeypatch.setattr(instagram.requests, "get",
                        lambda *a, **k: _Response(200, {"status_code": "FINISHED"}))
    monkeypatch.setattr(safe.time, "sleep", lambda seconds: None)

    result = instagram.publish_post("uproductionevents", "caption", "https://cdn.example/a.jpg")

    assert result["success"] is False
    assert result["container_id"] == "container-7"
    assert "media id is not available" in result["error"].lower()


def _marks():
    saved = []

    def mark(row_id, **fields):
        saved.append((row_id, fields))

    return saved, mark


def _started():
    return datetime.datetime(2026, 9, 27, 12, 0, tzinfo=datetime.timezone.utc)


def test_facebook_server_error_records_the_live_post_instead_of_failed():
    saved, mark = _marks()
    row = {"id": "d4262229", "network": "facebook", "account": "uproduction_spain",
           "caption": "Company trip caption that is long enough to match"}

    def find_post(page_id, token, caption, start, end):
        assert caption.startswith("Company trip")
        return "fb-post-48"

    outcome, found = publish_approved.settle_failed_publish(
        row, {"success": False, "error": "HTTP 500: An unknown error has occurred."},
        _started(), mark, facebook_find=find_post)

    assert outcome == "published" and found == "fb-post-48"
    assert saved[0][1]["status"] == "published"
    assert saved[0][1]["post_id"] == "fb-post-48"
    assert saved[0][1]["error"] is None


def test_server_error_without_a_live_post_stays_failed():
    saved, mark = _marks()
    row = {"id": "row-1", "network": "facebook", "account": "uproduction_spain",
           "caption": "Company trip caption"}

    outcome, found = publish_approved.settle_failed_publish(
        row, {"success": False, "error": "HTTP 502: bad gateway"},
        _started(), mark, facebook_find=lambda *a, **k: None)

    assert (outcome, found) == ("failed", None)
    assert saved[0][1]["status"] == "failed"
    assert saved[0][1]["error"] == "HTTP 502: bad gateway"
    assert "NEEDS_VERIFICATION" not in saved[0][1]["error"]


def test_failed_existence_check_notes_needs_verification_on_the_error_field():
    saved, mark = _marks()
    row = {"id": "row-1", "network": "instagram", "account": "ig_uproductionevents",
           "caption": "caption"}

    def explode(*args, **kwargs):
        raise ExistenceCheckError("HTTP 500")

    outcome, found = publish_approved.settle_failed_publish(
        row, {"success": False, "error": "HTTP 500: An unknown error has occurred. token SECRET"},
        _started(), mark, instagram_find=explode)

    assert (outcome, found) == ("failed", None)
    assert saved[0][1]["status"] == "failed"
    assert saved[0][1]["error"].startswith("NEEDS_VERIFICATION:")
    assert "token SECRET" in saved[0][1]["error"]
    assert set(saved[0][1]) == {"status", "error"}


def test_content_error_does_not_call_the_existence_check():
    saved, mark = _marks()
    row = {"id": "row-1", "network": "facebook", "account": "uproduction_spain",
           "caption": "caption"}

    def explode(*args, **kwargs):
        raise AssertionError("lookup should not run")

    outcome, _found = publish_approved.settle_failed_publish(
        row, {"success": False, "error": "HTTP 400: The image is too small."},
        _started(), mark, facebook_find=explode)

    assert outcome == "failed"
    assert saved[0][1]["error"] == "HTTP 400: The image is too small."


def test_facebook_match_requires_caption_prefix_inside_the_attempt_window():
    start = datetime.datetime(2026, 6, 13, 9, 0, tzinfo=datetime.timezone.utc)
    end = datetime.datetime(2026, 6, 13, 9, 5, tzinfo=datetime.timezone.utc)
    caption = "Day 48 Spain post about the company trip and the venue"

    def get(url, params=None, timeout=None):
        assert params["fields"] == "id,message,created_time"
        assert "access_token" in params
        return _Response(200, {"data": [
            {"id": "old", "message": caption, "created_time": "2026-06-01T09:00:00+0000"},
            {"id": "live", "message": caption + " extra", "created_time": "2026-06-13T09:01:00+0000"},
            {"id": "other", "message": "unrelated", "created_time": "2026-06-13T09:02:00+0000"},
        ]})

    assert find_facebook_post("page", "token", caption, start, end, get=get) == "live"


def test_instagram_matches_container_id_or_recent_caption():
    start = datetime.datetime(2026, 9, 27, 12, 0, tzinfo=datetime.timezone.utc)
    end = datetime.datetime(2026, 9, 27, 12, 5, tzinfo=datetime.timezone.utc)

    def get(url, params=None, timeout=None):
        return _Response(200, {"data": [
            {"id": "container-7", "caption": "different", "timestamp": "2026-01-01T00:00:00+0000"},
        ]})

    assert find_instagram_media("ig", "token", "Day caption", start, end,
                                container_id="container-7", get=get) == "container-7"

    def by_caption(url, params=None, timeout=None):
        return _Response(200, {"data": [
            {"id": "old-media", "caption": "Day caption lives here",
             "timestamp": "2026-09-01T00:00:00+0000"},
            {"id": "new-media", "caption": "Day caption lives here",
             "timestamp": "2026-09-27T12:01:00+0000"},
        ]})

    assert find_instagram_media("ig", "token", "Day caption", start, end, get=by_caption) == "new-media"


def test_lookup_http_failure_does_not_include_the_response_body():
    def get(url, params=None, timeout=None):
        return _Response(500, {"error": {"message": "token SECRET"}})

    with pytest.raises(ExistenceCheckError) as caught:
        find_facebook_post("page", "token", "caption text", _started(),
                           _started() + datetime.timedelta(minutes=1), get=get)
    assert str(caught.value) == "HTTP 500"
    assert "SECRET" not in str(caught.value)
