import scripts.aeo_publish as pub
import pytest

PAGE = {"collection": "blog", "lang": "en", "slug": "my-slug",
        "frontmatter": {"title": "T", "language": "en"}, "body": "Uproduction Events has operated since 2010. See [conferences](/en/corporate-conference-producer-incentive-travel/) and [Europe](/en/corporate-event-production-europe-10-to-25000-attendees/).\n\n## b\n\nA complete sentence.", "violations": []}


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
    (tmp_path / "scripts/check-canonical-facts.mjs").write_text("// fixture")
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
    assert ["node", "scripts/check-canonical-facts.mjs"] in seq
    # site facts guard runs after the commit and before the push
    assert seq.index(["node", "scripts/check-canonical-facts.mjs"]) < seq.index(["git", "push"])
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
    (tmp_path / "scripts/check-canonical-facts.mjs").write_text("// fixture")
    calls = []
    def runner(cmd, **kwargs):
        calls.append(cmd)
        return type("R", (), {"returncode": 1 if cmd[:2] == ["git", "push"] else 0, "stdout": ""})()
    with pytest.raises(RuntimeError, match="git push"):
        pub.publish(str(tmp_path), [PAGE], "aeo/test", "2026-09-13", runner=runner)
    assert not any(cmd[:2] == ["gh", "pr"] for cmd in calls)


# --- PR #203 regression: a cut-off page or "16 years" never reaches git/gh ---

@pytest.mark.parametrize("body", ["…במקרה של מזג אוויר קי", "Founded in 2010, with over 16 years of operation."])
def test_truncated_or_noncanonical_page_never_pushes_or_opens_pr(tmp_path, body):
    guard = tmp_path / "scripts/check-competitor-names.mjs"
    guard.parent.mkdir()
    guard.write_text("// fixture")
    calls = []
    def runner(cmd, **kwargs):
        calls.append(cmd)
        return type("R", (), {"returncode": 0, "stdout": "https://github.com/x/y/pull/1"})()
    bad = dict(PAGE, body=body)
    with pytest.raises(ValueError, match="completeness/canon guard"):
        pub.publish(str(tmp_path), [bad], "aeo/test", "2026-10-11", runner=runner)
    assert calls == []
    assert not (tmp_path / "src").exists()  # nothing written either


# --- AEO 18.10: site canonical-facts guard is the source of truth; PR is a draft ---

def _repo_with_guards(tmp_path):
    (tmp_path / "scripts").mkdir()
    (tmp_path / "scripts/check-competitor-names.mjs").write_text("// fixture")
    (tmp_path / "scripts/check-canonical-facts.mjs").write_text("// fixture")


def test_site_facts_warning_on_generated_file_blocks_push(tmp_path):
    _repo_with_guards(tmp_path)
    calls = []
    warn = ("\n! canonical-facts guard: 1 founded-in-2010 warning(s) in 1 file(s)\n  ...\n\n"
            "  src/content/blog/en/my-slug.md:12\n\n✓ canonical-facts guard: clean aside from the warnings above\n")
    def runner(cmd, **kwargs):
        calls.append(cmd)
        out = warn if "check-canonical-facts.mjs" in " ".join(cmd) else ""
        return type("R", (), {"returncode": 0, "stdout": out})()
    with pytest.raises(ValueError, match="site canonical-facts guard"):
        pub.publish(str(tmp_path), [PAGE], "draft/aeo-test", "2026-10-18", runner=runner)
    assert not any(c[:2] in (["git", "push"], ["gh", "pr"]) for c in calls)


def test_site_facts_warning_on_other_file_does_not_block(tmp_path):
    _repo_with_guards(tmp_path)
    calls = []
    warn = "  src/data/about.en.ts:4\n✓ canonical-facts guard: clean aside from the warnings above\n"
    def runner(cmd, **kwargs):
        calls.append(cmd)
        out = warn if "check-canonical-facts.mjs" in " ".join(cmd) else (
            "https://github.com/x/y/pull/9\n" if cmd[:2] == ["gh", "pr"] else "")
        return type("R", (), {"returncode": 0, "stdout": out})()
    res = pub.publish(str(tmp_path), [PAGE], "draft/aeo-test", "2026-10-18", runner=runner)
    pr = next(c for c in calls if c[:2] == ["gh", "pr"])
    assert "--draft" in pr
    assert "Do not merge" in pr[pr.index("--body") + 1]
    assert res["pr_url"].endswith("/9")


def test_missing_site_facts_script_fails_closed(tmp_path):
    (tmp_path / "scripts").mkdir()
    (tmp_path / "scripts/check-competitor-names.mjs").write_text("// fixture")
    calls = []
    def runner(cmd, **kwargs):
        calls.append(cmd)
        return type("R", (), {"returncode": 0, "stdout": ""})()
    with pytest.raises(RuntimeError, match="check-canonical-facts"):
        pub.publish(str(tmp_path), [PAGE], "draft/aeo-test", "2026-10-18", runner=runner)
    assert not any(c[:2] in (["git", "push"], ["gh", "pr"]) for c in calls)


def test_generated_faqs_default_to_exclude_from_schema():
    import scripts.aeo_generate as gen
    md = gen.to_markdown({"title": "T", "faqs": [{"question": "q", "answer": "a."}]}, "b.")
    assert "    excludeFromSchema: true" in md
