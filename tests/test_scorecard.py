import json, pathlib
import council

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
