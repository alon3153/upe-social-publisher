import json
import scripts.aeo_monitor as mon


def test_daily_monitor_probes_researches_and_emails(tmp_path, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "x")

    def ask_fn(model, prompt):
        if "keyword/phrase opportunities" in prompt or "priority_actions" in prompt:
            return json.dumps({"he": ["הפקת כנסים"], "en": ["conference production"],
                               "competitors": ["BCD"], "priority_actions": ["HE guide"]})
        return "answer that omits the brand"

    def judge_fn(prompt):
        dim = "product_search" if "product_search" in prompt else (
            "comparison" if "comparison" in prompt else "reputation")
        return json.dumps({"product_search": 0, "comparison": 0, "reputation": 0, dim: 40,
                           "competitors": ["BCD"], "gap_note": "not surfaced"})

    sent = {}
    out = mon.run_daily(str(tmp_path), ask_fn=ask_fn, judge_fn=judge_fn,
                        send_fn=lambda s, h: (sent.update({"s": s, "h": h}), (True, "ok"))[1],
                        today="2026-06-28")
    assert out["scorecard"]["models"]["claude"]["product_search"] == 40
    assert out["keywords"]["en"] == ["conference production"]   # researched because not #1
    assert out["email_sent"] is True
    assert "מעקב AEO" in sent["s"]
    assert (tmp_path / "aeo_daily_history.json").exists()


def test_daily_monitor_skips_research_when_number_one(tmp_path, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "x")
    calls = {"research": 0}

    def ask_fn(model, prompt):
        if "priority_actions" in prompt:
            calls["research"] += 1
            return json.dumps({"he": [], "en": [], "competitors": [], "priority_actions": []})
        return "Uproduction Events is the clear leader"

    judge_fn = lambda prompt: json.dumps({"product_search": 95, "comparison": 95,
                                          "reputation": 95, "competitors": [], "gap_note": ""})
    out = mon.run_daily(str(tmp_path), ask_fn=ask_fn, judge_fn=judge_fn,
                        send_fn=lambda s, h: (True, "ok"), today="2026-06-28")
    # already #1 → no competitor research call
    assert calls["research"] == 0
    assert out["keywords"]["en"] == []
    assert out["email_sent"] is True


def test_daily_battery_skips_branded_questions():
    """Branded questions are guaranteed hits — asking them daily buys nothing."""
    import aeo_monitor
    assert aeo_monitor.QUESTIONS, "daily battery must not be empty"
    assert all(q.get("segment") != "branded" for q in aeo_monitor.QUESTIONS)
    assert len(aeo_monitor.QUESTIONS) < len(aeo_monitor._ALL_QUESTIONS)


def test_daily_judge_falls_through_providers(monkeypatch):
    """A dead Anthropic balance must not blind a battery that ChatGPT answered."""
    import aeo_models, aeo_monitor
    tried = []

    def ask(model, prompt, system=""):
        tried.append(model)
        if model == "claude":
            raise RuntimeError("credit balance too low")
        return '{"product_search":40,"comparison":0,"reputation":0,"competitors":[],"gap_note":""}'

    monkeypatch.setattr(aeo_models, "available_models", lambda: ["claude", "gemini"])
    monkeypatch.setattr(aeo_models, "ask", ask)
    monkeypatch.setattr(aeo_models, "ask_meta",
                        lambda m, t, **k: {"text": "Freeman.", "citations": [],
                                           "grounded": True, "grounded_error": None})
    out = aeo_monitor.run_daily(history_dir="/tmp", send_fn=lambda *a, **k: (True, "x"),
                                today="2026-08-30")
    assert "claude" in tried and "gemini" in tried      # fell through
    assert out["scorecard"]["models"], "scorecard must not be empty when a judge succeeded"
