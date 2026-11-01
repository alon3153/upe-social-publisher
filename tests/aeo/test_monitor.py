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
    assert out["keywords"]["en"] == ["conference production"]   # researched because score target is unmet
    assert out["email_sent"] is True
    assert "מעקב AEO" in sent["s"]
    assert (tmp_path / "aeo_daily_history.json").exists()


def test_daily_monitor_skips_research_when_score_target_met(tmp_path, monkeypatch):
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
    # score target met → no competitor research call
    assert calls["research"] == 0
    assert out["keywords"]["en"] == []
    assert out["email_sent"] is True


def test_daily_battery_skips_branded_questions():
    """Branded questions are guaranteed hits — asking them daily buys nothing."""
    import aeo_monitor
    assert aeo_monitor.QUESTIONS, "daily battery must not be empty"
    assert all(q.get("segment") != "branded" for q in aeo_monitor.QUESTIONS)
    assert len(aeo_monitor.QUESTIONS) == 32
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


def test_degraded_high_score_does_not_satisfy_target():
    scorecard = {"models": {"claude": {"product_search": 95, "degraded": True}}}
    assert not mon._meets_score_target(scorecard, 70)
    scorecard["models"]["claude"]["degraded"] = False
    assert mon._meets_score_target(scorecard, 70)


def _judge_ok(prompt):
    return json.dumps({"product_search": 80, "comparison": 80, "reputation": 80,
                       "competitors": [], "gap_note": ""})


def _probe_answer(model, prompt):
    return "answer that omits the brand"


def test_chatgpt_runs_on_monday_wednesday_friday_only(tmp_path, monkeypatch):
    """UTC weekday of the run. Other days record skipped_schedule and do not call ChatGPT."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "x")
    monkeypatch.setenv("OPENAI_API_KEY", "x")
    monkeypatch.setenv("GEMINI_API_KEY", "x")
    called = []

    def ask_fn(model, prompt):
        called.append(model)
        return _probe_answer(model, prompt)

    schedule = [
        ("2026-11-02", True),   # Monday
        ("2026-11-03", False),  # Tuesday
        ("2026-11-04", True),   # Wednesday
        ("2026-11-05", False),  # Thursday
        ("2026-11-06", True),   # Friday
        ("2026-11-07", False),  # Saturday
        ("2026-11-01", False),  # Sunday
    ]
    sent = {}
    for day, runs in schedule:
        called.clear()
        sent.clear()
        day_dir = tmp_path / day
        day_dir.mkdir()
        out = mon.run_daily(str(day_dir), ask_fn=ask_fn, judge_fn=_judge_ok,
                            send_fn=lambda s, h, sent=sent: (sent.update({"s": s, "h": h}), (True, "ok"))[1],
                            today=day, send_email=True)
        block = out["scorecard"]["models"]["chatgpt"]
        assert "claude" in called and "gemini" in called
        assert called.count("chatgpt") == (len(mon.QUESTIONS) if runs else 0)
        assert out["scorecard"]["date"] == day
        if runs:
            assert block.get("status") != "skipped_schedule"
            assert block["product_search"] == 80
            assert "not scheduled" not in sent["h"]
        else:
            assert "chatgpt" not in called
            assert block["status"] == "skipped_schedule"
            assert block["reason"] == "not scheduled"
            assert not any("chatgpt" in f.lower() for f in out["failures"])
            assert "429" not in sent["h"] and "תקלות" not in sent["h"]
            assert "not scheduled" in sent["h"]
            assert "מכשיר תקול" not in sent["h"]
            joined = " ".join(out["failures"])
            assert "error" not in joined.lower() and "429" not in joined


def test_skip_day_does_not_call_openai_as_judge(tmp_path, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "x")
    monkeypatch.setenv("OPENAI_API_KEY", "x")
    monkeypatch.setenv("GEMINI_API_KEY", "x")
    seen = []

    def ask(model, prompt, system=""):
        seen.append(model)
        if model == "chatgpt":
            raise AssertionError("OpenAI judge must not run off the Mon/Wed/Fri schedule")
        return _judge_ok(prompt)

    def ask_meta(model, text, **kwargs):
        seen.append(model)
        if model == "chatgpt":
            raise AssertionError("OpenAI probe must not run off the Mon/Wed/Fri schedule")
        return {"text": "Freeman.", "citations": ["https://upe.co.il/"],
                "grounded": True, "grounded_error": None}

    monkeypatch.setattr(mon.aeo_models, "ask", ask)
    monkeypatch.setattr(mon.aeo_models, "ask_meta", ask_meta)
    out = mon.run_daily(str(tmp_path), send_fn=lambda *a, **k: (True, "ok"), today="2026-11-03")
    assert out["scorecard"]["models"]["chatgpt"]["status"] == "skipped_schedule"
    assert "chatgpt" not in seen
    assert not any(str(f).lower().startswith("chatgpt") for f in out["failures"])


def test_missing_openai_key_is_a_failure_only_on_scheduled_days(tmp_path, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "x")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)

    def ask_fn(model, prompt):
        return _probe_answer(model, prompt)

    (tmp_path / "tue").mkdir()
    (tmp_path / "mon").mkdir()
    skipped = mon.run_daily(str(tmp_path / "tue"), ask_fn=ask_fn, judge_fn=_judge_ok,
                            send_fn=lambda *a, **k: (True, "ok"), today="2026-11-03")
    assert skipped["scorecard"]["models"]["chatgpt"]["status"] == "skipped_schedule"
    assert not any("chatgpt" in f for f in skipped["failures"])

    scheduled = mon.run_daily(str(tmp_path / "mon"), ask_fn=ask_fn, judge_fn=_judge_ok,
                              send_fn=lambda *a, **k: (True, "ok"), today="2026-11-02")
    assert any(f == "chatgpt: no key" for f in scheduled["failures"])
    assert scheduled["scorecard"]["models"].get("chatgpt", {}).get("status") != "skipped_schedule"


def test_chatgpt_average_and_trend_ignore_skipped_days(tmp_path, monkeypatch):
    """Mon/Wed/Fri scores only. A Tuesday skip must not pull the mean down or zero the trend."""
    import aeo_probe
    monkeypatch.setenv("ANTHROPIC_API_KEY", "x")
    monkeypatch.setenv("OPENAI_API_KEY", "x")
    history = [
        {"date": "2026-10-30", "battery_version": "2026-08-30.1", "models": {
            "chatgpt": {"mention_rate_nonbranded": 99, "product_search": 99}}},  # outside the 7-day window
        {"date": "2026-11-02", "battery_version": "2026-08-30.1", "models": {
            "chatgpt": {"mention_rate_nonbranded": 10, "product_search": 40},
            "claude": {"mention_rate_nonbranded": 10, "product_search": 40}}},
        {"date": "2026-11-03", "battery_version": "2026-08-30.1", "models": {
            "chatgpt": {"status": "skipped_schedule", "reason": "not scheduled"},
            "claude": {"mention_rate_nonbranded": 10, "product_search": 40}}},
        {"date": "2026-11-04", "battery_version": "2026-08-30.1", "models": {
            "chatgpt": {"mention_rate_nonbranded": 30, "product_search": 40},
            "claude": {"mention_rate_nonbranded": 10, "product_search": 40}}},
    ]
    path = tmp_path / "seed"
    path.mkdir()
    (path / "aeo_daily_history.json").write_text(json.dumps(history), encoding="utf-8")
    called = []

    def ask_fn(model, prompt):
        called.append(model)
        return "Uproduction Events is mentioned here"

    out = mon.run_daily(str(path), ask_fn=ask_fn, judge_fn=_judge_ok,
                        send_fn=lambda *a, **k: (True, "ok"), today="2026-11-06")
    assert "chatgpt" in called
    stats = aeo_probe.seven_day_stats(
        json.loads((path / "aeo_daily_history.json").read_text()),
        "chatgpt", "mention_rate_nonbranded", "2026-11-06", battery_version="2026-08-30.1")
    # Friday's probe mentions the brand on every non-branded question → 100.
    # Skipped Tuesday and the out-of-window 99 are not in the mean: (10+30+100)/3.
    assert stats["days"] == 3
    assert stats["average"] == round((10 + 30 + 100) / 3, 1)
    assert out["trends"]["chatgpt"]["avg7_mention_days"] == 3
    assert out["trends"]["chatgpt"]["prev_date"] == "2026-11-04"
    assert out["trends"]["chatgpt"]["prev_product_search"] == 40
    claude = aeo_probe.seven_day_stats(
        json.loads((path / "aeo_daily_history.json").read_text()),
        "claude", "mention_rate_nonbranded", "2026-11-06", battery_version="2026-08-30.1")
    assert claude["days"] == 4  # Mon, Tue, Wed, Fri — Claude was not skipped


def test_legacy_history_stays_readable_beside_skipped_rows(tmp_path):
    import aeo_probe
    from scripts.council_source_evidence import unbranded_mention_rates
    legacy = {
        "date": "2026-11-02",
        "battery_version": "2026-08-30.1",
        "models": {
            "chatgpt": {"mention_rate_nonbranded": 12, "mentioned_nonbranded": 4,
                        "n_nonbranded": 32, "product_search": 40, "degraded": False, "answers": []},
            "claude": {"mention_rate_nonbranded": 20, "mentioned_nonbranded": 6,
                       "n_nonbranded": 32, "product_search": 40},
        },
        "errors": [],
    }
    path = tmp_path / "aeo_daily_history.json"
    aeo_probe.append_history(legacy, path)
    skipped = {
        "date": "2026-11-03",
        "battery_version": "2026-08-30.1",
        "models": {
            "chatgpt": aeo_probe.skipped_schedule_block(),
            "claude": {"mention_rate_nonbranded": 22, "mentioned_nonbranded": 7,
                       "n_nonbranded": 32, "product_search": 41},
        },
        "errors": [],
    }
    aeo_probe.append_history(skipped, path)
    loaded = json.loads(path.read_text(encoding="utf-8"))
    assert loaded[0]["models"]["chatgpt"]["mention_rate_nonbranded"] == 12
    assert "status" not in loaded[0]["models"]["chatgpt"]
    assert loaded[1]["models"]["chatgpt"]["status"] == "skipped_schedule"
    stats = aeo_probe.seven_day_stats(loaded, "chatgpt", "mention_rate_nonbranded", "2026-11-03")
    assert stats == {"average": 12.0, "days": 1}
    monday = unbranded_mention_rates(path, "2026-11-02")
    assert monday["by_engine"]["chatgpt"] == 12
    tuesday = unbranded_mention_rates(path, "2026-11-03")
    assert "chatgpt" not in tuesday["by_engine"]
    assert tuesday["by_engine"]["claude"] == 22
    # A stored rate on a skipped row must still be ignored, not averaged in as a zero.
    loaded[1]["models"]["chatgpt"]["mention_rate_nonbranded"] = 0
    assert aeo_probe.seven_day_stats(
        loaded, "chatgpt", "mention_rate_nonbranded", "2026-11-03")["days"] == 1


def test_openai_search_model_and_weekly_loop_are_unchanged():
    from pathlib import Path
    root = Path(__file__).resolve().parents[2]
    models = (root / "scripts" / "aeo_models.py").read_text(encoding="utf-8")
    weekly = (root / "scripts" / "aeo_run.py").read_text(encoding="utf-8")
    assert 'os.environ.get("AEO_OPENAI_SEARCH_MODEL") or "gpt-5.6"' in models
    assert "chatgpt_scheduled" not in weekly
    assert "skipped_schedule" not in weekly


def test_no_email_run_still_produces_reviewable_report(tmp_path, monkeypatch):
    monkeypatch.setattr(mon.aeo_models, 'available_models', lambda: ['claude'])
    monkeypatch.setattr(mon.aeo_probe, 'run_probe', lambda *a, **k: {'date': '2026-09-13', 'models': {}})
    monkeypatch.setattr(mon.aeo_competitor, 'research_keywords', lambda *a: {})
    def forbidden(*a, **kw):
        raise AssertionError('No email transport may be invoked')
    monkeypatch.setattr(mon.aeo_report, 'send', forbidden)
    out = mon.run_daily(history_dir=tmp_path, send_email=False, output_dir=tmp_path / 'report')
    assert out['email_sent'] is False
    assert (tmp_path / 'report' / 'daily-report.html').exists()
    assert json.loads((tmp_path / 'report' / 'daily-report.json').read_text())['scorecard']['date'] == '2026-09-13'
