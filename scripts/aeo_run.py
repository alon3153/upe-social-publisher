"""Orchestrate the weekly AEO loop: probe -> gaps -> generate -> publish -> report."""
import os, sys, json, argparse, datetime
from pathlib import Path

import aeo_models, aeo_probe, aeo_gaps, aeo_generate, aeo_guards, aeo_publish, aeo_report
import aeo_intents
import citations_pipeline
import held_pages
import indexnow_ping

ROOT = Path(__file__).resolve().parent
HISTORY = ROOT / "aeo_history.json"
TARGETS = json.loads((ROOT / "kpi_targets.json").read_text(encoding="utf-8"))["aeo_targets"]
_QDOC = json.loads((ROOT / "aeo_questions.json").read_text(encoding="utf-8"))
QUESTIONS = _QDOC["questions"]
SEGMENT_WEIGHTS = _QDOC.get("segment_weights") or aeo_gaps.DEFAULT_WEIGHTS


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
    probe_fn = probe_fn or ask_fn or (lambda model, text: aeo_models.ask_meta(model, text, grounded=grounded))
    ask_fn = ask_fn or (lambda model, text: aeo_models.ask(model, text))
    models = aeo_models.available_models() or ["claude"]
    failures = [f"{m}: no key" for m in ("chatgpt", "gemini") if m not in models]
    # The judge scores EVERY model's answers, so pinning it to one provider made that
    # provider a single point of failure for the whole battery: on 31.07.2026 the
    # Anthropic balance ran dry and the run returned an empty scorecard even though the
    # working ChatGPT and Gemini keys had answered. Fall through the other available
    # providers instead, and surface which one actually did the judging.
    judge_order = [m for m in ("claude", "gemini", "chatgpt") if m in models] or ["claude"]

    def _judge(prompt):
        errors = []
        for m in judge_order:
            try:
                return aeo_models.ask(m, prompt, system=aeo_probe.JUDGE_SYSTEM)
            except Exception as e:
                errors.append(f"{m}: {type(e).__name__}: {str(e)[:120]}")
        raise RuntimeError("all judges failed — " + " | ".join(errors))

    judge_fn = judge_fn or _judge

    history_path = str(Path(repo) / "aeo_history.json") if dry_run else str(HISTORY)
    prev = _prev_scorecard(history_path)
    scorecard = aeo_probe.run_probe(QUESTIONS, models, probe_fn, judge_fn)
    failures.extend(scorecard.get("errors", []))
    aeo_probe.append_history(scorecard, history_path)

    # Filter the backlog BEFORE calling the model: an intent that already has a live page,
    # or that the founder vetoed, must not be regenerated. Previously the veto was checked
    # only after generation, so a permanently-blocked topic was rewritten in full every
    # week and thrown away — invisible from both ends, and paid for every time.
    covered = aeo_intents.covered()
    vetoed = held_pages.vetoed_intents()
    briefs, deferred = aeo_gaps.briefs_with_overflow(
        scorecard, TARGETS, covered=covered, vetoed=vetoed,
        cap=TARGETS.get("briefs_per_run", 3), weights=SEGMENT_WEIGHTS)

    # Citation gate (council decision 05.07): marginal value of another self-published
    # page is ~0 until third-party corroboration exists. Verify the external pipeline,
    # and pause on-site generation while verified citations < 3 — the weekly email
    # carries the approval digest + outreach targets instead.
    citations_status = ""
    try:
        # verify() crawls the live web; a dry run must not do network side effects
        advanced = citations_pipeline.verify() if not dry_run else []
        if advanced:
            failures.append("citations advanced: " + ", ".join(advanced))  # informational
        citations_status = citations_pipeline.digest_html()
        if citations_pipeline.verified_count() < 3:
            briefs, deferred = [], deferred + len(briefs)
    except FileNotFoundError:
        pass  # no pipeline state — behave as before

    pages = []
    held_now = []
    comparative = []
    for brief in briefs:
        try:
            rendered = aeo_generate.render_brief(brief, ask_fn, today)
        except Exception as e:  # generation error for one brief must not kill the whole run
            failures.append(f"generation failed for {brief['type']} ({type(e).__name__}: {str(e)[:160]})")
            continue
        for page in rendered:
            body = page.get("body", "")
            page.setdefault("intent", brief.get("intent"))
            page.setdefault("lang", brief.get("lang", ""))
            problems = list(page["violations"])
            problems += aeo_guards.sourcing_violations(body)
            comp = aeo_guards.names_competitor(body)
            if comp:
                # Founder decision 30.08: a roster page naming competitors is allowed when
                # it is structurally neutral. It is rejected — not silently held — when it
                # is not, because a held page was never actually reviewed.
                page["_competitors"] = comp
                problems += aeo_guards.comparative_violations(body, comp)
            if problems:
                failures.append(f"guard rejected {page['slug']}: {problems}")
                continue
            if comp:
                comparative.append({"slug": page["slug"], "competitors": comp})
            pages.append(page)

    # Founder-veto window (council 05.07): persist newly-held competitor-naming
    # pages instead of discarding them, and merge any prior-held page whose 24h
    # window has elapsed and that Alon did not veto. The weekly email surfaces
    # what's held + when it will merge.
    merged_from_hold = []
    if not dry_run:
        held_pages.hold(held_now, today)
        merged_from_hold = held_pages.due_for_merge(today)
        pages.extend(merged_from_hold)
    citations_status += held_pages.digest_html(today)

    astro_repo = repo if dry_run else os.environ.get("ASTRO_REPO", "/Users/alonouanine/dev/uproduction-astro")
    pub_kwargs = {"dry_run": dry_run}
    if runner:
        pub_kwargs["runner"] = runner
    publish = aeo_publish.publish(astro_repo, pages, f"aeo/{today}", today, **pub_kwargs) if pages else \
        {"branch": None, "files": [], "pr_url": None, "dry_run": dry_run}
    if merged_from_hold and not dry_run and (publish.get("pr_url") or publish.get("files")):
        held_pages.release([p["slug"] for p in merged_from_hold])

    shipped = [{"title": p["frontmatter"]["title"], "url": p["frontmatter"]["canonical"]} for p in pages]

    # Record intents, then confirm the URLs actually resolve. Opening a PR is not
    # publishing: PRs #99/#108/#112 were closed unmerged and #120 failed its build, yet
    # four weekly emails reported those pages as shipped and IndexNow was pinged for URLs
    # that 404. Only verified-live URLs are reported or pinged.
    not_live = []
    if pages and not dry_run:
        aeo_intents.record(pages, today)
        _, dead, _unknown = aeo_intents.verify(today)
        if dead:
            failures.append("intents whose page is no longer live (will be re-briefed): "
                            + ", ".join(dead))
        shipped, not_live = aeo_intents.filter_live(shipped)
        for s_ in not_live:
            failures.append(f"reported-but-not-live (NOT counted as published): {s_['url']}")
    if shipped and not dry_run:
        try:
            indexnow_ping.ping([s["url"] for s in shipped])
        except Exception as e:
            failures.append(f"indexnow ping failed ({type(e).__name__})")
    subject, html = aeo_report.build_email(scorecard, prev, shipped, deferred, failures,
                                           publish.get("pr_url"), citations_status=citations_status,
                                           not_live=not_live, comparative=comparative)
    email_sent = False
    if not dry_run or send_fn:
        ok, _ = aeo_report.send(subject, html, send_fn=send_fn)
        email_sent = bool(ok)

    return {"scorecard": scorecard, "briefs": briefs, "deferred": deferred,
            "pages": pages, "publish": publish, "email_sent": email_sent,
            "comparative": comparative, "shipped": shipped, "not_live": not_live,
            "failures": failures}


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
