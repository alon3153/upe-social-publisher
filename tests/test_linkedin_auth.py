from publishers import linkedin


def test_preflight_rejects_active_token_without_required_scope(monkeypatch):
    monkeypatch.setattr(
        linkedin, "introspect_token",
        lambda token: {"active": True, "scope": "openid profile"},
    )
    result = linkedin.preflight(token="token", member_urn_expected="person-1")

    assert result["ok"] is False
    assert result["code"] == "missing_scope"
    assert "w_member_social" in result["message"]


def test_preflight_rejects_member_identity_mismatch(monkeypatch):
    monkeypatch.setattr(
        linkedin, "introspect_token",
        lambda token: {"active": True, "scope": "w_member_social openid profile"},
    )
    monkeypatch.setattr(linkedin, "_member_urn_for_token",
                        lambda token: "urn:li:person:wrong-person")

    result = linkedin.preflight(token="token",
                                member_urn_expected="urn:li:person:alon")

    assert result["ok"] is False
    assert result["code"] == "identity_mismatch"
    assert "wrong-person" in result["message"]


def test_preflight_requires_approved_role_for_exact_org(monkeypatch):
    monkeypatch.setattr(
        linkedin, "introspect_token",
        lambda token: {"active": True, "scope": "w_organization_social"},
    )
    monkeypatch.setattr(
        linkedin, "_organization_roles",
        lambda token: {"urn:li:organization:english": {"ADMINISTRATOR"}},
    )

    denied = linkedin.preflight(token="token", org_urn="urn:li:organization:spain")
    allowed = linkedin.preflight(token="token", org_urn="urn:li:organization:english")

    assert denied["code"] == "org_role_missing"
    assert allowed["ok"] is True
