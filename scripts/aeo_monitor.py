"""Daily AEO visibility monitor: probe 3 models, compare to yesterday, research
competitor keywords (he+en) when the judge rubric score is below its target, email Alon. No content
generation — that stays in the weekly loop (aeo_run.py) so pages have time to index."""
import os, sys, json, argparse, datetime
from pathlib import Path

import aeo_models, aeo_probe, aeo_competitor, aeo_report

ROOT = Path(__file__).resolve().parent
DAILY_HISTORY = ROOT / "aeo_daily_history.json"
_ALL_QUESTIONS = json.loads((ROOT / "aeo_questions.json").read_text(encoding="utf-8"))["questions"]
# The daily tracker skips the branded questions. They name the company, so an engine can
# only read it back — they are guaranteed hits that cost API credit every single day and
# measure nothing. The weekly loop still asks them, on its own "brand recall" line.
QUESTIONS = [q for q in _ALL_QUESTIONS if q.get("segment") != "branded"]
TARGET = json.loads((ROOT / "kpi_targets.json").read_text(encoding="utf-8"))["aeo_targets"]["per_dimension_min"]["product_search"]


def _utc_today():
    return datetime.datetime.now(datetime.timezone.utc).date().isoformat()


def _load_history(history_path):
    p = Path(history_path)
    if not p.exists():
        return []
    try:
        data = json.loads(p.read_text())
    except (OSError, ValueError):
        return []
    return data if isinstance(data, list) else []


def _prev(history_path):
    data = _load_history(history_path)
    return data[-1] if data else None


def _meets_score_target(scorecard, target):
    """An internal rubric threshold, never evidence of first-place ranking.

    A model that was not scheduled did not miss the target.
    """
    models = [b for b in scorecard.get("models", {}).values() if aeo_probe.model_ran(b)]
    return bool(models) and all(
        not b.get("degraded") and b.get("product_search", 0) >= target
        for b in models
    )


def _trends(history, scorecard):
    """7-day means and the previous real run, per model. Skipped days are absent."""
    end = scorecard.get("date") or ""
    battery = scorecard.get("battery_version")
    trends = {}
    for model in ("claude", "chatgpt", "gemini"):
        prev_block, prev_date, prev_battery = aeo_probe.last_ran(history, model, end)
        same_battery = bool(battery) and prev_battery == battery
        mention = aeo_probe.seven_day_stats(
            history, model, "mention_rate_nonbranded", end, battery_version=battery)
        prominence = aeo_probe.seven_day_stats(
            history, model, "product_search", end, battery_version=battery)
        trends[model] = {
            "prev_date": prev_date if same_battery else None,
            "prev_product_search": prev_block.get("product_search") if same_battery and prev_block else None,
            "prev_mention_rate_nonbranded": (
                prev_block.get("mention_rate_nonbranded") if same_battery and prev_block else None),
            "avg7_mention_rate_nonbranded": mention["average"],
            "avg7_mention_days": mention["days"],
            "avg7_product_search": prominence["average"],
            "avg7_product_search_days": prominence["days"],
        }
    return trends


def run_daily(history_dir=None, ask_fn=None, judge_fn=None, send_fn=None, today=None, send_email=True, output_dir=None):
    today = today or _utc_today()
    # One daily cron (06:00 UTC). ChatGPT rides that run only on Mon/Wed/Fri.
    # Claude and Gemini stay on the same schedule every day. The weekday is the
    # UTC date of this run — not a second cron.
    chatgpt_today = aeo_probe.chatgpt_scheduled(today)
    # Probe with live web search like the weekly loop (AEO_GROUNDED=0 reverts).
    grounded = os.environ.get("AEO_GROUNDED", "1") != "0"
    ask_fn = ask_fn or (lambda model, text: aeo_models.ask_meta(model, text, grounded=grounded))
    history_path = str(Path(history_dir) / "aeo_daily_history.json") if history_dir else str(DAILY_HISTORY)

    keyed = aeo_models.available_models() or ["claude"]
    models = [m for m in keyed if m != "chatgpt" or chatgpt_today]
    failures = []
    for name in ("chatgpt", "gemini"):
        if name == "chatgpt" and not chatgpt_today:
            continue  # not scheduled — absence of a key is not an outage
        if name not in models:
            failures.append(f"{name}: no key")

    # The judge scores EVERY model's answers, so pinning it to one provider makes that
    # provider a single point of failure for the whole battery — on 31.07.2026 an empty
    # Anthropic balance produced an empty scorecard even though ChatGPT and Gemini had
    # answered. The weekly loop already falls through providers; the daily one did not.
    # ChatGPT is not in `models` off-schedule, so the judge cannot call OpenAI either.
    if judge_fn is None:
        order = [m for m in ("claude", "gemini", "chatgpt") if m in models] or ["claude"]

        def judge_fn(prompt):
            errors = []
            for m in order:
                try:
                    return aeo_models.ask(m, prompt, system=aeo_probe.JUDGE_SYSTEM)
                except Exception as e:
                    errors.append(f"{m}: {type(e).__name__}: {aeo_models.redact(str(e))[:120]}")
            raise RuntimeError("all judges failed — " + " | ".join(errors))

    prior = _load_history(history_path)
    prev = prior[-1] if prior else None
    scorecard = aeo_probe.run_probe(QUESTIONS, models, ask_fn, judge_fn, on_date=today)
    if not chatgpt_today:
        scorecard.setdefault("models", {})["chatgpt"] = aeo_probe.skipped_schedule_block()
        scorecard["errors"] = [e for e in scorecard.get("errors", [])
                               if not str(e).lower().startswith("chatgpt")]
    failures.extend(scorecard.get("errors", []))
    if not chatgpt_today:
        failures = [f for f in failures if not str(f).lower().startswith("chatgpt")]
    aeo_probe.append_history(scorecard, history_path)
    history = [row for row in prior if row.get("date") != scorecard.get("date")]
    history.append(scorecard)
    trends = _trends(history, scorecard)

    keywords = {"he": [], "en": [], "competitors": [], "priority_actions": []}
    measured = any(aeo_probe.model_ran(b) for b in scorecard.get("models", {}).values())
    if measured and not _meets_score_target(scorecard, TARGET):
        try:
            # strategist call is plain-text (no grounding needed); unwrap ask_meta dicts
            plain_fn = lambda model, text: (lambda r: r["text"] if isinstance(r, dict) else r)(ask_fn(model, text))
            keywords = aeo_competitor.research_keywords(scorecard, plain_fn)
        except Exception as e:
            failures.append(f"competitor research failed ({type(e).__name__}: {str(e)[:160]})")

    reminders = []
    try:
        import citations_pipeline
        reminders = citations_pipeline.overdue_reminders()
    except Exception:
        pass  # pipeline optional — reminders must never sink the daily email
    subject, html = aeo_report.build_daily_email(scorecard, prev, keywords, failures,
                                                 target=TARGET, reminders=reminders, trends=trends)
    if output_dir:
        folder = Path(output_dir)
        folder.mkdir(parents=True, exist_ok=True)
        (folder / 'daily-report.html').write_text(html, encoding='utf-8')
        (folder / 'daily-report.json').write_text(json.dumps(aeo_models.redact_obj({
            'scorecard': scorecard, 'keywords': keywords, 'failures': failures, 'trends': trends,
        }), ensure_ascii=False, indent=2), encoding='utf-8')
    ok = False
    if send_email:
        ok, _ = aeo_report.send(subject, html, send_fn=send_fn)
    return {"scorecard": scorecard, "keywords": keywords, "email_sent": bool(ok),
            "failures": failures, "trends": trends}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--send-email', action='store_true', help='Explicitly enable delivery')
    parser.add_argument('--output-dir')
    args = parser.parse_args()
    out = run_daily(send_email=args.send_email, output_dir=args.output_dir)
    sc = out["scorecard"]["models"]
    print(f"AEO daily {datetime.date.today().isoformat()}: models={list(sc)} "
          f"kw_he={len(out['keywords']['he'])} kw_en={len(out['keywords']['en'])} "
          f"email_sent={out['email_sent']}")
    for f in out.get("failures", []):
        print(f"  FAILURE: {f}")


if __name__ == "__main__":
    main()
