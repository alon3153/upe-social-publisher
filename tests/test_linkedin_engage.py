import importlib.util
import sys
from pathlib import Path


ROOT = Path(__file__).parents[1]
SCRIPT = ROOT / "scripts" / "linkedin_engage.py"


def _load_module():
    sys.path.insert(0, str(ROOT))
    spec = importlib.util.spec_from_file_location("linkedin_engage", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _advocates(engage, monkeypatch):
    monkeypatch.setattr(engage.queue, "list_advocates", lambda: [
        {"account": "li_danielle", "access_token": "t-dan",
         "member_urn": "urn:li:person:DAN"},
        {"account": "li_natalia", "access_token": "t-nat",
         "member_urn": "urn:li:person:NAT"},
    ])


def test_each_advocate_comments_once_with_her_own_token(monkeypatch, capsys):
    engage = _load_module()
    monkeypatch.setattr(sys, "argv", ["linkedin_engage.py"])
    _advocates(engage, monkeypatch)
    monkeypatch.setattr(engage, "recent_posts", lambda: [
        {"post_id": "urn:li:share:1", "day": 106, "account": "li_personal",
         "caption": "פוסט של אלון"}])
    monkeypatch.setattr(engage, "load_state", lambda: {})
    monkeypatch.setattr(engage, "save_state", lambda state: None)
    monkeypatch.setattr(engage, "comment_text",
                        lambda base, name, lang="he": f"תגובה של {name}")

    posted = []
    monkeypatch.setattr(engage.linkedin, "create_comment",
                        lambda urn, text, token, actor: posted.append(
                            (urn, text, token, actor)) or {"success": True,
                                                           "comment_id": "c1"})

    assert engage.main() == 0
    assert len(posted) == 2
    assert {p[3] for p in posted} == {"urn:li:person:DAN", "urn:li:person:NAT"}
    # each advocate must post with HER token, never the shared/company one
    assert dict((p[3], p[2]) for p in posted) == {
        "urn:li:person:DAN": "t-dan", "urn:li:person:NAT": "t-nat"}
    assert {p[1] for p in posted} == {"תגובה של דניאל", "תגובה של נטליה"}


def test_advocate_does_not_comment_twice_on_the_same_post(monkeypatch):
    """Idempotency comes from LinkedIn, so retries cannot double-comment."""
    engage = _load_module()
    monkeypatch.setattr(sys, "argv", ["linkedin_engage.py"])
    _advocates(engage, monkeypatch)
    monkeypatch.setattr(engage, "recent_posts", lambda: [
        {"post_id": "urn:li:share:1", "day": 106, "account": "li_personal",
         "caption": "פוסט"}])
    monkeypatch.setattr(engage, "load_state",
                        lambda: {"urn:li:share:1": ["li_danielle"]})
    monkeypatch.setattr(engage, "save_state", lambda state: None)
    monkeypatch.setattr(engage, "comment_text", lambda base, name, lang="he": "טקסט")

    posted = []
    monkeypatch.setattr(engage.linkedin, "create_comment",
                        lambda urn, text, token, actor: posted.append(actor)
                        or {"success": True, "comment_id": "c1"})

    assert engage.main() == 0
    assert posted == ["urn:li:person:NAT"]


def test_advocate_never_comments_on_her_own_post(monkeypatch):
    engage = _load_module()
    monkeypatch.setattr(sys, "argv", ["linkedin_engage.py"])
    _advocates(engage, monkeypatch)
    monkeypatch.setattr(engage, "recent_posts", lambda: [
        {"post_id": "urn:li:share:9", "day": 106, "account": "li_danielle",
         "caption": "הפוסט של דניאל"}])
    monkeypatch.setattr(engage, "load_state", lambda: {})
    monkeypatch.setattr(engage, "save_state", lambda state: None)
    monkeypatch.setattr(engage, "comment_text", lambda base, name, lang="he": "טקסט")

    posted = []
    monkeypatch.setattr(engage.linkedin, "create_comment",
                        lambda urn, text, token, actor: posted.append(actor)
                        or {"success": True, "comment_id": "c1"})

    assert engage.main() == 0
    assert posted == ["urn:li:person:NAT"]


def test_no_generic_fallback_when_generation_fails(monkeypatch):
    """Three profiles posting identical filler is exactly what a pod looks like."""
    engage = _load_module()
    monkeypatch.setattr(sys, "argv", ["linkedin_engage.py"])
    _advocates(engage, monkeypatch)
    monkeypatch.setattr(engage, "recent_posts", lambda: [
        {"post_id": "urn:li:share:1", "day": 106, "account": "li_personal",
         "caption": "פוסט"}])
    monkeypatch.setattr(engage, "load_state", lambda: {})
    monkeypatch.setattr(engage, "save_state", lambda state: None)
    monkeypatch.setattr(engage, "comment_text", lambda base, name, lang="he": "")

    posted = []
    monkeypatch.setattr(engage.linkedin, "create_comment",
                        lambda *a: posted.append(a) or {"success": True})

    assert engage.main() == 0
    assert posted == []


def test_the_record_is_written_before_the_next_comment_is_attempted(monkeypatch):
    """A lost record is a duplicate comment on the next run."""
    engage = _load_module()
    monkeypatch.setattr(sys, "argv", ["linkedin_engage.py"])
    _advocates(engage, monkeypatch)
    monkeypatch.setattr(engage, "recent_posts", lambda: [
        {"post_id": "urn:li:share:1", "day": 106, "account": "li_personal",
         "caption": "פוסט"}])
    monkeypatch.setattr(engage, "load_state", lambda: {})
    monkeypatch.setattr(engage, "comment_text", lambda base, name, lang="he": "טקסט")
    monkeypatch.setattr(engage.linkedin, "create_comment",
                        lambda *a: {"success": True, "comment_id": "c1"})

    saves = []
    monkeypatch.setattr(engage, "save_state",
                        lambda state: saves.append({k: list(v) for k, v in state.items()}))

    assert engage.main() == 0
    assert saves[0] == {"urn:li:share:1": ["li_danielle"]}
    assert saves[-1] == {"urn:li:share:1": ["li_danielle", "li_natalia"]}


def test_the_comment_follows_the_language_of_the_post(monkeypatch):
    """A Hebrew comment under the Spain page reads as an outsider."""
    engage = _load_module()
    monkeypatch.setattr(sys, "argv", ["linkedin_engage.py"])
    _advocates(engage, monkeypatch)
    monkeypatch.setattr(engage, "recent_posts", lambda: [
        {"post_id": "urn:li:share:5", "day": 108, "account": "li_spain",
         "lang": "es", "caption": "publicación"}])
    monkeypatch.setattr(engage, "load_state", lambda: {})
    monkeypatch.setattr(engage, "save_state", lambda state: None)
    monkeypatch.setattr(engage.linkedin, "create_comment",
                        lambda *a: {"success": True, "comment_id": "c1"})

    seen = []
    monkeypatch.setattr(engage, "comment_text",
                        lambda base, name, lang="he": seen.append(lang) or "texto")

    assert engage.main() == 0
    assert seen == ["es", "es"]
