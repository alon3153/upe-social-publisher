import copy
import json
from pathlib import Path
from unittest.mock import patch
import council
import council_evidence as evidence


def test_rejects_report_misinterpretations_without_changing_scores():
    original = {'scores': {'overall': 62}, 'verdict_summary': 'Web הוא הערוץ הממיר המוכח',
                'what_worked': ['UPE ב-4 מנועי AI'],
                'what_failed': ['1,111 חיפושים חודשיים לא מנוצלים', 'YouTube top post עזב את החלון'],
                'follower_growth_plan': ['500 followers חדשים', 'algorithm memory בונה צמיחה'],
                'recommendations': [], 'auto_fixes': []}
    before = copy.deepcopy(original)
    out = evidence.sanitize(original, state={})
    assert original == before and out['scores'] == original['scores']
    assert out['what_worked'] == out['what_failed'] == out['follower_growth_plan'] == []
    assert len(out['evidence_notes']) == 6
    assert 'הערוץ הממיר' not in out['verdict_summary']


def test_completed_page_audit_prevents_repeat_rewrite_even_under_new_action_key():
    action = {'action_key': 'brand-new-title', 'channel': 'google_organic_geo',
              'action': 'עדכן H1 והוסף FAQPage', 'target_url': 'https://upe.co.il/נופש-חברה/'}
    out = evidence.sanitize({'recommendations': [action]})
    assert out['recommendations'] == []
    assert out['withheld_advice'][0]['action_key'] == 'brand-new-title'


def test_pending_evidenced_patch_survives_but_cooldown_blocks_it():
    url = 'https://upe.co.il/x/'
    state = {'page_audits': [{'url': url, 'update_required': True, 'evidence': 'Live missing FAQ schema'}]}
    action = {'action_key': 'fix-faq', 'channel': 'google_organic_geo', 'action': 'הוסף FAQPage', 'target_url': url}
    assert evidence.sanitize({'recommendations': [action]}, state=state)['recommendations'] == [action]
    assert evidence.sanitize({'recommendations': [action]}, state=state, shipped=[{'url': url, 'cooldown': True}])['recommendations'] == []


def test_web_source_must_be_provider_citation_not_model_invented_url():
    action = {'channel': 'linkedin', 'action': 'המחקר ב-2026 מצביע על שעות אלה כפיק הפעילות',
              'evidence_url': 'https://example.org/study'}
    assert evidence.sanitize({'auto_fixes': [action]}, state={})['auto_fixes'] == []
    assert evidence.sanitize({'auto_fixes': [action]}, state={}, source_urls=[action['evidence_url']])['auto_fixes'] == [action]


def test_sanitizer_preserves_approval_identifiers_and_safe_drafts():
    action = {'id': 'original', 'action_key': 'linkedin-executive-advocacy', 'channel': 'linkedin',
              'action': 'הכן טיוטת פוסט מקצועי', 'approval_token': 'unchanged'}
    out = evidence.sanitize({'recommendations': [action], 'updated_at': '2026-09-13'}, state={})
    assert out['recommendations'] == [action] and out['updated_at'] == '2026-09-13'
    assert evidence.sanitize(out, state={}) == out


def test_report_distinguishes_saved_directive_from_execution_and_displays_warnings():
    cur = {'networks': {}, 'period_days': 7, 'totals': {}}
    score = {'weighted': 88, 'passed': 4, 'total': 6, 'scored_rows': [], 'warnings': ['מקור AI יחיד; היקף שאלות בלבד']}
    verdict = {'scores': {}, 'evidence_notes': ['אין נתון המרה']}
    html = council.render_html(cur, score, verdict, [], {})
    md = council.render_md(cur, score, verdict, [])
    assert 'תיקונים אוטומטיים שבוצעו' not in html
    assert 'נאכף אוטומטית' not in html and 'דרך ל-500K' not in html
    assert 'מקור AI יחיד' in html and 'אין נתון המרה' in html
    assert 'execution unverified' in md and 'מקור AI יחיד' in md


def test_live_council_consumer_validates_model_prose_before_returning_it(monkeypatch):
    class Response:
        def __enter__(self): return self
        def __exit__(self, *args): return False
        def read(self):
            return json.dumps({'content': [{'type': 'text', 'text': json.dumps({
                'verdict_summary': 'Web הוא הערוץ הממיר המוכח',
                'recommendations': [{'action_key': 'repeat', 'channel': 'google_organic_geo',
                                     'action': 'הוסף FAQPage', 'target_url': 'https://upe.co.il/נופש-חברה/'}],
                'channel_cadence': {}, 'scores': {'overall': 62}})}]}).encode()
    monkeypatch.setattr(council, 'API_KEY', 'test')
    monkeypatch.setattr(council.urllib.request, 'urlopen', lambda *a, **kw: Response())
    out = council.run_council({'networks': {}}, {'totals': {}}, {}, inventory={'ok': True})
    assert out['recommendations'] == []
    assert 'הערוץ הממיר' not in out['verdict_summary']
    assert out['scores']['overall'] == 62
    assert out['evidence_notes']


def actual_cloud_report():
    return json.loads((Path(__file__).parent / 'fixtures/council_2026-09-13_cloud_report.json').read_text())


def test_actual_cloud_output_gets_deterministic_findings_and_verified_candidates():
    report = actual_cloud_report()
    before = copy.deepcopy(report)
    out = evidence.sanitize(report['verdict'], scorecard=report['scorecard'])
    assert report == before
    expected = evidence.scorecard_narrative(report['scorecard'])
    assert all(out[key] == value for key, value in expected.items())
    assert any('לידים מיוחסים לדיגיטל: 4; יעד 3' in item for item in out['what_worked'])
    assert any('9; יעד 10' in item for item in out['what_failed'])
    assert any('40; יעד 300' in item for item in out['what_failed'])
    narrative = ' '.join([out['verdict_summary'], *out['what_worked'], *out['what_failed'], *out['leads_actions']])
    for falsehood in ('יתרון תחרותי מוכח', '332-275 חיפושים', 'ROI', 'היעד של 10 לידים דיגיטליים הושג'):
        assert falsehood not in narrative
    assert 'שינוי תווית מקור אינו מוסיף ליד' in narrative
    assert 'אינה מספיקה לסיווג כאורגני' in narrative
    assert out['recommendations']
    for action in out['recommendations']:
        assert action['status'] == 'candidate'
        assert evidence.metric_evidence(action['evidence'], report['scorecard']) == action['evidence']
    assert all('מדכא' not in cfg['reason'] and 'מכסה מוצעת' in cfg['reason'] for cfg in out['channel_cadence'].values())
    assert evidence.sanitize(out, scorecard=report['scorecard']) == out


def test_wrong_digital_target_and_plain_evidence_cannot_enter_candidates():
    sc = actual_cloud_report()['scorecard']
    actions = [{'action_key': 'wrong-target', 'channel': 'salesforce', 'action': 'הכן הנחיה',
                'evidence': {'metric': 'לידים מיוחסים לדיגיטל', 'value': 4, 'target': 10}},
               {'action_key': 'plain-proof', 'channel': 'salesforce', 'action': 'הכן הנחיה',
                'evidence': '9 לידים ועוד Advertisement שיתברר כדיגיטלי מביאים ל-10'}]
    out = evidence.sanitize({'recommendations': actions}, scorecard=sc)
    assert {r['action_key'] for r in out['recommendations']}.isdisjoint({'wrong-target', 'plain-proof'})
    assert len([r for r in out['withheld_advice'] if r['reason'] == 'metric_evidence']) == 2


def test_offline_replay_preserves_date_and_never_calls_external_systems(tmp_path, monkeypatch):
    report = actual_cloud_report()
    input_file = tmp_path / 'input.json'
    input_file.write_text(json.dumps(report))
    snapshot_file = tmp_path / 'snapshot.json'
    snapshot_file.write_text(json.dumps({'networks': {}, 'period_days': 7, 'totals': {}}))
    def forbidden(*args, **kwargs): raise AssertionError('No API or fresh measurement allowed during replay')
    monkeypatch.setattr(council.urllib.request, 'urlopen', forbidden)
    monkeypatch.setattr(council.ma, 'snapshot', forbidden)
    monkeypatch.setattr(council.leads_source, 'count', forbidden)
    monkeypatch.setattr(council.seo_geo_source, 'fetch', forbidden)
    monkeypatch.setattr(council, 'run_council', forbidden)
    monkeypatch.setattr(council, '_today', lambda: '2026-09-14')
    result = council.replay_report(input_file, snapshot_file, tmp_path / 'output')
    assert result['date'] == '2026-09-13' and result['scorecard'] == report['scorecard']
    assert result['email_requested'] is False and result['replay']['new_measurements'] is False
    html = (tmp_path / 'output/report.html').read_text()
    assert '2026-09-13' in html and '2026-09-14' not in html
    assert '2026-09-13' in (tmp_path / 'output/report.md').read_text()


def test_rendered_rtl_blocks_and_numeric_cells_are_explicit():
    from html.parser import HTMLParser
    from council_html import BLOCKS
    class Audit(HTMLParser):
        def __init__(self): super().__init__(); self.blocks=[]; self.ltr_cells=0
        def handle_starttag(self, tag, attrs):
            attrs=dict(attrs)
            if tag in BLOCKS: self.blocks.append((tag, attrs))
            if tag=='td' and attrs.get('dir')=='ltr': self.ltr_cells+=1
    report = actual_cloud_report()
    html = council.render_html({'networks': {}, 'period_days': 7, 'totals': {}}, report['scorecard'], report['verdict'], [], report['cadence'], report_date=report['date'])
    audit=Audit();audit.feed(html)
    assert audit.blocks and audit.ltr_cells > 5
    for tag, attrs in audit.blocks:
        assert attrs.get('dir') in ('rtl','ltr'), tag
        assert 'direction:' in attrs.get('style','') and 'text-align:' in attrs['style'], tag
    assert 'engagement_rate unreliable' not in html and '<th>ER</th>' not in html
