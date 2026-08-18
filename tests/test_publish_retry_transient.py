import datetime

from scripts import publish_approved


def _rows(monkeypatch, failed):
    monkeypatch.setattr(publish_approved.queue, "_req", lambda *a, **k: failed)
    marks = []
    monkeypatch.setattr(publish_approved.queue, "mark",
                        lambda row_id, **fields: marks.append((row_id, fields)))
    return marks


def _today():
    return datetime.date.today().isoformat()


def test_recent_transient_failure_is_requeued(monkeypatch):
    marks = _rows(monkeypatch, [{
        "id": "r1", "day": 107, "network": "instagram", "account": "ig_uproductionevents",
        "error": "HTTP 400: Only photo or video can be accepted media type.",
        "scheduled_date": _today(),
    }])

    assert publish_approved._retry_transient_failures() == 1
    assert marks[0][0] == "r1"
    assert marks[0][1]["status"] == "approved"
    assert marks[0][1]["error"].startswith("retry 1/3 · ")


def test_attempts_are_counted_and_capped(monkeypatch):
    marks = _rows(monkeypatch, [{
        "id": "r1", "day": 107, "network": "facebook", "account": "uproductionevents",
        "error": "retry 3/3 · HTTP 500: An unknown error has occurred.",
        "scheduled_date": _today(),
    }])

    assert publish_approved._retry_transient_failures() == 0
    assert marks == []


def test_second_attempt_increments_without_stacking_tags(monkeypatch):
    marks = _rows(monkeypatch, [{
        "id": "r1", "day": 107, "network": "facebook", "account": "uproductionevents",
        "error": "retry 1/3 · HTTP 500: An unknown error has occurred.",
        "scheduled_date": _today(),
    }])

    publish_approved._retry_transient_failures()

    assert marks[0][1]["error"] == "retry 2/3 · HTTP 500: An unknown error has occurred."


def test_old_failure_is_reported_not_republished(monkeypatch, capsys):
    """A two-month-old row must not be pushed out silently."""
    marks = _rows(monkeypatch, [{
        "id": "r1", "day": 48, "network": "facebook", "account": "uproduction_spain",
        "error": "HTTP 500: An unknown error has occurred.",
        "scheduled_date": "2026-06-12",
    }])

    assert publish_approved._retry_transient_failures() == 0
    assert marks == []
    assert "STALE-FAILED" in capsys.readouterr().out


def test_content_defect_is_not_retried(monkeypatch):
    marks = _rows(monkeypatch, [{
        "id": "r1", "day": 107, "network": "instagram", "account": "ig_uproductionevents",
        "error": "HTTP 400: The image is too small.", "scheduled_date": _today(),
    }])

    assert publish_approved._retry_transient_failures() == 0
    assert marks == []


def test_linkedin_auth_failure_is_left_to_the_auth_recovery(monkeypatch):
    marks = _rows(monkeypatch, [{
        "id": "r1", "day": 104, "network": "linkedin", "account": "li_dorin",
        "error": "AUTH_BLOCKED: advocate not connected: li_dorin",
        "scheduled_date": _today(),
    }])

    assert publish_approved._retry_transient_failures() == 0
    assert marks == []
