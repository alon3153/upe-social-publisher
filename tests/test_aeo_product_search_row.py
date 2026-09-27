import json
from pathlib import Path

import council
import council_source_evidence as evidence

ROOT = Path(__file__).resolve().parent.parent


def _targets():
    return json.loads((ROOT / "scripts" / "kpi_targets.json").read_text())


def test_history_entries_match_the_recorded_product_search_scores():
    daily = evidence.product_search_for_date("2026-09-23")
    weekly = evidence.product_search_for_date("2026-09-27")
    assert daily["source"] == "daily"
    assert daily["scores"] == {"claude": 20, "chatgpt": 19, "gemini": 17}
    assert evidence.format_product_search(daily) == "Claude 20 · ChatGPT 19 · Gemini 17 (23.09.2026)"
    assert weekly["source"] == "weekly"
    assert weekly["scores"] == {"claude": 24, "chatgpt": 21, "gemini": 18}
    assert evidence.format_product_search(weekly) == "Claude 24 · ChatGPT 21 · Gemini 18 (27.09.2026)"


def test_missing_engine_is_blank_and_not_carried(tmp_path):
    daily = tmp_path / "daily.json"
    weekly = tmp_path / "weekly.json"
    daily.write_text(json.dumps([
        {"date": "2026-09-26", "models": {
            "claude": {"product_search": 19},
            "chatgpt": {"product_search": 25},
            "gemini": {"product_search": 20},
        }},
        {"date": "2026-09-27", "models": {
            "claude": {"product_search": 24},
            "gemini": {"product_search": 99, "degraded": True},
        }},
    ]))
    weekly.write_text("[]")
    entry = evidence.product_search_for_date("2026-09-27", daily, weekly)
    assert entry["scores"] == {"claude": 24, "chatgpt": None, "gemini": None}
    assert evidence.format_product_search(entry) == "Claude 24 · ChatGPT אין נתון · Gemini אין נתון (27.09.2026)"
    latest = evidence.latest_product_search(daily, weekly)
    assert latest["date"] == "2026-09-27"
    assert latest["scores"]["chatgpt"] is None


def test_same_day_uses_the_weekly_battery_without_mixing(tmp_path):
    daily = tmp_path / "daily.json"
    weekly = tmp_path / "weekly.json"
    daily.write_text(json.dumps([{"date": "2026-09-27", "models": {
        "claude": {"product_search": 1}, "chatgpt": {"product_search": 2}, "gemini": {"product_search": 3},
    }}]))
    weekly.write_text(json.dumps([{"date": "2026-09-27", "models": {
        "claude": {"product_search": 24}, "gemini": {"product_search": 18},
    }}]))
    entry = evidence.latest_product_search(daily, weekly)
    assert entry["source"] == "weekly"
    assert entry["scores"] == {"claude": 24, "chatgpt": None, "gemini": 18}


def test_scorecard_row_shows_latest_product_search_without_changing_aeo_weight():
    target = _targets()["aeo_targets"]["per_dimension_min"]["product_search"]
    assert target == 70
    cur = json.loads((ROOT / "reports/metrics/2026-09-26.json").read_text())
    card = council.build_scorecard(cur, cur, cur["leads"], cur["seo_geo"])
    row = next(r for r in card["context_rows"] if r["metric"].startswith("ציון בולטות AI"))
    assert row["metric"] == f"ציון בולטות AI (יעד {target})"
    assert row["target"] == target
    assert row["value"] == "Claude 24 · ChatGPT 21 · Gemini 18 (27.09.2026)"
    assert row["snapshot_date"] == "2026-09-27"
    assert row["product_search"] == {"claude": 24, "chatgpt": 21, "gemini": 18}
    assert row["status"] == "—"
    assert all(r["metric"] != row["metric"] for r in card["scored_rows"])
    assert card["components"]["aeo"] == 1.0
    assert card["weighted"] == 84
