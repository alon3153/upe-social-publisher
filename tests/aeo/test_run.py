import json
import scripts.aeo_run as run_mod


def test_full_loop_dry_run(tmp_path, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "x")

    def ask_fn(model, prompt):
        if "PAGE TYPE" in prompt:
            meta = json.dumps({"title": "Guide to event production",
                               "description": "Uproduction Events — 16 years, 1,500+ events.",
                               "h1": "Guide", "slug": "guide-event-production",
                               "faqs": [{"question": "q?", "answer": "a full sentence answer about events."}]})
            return meta + "\n===BODY===\n## Overview\nFactual content.\n"
        return "Some answer that omits the brand."

    def judge_fn(prompt):
        dim = "product_search" if "product_search" in prompt else (
            "comparison" if "comparison" in prompt else "reputation")
        return json.dumps({"product_search": 0, "comparison": 0, "reputation": 0, dim: 30,
                           "competitors": ["BCD"], "gap_note": "not surfaced"})

    sent = {}

    def send_fn(subject, html):
        sent["subject"] = subject
        return True, "ok"

    # citation gate open (>=3 verified) so generation proceeds in this test
    monkeypatch.setattr(run_mod.citations_pipeline, "verified_count", lambda data=None: 3)
    out = run_mod.run(str(tmp_path), dry_run=True, ask_fn=ask_fn, judge_fn=judge_fn,
                      send_fn=send_fn, today="2026-06-28")
    assert out["scorecard"]["models"]["claude"]["product_search"] == 30
    assert len(out["briefs"]) >= 1
    assert out["pages"]                      # pages generated
    assert out["publish"]["dry_run"] is True
    assert out["email_sent"] is True
    assert "AEO" in sent["subject"]
    assert (tmp_path / "aeo_history.json").exists()


def test_generation_failure_is_not_fatal(tmp_path, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "x")

    def ask_fn(model, prompt):
        if "PAGE TYPE" in prompt:
            raise RuntimeError("HTTP 400 from anthropic: bad request")
        return "answer omitting brand"

    def judge_fn(prompt):
        dim = "product_search" if "product_search" in prompt else (
            "comparison" if "comparison" in prompt else "reputation")
        return json.dumps({"product_search": 0, "comparison": 0, "reputation": 0, dim: 30,
                           "competitors": [], "gap_note": "gap"})

    out = run_mod.run(str(tmp_path), dry_run=True, ask_fn=ask_fn, judge_fn=judge_fn,
                      send_fn=lambda s, h: (True, "ok"), today="2026-06-28")
    # probe + briefs still work; generation failures are recorded, run does not crash
    assert out["scorecard"]["models"]["claude"]["product_search"] == 30
    assert out["pages"] == []
    assert out["email_sent"] is True


def test_main_smoke(monkeypatch, capsys):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "x")
    monkeypatch.setattr("sys.argv", ["aeo_run.py", "--dry-run"])
    monkeypatch.setattr(run_mod, "run", lambda *a, **k: {"scorecard": {"models": {}}, "briefs": [],
                        "deferred": 0, "pages": [], "publish": {"dry_run": True}, "email_sent": False})
    run_mod.main()
    assert "AEO" in capsys.readouterr().out


def test_citation_gate_pauses_generation(tmp_path, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "x")
    ask_fn = lambda model, prompt: "Some answer that omits the brand."

    def judge_fn(prompt):
        return json.dumps({"product_search": 10, "comparison": 0, "reputation": 0,
                           "competitors": [], "gap_note": "gap"})

    monkeypatch.setattr(run_mod.citations_pipeline, "verified_count", lambda data=None: 0)
    monkeypatch.setattr(run_mod.citations_pipeline, "verify", lambda: [])
    monkeypatch.setattr(run_mod.citations_pipeline, "digest_html", lambda: "<h3>digest</h3>")
    out = run_mod.run(str(tmp_path), dry_run=True, ask_fn=ask_fn, judge_fn=judge_fn,
                      send_fn=lambda s, h: (True, "ok"), today="2026-07-05")
    assert out["pages"] == [] and out["briefs"] == []
    assert out["deferred"] >= 1                     # paused briefs counted as deferred


def test_publish_rejection_is_reported_without_claiming_shipment(tmp_path, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "x")
    monkeypatch.setattr(run_mod.citations_pipeline, "verified_count", lambda data=None: 3)
    def ask(model, prompt):
        if "PAGE TYPE" in prompt:
            return json.dumps({"title": "Guide", "description": "d", "h1": "Guide", "slug": "safe-guide"}) + "\n===BODY===\nBuyer criteria."
        return "answer omitting brand"
    def reject(*args, **kwargs):
        raise RuntimeError("destination guard blocked this draft")
    monkeypatch.setattr(run_mod.aeo_publish, "publish", reject)
    out = run_mod.run(str(tmp_path), dry_run=True, ask_fn=ask,
                      judge_fn=lambda prompt: json.dumps({"product_search": 0, "comparison": 0,
                          "reputation": 0, "competitors": [], "gap_note": "gap"}),
                      today="2026-09-13")
    assert out["pages"] == []
    assert out["publish"]["pr_url"] is None
    assert any("publication preflight failed" in failure for failure in out["failures"])


def test_unmerged_pr_is_recorded_pending_and_reported_as_pending_merge(tmp_path, monkeypatch):
    """A PR that is not merged yet must not be filed as reported-but-not-live."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "x")
    monkeypatch.setenv("ASTRO_REPO", str(tmp_path))
    monkeypatch.setattr(run_mod, "HISTORY", tmp_path / "aeo_history.json")
    monkeypatch.setattr(run_mod.citations_pipeline, "verified_count", lambda data=None: 3)
    monkeypatch.setattr(run_mod.citations_pipeline, "verify", lambda: [])
    monkeypatch.setattr(run_mod.citations_pipeline, "digest_html", lambda: "")
    monkeypatch.setattr(run_mod.held_pages, "hold", lambda *a, **k: None)
    monkeypatch.setattr(run_mod.held_pages, "due_for_merge", lambda *a, **k: [])
    monkeypatch.setattr(run_mod.held_pages, "digest_html", lambda *a, **k: "")
    monkeypatch.setattr(run_mod.held_pages, "release", lambda *a, **k: None)
    def ping(urls):
        raise AssertionError("pending urls must not be pinged")

    monkeypatch.setattr(run_mod.indexnow_ping, "ping", ping)

    seen = {}

    def record(pages, today, path=None, pending=False):
        seen["pending"] = pending
        seen["urls"] = [(p.get("frontmatter") or {}).get("canonical") for p in pages]

    def verify(today=None, path=None, opener=None):
        return [], [], []

    def filter_live(shipped, opener=None):
        return [], list(shipped)

    monkeypatch.setattr(run_mod.aeo_intents, "record", record)
    monkeypatch.setattr(run_mod.aeo_intents, "verify", verify)
    monkeypatch.setattr(run_mod.aeo_intents, "filter_live", filter_live)
    monkeypatch.setattr(run_mod.aeo_intents, "cover", lambda *a, **k: None)

    def publish(repo, pages, branch, date, runner=None, dry_run=False):
        return {"branch": branch, "files": ["x.md"],
                "pr_url": "https://github.com/alon3153/uproduction-astro/pull/278",
                "dry_run": False}

    monkeypatch.setattr(run_mod.aeo_publish, "publish", publish)
    sent = {}

    def ask(model, prompt):
        if "PAGE TYPE" in prompt:
            return (json.dumps({"title": "Cómo elegir", "description": "d", "h1": "Cómo elegir",
                                "slug": "como-elegir-productora"})
                    + "\n===BODY===\nBuyer criteria for a corporate producer.\n")
        return "answer omitting brand"

    out = run_mod.run(str(tmp_path), dry_run=False, ask_fn=ask,
                      judge_fn=lambda prompt: json.dumps({
                          "product_search": 0, "comparison": 0, "reputation": 0,
                          "competitors": [], "gap_note": "gap"}),
                      send_fn=lambda subject, html: sent.update(subject=subject, html=html) or (True, "ok"),
                      today="2026-11-22")
    assert seen.get("pending") is True
    assert out["shipped"] == []
    assert out["not_live"] == []
    assert out["pending"]
    assert "pending merge" in sent["html"]
    assert "reported-but-not-live" not in sent["html"]
    assert all("reported-but-not-live" not in f for f in out["failures"])
