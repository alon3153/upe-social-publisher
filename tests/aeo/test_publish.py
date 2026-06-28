import scripts.aeo_publish as pub

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
    seq = []

    def runner(cmd, **kw):
        seq.append(cmd[:2])
        class R:
            returncode = 0
            stdout = "https://github.com/x/y/pull/1\n" if cmd[:2] == ["gh", "pr"] else ""
        return R()

    out = pub.publish(str(tmp_path), [PAGE], "aeo/2026-06-28", "2026-06-28", runner=runner, dry_run=False)
    assert ["git", "checkout"] in seq
    assert ["git", "add"] in seq
    assert ["gh", "pr"] in seq
    assert out["pr_url"] == "https://github.com/x/y/pull/1"
