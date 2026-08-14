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


def test_advocate_row_pointing_at_alons_own_profile_is_flagged(monkeypatch):
    """A connect link authorizes whoever opens it — not who it was addressed to."""
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("LINKEDIN_MEMBER_URN", "urn:li:person:ALON")
    monkeypatch.setenv("LINKEDIN_ORG_URN", "urn:li:organization:1")
    monkeypatch.setenv("LINKEDIN_ORG_URN_SPAIN", "urn:li:organization:2")
    monkeypatch.setattr(watchdog.linkedin, "_token", lambda: "shared")
    monkeypatch.setattr(watchdog.linkedin, "preflight",
                        lambda **kwargs: {"ok": True, "code": "ok"})
    monkeypatch.setattr(watchdog.queue, "list_advocates", lambda: [
        {"account": "li_danielle", "member_urn": "urn:li:person:DANIELLE",
         "access_token": "t1"},
        {"account": "li_dorin", "member_urn": "urn:li:person:ALON",
         "access_token": "t2"},
    ])

    messages = watchdog.check_linkedin_auth()

    assert len(messages) == 1
    assert "דורין" in messages[0]
    assert "מצביע על הפרופיל של אלון" in messages[0]
    assert "advocate=dorin" in messages[0]
