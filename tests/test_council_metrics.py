import json
from pathlib import Path

import council
import seo_geo_source
from scripts.council_source_evidence import unbranded_mention_rates

ROOT = Path(__file__).resolve().parent.parent


def _base_cur():
    return {"totals": {"impressions": 2530, "engagement_rate_pct": 0.04, "posts": 14},
            "period_days": 7, "period_start": "2026-09-19T10:05:47",
            "period_end": "2026-09-26T10:05:47", "generated_at": "2026-09-26T10:05:47",
            "networks": {}}


def _leads():
    return {"ok": True, "qualified_leads": 38, "period_days": 30,
            "by_source": {"Web": 9, "Google Organic": 3, "Advertisement": 2, "Other": 21},
            "ambiguous_sources": ["Advertisement", "Other"],
            "dominant_source": "Other", "attribution_gap": True}


def _seo():
    return {"ok": True, "generated_at": "2026-09-23", "window_days": 28,
            "weekly_clicks": 25, "clicks_28d": 167, "top3_keywords": 10,
            "aeo_cited_engines": 3,
            "aeo_engine_evidence": {"ok": True, "date": "2026-09-25", "measured_engines": 3,
                                    "cited_engines": 3},
            "sites": [{
                "clicks_7d": 25, "clicks": 167,
                "windows": {"weekly": {"start": "2026-09-17", "end": "2026-09-23", "days": 7},
                            "current": {"start": "2026-08-27", "end": "2026-09-23", "days": 28}},
                "top3_terms": [
                    ["טיולי חברה", 1.3, 110, 0],
                    ["איזה מקום מתאים לארגן כנס בינלאומי עם משתתפים מארצות שונות?", 1.8, 28, 0],
                ],
            }]}


def test_targets_are_unchanged():
    targets = json.loads((ROOT / "scripts" / "kpi_targets.json").read_text())
    assert targets["organic_targets"]["weekly_clicks_min"] == 300
    assert targets["organic_targets"]["top3_keywords_min"] == 3
    assert "TODO(Alon)" in targets["organic_targets"]["_todo"]
    assert targets["scorecard_weights"]["organic"] == 20


def test_tracked_top3_ignores_unlisted_questions_and_keeps_all_queries_out_of_score():
    raw = _seo()
    raw["tracked_keywords"] = ["טיולי חברה"]
    card = council.build_scorecard(_base_cur(), {"totals": {"impressions": 1}}, _leads(), raw)
    tracked = next(r for r in card["scored_rows"] if r["metric"] == "מונחי מעקב ב-Top-3")
    all_queries = next(r for r in card["context_rows"] if "בכל השאילתות" in r["metric"])
    assert tracked["value"] == 1 and tracked["status"] == "❌"
    assert all_queries["value"] == 2 and all_queries["status"] == "—"
    assert card["components"]["organic"] == (25 / 300 + 1 / 3) / 2
    assert "top3_keywords_all_queries" not in card["components"]


def test_missing_keyword_list_is_not_replaced_by_the_precomputed_count(monkeypatch):
    monkeypatch.setattr(seo_geo_source, "tracked_keywords", lambda data=None: None)
    card = council.build_scorecard(_base_cur(), {"totals": {"impressions": 1}}, _leads(), _seo())
    tracked = next(r for r in card["scored_rows"] if r["metric"] == "מונחי מעקב ב-Top-3")
    all_queries = next(r for r in card["context_rows"] if "בכל השאילתות" in r["metric"])
    clicks = next(r for r in card["scored_rows"] if r["metric"] == "קליקים אורגניים/שבוע")
    assert tracked["value"] == "לא נמדד"
    assert all_queries["value"] == 2
    assert clicks["value"] == 25 and clicks["weekly_avg_28d"] == 41.75
    assert card["components"]["organic"] == 25 / 300
    assert any("אינה במאגר" in note for note in card["warnings"])


def test_23_09_snapshot_recomputes_top3_and_ignores_precomputed_10():
    seo = json.loads((ROOT / "reports/metrics/2026-09-23.json").read_text())["seo_geo"]
    assert seo["top3_keywords"] == 10
    out = seo_geo_source.normalize(json.loads(json.dumps(seo)))
    assert out["top3_all_queries"] == 10
    assert out["top3_keywords"] == 1
    assert out["top3_tracked_terms"] == ["טיולי חברה"]
    assert seo["top3_keywords"] == 10


def test_28_day_average_is_info_and_rows_carry_windows_and_snapshot_dates():
    card = council.build_scorecard(_base_cur(), {"totals": {"impressions": 1}}, _leads(), _seo())
    clicks = next(r for r in card["scored_rows"] if r["metric"] == "קליקים אורגניים/שבוע")
    avg = next(r for r in card["context_rows"] if "28 יום" in r["metric"])
    assert clicks["window_from"] == "2026-09-17" and clicks["window_to"] == "2026-09-23"
    assert clicks["snapshot_date"] == "2026-09-23"
    assert avg["value"] == 41.75 and avg["status"] == "—"
    assert avg["window_from"] == "2026-08-27" and avg["window_to"] == "2026-09-23"
    assert avg["snapshot_date"] == "2026-09-23"
    for row in card["rows"]:
        assert "window_from" in row and "window_to" in row and "snapshot_date" in row
    leads = next(r for r in card["scored_rows"] if r["metric"] == "Website leads (not paid)")
    assert leads["value"] == 12
    assert leads["window_from"] == "2026-08-28" and leads["window_to"] == "2026-09-26"
    assert leads["snapshot_date"] == "2026-09-26"


def test_ai_row_is_engines_checked_and_mention_rate_is_info(tmp_path, monkeypatch):
    history = [{"date": "2026-09-25", "models": {
        "claude": {"mention_rate_nonbranded": 34, "mentioned_nonbranded": 11, "n_nonbranded": 32},
        "chatgpt": {"mention_rate_nonbranded": 25, "mentioned_nonbranded": 8, "n_nonbranded": 32},
        "gemini": {"mention_rate_nonbranded": 23, "mentioned_nonbranded": 7, "n_nonbranded": 31},
    }}]
    path = tmp_path / "history.json"
    path.write_text(json.dumps(history))
    monkeypatch.setattr(council.council_source_evidence, "HISTORY", path)
    card = council.build_scorecard(_base_cur(), {"totals": {"impressions": 1}}, _leads(), _seo())
    engines = next(r for r in card["scored_rows"] if "מנועי AI" in r["metric"])
    mention = next(r for r in card["context_rows"] if "אזכור לא-ממותג" in r["metric"])
    assert engines["metric"] == "מנועי AI שנבדקו (לא אזכורים)"
    assert engines["value"] == 3 and engines["target"] == 3
    assert engines["snapshot_date"] == "2026-09-25"
    assert mention["value"] == 27.4 and mention["unit"] == "%" and mention["status"] == "—"
    assert mention["by_engine"]["chatgpt"] == 25
    assert card["components"]["aeo"] == 1.0


def test_september_26_score_drops_the_untracked_top3_credit():
    cur = json.loads((ROOT / "reports/metrics/2026-09-26.json").read_text())
    card = council.build_scorecard(cur, cur, cur["leads"], cur["seo_geo"])
    stored = json.loads((ROOT / "reports/council/2026-09-26.json").read_text())
    assert stored["scorecard"]["weighted"] == 91
    clicks = next(r for r in card["scored_rows"] if r["metric"] == "קליקים אורגניים/שבוע")
    assert clicks["value"] == 25 and clicks["weekly_avg_28d"] == 41.75
    assert clicks["snapshot_date"] == "2026-09-23"
    all_queries = next(r for r in card["context_rows"] if "בכל השאילתות" in r["metric"])
    assert all_queries["value"] == 10 and all_queries["status"] == "—"
    tracked = next(r for r in card["scored_rows"] if r["metric"] == "מונחי מעקב ב-Top-3")
    assert tracked["value"] == 1 and tracked["tracked_terms"] == ["טיולי חברה"]
    assert card["components"]["organic"] == (25 / 300 + 1 / 3) / 2
    assert card["weighted"] == 84
    mention = next(r for r in card["context_rows"] if "אזכור לא-ממותג" in r["metric"])
    assert mention["snapshot_date"] == "2026-09-25"
    assert mention["by_engine"]["chatgpt"] == 25
    assert mention["by_engine"]["gemini"] == 23


def test_normalize_counts_only_a_supplied_tracked_list():
    raw = {"ok": True, "sites": [{
        "clicks_7d": 25,
        "windows": {"weekly": {"start": "2026-09-17", "end": "2026-09-23", "days": 7}},
        "top3_terms": [["טיולי חברה", 1.3, 110, 0],
                       ["איזה מקום מתאים לארגן כנס?", 1.8, 28, 0]],
    }], "tracked_keywords": ["טיולי חברה"], "clicks_28d": 167, "window_days": 28}
    out = seo_geo_source.normalize(raw)
    assert out["weekly_clicks"] == 25
    assert out["top3_keywords"] == 1
    assert out["top3_all_queries"] == 2
    assert out["top3_tracked_terms"] == ["טיולי חברה"]
    assert out["weekly_clicks_28d_avg"] == 41.75


def test_unbranded_mention_rate_reads_the_named_history_date(tmp_path):
    path = tmp_path / "history.json"
    path.write_text(json.dumps([
        {"date": "2026-09-24", "models": {"claude": {"mention_rate_nonbranded": 22,
                                                     "mentioned_nonbranded": 7, "n_nonbranded": 32}}},
    ]))
    assert unbranded_mention_rates(path, "2026-09-23") is None
    found = unbranded_mention_rates(path, "2026-09-24")
    assert found["pooled_pct"] == 21.9
    assert found["by_engine"] == {"claude": 22}
