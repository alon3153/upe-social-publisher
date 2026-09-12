import datetime
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import council
import executor
import metricool_analytics as ma


class ImprovementTests(unittest.TestCase):
    def test_partial_cadence_keeps_other_network_caps(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'directives.json'
            path.write_text(json.dumps({'channel_cadence': {'facebook': {'max_posts_per_week': 2}}}))
            with patch.object(council, 'DIRECTIVES', path):
                _, caps = council.apply_auto_fixes({'channel_cadence': {'linkedin': {'max_posts_per_week': 4}}}, True)
            self.assertEqual(caps['facebook']['max_posts_per_week'], 2)
            self.assertEqual(caps['linkedin']['max_posts_per_week'], 4)

    def test_failed_review_does_not_overwrite_directives(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'directives.json'
            original = json.dumps({'directives': [{'action': 'keep'}], 'channel_cadence': {}})
            path.write_text(original)
            with patch.object(council, 'DIRECTIVES', path):
                council.apply_auto_fixes({'error': 'upstream unavailable'}, False)
            self.assertEqual(path.read_text(), original)

    def test_renamed_initiative_keeps_work_and_approval_identity(self):
        old = {'id': 'original-id', 'title': 'old title', 'action_key': 'seo-service',
               'channel': 'google_organic', 'status': 'awaiting_approval', 'revisions': 2, 'history': ['draft']}
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'recommendations.json'
            path.write_text(json.dumps({'recommendations': [{'action': 'rewritten title',
                'action_key': 'seo-service', 'channel': 'google_organic', 'priority': 'P0'}]}))
            with patch.object(executor, 'RECS_PATH', path):
                result, _ = executor.sync_backlog({'original-id': old})
            self.assertEqual(list(result), ['original-id'])
            self.assertEqual(result['original-id']['history'], ['draft'])
            self.assertEqual(result['original-id']['status'], 'awaiting_approval')

    def test_omission_is_not_cancellation(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'recommendations.json'
            path.write_text('{}')
            with patch.object(executor, 'RECS_PATH', path):
                result, _ = executor.sync_backlog({'x': {'id': 'x', 'status': 'in_progress'}})
            self.assertEqual(result['x']['status'], 'in_progress')

    def test_ready_and_revision_capped_work_is_parked(self):
        work = {'a': {'id': 'a', 'status': 'awaiting_approval', 'revisions': 1},
                'b': {'id': 'b', 'status': 'in_progress', 'revisions': executor.MAX_REVISIONS},
                'c': {'id': 'c', 'status': 'todo', 'revisions': 0}}
        self.assertEqual([x['id'] for x in executor.pick_to_advance(work, set(), 6)], ['c'])

    def test_previous_period_is_separate_and_failure_is_unknown(self):
        end = datetime.datetime(2026, 9, 5, 8)
        calls = []
        def pull(net, frm, to, *args, **kwargs):
            calls.append((frm, to))
            if net == 'tiktok':
                raise TimeoutError('unavailable')
            return []
        with patch.object(ma, '_load_creds', return_value=('token', 'uid', 'bid')), patch.object(ma, 'pull_posts', side_effect=pull):
            result = ma.snapshot(7, end=end)
        self.assertTrue(all(pair == (end - datetime.timedelta(days=7), end) for pair in calls))
        self.assertFalse(result['networks']['tiktok']['ok'])
        self.assertTrue(result['networks']['linkedin']['ok'])
        self.assertEqual(result['unavailable_networks'], ['tiktok'])

    def test_unreliable_facebook_er_excluded_from_total(self):
        def pull(net, *args, **kwargs):
            if net == 'facebook':
                return [{'impressions': 39, 'interactions': 41}]
            if net == 'linkedin':
                return [{'impressions': 100, 'interactions': 2}]
            return []
        with patch.object(ma, '_load_creds', return_value=('token', 'uid', 'bid')), patch.object(ma, 'pull_posts', side_effect=pull):
            result = ma.snapshot()
        self.assertEqual(result['totals']['engagement_rate_pct'], 2.0)
        self.assertEqual(result['totals']['interactions'], 43)

    def test_invalid_api_payload_is_failure_not_empty_activity(self):
        with patch.object(ma, '_req', return_value={'error': 'invalid credentials'}):
            with self.assertRaises(ValueError):
                ma.pull_posts('tiktok', datetime.datetime.now(), datetime.datetime.now(), 't', 'u', 'b', strict=True)

    def test_existing_snapshot_score_is_unchanged(self):
        cur = json.loads((council.ROOT / 'reports/metrics/2026-09-11.json').read_text())
        score = council.build_scorecard(cur, cur, cur['leads'], cur['seo_geo'])
        self.assertEqual(score['weighted'], 88)

    def test_prompt_formats_with_canonical_facts_and_measurement_policy(self):
        rendered = council.COUNCIL_PROMPT.format(data='{}', scorecard='{}', site_inventory='{}', blog_hint=100)
        self.assertIn('1,500+ events', rendered)
        self.assertIn('action_key', rendered)
        self.assertIn('Never change KPI targets/weights', rendered)


if __name__ == '__main__':
    unittest.main()
