"""Founder-veto window: hold -> surface -> auto-merge-unless-vetoed."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
import held_pages as hp


def _page(slug, comps, title=None):
    return {"slug": slug, "frontmatter": {"title": title or slug, "canonical": f"/{slug}/"},
            "body": "x", "violations": [], "_competitors": comps}


def test_hold_persists_and_is_idempotent(tmp_path):
    p = tmp_path / "held.json"
    added = hp.hold([_page("a", ["freeman"]), _page("b", ["encore"])], "2026-07-12", path=p)
    assert set(added) == {"a", "b"}
    # re-holding keeps original held_since, adds nothing new
    again = hp.hold([_page("a", ["freeman"])], "2026-07-20", path=p)
    assert again == []
    data = hp.load(p)
    assert [h["held_since"] for h in data["held"] if h["slug"] == "a"] == ["2026-07-12"]


def test_not_due_inside_window(tmp_path):
    p = tmp_path / "held.json"
    hp.hold([_page("a", ["freeman"])], "2026-07-12", path=p)
    assert hp.due_for_merge("2026-07-12", path=p) == []  # 0 days < window


def test_due_after_window(tmp_path):
    p = tmp_path / "held.json"
    hp.hold([_page("a", ["freeman"])], "2026-07-12", path=p)
    due = hp.due_for_merge("2026-07-14", path=p)
    assert [d["slug"] for d in due] == ["a"]
    assert due[0]["frontmatter"]["title"] == "a"  # publishable shape


def test_veto_blocks_merge_and_reholding(tmp_path):
    p = tmp_path / "held.json"
    hp.hold([_page("a", ["freeman"])], "2026-07-12", path=p)
    hp.veto("a", path=p)
    assert hp.due_for_merge("2026-07-30", path=p) == []
    # a vetoed slug must never be re-held
    assert hp.hold([_page("a", ["freeman"])], "2026-07-30", path=p) == []


def test_release_removes_merged(tmp_path):
    p = tmp_path / "held.json"
    hp.hold([_page("a", ["freeman"]), _page("b", ["encore"])], "2026-07-12", path=p)
    assert hp.release(["a"], path=p) == 1
    assert {h["slug"] for h in hp.load(p)["held"]} == {"b"}


def test_digest_lists_awaiting_and_hides_when_empty(tmp_path):
    p = tmp_path / "held.json"
    assert hp.digest_html("2026-07-12", path=p) == ""
    hp.hold([_page("a", ["freeman"], title="Boutique vs Large")], "2026-07-12", path=p)
    html = hp.digest_html("2026-07-12", path=p)
    assert "Boutique vs Large" in html and "freeman" in html
    assert 'dir="rtl"' in html
