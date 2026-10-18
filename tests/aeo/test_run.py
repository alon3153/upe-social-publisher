import json
import scripts.aeo_run as run_mod


def test_full_loop_dry_run(tmp_path, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "x")

    def ask_fn(model, prompt):
        if "PAGE TYPE" in prompt:
            meta = json.dumps({"title": "Guide to event production",
                               "description": "Uproduction Events — operating since 2010, 1,500+ events.",
                               "h1": "Guide", "slug": "guide-event-production",
                               "faqs": [{"question": "q?", "answer": "Uproduction Events gives a full sentence answer about events."}]})
            return meta + "\n===BODY===\nUproduction Events has operated since 2010. See [conferences](/en/corporate-conference-producer-incentive-travel/) and [Europe](/en/corporate-event-production-europe-10-to-25000-attendees/).\n\n## Overview\nFactual content.\n"
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
            return json.dumps({"title": "Guide", "description": "d", "h1": "Guide", "slug": "safe-guide"}) + "\n===BODY===\nUproduction Events has operated since 2010. See [conferences](/en/corporate-conference-producer-incentive-travel/) and [Europe](/en/corporate-event-production-europe-10-to-25000-attendees/).\n\nBuyer criteria."
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


# --- PR #203 / AEO 18.10: a broken page fails the whole run; owned intents are not rewritten ---

def _judge_all_gaps(prompt):
    return json.dumps({"product_search": 0, "comparison": 0, "reputation": 0,
                       "competitors": [], "gap_note": "gap"})


def test_noncanonical_page_blocks_the_whole_run(tmp_path, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "x")
    monkeypatch.setattr(run_mod.citations_pipeline, "verified_count", lambda data=None: 3)
    monkeypatch.setattr(run_mod.aeo_policy, "load_owners", lambda path=None: {"owners": {}, "service_pages": {}})
    published = []
    monkeypatch.setattr(run_mod.aeo_publish, "publish", lambda *a, **k: published.append(a) or {})

    def ask(model, prompt):
        if "PAGE TYPE" in prompt:
            meta = json.dumps({"title": "Guide", "description": "d", "h1": "Guide", "slug": "g",
                               "faqs": [{"question": "q", "answer": "Uproduction Events helps."}]})
            return meta + ("\n===BODY===\nUproduction Events, founded in 2010, with over 16 years. "
                           "See [a](/en/a/) and [b](/en/b/).")
        return "answer omitting brand"
    out = run_mod.run(str(tmp_path), dry_run=True, ask_fn=ask, judge_fn=_judge_all_gaps,
                      send_fn=lambda s, h: (True, "ok"), today="2026-10-18")
    assert out["blocked"]
    assert out["pages"] == [] and published == []
    assert any(f.startswith("RUN BLOCKED") for f in out["failures"])
    # one failure line per violation, so the email lists each reason
    assert any("canonical fact" in f and f.startswith("guard rejected") for f in out["failures"])


def test_truncated_generation_blocks_the_run(tmp_path, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "x")
    monkeypatch.setattr(run_mod.citations_pipeline, "verified_count", lambda data=None: 3)
    monkeypatch.setattr(run_mod.aeo_policy, "load_owners", lambda path=None: {"owners": {}, "service_pages": {}})

    def ask(model, prompt):
        if "PAGE TYPE" in prompt:
            raise run_mod.aeo_models.TruncatedOutputError("claude output incomplete (stop_reason='max_tokens')")
        return "answer omitting brand"
    out = run_mod.run(str(tmp_path), dry_run=True, ask_fn=ask, judge_fn=_judge_all_gaps,
                      send_fn=lambda s, h: (True, "ok"), today="2026-10-18")
    assert out["blocked"] and out["pages"] == []


def test_main_exits_nonzero_when_blocked(monkeypatch):
    import pytest
    monkeypatch.setattr(run_mod, "run", lambda *a, **k: {"scorecard": {"models": {}}, "briefs": [], "pages": [],
                                                          "deferred": 0, "email_sent": True, "failures": ["x"],
                                                          "blocked": ["x"]})
    monkeypatch.setattr("sys.argv", ["aeo_run.py", "--dry-run"])
    with pytest.raises(SystemExit) as e:
        run_mod.main()
    assert e.value.code == 1


def test_owned_intents_get_strengthen_briefs_not_pages(tmp_path, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "x")
    monkeypatch.setattr(run_mod.citations_pipeline, "verified_count", lambda data=None: 3)
    every = {q["id"]: ["/owned/"] for q in run_mod.QUESTIONS}
    monkeypatch.setattr(run_mod.aeo_policy, "load_owners", lambda path=None: {"owners": every, "service_pages": {}})
    generated = []

    def ask(model, prompt):
        if "PAGE TYPE" in prompt:
            generated.append(prompt)
        return "answer omitting brand"
    sent = {}
    out = run_mod.run(str(tmp_path), dry_run=True, ask_fn=ask, judge_fn=_judge_all_gaps,
                      send_fn=lambda s, h: (sent.setdefault("html", h), (True, "ok"))[1], today="2026-10-18")
    assert generated == [] and out["pages"] == []
    assert out["strengthen"] and all(s["strengthen"] == ["/owned/"] for s in out["strengthen"])
    assert "/owned/" in sent["html"]



def test_blocked_brief_appears_in_email_as_content_task(tmp_path, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "x")
    monkeypatch.setattr(run_mod.citations_pipeline, "verified_count", lambda data=None: 3)
    monkeypatch.setattr(run_mod.aeo_policy, "load_owners", lambda path=None: {"owners": {}, "service_pages": {}})

    def ask(model, prompt):
        if "PAGE TYPE" in prompt:
            meta = json.dumps({"title": "G", "description": "d", "h1": "G", "slug": "g",
                               "faqs": [{"question": "q", "answer": "Uproduction Events helps."}]})
            return meta + "\n===BODY===\nUproduction Events. Plan 9-12 months ahead. [a](/en/a/) [b](/en/b/)."
        return "answer omitting brand"
    sent = {}
    out = run_mod.run(str(tmp_path), dry_run=True, ask_fn=ask, judge_fn=_judge_all_gaps,
                      send_fn=lambda s, h: (sent.setdefault("html", h), (True, "ok"))[1], today="2026-10-18")
    assert out["blocked"] and out["content_tasks"]
    assert "משימות חיזוק ל-CONTENT" in sent["html"]
    assert "operational number" in sent["html"]
