from scripts import publish_approved


def test_disconnected_advocate_never_falls_through_to_company(monkeypatch):
    monkeypatch.setenv("LINKEDIN_ORG_URN", "urn:li:organization:company")
    monkeypatch.setattr(publish_approved.queue, "get_advocate", lambda account: None)

    target = publish_approved._linkedin_target("li_dorin")

    assert target["ok"] is False
    assert "not connected" in target["message"]


def test_known_company_alias_routes_to_company(monkeypatch):
    monkeypatch.setenv("LINKEDIN_ORG_URN", "urn:li:organization:company")

    target = publish_approved._linkedin_target("alon3153")

    assert target == {
        "ok": True,
        "account": "alon3153",
        "kind": "organization",
        "token": None,
        "author_urn": "urn:li:organization:company",
    }


def test_auth_failure_requeues_only_after_exact_target_is_healthy(monkeypatch):
    failed = [{
        "id": "row-1", "day": 104, "network": "linkedin",
        "account": "li_spain", "error": "HTTP 403: organizationUgcAuthorizations",
    }]
    monkeypatch.setattr(publish_approved.queue, "_req", lambda *args, **kwargs: failed)
    monkeypatch.setattr(publish_approved, "_linkedin_target",
                        lambda account: {"ok": True, "account": account,
                                         "kind": "organization", "token": None,
                                         "author_urn": "urn:li:organization:spain"})
    marks = []
    monkeypatch.setattr(publish_approved.queue, "mark",
                        lambda row_id, **fields: marks.append((row_id, fields)))

    monkeypatch.setattr(publish_approved, "_linkedin_authorized",
                        lambda target, cache=None: {"ok": False, "code": "missing_scope",
                                                    "message": "missing"})
    assert publish_approved._recover_linkedin_auth_failures({}) == 0
    assert marks == []

    monkeypatch.setattr(publish_approved, "_linkedin_authorized",
                        lambda target, cache=None: {"ok": True})
    assert publish_approved._recover_linkedin_auth_failures({}) == 1
    assert marks == [("row-1", {"status": "approved", "error": None})]
