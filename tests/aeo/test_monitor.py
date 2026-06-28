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
