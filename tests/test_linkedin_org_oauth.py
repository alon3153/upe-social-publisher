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


def test_authorize_url_uses_registered_callback_state(monkeypatch):
    monkeypatch.setattr(oauth, "CID", "client-id")
    url = oauth.authorize_url()
    assert "state=main_callback" in url
    assert "functions%2Fv1%2Flinkedin-oauth" in url
