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
