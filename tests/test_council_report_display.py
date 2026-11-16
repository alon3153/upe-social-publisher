"""Regressions from the 14.11.2026 council email."""
import json
import council
import council_source_evidence
import metricool_analytics

LEADS = {"ok": True, "qualified_leads": 7, "by_source": {"Web": 7}, "dominant_source": "Web",
         "dominant_share_pct": 100, "attribution_gap": False}


def _growth_row(prev_impressions):
    cur = {"totals": {"impressions": 53403, "engagement_rate_pct": 10.9, "posts": 9}, "period_days": 7,
           "networks": {}}
    sc = council.build_scorecard(cur, {"totals": {"impressions": prev_impressions}}, LEADS, None)
    return next(r for r in sc["context_rows"] if r["metric"] == "צמיחת חשיפות")


def test_tiny_growth_base_is_not_a_percentage_or_a_pass():
    for prev in (0, 76):
        r = _growth_row(prev)
        assert r["value"] == "בסיס קטן מדי — לא בר השוואה" and r["status"] == "—"
    r = _growth_row(40000)
    assert r["value"] == 33.5 and r["status"] == "✅"


def test_missing_target_renders_dash_not_none():
    cur = {"totals": {"impressions": 0, "engagement_rate_pct": 0, "posts": 0}, "period_days": 7, "networks": {}}
    sc = {"weighted": 50, "passed": 0, "total": 1, "scored_rows": [], "context_rows": [
        {"metric": "מונחי Top-3 בכל השאילתות (מידע)", "value": 28, "target": None, "unit": "", "status": "—"},
        {"metric": "שיעור אזכור לא-ממותג (מידע)", "value": 34.4, "target": "מידע", "unit": "%", "status": "—"}]}
    html = council.render_html(cur, sc, {}, [], report_date="2026-11-14")
    assert "None" not in html and "מידע%" not in html


def test_unmeasured_engines_carry_account_reason(tmp_path):
    row = {"date": "2026-11-13", "models": {"claude": {"degraded": False, "answers": [
        {"grounded": True, "branded": False, "cited_urls": ["https://upe.co.il/x"]}]}},
        "errors": ["chatgpt/q1: RuntimeError: HTTP 429 ... You have no credits remaining",
                   "gemini/q1: RuntimeError: HTTP 401 ... API key not valid."]}
    path = tmp_path / "h.json"
    path.write_text(json.dumps([row]))
    ev = council_source_evidence.engine_evidence(path=path, today="2026-11-14")
    assert ev["measured_engines"] == 1
    assert ev["failed_engines"] == {"chatgpt": "אין קרדיט", "gemini": "מפתח לא תקין"}
    sc = council.build_scorecard(
        {"totals": {"impressions": 0, "engagement_rate_pct": 0, "posts": 0}, "period_days": 7, "networks": {}},
        {"totals": {}}, LEADS, {"ok": True, "aeo_engine_evidence": ev, "aeo_cited_engines": 1})
    aeo = next(r for r in sc["scored_rows"] if r["metric"].startswith("מנועי AI"))
    assert "ChatGPT: אין קרדיט" in aeo["note"] and "Gemini: מפתח לא תקין" in aeo["note"]


def test_reach_not_provided_is_none_not_zero():
    linkedin = [{"impressions": 23, "viewers": 16}, {"impressions": 16}]
    assert metricool_analytics.summarize(linkedin)["reach"] is None
    assert metricool_analytics.summarize([{"impressionsTotal": 28, "reach": 15}])["reach"] == 15
    assert metricool_analytics.summarize([{"impressions": 340, "impressionsUnique": 188}])["reach"] == 188
