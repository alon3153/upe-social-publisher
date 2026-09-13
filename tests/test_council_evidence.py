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
