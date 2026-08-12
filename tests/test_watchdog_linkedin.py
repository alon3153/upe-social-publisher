from scripts import watchdog


def test_linkedin_auth_failures_are_grouped_as_recoverable_holds(monkeypatch):
    rows = [
        {"day": 104, "network": "linkedin", "account": "li_spain",
         "error": "HTTP 403: organizationUgcAuthorizations"},
        {"day": 104, "network": "linkedin", "account": "li_personal",
         "error": "HTTP 401: Submitter is not authorized"},
        {"day": 104, "network": "instagram", "account": "ig_uproductionevents",
         "error": "HTTP 500: transient"},
    ]
    monkeypatch.setattr(watchdog.queue, "_req", lambda *args, **kwargs: rows)

    messages = watchdog.check_failures()

    assert "2 פוסטי LinkedIn מושהים" in messages[0]
    assert "יוחזרו אוטומטית לתור" in messages[0]
    assert "כשלי פרסום אחרים" in messages[1]
    assert "instagram/ig_uproductionevents" in messages[2]
    assert all("organizationUgcAuthorizations" not in message for message in messages)
