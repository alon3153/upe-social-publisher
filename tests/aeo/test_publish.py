import scripts.aeo_publish as pub
import pytest

PAGE = {"collection": "blog", "lang": "en", "slug": "my-slug",
        "frontmatter": {"title": "T", "language": "en"}, "body": "## b", "violations": []}


def test_page_path():
    p = pub.page_path("/repo", PAGE)
    assert p == "/repo/src/content/blog/en/my-slug.md"


def test_write_pages(tmp_path):
    written = pub.write_pages(str(tmp_path), [PAGE])
    assert written == ["src/content/blog/en/my-slug.md"]
    f = tmp_path / "src/content/blog/en/my-slug.md"
    assert f.read_text(encoding="utf-8").startswith("---")


def test_publish_dry_run_skips_git(tmp_path):
    calls = []

    def runner(cmd, **kw):
        calls.append(cmd)
        class R:
            returncode = 0
            stdout = ""
        return R()

    out = pub.publish(str(tmp_path), [PAGE], "aeo/2026-06-28", "2026-06-28", runner=runner, dry_run=True)
    assert out["dry_run"] is True
    assert out["pr_url"] is None
    assert calls == []   # no git/gh in dry-run
    assert (tmp_path / "src/content/blog/en/my-slug.md").exists()


def test_publish_runs_git_then_pr(tmp_path):
    guard = tmp_path / "scripts/check-competitor-names.mjs"
    guard.parent.mkdir()
    guard.write_text("// fixture")
    seq = []

    def runner(cmd, **kw):
        seq.append(cmd[:2])
        class R:
            returncode = 0
            stdout = "https://github.com/x/y/pull/1\n" if cmd[:2] == ["gh", "pr"] else ""
        return R()

    out = pub.publish(str(tmp_path), [PAGE], "aeo/2026-06-28", "2026-06-28", runner=runner, dry_run=False)
    assert seq[0] == ["node", "scripts/check-competitor-names.mjs"]
    assert ["git", "checkout"] in seq
    assert ["git", "add"] in seq
    assert ["gh", "pr"] in seq
    assert out["pr_url"] == "https://github.com/x/y/pull/1"


def test_destination_guard_failure_never_pushes_or_opens_pr(tmp_path):
    guard = tmp_path / "scripts/check-competitor-names.mjs"
    guard.parent.mkdir()
    guard.write_text("// fixture")
    calls = []
    def runner(cmd, **kwargs):
        calls.append(cmd)
        return type("R", (), {"returncode": 1, "stdout": "new destination rule"})()
    with pytest.raises(RuntimeError, match="command failed"):
        pub.publish(str(tmp_path), [PAGE], "aeo/test", "2026-09-13", runner=runner)
    assert calls == [["node", "scripts/check-competitor-names.mjs"]]


def test_veto_is_enforced_before_writing_any_file(tmp_path, monkeypatch):
    monkeypatch.setattr(pub.held_pages, "load", lambda: {"vetoed": [PAGE["slug"]]})
    with pytest.raises(ValueError, match="vetoed page"):
        pub.publish(str(tmp_path), [PAGE], "aeo/test", "2026-09-13", dry_run=True)
    assert not (tmp_path / "src").exists()


def test_metadata_name_is_rejected_before_writing(tmp_path):
    page = dict(PAGE, frontmatter={"title": "BCD Meetings comparison"})
    with pytest.raises(ValueError, match="destination guard"):
        pub.publish(str(tmp_path), [page], "aeo/test", "2026-09-13", dry_run=True)
    assert not (tmp_path / "src").exists()


def test_missing_destination_guard_fails_closed(tmp_path):
    with pytest.raises(RuntimeError, match="guard is missing"):
        pub.publish(str(tmp_path), [PAGE], "aeo/test", "2026-09-13")


def test_failed_push_cannot_create_pr(tmp_path):
    guard = tmp_path / "scripts/check-competitor-names.mjs"
    guard.parent.mkdir()
    guard.write_text("// fixture")
    calls = []
    def runner(cmd, **kwargs):
        calls.append(cmd)
        return type("R", (), {"returncode": 1 if cmd[:2] == ["git", "push"] else 0, "stdout": ""})()
    with pytest.raises(RuntimeError, match="git push"):
        pub.publish(str(tmp_path), [PAGE], "aeo/test", "2026-09-13", runner=runner)
    assert not any(cmd[:2] == ["gh", "pr"] for cmd in calls)
