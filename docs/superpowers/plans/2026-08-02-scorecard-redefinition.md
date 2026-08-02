# Scorecard Redefinition Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the erratic LLM-produced overall council score with a deterministic, weighted 0-100 score anchored on business outcomes (qualified + digital-attributed leads, organic, AEO), so the council stops being dragged to ~22/100 by social vanity metrics.

**Architecture:** Add a pure, unit-testable `weighted_score()` to `scripts/council.py` that scores five business metrics with weights from `kpi_targets.json`. `build_scorecard` computes it, splits its rows into **scored** vs **context** (engagement/impressions become non-scoring context), and derives digital-attributed leads from the existing `leads.by_source` Salesforce breakdown. The email/markdown headline uses this deterministic number; the LLM's own `overall` is demoted to a secondary "council read". The `COUNCIL_PROMPT` GOALS are rewritten so the LLM's qualitative verdict stops treating engagement as the headline failure.

**Tech Stack:** Python 3.11 (stdlib only — no new deps), pytest for tests, existing `leads_source.py` (Salesforce REST) and `seo_geo_source.py` (GSC/GEO snapshot) data sources.

## Global Constraints

- Python stdlib only in `council.py` scoring — no new runtime dependencies (matches repo pattern).
- Every data source degrades gracefully: if `leads.ok` / `seo_geo.ok` is False, the corresponding weighted component scores as **unavailable** and its weight is redistributed across available components — NEVER fabricate a number, NEVER hard-fail (the council daemon "always exits 0").
- The deterministic score is the headline; the LLM `scores.overall` is shown as a secondary "council read", never the headline.
- Weights must sum to 100; a test enforces this.
- Hebrew RTL email rules apply to any new rendered rows (`dir="rtl"`, LTR numbers wrapped) — see CLAUDE.md.
- No change publishes anything or touches Salesforce/live channels — this is read + score + render only.

---

## File Structure

- `scripts/kpi_targets.json` (modify) — add `scorecard_weights`, `digital_lead_sources`, `word_of_mouth_sources`, `organic_targets`, `context_metrics`.
- `scripts/council.py` (modify) — add `weighted_score()` + `digital_attributed_leads()` helpers; rewrite `build_scorecard` to emit `{scored_rows, context_rows, weighted, passed, total, ...}`; update `render_html`/`render_md` headline + context block; rewrite `COUNCIL_PROMPT` GOALS.
- `tests/test_scorecard.py` (create) — unit tests for the pure scoring helpers.

---

## Task 1: Weights + source config in kpi_targets.json

**Files:**
- Modify: `scripts/kpi_targets.json`
- Test: `tests/test_scorecard.py`

**Interfaces:**
- Produces: a `scorecard_weights` dict (keys: `qualified_leads`, `digital_leads`, `organic`, `aeo`, `social_presence`; integer percentages summing to 100), `digital_lead_sources` (list[str]), `word_of_mouth_sources` (list[str]), `organic_targets` (`weekly_clicks_min`, `top3_keywords_min`), consumed by Task 2/3 helpers.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_scorecard.py
import json, pathlib
ROOT = pathlib.Path(__file__).resolve().parent.parent

def test_weights_present_and_sum_to_100():
    t = json.loads((ROOT / "scripts" / "kpi_targets.json").read_text())
    w = t["scorecard_weights"]
    assert set(w) == {"qualified_leads", "digital_leads", "organic", "aeo", "social_presence"}
    assert sum(w.values()) == 100

def test_source_buckets_present():
    t = json.loads((ROOT / "scripts" / "kpi_targets.json").read_text())
    assert "Word of mouth" in t["word_of_mouth_sources"]
    assert "Web" in t["digital_lead_sources"]
    assert t["organic_targets"]["weekly_clicks_min"] > 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ~/dev/upe-sp && python3 -m pytest tests/test_scorecard.py -v` (install first if needed: `pip install pytest`)
Expected: FAIL with `KeyError: 'scorecard_weights'`

- [ ] **Step 3: Add the config to `scripts/kpi_targets.json`**

Add these top-level keys (keep existing keys intact):

```json
  "scorecard_weights": {
    "qualified_leads": 35,
    "digital_leads": 20,
    "organic": 20,
    "aeo": 15,
    "social_presence": 10
  },
  "digital_lead_sources": ["Web", "Website", "LinkedIn", "Google", "Organic Search", "Social", "Paid Search", "Email"],
  "word_of_mouth_sources": ["Word of mouth", "Referral", "Existing Client", "Partner"],
  "organic_targets": { "weekly_clicks_min": 300, "top3_keywords_min": 3 },
  "context_metrics": {
    "_comment": "Shown for visibility, NOT scored. Engagement/impressions no longer drag the headline.",
    "engagement_rate_pct": 2.0,
    "weekly_impressions_growth_pct": 10
  }
```

Also update the stale `primary_kpi.leads_source` string from `"UNWIRED — ..."` to `"WIRED via leads_source.py (Salesforce client-credentials); Opportunity CreatedDate LAST_N_DAYS."`.

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_scorecard.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add scripts/kpi_targets.json tests/test_scorecard.py
git commit -m "feat(council): scorecard weights + lead-source buckets in kpi_targets"
```

---

## Task 2: `digital_attributed_leads()` helper

**Files:**
- Modify: `scripts/council.py` (add helper near `build_scorecard`, after line 50)
- Test: `tests/test_scorecard.py`

**Interfaces:**
- Consumes: `leads` dict from `leads_source.count()` (has `by_source: dict[str,int]`, `ok: bool`), and the `digital_lead_sources` list from `kpi_targets.json` (via module `TARGETS`).
- Produces: `digital_attributed_leads(leads, digital_sources) -> int` — count of opportunities whose `LeadSource` is in `digital_sources` (case-insensitive match). Returns 0 when `by_source` empty.

- [ ] **Step 1: Write the failing test**

```python
from scripts import council  # council.py is importable (scripts/ on sys.path in council)
# If direct import fails, use importlib as in existing tests/conftest.py.

def test_digital_attributed_counts_only_digital():
    leads = {"ok": True, "by_source": {"Web": 3, "Word of mouth": 5, "LinkedIn": 2, "(none)": 1}}
    ds = ["Web", "LinkedIn", "Google"]
    assert council.digital_attributed_leads(leads, ds) == 5  # 3 Web + 2 LinkedIn

def test_digital_attributed_case_insensitive_and_empty():
    assert council.digital_attributed_leads({"ok": True, "by_source": {"web": 4}}, ["Web"]) == 4
    assert council.digital_attributed_leads({"ok": False}, ["Web"]) == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_scorecard.py::test_digital_attributed_counts_only_digital -v`
Expected: FAIL with `AttributeError: module 'council' has no attribute 'digital_attributed_leads'`

- [ ] **Step 3: Implement the helper in `scripts/council.py`**

```python
def digital_attributed_leads(leads, digital_sources):
    """Count opportunities whose LeadSource is a digital channel (case-insensitive).
    Digital = not Word-of-Mouth. Proves the digital engine converts (spec Part 3 metric,
    computable today from Salesforce by_source without a new form field)."""
    by_source = (leads or {}).get("by_source") or {}
    wanted = {s.lower() for s in digital_sources}
    return sum(n for src, n in by_source.items() if str(src).lower() in wanted)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_scorecard.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add scripts/council.py tests/test_scorecard.py
git commit -m "feat(council): digital_attributed_leads from Salesforce by_source"
```

---

## Task 3: `weighted_score()` — deterministic 0-100

**Files:**
- Modify: `scripts/council.py` (add helper after `digital_attributed_leads`)
- Test: `tests/test_scorecard.py`

**Interfaces:**
- Consumes: a `components` dict mapping each weight key to either a float in `[0,1]` (fraction of target achieved, capped at 1.0) or `None` (unavailable). Weight keys: `qualified_leads`, `digital_leads`, `organic`, `aeo`, `social_presence`. Also the `scorecard_weights` dict.
- Produces: `weighted_score(components, weights) -> int` in `[0,100]`. `None` components are dropped and the remaining weights are renormalized over available components. If ALL components are None, returns 0.

- [ ] **Step 1: Write the failing test**

```python
def test_weighted_score_full_and_renormalize():
    w = {"qualified_leads": 35, "digital_leads": 20, "organic": 20, "aeo": 15, "social_presence": 10}
    # all targets fully met -> 100
    full = {k: 1.0 for k in w}
    assert council.weighted_score(full, w) == 100
    # half on everything -> 50
    half = {k: 0.5 for k in w}
    assert council.weighted_score(half, w) == 50
    # unavailable aeo+organic renormalize over the rest (fractions still 0.5) -> 50
    part = {"qualified_leads": 0.5, "digital_leads": 0.5, "organic": None, "aeo": None, "social_presence": 0.5}
    assert council.weighted_score(part, w) == 50

def test_weighted_score_caps_and_all_none():
    w = {"qualified_leads": 35, "digital_leads": 20, "organic": 20, "aeo": 15, "social_presence": 10}
    over = {k: 2.0 for k in w}  # over-achievement capped at 1.0
    assert council.weighted_score(over, w) == 100
    assert council.weighted_score({k: None for k in w}, w) == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_scorecard.py::test_weighted_score_full_and_renormalize -v`
Expected: FAIL with `AttributeError: ... 'weighted_score'`

- [ ] **Step 3: Implement the helper in `scripts/council.py`**

```python
def weighted_score(components, weights):
    """Deterministic 0-100. components[k] is a fraction-of-target in [0,1] or None
    (unavailable). Unavailable components are dropped and their weight is renormalized
    over what IS available, so a missing data source lowers confidence, not the score."""
    avail = {k: max(0.0, min(1.0, v)) for k, v in components.items() if v is not None}
    wsum = sum(weights[k] for k in avail)
    if not wsum:
        return 0
    return round(sum(weights[k] * avail[k] for k in avail) / wsum * 100)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_scorecard.py -v`
Expected: PASS (6 tests)

- [ ] **Step 5: Commit**

```bash
git add scripts/council.py tests/test_scorecard.py
git commit -m "feat(council): deterministic weighted_score with graceful renormalization"
```

---

## Task 4: Wire weighted score into `build_scorecard`

**Files:**
- Modify: `scripts/council.py:51-96` (`build_scorecard`)
- Test: `tests/test_scorecard.py`

**Interfaces:**
- Consumes: `cur` (has `totals.impressions`, `totals.engagement_rate_pct`, `totals.posts`, `period_days`), `prev`, `leads`, and now `seo_geo` (dict from `seo_geo_source.fetch()`, keys read defensively: `weekly_clicks`, `top3_keywords`, `aeo_cited_engines`). Reads `TARGETS["scorecard_weights"]`, `TARGETS["digital_lead_sources"]`, `TARGETS["organic_targets"]`, `TARGETS["primary_kpi"]`.
- Produces: adds `weighted` (int 0-100), `components` (dict of fraction/None), and splits rows into `scored_rows` (leads/digital/organic/aeo/social) and `context_rows` (engagement, impressions-growth). Keeps `rows`, `passed`, `total` for backward compat (rows = scored_rows + context_rows; passed/total counts scored_rows only).

- [ ] **Step 1: Write the failing test**

```python
def test_build_scorecard_weighted_present_and_context_split():
    cur = {"totals": {"impressions": 14000, "engagement_rate_pct": 0.04, "posts": 41}, "period_days": 7,
           "networks": {}}
    prev = {"totals": {"impressions": 14700}}
    leads = {"ok": True, "qualified_leads": 7, "new_opportunities": 7,
             "by_source": {"Word of mouth": 6, "Web": 1}, "dominant_source": "Word of mouth",
             "dominant_share_pct": 86, "attribution_gap": False}
    seo_geo = {"ok": True, "weekly_clicks": 145, "top3_keywords": 0, "aeo_cited_engines": 1}
    sc = council.build_scorecard(cur, prev, leads, seo_geo)
    assert 0 <= sc["weighted"] <= 100
    # engagement + impressions-growth must be CONTEXT, not scored
    scored_labels = " ".join(r["metric"] for r in sc["scored_rows"])
    context_labels = " ".join(r["metric"] for r in sc["context_rows"])
    assert "Engagement" in context_labels and "Engagement" not in scored_labels
    assert "צמיחת חשיפות" in context_labels
    # with 7/10 leads, 1 digital, weak organic/aeo — weighted should be well above the old 22
    assert sc["weighted"] >= 30
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_scorecard.py::test_build_scorecard_weighted_present_and_context_split -v`
Expected: FAIL — `build_scorecard` takes 3 args / has no `weighted` key.

- [ ] **Step 3: Implement**

Change the signature to `build_scorecard(cur, prev, leads, seo_geo=None)`. Keep the existing `grade()` helper but tag each row. Build components and split rows:

```python
def build_scorecard(cur, prev, leads, seo_geo=None):
    t = TARGETS["effectiveness_targets"]
    W = TARGETS["scorecard_weights"]
    org_t = TARGETS["organic_targets"]
    lead_target = TARGETS["primary_kpi"]["qualified_leads_per_month"]
    ct, pt = cur["totals"], prev["totals"]
    scored, context = [], []

    def row(bucket, label, value, target, ok, unit=""):
        bucket.append({"metric": label, "value": value, "target": target,
                       "unit": unit, "status": "✅" if ok else "❌"})

    comp = {}

    # 1) qualified leads (scored)
    if leads.get("ok"):
        ql = leads.get("qualified_leads") or 0
        comp["qualified_leads"] = ql / lead_target if lead_target else None
        row(scored, "לידים מוסמכים (30 ימים)", ql, lead_target, ql >= lead_target)
    else:
        comp["qualified_leads"] = None
        row(scored, "לידים מוסמכים/חודש", "לא מחובר", lead_target, False)

    # 2) digital-attributed leads (scored) — target = 3 of the 10
    dig_target = max(1, round(lead_target * 0.3))
    if leads.get("ok"):
        dl = digital_attributed_leads(leads, TARGETS["digital_lead_sources"])
        comp["digital_leads"] = dl / dig_target
        row(scored, "לידים מיוחסים לדיגיטל", dl, dig_target, dl >= dig_target)
    else:
        comp["digital_leads"] = None
        row(scored, "לידים מיוחסים לדיגיטל", "לא מחובר", dig_target, False)

    # 3) organic (scored) — clicks + top3 keywords, averaged
    if seo_geo and seo_geo.get("ok"):
        clicks = seo_geo.get("weekly_clicks") or 0
        top3 = seo_geo.get("top3_keywords") or 0
        f_clicks = min(1.0, clicks / org_t["weekly_clicks_min"])
        f_top3 = min(1.0, top3 / org_t["top3_keywords_min"])
        comp["organic"] = (f_clicks + f_top3) / 2
        row(scored, "קליקים אורגניים/שבוע", clicks, org_t["weekly_clicks_min"],
            clicks >= org_t["weekly_clicks_min"])
        row(scored, "מונחים ב-Top-3", top3, org_t["top3_keywords_min"],
            top3 >= org_t["top3_keywords_min"])
    else:
        comp["organic"] = None
        row(scored, "אורגני (GSC)", "לא מחובר", org_t["weekly_clicks_min"], False)

    # 4) AEO (scored) — cited in N engines out of 3
    if seo_geo and seo_geo.get("ok") and seo_geo.get("aeo_cited_engines") is not None:
        cited = seo_geo.get("aeo_cited_engines") or 0
        comp["aeo"] = min(1.0, cited / 3)
        row(scored, "נראות ב-AI (מנועים)", cited, 3, cited >= 3)
    else:
        comp["aeo"] = None
        row(scored, "נראות ב-AI (מנועים)", "לא מחובר", 3, False)

    # 5) social presence floor (scored) — cadence met, NOT growth
    posts_week = round(ct["posts"] / (cur["period_days"] / 7.0), 1) if cur["period_days"] else 0
    floor_ok = posts_week >= t["posts_per_week_min"]
    comp["social_presence"] = 1.0 if floor_ok else min(1.0, posts_week / t["posts_per_week_min"])
    row(scored, "נוכחות סושיאל (רצפה)", posts_week, t["posts_per_week_min"], floor_ok)

    # CONTEXT (not scored): engagement + impressions growth
    imp_growth = round(((ct["impressions"] - pt["impressions"]) / pt["impressions"] * 100)
                       if pt.get("impressions") else 0.0, 1)
    row(context, "צמיחת חשיפות", imp_growth, t["weekly_impressions_growth_pct"],
        imp_growth >= t["weekly_impressions_growth_pct"], "%")
    row(context, "Engagement rate", ct["engagement_rate_pct"], t["min_avg_engagement_rate_pct"],
        ct["engagement_rate_pct"] >= t["min_avg_engagement_rate_pct"], "%")
    row(context, "חשיפות (תקופה)", ct["impressions"], "↑", ct["impressions"] > 0)

    # attribution note (kept from old scorecard) as a context row
    if leads.get("ok") and leads.get("dominant_source"):
        if leads.get("attribution_gap"):
            row(context, "ייחוס לידים", "לא-מיוחס", "מקור אמיתי", False)
        else:
            row(context, f"ערוץ ממיר ({leads['dominant_source']})",
                leads.get("dominant_share_pct", 0), "↑", True, "%")

    weighted = weighted_score(comp, W)
    passed = sum(1 for r in scored if r["status"] == "✅")
    return {"rows": scored + context, "scored_rows": scored, "context_rows": context,
            "components": comp, "weighted": weighted,
            "passed": passed, "total": len(scored),
            "impressions_growth_pct": imp_growth, "posts_per_week": posts_week,
            "lead_attribution": {"by_source": leads.get("by_source", {}),
                                 "dominant_source": leads.get("dominant_source"),
                                 "dominant_share_pct": leads.get("dominant_share_pct", 0),
                                 "attribution_gap": leads.get("attribution_gap", False),
                                 "note": leads.get("attribution_note", "")}}
```

Then update the ONE caller in `run()` (search `build_scorecard(`) to pass `seo_geo`: it already computes `cur["seo_geo"] = seo_geo_source.fetch()` at line ~399 — pass `cur.get("seo_geo")`.

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_scorecard.py -v`
Expected: PASS (7 tests)

- [ ] **Step 5: Commit**

```bash
git add scripts/council.py tests/test_scorecard.py
git commit -m "feat(council): build_scorecard emits deterministic weighted score + context split"
```

---

## Task 5: Headline uses deterministic score; context block in email

**Files:**
- Modify: `scripts/council.py` `render_html` (line ~331-347) and `render_md` (line ~368-379)
- Test: manual render smoke test (no unit test — pure formatting)

**Interfaces:**
- Consumes: `scorecard["weighted"]`, `scorecard["scored_rows"]`, `scorecard["context_rows"]`, and `verdict["scores"]["overall"]` (LLM, now secondary).
- Produces: email headline shows the deterministic weighted score; a new "הקשר (לא נספר בציון)" table renders `context_rows`; the Scorecard table renders `scored_rows` only.

- [ ] **Step 1: Update the headline line in `render_html`**

Replace:
```python
<p style="font-size:16px;"><b>ציון כולל: {sc.get('overall','—')}/100</b> · scorecard עבר {scorecard['passed']}/{scorecard['total']}</p>
```
with:
```python
<p style="font-size:16px;"><b>ציון כולל: {scorecard['weighted']}/100</b> · scorecard עבר {scorecard['passed']}/{scorecard['total']} · <span style="color:#888">קריאת המועצה (LLM): {sc.get('overall','—')}/100</span></p>
```

- [ ] **Step 2: Render only scored rows in the Scorecard table**

Change `sb_rows` to iterate `scorecard["scored_rows"]` instead of `scorecard["rows"]`.

- [ ] **Step 3: Add a context table after the Scorecard table**

After the `{sb_rows}</table>` block insert:
```python
<h3>הקשר (לא נספר בציון)</h3>
<table dir="rtl" border="0" cellpadding="6" style="border-collapse:collapse;width:100%;font-size:13px;color:#555;">
<tr style="background:#666;color:#fff;"><th>מדד</th><th>ערך</th><th>יעד</th><th></th></tr>
{ctx_rows}</table>
```
and build `ctx_rows` next to `sb_rows`:
```python
    ctx_rows = "".join(
        f"<tr><td>{r['metric']}</td><td dir='ltr'>{r['value']}{r['unit']}</td>"
        f"<td dir='ltr'>{r['target']}{r['unit']}</td><td>{r['status']}</td></tr>"
        for r in scorecard.get("context_rows", []))
```

- [ ] **Step 4: Update `render_md` headline**

Replace the `Overall:` line to lead with `scorecard['weighted']`:
```python
f"Overall (weighted): {scorecard['weighted']}/100 · scorecard {scorecard['passed']}/{scorecard['total']} · LLM read {verdict.get('scores',{}).get('overall','—')}/100\n\n"
```

- [ ] **Step 5: Smoke-test the render + commit**

Run: `python3 scripts/council.py --no-llm --dry-run` — confirm it prints/renders a weighted score and a context section without error (LLM skipped; leads/seo_geo may be unwired locally → components None → renormalized score).
Expected: no exception, headline shows `ציון כולל: N/100`, a "הקשר (לא נספר בציון)" section is present.

```bash
git add scripts/council.py
git commit -m "feat(council): email/md headline uses deterministic weighted score; engagement demoted to context"
```

---

## Task 6: Rewrite COUNCIL_PROMPT GOALS

**Files:**
- Modify: `scripts/council.py:106-109` (GOALS block inside `COUNCIL_PROMPT`)
- Test: assertion test on the prompt string.

**Interfaces:**
- Produces: GOALS text that instructs the LLM that PRIMARY = qualified + digital-attributed leads, SECONDARY = organic + AEO, and engagement/impressions are context that must NOT dominate; the LLM `overall` is advisory, the deterministic weighted score is the headline.

- [ ] **Step 1: Write the failing test**

```python
def test_prompt_demotes_engagement():
    src = (ROOT / "scripts" / "council.py").read_text()
    assert "Maximize impressions, raise engagement" not in src
    assert "engagement/impressions are CONTEXT" in src
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_scorecard.py::test_prompt_demotes_engagement -v`
Expected: FAIL

- [ ] **Step 3: Replace the GOALS block**

Replace:
```
GOALS:
- North-star: 500,000 organic followers over ~3 years (leading indicators matter more than the count).
- PRIMARY KPI: 10 real NEW qualified leads per month from NEW potential clients for substantial events.
- Maximize impressions, raise engagement, continuous measurable improvement.
```
with:
```
GOALS (scored deterministically — do not invent your own overall number; the headline score
is computed from business outcomes, your "overall" is an advisory second opinion):
- PRIMARY: 10 real NEW qualified leads/month, of which >=3 are digital-attributed (LeadSource
  not Word-of-Mouth). This is what winning means.
- SECONDARY: Google-organic momentum (clicks + Top-3 Hebrew keywords) and AI/AEO citations.
- CONTEXT ONLY — engagement/impressions are CONTEXT, not goals. A low engagement rate on
  Israeli-B2B social is EXPECTED and must NOT dominate your assessment or the overall score.
- North-star: 500,000 organic followers over ~3 years (leading indicator, not a near-term target).
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_scorecard.py -v`
Expected: PASS (8 tests)

- [ ] **Step 5: Commit**

```bash
git add scripts/council.py tests/test_scorecard.py
git commit -m "feat(council): rewrite GOALS so LLM stops anchoring on engagement"
```

---

## Task 7: Before/after verification on the last real snapshot

**Files:**
- Read: `reports/metrics/*.json` (latest saved snapshot, if present) or run live.

**Interfaces:** none (verification only).

- [ ] **Step 1: Recompute old vs new on the same data**

Run the council against the most recent snapshot and confirm the weighted score reflects lead/organic reality rather than engagement. If a saved snapshot exists in `reports/metrics/`, load `cur`/`prev` from it; otherwise run `python3 scripts/council.py --no-llm --dry-run` in the cloud (secrets present) via a `workflow_dispatch`.
Expected: on the 2026-07-31 data (7/10 leads, +63% organic clicks, 0.04% engagement), weighted score lands materially above 22 (target band ~40-60), and engagement appears only in the context table.

- [ ] **Step 2: Confirm graceful degradation**

Temporarily unset `SEO_GEO`/`SALESFORCE` locally and run `--no-llm --dry-run`; confirm no crash and the score renormalizes over available components (never `—/100`, never a traceback).

- [ ] **Step 3: Final full test run**

Run: `python3 -m pytest tests/test_scorecard.py -v`
Expected: PASS (8 tests). Then `git status` clean.

---

## Self-Review

- **Spec coverage (Part 1):** weighting model → Tasks 1,3,4 ✓; engagement/impressions demoted to context → Tasks 4,5 ✓; `council.py` + `kpi_targets.json` changes → all tasks ✓; GOALS rewrite → Task 6 ✓; digital-attributed leads metric → Task 2 (computed from existing `by_source`, decoupled from Part 3 form) ✓; acceptance "22 → 45-60 on same data" → Task 7 ✓. Parts 2 (three engines) and 3 (attribution form) are **out of scope for this plan** — separate follow-up plans, noted at handoff.
- **Placeholder scan:** every code step has concrete code; no TBD/TODO.
- **Type consistency:** `digital_attributed_leads(leads, digital_sources)`, `weighted_score(components, weights)`, `build_scorecard(cur, prev, leads, seo_geo=None)` used identically across tasks. `components` keys match `scorecard_weights` keys in all tasks.
- **Open assumption to verify in Task 4/7:** the `seo_geo_source.fetch()` snapshot key names (`weekly_clicks`, `top3_keywords`, `aeo_cited_engines`) are read defensively with `.get()`; if the astro snapshot uses different names, adjust the three `.get()` calls in Task 4 (they degrade to `None` → organic/aeo unavailable, never crash). Confirm real key names against a live fetch during Task 7.
