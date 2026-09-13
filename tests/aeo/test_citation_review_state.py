import datetime
import json

from scripts import citations_pipeline as cp


def item(**updates):
    value = dict(id='membership', title='Membership', state='awaiting_founder',
                 since='2026-07-31', action='Check membership', target_url='', kind='directory')
    return value | updates


def run_verify(tmp_path, value, response='Uproduction profile'):
    path = tmp_path / 'citations.json'
    path.write_text(json.dumps({'items': [value]}))
    cp.verify(path=path, fetch=lambda url: response, today='2026-09-13')
    return json.loads(path.read_text())['items'][0]


def test_successful_recheck_persists_without_state_transition(tmp_path):
    result = run_verify(tmp_path, item(state='verified_cited', target_url='https://example.com/profile'))
    assert result['last_check'] == '2026-09-13'
    assert result['last_check_result'] == 'cited'
    assert not cp._due_reverify(result, '2026-09-14')


def test_blocked_recheck_persists_without_false_success(tmp_path):
    result = run_verify(tmp_path, item(state='verified_cited', target_url='https://example.com/profile'),
                        'Just a moment - enable JavaScript and cookies')
    assert result['state'] == 'verified_cited'
    assert result['last_check_result'] == 'blocked'


def test_stale_unverifiable_item_becomes_review_not_founder_delay(tmp_path):
    result = run_verify(tmp_path, item())
    assert result['state'] == 'needs_verification'
    assert result['owner'] == 'automation'
    assert result['since'] == '2026-07-31'
    assert result['next_review_at'] == '2026-09-20'
    assert cp.overdue_reminders({'items': [result]}, now=datetime.datetime(2026, 9, 14)) == []
    assert 'Membership' in cp.digest_html({'items': [result]})


def test_review_can_advance_only_with_real_profile_evidence(tmp_path):
    result = run_verify(tmp_path, item(state='needs_verification', target_url='https://example.com/profile'))
    assert result['state'] == 'verified_cited'
    result = run_verify(tmp_path, item(state='needs_verification', target_url='https://example.com/profile'),
                        'Directory home')
    assert result['state'] == 'needs_verification'


def test_closed_items_are_not_reopened_or_mutated(tmp_path):
    value = item(state='closed_no_recontact')
    assert run_verify(tmp_path, value) == value
