# AEO/GEO Closed-Loop Engine — Design Spec

**Date:** 2026-06-28
**Owner:** Alon Ouaknine (UPE) · built by UPE agent
**Source trigger:** Open-Finance.ai AEO report (2026-06-28) for uproduction events
**Repos touched:** `upe-sp` (engine) · `uproduction-astro` (content target)

---

## 1. Problem

The AEO report scored UPE's visibility across three answer engines on three dimensions:

| Model | AEO | Product search | Comparison | Reputation |
|-------|-----|----------------|-----------|------------|
| Claude | 64 | 70 | **40** | 100 |
| ChatGPT | 76 | **40** | 100 | 100 |
| Gemini | 76 | **40** | 100 | 100 |

**Diagnosis (from the numbers, not the headlines):**
- **Reputation = 100 everywhere** → brand-name recall is solved. Strong base.
- **Product search = 40 on ChatGPT/Gemini** → on *category* queries ("leading conference production company") with no brand name, UPE does **not** surface; competitors (BCD, Maritz, GL events) do.
- **Comparison = 40 on Claude** → Claude can't tell *when* to recommend UPE over an alternative.

All six report recommendations converge on one root cause: **missing non-branded content that matches how clients actually search** — category guides, comparison pages, "who is this for", and a trust layer. The infrastructure to host this already exists in `uproduction-astro`; what's missing is (a) the content itself and (b) a measure→generate→remeasure loop that targets the real gaps.

## 2. Goal & Success Criteria

**Goal:** A self-running weekly loop that raises UPE's AEO scores — especially Product-search (ChatGPT/Gemini) and Comparison (Claude) — by generating exactly the pages that close measured visibility gaps.

**Success criteria:**
- Each weekly run produces: a fresh scorecard, N shipped content pages, and an RTL summary email.
- Scorecard trend is upward over rolling 4-week windows on the two weak dimensions.
- Zero manual steps in steady state (full autonomy + summary email — confirmed by owner).
- No content violates the canonical-facts rule or the no-event-dates rule.

**Non-goals (YAGNI):**
- Not reproducing Open-Finance.ai's exact scoring algorithm — we build our own equivalent 3-dimension probe.
- No paid-ads, social, or off-page link-building in this loop (separate systems already exist).
- No new website templates — reuse existing `blog` / `services` collections and their layouts.

## 3. Architecture — 5 Components

All engine code lives in `upe-sp/scripts/aeo/`. Content output lands in `uproduction-astro`.

### 3.1 `aeo_probe.py` — Measurement engine
- Asks a fixed battery of **~18 category/comparison questions** (no brand name) — e.g. "Who are the best corporate event production companies in the world?", "Best agency for incentive travel?", "חברת הפקת כנסים מובילה". Battery stored in `aeo/questions.json` (versioned; changes invalidate trend comparisons, so the file carries a `battery_version`).
- Scores **3 dimensions per model**, mirroring the report: `product_search` (does UPE appear unprompted, at what rank), `comparison` (when asked to compare/choose, is UPE positioned correctly), `reputation` (brand-name recall).
- **Model adapters are pluggable.** Start: **Claude only** (`ANTHROPIC_API_KEY` exists in CI). OpenAI + Gemini adapters are written but gated behind presence of `OPENAI_API_KEY` / `GEMINI_API_KEY`; absent key → that model is skipped and marked `n/a` in the scorecard, never blocks the run.
- Scoring is itself done by an LLM judge (Claude) reading each answer against a rubric, returning structured JSON (0–100 per dimension + which competitors outranked UPE + a one-line gap note).
- Appends a timestamped record to `aeo/aeo_history.json`.

### 3.2 Gap analyzer (`aeo_gaps.py`)
- Reads the latest scorecard + previous run + `kpi_targets.json` (extended with AEO targets).
- For each weak answer, extracts: the question, which competitors beat UPE, and *what page would have closed it*.
- Emits a **prioritized brief list** (`aeo/briefs/<date>.json`): each brief = `{type, topic, target_dimension, lang_set, why, competitors_to_beat}`. Priority = (dimension gap size) × (query frequency weight). Caps at **N briefs/run** (default 3) to protect content quality — overflow carries to next week. `log()`-equivalent records what was deferred (no silent truncation).

### 3.3 Content generator (`aeo_generate.py`)
- For each brief, generates the right page type, in the brief's `lang_set` (he/en/es), as markdown matching the existing collection schema:
  - **Category guide** → `blog` collection, non-branded title matching real search phrasing, with `faqs` (→ FAQPage JSON-LD).
  - **Comparison page** → `services` or `blog`, includes "who is this for", pros/cons table, use-case scenarios vs named alternatives, `schemaType` set appropriately.
  - **Trust/solution page** → `services` collection (audience-segment solution pages, client proofs, expanded FAQ).
- Every generated file: sets `canonical`, `translationKey` (shared across the 3 langs for reciprocal hreflang), `llmsDescription`, `datePublished`/`dateModified` = run date.
- **Hard content guards** (generator refuses output that fails):
  - Canonical facts only: 2010 / 16yr / 1,500+ events / 130+ destinations / 25K+ participants. No 200+/2000/27yr.
  - No event dates (no year an event took place — case studies read timeless).
  - Hebrew RTL correctness for `he` files.

### 3.4 Publisher (`aeo_publish.py`)
- Writes files into a fresh `uproduction-astro` worktree, commits specific files (defends against the background guardian that resets the tree), pushes a feature branch, opens a PR.
- **Full autonomy:** relies on the existing astro auto-merge guardian — PR auto-merges once the Vercel build passes → live. No human gate (per owner decision).
- If build fails, the PR stays open and the failure is surfaced in the email (not silently dropped). Retry next run.

### 3.5 Reporter (`aeo_report.py`)
- After each run, sends one **RTL Hebrew summary email** via the existing MS Graph mailer (`MS_GRAPH_*` secrets, from alon@upe.co.il):
  - Scorecard table with **delta vs last week** per model/dimension.
  - What shipped this run (page titles + live URLs once merged).
  - What's queued for next week (deferred briefs).
  - Any failures (build failed / model skipped for missing key).
- HTML body wrapped `<html dir="rtl" lang="he">` per UPE RTL rules; LTR tokens (URLs) isolated.

## 4. Data Flow (one weekly iteration)

```
aeo_probe  → scorecard + aeo_history.json
   ↓
aeo_gaps   → prioritized briefs (≤N)
   ↓
aeo_generate → markdown pages (he/en/es), guards enforced
   ↓
aeo_publish → branch → PR → auto-merge → live
   ↓
aeo_report → RTL summary email (scorecard delta + shipped + queued + failures)
```

A thin `aeo_run.py` orchestrates the five steps and is the single entry point.

## 5. Orchestration & Cadence

- **Steady state:** GitHub Action cron in `upe-sp`, weekly (`aeo-loop.yml`), modeled on `daily-council.yml`. Reuses existing secrets (`ANTHROPIC_API_KEY`, `GH_PAT`, `MS_GRAPH_*`). Runs even when the laptop is off.
- **Build/first-run:** driven now via `/loop` self-paced — the agent runs `aeo_run.py` live to validate the first real iteration end-to-end, then commits the `aeo-loop.yml` cron to make it standing.
- Weekly cadence chosen so generated content has time to be indexed/ingested by the answer engines before re-measuring (daily would measure noise and dilute quality).

## 6. Error Handling

| Failure | Behavior |
|---------|----------|
| Model API key missing | Skip that model, mark `n/a`, continue. Never block. |
| LLM judge returns unparseable JSON | Retry once with stricter instruction; on 2nd failure, record raw + flag in email. |
| Astro build fails | PR left open, failure reported in email, retried next run. |
| Guardian resets worktree | Commit specific files immediately post-write; verify with `git show HEAD:<path>`. |
| Content guard rejects (bad facts/dates) | Regenerate once with the violation called out; if still failing, drop that brief and report it. |

## 7. Testing

- **Probe:** unit-test the scorer against 2–3 canned model answers (UPE present / absent / mid-rank) → expected dimension scores.
- **Generator guards:** unit-test that a draft containing "200+ events" or an event year is rejected.
- **Dry-run mode:** `aeo_run.py --dry-run` runs probe + gaps + generate but writes to a scratch dir and skips PR/email — used for the first live validation under `/loop`.
- **First real run** is the integration test: one brief, one page, one PR, one email — verified by Alon before the cron is enabled.

## 8. Open Constraints

- **OpenAI + Gemini measurement** is dark until keys are supplied. Until then the scorecard shows Claude only; the report email notes the two models as `n/a (no key)`. Adding the secrets later turns them on with no code change.
- Local `/loop` dev runs need `ANTHROPIC_API_KEY` available to the shell (currently CI-only). First step of implementation confirms/loads the key locally or runs the first iteration via a manual workflow dispatch instead.

## 9. Out-of-Repo Dependencies (reused, not built)

- MS Graph mailer (UPE Social Approval Mailer app) — for `aeo_report`.
- astro content collections `blog` / `services` + their FAQPage/Article JSON-LD emission.
- astro auto-merge guardian — provides the "full autonomy" publish path.
