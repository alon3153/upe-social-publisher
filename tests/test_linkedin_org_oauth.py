from unittest.mock import patch

from scripts import linkedin_org_oauth as oauth


@patch("publishers.queue.delete_advocate")
@patch("publishers.queue.get_advocate")
@patch.object(oauth, "persist_token")
@patch.object(oauth, "validate_token", return_value=(True, []))
def test_promote_callback_validates_persists_and_deletes(
        validate, persist, get_advocate, delete_advocate):
    get_advocate.return_value = {
        "access_token": "callback-access",
        "refresh_token": "callback-refresh",
        "expires_at": "2099-01-01T00:00:00Z",
    }

    assert oauth.promote_callback_token() == 0
    validate.assert_called_once_with("callback-access")
    assert persist.call_args.args[0]["access_token"] == "callback-access"
    assert persist.call_args.args[0]["refresh_token"] == "callback-refresh"
    delete_advocate.assert_called_once_with("li_main_callback")


@patch("publishers.queue.delete_advocate")
@patch("publishers.queue.get_advocate")
@patch.object(oauth, "persist_token")
@patch.object(oauth, "validate_token", return_value=(False, ["wrong member"]))
def test_promote_callback_rejects_without_overwrite_and_still_deletes(
        validate, persist, get_advocate, delete_advocate):
    get_advocate.return_value = {"access_token": "wrong-access"}

    assert oauth.promote_callback_token() == 1
    persist.assert_not_called()
    delete_advocate.assert_called_once_with("li_main_callback")


@patch("publishers.queue.get_advocate", return_value=None)
def test_promote_callback_requires_staged_credential(get_advocate):
    assert oauth.promote_callback_token() == 1


def test_authorize_url_starts_at_the_registered_callback(monkeypatch):
    """The consent redirect must be issued by the edge function (CSRF nonce +
    cookie); a hand-built LinkedIn URL with a bare state is refused on return."""
    monkeypatch.setattr(oauth, "CID", "client-id")
    url = oauth.authorize_url()
    assert url.startswith(oauth.REDIRECT + "?")
    assert "advocate=main_callback" in url
    assert "linkedin.com" not in url
    assert "client-id" not in url


def test_org_scopes_match_the_edge_function():
    """scripts/linkedin_org_oauth.SCOPES documents what the function requests for
    the shared credential; the function's ORG_SCOPES is the value actually sent."""
    import re, os
    src = open(os.path.join(os.path.dirname(__file__), "..", "supabase", "functions",
                            "linkedin-oauth", "handler.ts"), encoding="utf-8").read()
    m = re.search(r'export const ORG_SCOPES =\s*"([^"]+)"', src)
    assert m, "ORG_SCOPES not found in handler.ts"
    assert set(m.group(1).split()) == set(oauth.SCOPES.split())


def test_authorize_url_only_requests_scopes_the_app_is_allowed():
    """LinkedIn answers unauthorized_scope_error instead of showing consent.

    App 78nrl43hscor4q has never had the OpenID Connect product approved, so
    openid/profile/r_liteprofile in the request make re-auth impossible — which
    is exactly what blocked recovery on 14.08.
    """
    requested = set(oauth.SCOPES.split())
    assert not requested & {"openid", "profile", "r_liteprofile"}
    assert {"w_organization_social", "w_member_social", "r_basicprofile"} <= requested
