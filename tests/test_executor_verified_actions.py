import json
from unittest.mock import patch

from scripts import executor as e


def test_verified_work_and_explicit_legacy_duplicates_are_not_reselected(tmp_path):
    (tmp_path / 'council_verified_actions.json').write_text(json.dumps({
        'completed_action_keys': ['seo-service-page-optimization'],
        'superseded_initiatives': {'legacy': {'evidence': 'verified live audit'}},
    }))
    items = {key: {'id': key, 'status': 'todo', 'history': ['keep'], **extra}
             for key, extra in {
                 'done': {'action_key': 'seo-service-page-optimization'},
                 'legacy': {},
                 'open': {'action_key': 'salesforce-attribution-fix'},
                 'approved': {},
             }.items()}
    with patch.object(e, 'STATE_DIR', tmp_path):
        selected = e.pick_to_advance(items, {'approved'}, 6)
    assert [item['id'] for item in selected] == ['open']
    assert items['done']['status'] == items['legacy']['status'] == 'todo'
    assert items['done']['history'] == ['keep']
    assert items['approved']['status'] == 'approved'


def test_daily_sync_does_not_reactivate_verified_work(tmp_path):
    (tmp_path / 'council_verified_actions.json').write_text(json.dumps({
        'completed_action_keys': ['done'],
    }))
    recs = tmp_path / 'recommendations.json'
    recs.write_text(json.dumps({'recommendations': [{
        'action': 'Another wording for completed audit', 'action_key': 'done',
    }]}))
    with patch.multiple(e, STATE_DIR=tmp_path, RECS_PATH=recs):
        items, error = e.sync_backlog({})
        assert error is None and len(items) == 1
        assert e.pick_to_advance(items, set(), 6) == []


def test_missing_ledger_does_not_hide_unresolved_work(tmp_path):
    item = {'id': 'open', 'status': 'todo'}
    with patch.object(e, 'STATE_DIR', tmp_path):
        assert e.pick_to_advance({'open': item}, set(), 6) == [item]
