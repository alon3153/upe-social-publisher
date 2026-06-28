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
