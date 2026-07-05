"""Orchestrate the weekly AEO loop: probe -> gaps -> generate -> publish -> report."""
import os, sys, json, argparse, datetime
from pathlib import Path

import aeo_models, aeo_probe, aeo_gaps, aeo_generate, aeo_publish, aeo_report

ROOT = Path(__file__).resolve().parent
HISTORY = ROOT / "aeo_history.json"
TARGETS = json.loads((ROOT / "kpi_targets.json").read_text(encoding="utf-8"))["aeo_targets"]
QUESTIONS = json.loads((ROOT / "aeo_questions.json").read_text(encoding="utf-8"))["questions"]


def _prev_scorecard(history_path):
    p = Path(history_path)
    if p.exists():
        data = json.loads(p.read_text())
        if data:
            return data[-1]
    return None


def run(repo, dry_run, ask_fn=None, judge_fn=None, send_fn=None, runner=None, today=None, probe_fn=None):
    today = today or datetime.date.today().isoformat()
    # Probes ask with live web search (AEO_GROUNDED=0 reverts to training-data recall);
    # generation and judging stay ungrounded.
    grounded = os.environ.get("AEO_GROUNDED", "1") != "0"
    probe_fn = probe_fn or ask_fn or (lambda model, text: aeo_models.ask(model, text, grounded=grounded))
    ask_fn = ask_fn or (lambda model, text: aeo_models.ask(model, text))
    judge_fn = judge_fn or (lambda prompt: aeo_models.ask("claude", prompt, system=aeo_probe.JUDGE_SYSTEM))
    models = aeo_models.available_models() or ["claude"]
    failures = [f"{m}: no key" for m in ("chatgpt", "gemini") if m not in models]

    history_path = str(Path(repo) / "aeo_history.json") if dry_run else str(HISTORY)
    prev = _prev_scorecard(history_path)
    scorecard = aeo_probe.run_probe(QUESTIONS, models, probe_fn, judge_fn)
    failures.extend(scorecard.get("errors", []))
    aeo_probe.append_history(scorecard, history_path)

    briefs, deferred = aeo_gaps.briefs_with_overflow(scorecard, prev, TARGETS,
                                                     cap=TARGETS.get("briefs_per_run", 3))
    pages = []
    for brief in briefs:
        try:
            rendered = aeo_generate.render_brief(brief, ask_fn, today)
        except Exception as e:  # generation error for one brief must not kill the whole run
            failures.append(f"generation failed for {brief['type']} ({type(e).__name__}: {str(e)[:160]})")
            continue
        for page in rendered:
            if page["violations"]:
                failures.append(f"guard rejected {page['slug']}: {page['violations']}")
                continue
            pages.append(page)

    astro_repo = repo if dry_run else os.environ.get("ASTRO_REPO", "/Users/alonouanine/dev/uproduction-astro")
    pub_kwargs = {"dry_run": dry_run}
    if runner:
        pub_kwargs["runner"] = runner
    publish = aeo_publish.publish(astro_repo, pages, f"aeo/{today}", today, **pub_kwargs) if pages else \
        {"branch": None, "files": [], "pr_url": None, "dry_run": dry_run}

    shipped = [{"title": p["frontmatter"]["title"], "url": p["frontmatter"]["canonical"]} for p in pages]
    subject, html = aeo_report.build_email(scorecard, prev, shipped, deferred, failures, publish.get("pr_url"))
    email_sent = False
    if not dry_run or send_fn:
        ok, _ = aeo_report.send(subject, html, send_fn=send_fn)
        email_sent = bool(ok)

    return {"scorecard": scorecard, "briefs": briefs, "deferred": deferred,
            "pages": pages, "publish": publish, "email_sent": email_sent, "failures": failures}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    repo = os.environ.get("ASTRO_REPO", "/Users/alonouanine/dev/uproduction-astro")
    out = run(repo, dry_run=args.dry_run)
    sc = out["scorecard"]["models"]
    print(f"AEO run {datetime.date.today().isoformat()}: models={list(sc)} "
          f"briefs={len(out['briefs'])} pages={len(out['pages'])} "
          f"deferred={out['deferred']} email_sent={out['email_sent']}")
    for f in out.get("failures", []):
        print(f"  FAILURE: {f}")


if __name__ == "__main__":
    main()
