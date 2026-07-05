"""Daily AEO #1-tracking monitor: probe 3 models, compare to yesterday, research
competitor keywords (he+en) when UPE is not the #1 answer, email Alon. No content
generation — that stays in the weekly loop (aeo_run.py) so pages have time to index."""
import os, sys, json, argparse, datetime
from pathlib import Path

import aeo_models, aeo_probe, aeo_competitor, aeo_report

ROOT = Path(__file__).resolve().parent
DAILY_HISTORY = ROOT / "aeo_daily_history.json"
QUESTIONS = json.loads((ROOT / "aeo_questions.json").read_text(encoding="utf-8"))["questions"]
TARGET = json.loads((ROOT / "kpi_targets.json").read_text(encoding="utf-8"))["aeo_targets"]["per_dimension_min"]["product_search"]


def _prev(history_path):
    p = Path(history_path)
    if p.exists():
        data = json.loads(p.read_text())
        if data:
            return data[-1]
    return None


def _is_number_one(scorecard, target):
    models = scorecard.get("models", {})
    return bool(models) and all(b.get("product_search", 0) >= target for b in models.values())


def run_daily(history_dir=None, ask_fn=None, judge_fn=None, send_fn=None, today=None):
    today = today or datetime.date.today().isoformat()
    # Probe with live web search like the weekly loop (AEO_GROUNDED=0 reverts).
    grounded = os.environ.get("AEO_GROUNDED", "1") != "0"
    ask_fn = ask_fn or (lambda model, text: aeo_models.ask_meta(model, text, grounded=grounded))
    judge_fn = judge_fn or (lambda prompt: aeo_models.ask("claude", prompt, system=aeo_probe.JUDGE_SYSTEM))
    history_path = str(Path(history_dir) / "aeo_daily_history.json") if history_dir else str(DAILY_HISTORY)

    models = aeo_models.available_models() or ["claude"]
    failures = [f"{m}: no key" for m in ("chatgpt", "gemini") if m not in models]

    prev = _prev(history_path)
    scorecard = aeo_probe.run_probe(QUESTIONS, models, ask_fn, judge_fn)
    failures.extend(scorecard.get("errors", []))
    aeo_probe.append_history(scorecard, history_path)

    keywords = {"he": [], "en": [], "competitors": [], "priority_actions": []}
    if not _is_number_one(scorecard, TARGET):
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
                                                 target=TARGET, reminders=reminders)
    ok, _ = aeo_report.send(subject, html, send_fn=send_fn)
    return {"scorecard": scorecard, "keywords": keywords, "email_sent": bool(ok), "failures": failures}


def main():
    argparse.ArgumentParser().parse_args()
    out = run_daily()
    sc = out["scorecard"]["models"]
    print(f"AEO daily {datetime.date.today().isoformat()}: models={list(sc)} "
          f"kw_he={len(out['keywords']['he'])} kw_en={len(out['keywords']['en'])} "
          f"email_sent={out['email_sent']}")
    for f in out.get("failures", []):
        print(f"  FAILURE: {f}")


if __name__ == "__main__":
    main()
