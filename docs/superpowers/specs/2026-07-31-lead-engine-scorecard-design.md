# Design: Lead Engine, Not Engagement Chase

**Date:** 2026-07-31
**Owner:** Alon Ouaknine (via UPE COO agent)
**Goal:** Break the marketing council out of its stuck 22/100 by measuring what actually
grows UPE (qualified leads + organic + AI visibility) instead of social vanity metrics,
and build three lead engines that a solo founder + AI can run — everything automated or
2-minute quick-approve.

---

## Problem

The daily Marketing Council has sat at ~22/100 for weeks despite producing 41 posts/week.
Root cause: **the scorecard measures the wrong thing.**

- `COUNCIL_PROMPT` GOALS (council.py) explicitly say *"Maximize impressions, raise engagement"*
  next to the lead KPI, so the LLM anchors the overall score on engagement rate
  (0.04% vs a 2.0% target) and impressions growth (−4.8% vs +10%) — both catastrophic-looking.
- `build_scorecard` grades `צמיחת חשיפות`, `Engagement rate`, `פוסטים/שבוע` as pass/fail
  with equal weight to leads.
- Meanwhile UPE's real data: **86% of leads = Word of Mouth**, Google Organic clicks
  +63% WoW, social = **0 attributed leads**. The converting machine exists; no social
  channel feeds it.

So the score punishes UPE for (correctly) not dumping resources into Israeli-B2B social
engagement, and will stay stuck no matter what content ships.

## Decisions locked (from brainstorming)

1. **Fix the definition of winning AND build a real engine** (not either/or).
2. **Execution model: Alon + AI only.** Everything is automated or quick-approve.
   "Employee advocacy from 3 managers" is off the table — all social goes through Alon's
   personal profile.
3. **Leads first, visibility as fuel.** Victory = 10 qualified leads/month (≥3 digital-
   attributed) + Top-3 on 5 Hebrew keywords + cited in AI answers.

---

## Part 1 — Redefine the scorecard

Reweight the headline score around business outcomes; demote vanity metrics to context.

**New weighting (target model):**

| Metric | Weight | 90-day target | Source |
|--------|-------:|---------------|--------|
| Qualified leads / month | 35% | 10 (now 7) | Salesforce (leads_source.py) |
| Digital-attributed leads / month | 20% | 3 (now 0) | attribution field (Part 3) |
| Organic clicks + Top-3 Hebrew keywords | 20% | 300/wk + 3 terms | GSC |
| AI visibility (AEO citations) | 15% | cited in 3 engines | AEO loop |
| Social presence (floor, not growth) | 10% | minimum-cadence met | Metricool |

**Removed as pass/fail toward the headline score:** engagement-rate target, weekly
impressions-growth target. They still render as an **informational context block** so the
number is visible without dragging the score.

**Code changes:**
- `scripts/kpi_targets.json` — add a `scorecard_weights` block and a `context_metrics`
  list (engagement_rate, impressions_growth) marked non-scoring; keep `effectiveness_targets`
  for display only.
- `scripts/council.py::build_scorecard` — compute a weighted 0-100 from the five weighted
  metrics; emit engagement/impressions in a separate `context` array (not counted in
  `passed/total`).
- `scripts/council.py::COUNCIL_PROMPT` GOALS — rewrite: PRIMARY = qualified + digital-
  attributed leads; SECONDARY = organic + AEO; engagement/impressions = "context only, do
  not let them dominate the overall score." Instruct the LLM to score `overall` from the
  weighted business model, not from engagement.

**Acceptance:** on the same input data that produced 22/100, the new model yields a score
that reflects lead/organic reality (expected 45-60), and the email shows engagement as
context rather than a red ❌ driving the headline.

## Part 2 — Three lead engines (Alon + AI only)

**Engine 1 · Google Organic quick-win** (fully autonomous — already have the article pipeline)
- 5 Hebrew landing/blog pages targeting the near-miss keywords where upe.co.il ranks 9–19:
  `הפקת נופש חברה` (pos ~9.2), `ארגון טיולים לחברות` (~9.4), `נופש חברה בארץ` (~18.9), +2.
- Each page: one case study, real ROI numbers, direct lead-capture CTA
  (`קבל הצעת מחיר לנופש חברה 2026`).
- Reuse `uproduction-astro/scripts/generate_article.py` + `article_topics.json` priority
  queue (seed these 5 terms at top). Build-gated → PR → auto-merge deploy.

**Engine 2 · Word-of-Mouth systematization** (AI drafts, Alon 2-min approve)
- On every closed project: auto-draft a testimonial request + a referral ask ("intro to 3
  colleagues"). Hebrew RTL HTML email via the send-email skill (Outlook path). Draft only.
- Turn the 6 existing WOM clients into documented case studies (text now, video later) →
  becomes SEO (Engine 1) + LinkedIn (Engine 3) fuel.

**Engine 3 · Alon's personal LinkedIn** (AI drafts, Alon approve — NOT company page)
- 3–4 posts/week from Alon's profile, Hebrew-first, proof-point / case-study driven.
- Feeds from the same bank pipeline but routed to the personal-profile account; content is
  thought-leadership, not promo.

**Kill list (stop spending here):**
- Facebook as a growth channel → 1/week maintenance only.
- Instagram over-posting → 4 quality Reels/week from existing real footage.
- Chasing engagement-rate as a target.
- Company-page LinkedIn as the primary voice (personal profile wins B2B reach).

These cadence caps already exist as council directives; the scorecard change (Part 1) stops
penalizing them.

## Part 3 — Attribution loop (closes the measurement gap)

- Add a `how did you hear about us?` capture on every intake / lead-capture form and to the
  Salesforce lead intake, with values that separate **direct WOM** from **digital-assisted
  WOM** (found us via a page/post, then a colleague confirmed).
- `leads_source.py` reads this to populate the "digital-attributed leads" metric (Part 1,
  20% weight). This is what proves the engine works and unlocks the 3 digital leads target.

---

## Out of scope (deliberately deferred)

- TikTok activation and YouTube long-form series — reach without leads today; they are AEO
  fuel for a later phase, not first-90-days lead engines.
- Paid ads (separate ₪5k/mo track already approved 16.07).
- Video quality upgrade (Sofia) — separate track.

## Rollout / safety

- All content stays approval-gated; nothing publishes without Alon.
- Scorecard change ships as one PR to upe-sp; verify against the last 7-day snapshot before
  merge (recompute old vs new score side by side).
- Engines 1–3 reuse existing pipelines; no new infrastructure.

## Success criteria (90 days)

1. Council overall score reflects business reality (leads/organic weighted), not engagement.
2. ≥10 qualified leads in a trailing 30-day window, ≥3 digital-attributed.
3. ≥3 Hebrew keywords in Top-3; organic clicks ≥300/week.
4. UPE cited in ≥3 AI engines for core queries.
