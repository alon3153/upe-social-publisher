import json, pathlib
import council
import seo_geo_source
import site_inventory

ROOT = pathlib.Path(__file__).resolve().parent.parent


def test_council_prompt_has_site_inventory_guardrail():
    # REGRESSION (05.08.2026): the council was site-blind and kept recommending to
    # "create" pages (נופש-חברה / אירוע-קונספט / Brand Hub / llms.txt) that already
    # exist, which would cannibalize rankings. The prompt must carry the live inventory
    # AND the anti-duplication instruction, and must format without KeyError.
    p = council.COUNCIL_PROMPT.format(
        data="{}", scorecard="{}",
        site_inventory=json.dumps({"ok": True, "service_pages": ["נופש-חברה"]}, ensure_ascii=False),
        blog_hint=169)
    assert "EXISTING SITE ASSETS" in p
    assert "Do NOT recommend" in p and "DUPLICATE" in p
    assert "נופש-חברה" in p


def test_site_inventory_degrades_without_token():
    import os
    tok = os.environ.pop("GH_PAT", None)
    try:
        r = site_inventory.fetch()
        assert r["ok"] is False and "GH_PAT" in r["reason"]  # never fabricates, never raises
    finally:
        if tok is not None:
            os.environ["GH_PAT"] = tok

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

def test_digital_attributed_counts_only_digital():
    leads = {"ok": True, "by_source": {"Web": 3, "Word of mouth": 5, "LinkedIn": 2, "(none)": 1}}
    ds = ["Web", "LinkedIn", "Google"]
    assert council.digital_attributed_leads(leads, ds) == 5  # 3 Web + 2 LinkedIn

def test_digital_attributed_case_insensitive_and_empty():
    assert council.digital_attributed_leads({"ok": True, "by_source": {"web": 4}}, ["Web"]) == 4
    assert council.digital_attributed_leads({"ok": False}, ["Web"]) == 0

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

def test_prompt_demotes_engagement():
    src = (ROOT / "scripts" / "council.py").read_text()
    assert "Maximize impressions, raise engagement" not in src
    assert "engagement/impressions are CONTEXT" in src

def test_normalize_maps_guardian_nested_schema_to_flat_fields():
    # REGRESSION (05.08.2026): the guardian writes a NESTED schema (sites[].clicks,
    # sites[].top_opportunities, geo.cited) but the scorecard reads FLAT fields
    # (weekly_clicks / top3_keywords / aeo_cited_engines). The mismatch pinned the
    # daily score at 36 with AI-visibility falsely "not connected". normalize() bridges it.
    raw = {"ok": True,
           "sites": [
               {"site": "https://upe.co.il/", "clicks": 145,
                "top_opportunities": [["a", 9.2, 757], ["b", 2.0, 300]]},
               {"site": "https://upe-spain.com/", "clicks": 60,
                "top_opportunities": [["c", 15.0, 184]]}],
           "geo": {"status": "ok", "cited": 3, "total": 7}}
    n = seo_geo_source.normalize(raw)
    assert n["weekly_clicks"] == 205          # 145 + 60, not 0
    assert n["top3_keywords"] == 1            # only "b" at pos 2.0 <= 3
    assert n["aeo_cited_engines"] == 3        # from geo.cited, not "not connected"

def test_normalize_never_fabricates_when_source_dark():
    # ok=False (no GH_PAT / fetch error) must pass through untouched — no invented zeros.
    assert seo_geo_source.normalize({"ok": False, "reason": "x"}) == {"ok": False, "reason": "x"}
    # ok=True but no sites -> leave organic fields UNSET so the scorecard honestly
    # renders "not connected" rather than a fabricated 0-clicks pass/fail.
    n = seo_geo_source.normalize({"ok": True, "geo": {"cited": 5}})
    assert "weekly_clicks" not in n and n["aeo_cited_engines"] == 5

def test_all_sources_unwired_does_not_inflate():
    # Salesforce + GSC both dark, but posting continues (UPE posts ~41/wk).
    # The social floor must NOT renormalize the headline to a false green.
    cur = {"totals": {"impressions": 14000, "engagement_rate_pct": 0.04, "posts": 41},
           "period_days": 7, "networks": {}}
    prev = {"totals": {"impressions": 14700}}
    sc = council.build_scorecard(cur, prev, {"ok": False}, {"ok": False})
    assert sc["weighted"] <= 40  # capped — leads dark cannot be a winning score
    # and it must not have crashed / must still produce the standard shape
    assert "weighted" in sc and "scored_rows" in sc
