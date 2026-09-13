import json
from scripts.council_source_evidence import citation_basis, engine_evidence, valid_week
from scripts import seo_geo_source
import council
import leads_source


def test_citation_host_is_exact_and_domains_are_not_direct_urls():
    assert citation_basis('https://upe.co.il/service/') == 'direct_url'
    assert citation_basis('upe.co.il') == 'grounded_source_domain'
    assert citation_basis('https://evil.example/upe.co.il') is None
    assert citation_basis('https://upe.co.il.evil.example/') is None


def test_engine_count_uses_grounded_nonbranded_evidence(tmp_path):
    a = lambda url, **kw: dict(grounded=True, branded=False, cited_urls=[url], **kw)
    data = [{'date': '2026-09-13', 'models': {
        'claude': {'answers': [a('https://upe.co.il/')]},
        'chatgpt': {'answers': [dict(grounded=False, branded=False, cited_urls=['https://upe.co.il/'])]},
        'gemini': {'answers': [a('upe.co.il')]},
    }}]
    p = tmp_path / 'history.json'; p.write_text(json.dumps(data))
    result = engine_evidence(p, '2026-09-13')
    assert result['cited_engines'] == 2 and result['ok'] is False
    assert result['engines']['gemini']['source_domain_answers'] == 1
    assert engine_evidence(p, '2026-09-17')['ok'] is False


def test_perplexity_questions_are_never_counted_as_engines():
    value = seo_geo_source.normalize({'ok': True, 'geo': {'cited': 4, 'total': 7},
                                      'aeo_cited_engines': 4})
    assert value.get('aeo_cited_engines') is None
    assert value['aeo_cited_questions'] == 4


def test_28_day_total_cannot_become_weekly_clicks():
    value = seo_geo_source.normalize({'ok': True, 'sites': [{'clicks': 200}]})
    assert value.get('weekly_clicks') is None


def test_exact_week_metadata_required():
    assert valid_week({'start': '2026-09-01', 'end': '2026-09-07', 'days': 7})
    assert not valid_week({'start': '2026-09-01', 'end': '2026-09-08', 'days': 7})


def test_ambiguous_advertisement_is_not_verified_digital_attribution():
    attr = leads_source._attribution([{'LeadSource': 'Web'}, {'LeadSource': 'Advertisement'}])
    assert council.digital_attributed_leads(attr, ['Web', 'Advertisement']) == 1
    assert attr['attribution_gap'] is True


def test_missing_metrics_are_not_scored_as_zero():
    cur = {'totals': {'impressions': 10, 'posts': 5, 'engagement_rate_pct': 1}, 'period_days': 7}
    sc = council.build_scorecard(cur, cur, {'ok': True, 'qualified_leads': 9, 'by_source': {'Web': 3}},
                                {'ok': True, 'weekly_clicks': None, 'top3_keywords': 7})
    clicks = next(r for r in sc['scored_rows'] if 'קליקים' in r['metric'])
    assert clicks['value'] == 'לא נמדד' and clicks['status'] == '—'
    assert sc['components']['organic'] is None
    assert sc['coverage_percent'] < 100 and sc['warnings']


def test_manual_main_persists_reviewable_report_without_email(tmp_path, monkeypatch):
    import sys
    cur = {'totals': {'impressions': 10, 'posts': 5, 'engagement_rate_pct': 1},
           'period_days': 7, 'period_start': '2026-09-06T00:00:00', 'networks': {}}
    monkeypatch.setattr(sys, 'argv', ['council.py', '--no-llm'])
    monkeypatch.setattr(council.ma, 'snapshot', lambda *a, **k: dict(cur))
    monkeypatch.setattr(council.leads_source, 'count', lambda *a: {'ok': False})
    monkeypatch.setattr(council.seo_geo_source, 'fetch', lambda: {'ok': False})
    monkeypatch.setattr(council.site_inventory, 'fetch', lambda: {'ok': False})
    monkeypatch.setattr(council, 'apply_auto_fixes', lambda *a: ([], {}))
    monkeypatch.setattr(council, 'render_html', lambda *a: '<html dir="rtl">report</html>')
    monkeypatch.setattr(council, 'render_md', lambda *a: 'report')
    for field in ('METRICS_DIR', 'REPORT_DIR', 'STATE_DIR'):
        monkeypatch.setattr(council, field, tmp_path / field)
    class ForbiddenEmail:
        def __getattr__(self, name):
            raise AssertionError('Manual report must not load email transport')
    monkeypatch.setitem(sys.modules, 'daily_email', ForbiddenEmail())
    assert council.main() == 0
    assert list((tmp_path / 'REPORT_DIR').glob('*.html'))
    saved = json.loads(next((tmp_path / 'REPORT_DIR').glob('*.json')).read_text())
    assert saved['email_requested'] is False
