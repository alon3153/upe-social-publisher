import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from scripts.social_health_snapshot import (
    collect, collect_failed_ids, collect_stale_failed_ids, export_failed_ids)

class SnapshotTests(unittest.TestCase):
    def test_paginated_aggregate_only(self):
        calls=[]
        def read(method, path, params):
            calls.append((method,params))
            return [{'status':'pending','network':'instagram','secret':'MUST_NOT_EXPORT'}]*500 if params['offset']=='0' else [{'status':'failed','network':'linkedin'}]
        result=collect(read)
        self.assertEqual(result['approvals']['pending_count'],500)
        self.assertEqual(len(calls),2)
        self.assertTrue(all(c[0]=='GET' for c in calls))
        self.assertNotIn('MUST_NOT_EXPORT',json.dumps(result))
    def test_failure_unknown_and_sanitized(self):
        def fail(*a,**k): raise RuntimeError('token SECRET')
        result=collect(fail)
        self.assertFalse(result['approvals']['complete'])
        self.assertIsNone(result['approvals']['pending_count'])
        self.assertNotIn('SECRET',json.dumps(result))
    def test_zero_is_measured(self):
        self.assertEqual(collect(lambda *a,**k: [])['approvals']['pending_count'],0)

    def test_failed_ids_are_identity_columns_only(self):
        calls = []
        def read(method, path, params):
            calls.append((method, path, dict(params)))
            return [{
                'id': 'row-1', 'day': 48, 'network': 'facebook', 'account': 'main',
                'lang': 'he', 'status': 'failed',
                'caption': 'POST TEXT', 'error': 'token SECRET', 'access_token': 'abc',
            }]
        rows = collect_failed_ids(read)
        self.assertEqual(len(calls), 1)
        method, path, params = calls[0]
        self.assertEqual(method, 'GET')
        self.assertEqual(path, 'post_approvals')
        self.assertEqual(params['select'], 'id,day,network,account,lang,status')
        self.assertEqual(params['status'], 'eq.failed')
        self.assertEqual(params['limit'], '20')
        self.assertNotIn('*', params['select'])
        for banned in ('caption', 'error', 'token', 'access_token'):
            self.assertNotIn(banned, params['select'])
        self.assertEqual(rows, [{
            'id': 'row-1', 'day': 48, 'network': 'facebook',
            'account': 'main', 'lang': 'he', 'status': 'failed',
        }])
        blob = json.dumps(rows)
        self.assertNotIn('POST TEXT', blob)
        self.assertNotIn('SECRET', blob)
        self.assertNotIn('caption', blob)

    def test_failed_ids_capped_at_20(self):
        def read(method, path, params):
            self.assertEqual(params['limit'], '20')
            return [{
                'id': i, 'day': 1, 'network': 'facebook', 'account': 'a',
                'lang': 'he', 'status': 'failed', 'caption': 'POST TEXT',
            } for i in range(25)]
        rows = collect_failed_ids(read)
        self.assertEqual(len(rows), 20)
        self.assertEqual([row['id'] for row in rows], list(range(20)))
        self.assertNotIn('POST TEXT', json.dumps(rows))

    def test_export_writes_artifact_and_summary_without_secrets(self):
        def read(method, path, params):
            return [{
                'id': 'row-9', 'day': 12, 'network': 'linkedin', 'account': 'alon|x',
                'lang': 'he\nsecret', 'status': 'failed',
                'caption': 'POST TEXT', 'error': 'token SECRET',
            }]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            cloud = root / 'social-health-cloud.json'
            feed = root / 'sp_watchdog.json'
            summary = root / 'summary.md'
            cloud.write_text(json.dumps({'approvals': {'pending_count': 3, 'secret': 'MUST_NOT_TOUCH'}}))
            feed.write_text(json.dumps({'status': 'ok', 'source_key': 'sp_watchdog'}))
            summary.write_text('earlier\n')
            with patch.dict(os.environ, {'GITHUB_STEP_SUMMARY': str(summary)}):
                block = export_failed_ids(cloud, feed, read)
            cloud_data = json.loads(cloud.read_text())
            feed_data = json.loads(feed.read_text())
            summary_text = summary.read_text()
            self.assertTrue(block['complete'])
            self.assertEqual(block['count'], 1)
            self.assertEqual(cloud_data['approvals']['pending_count'], 3)
            self.assertEqual(cloud_data['failed_rows']['rows'][0]['id'], 'row-9')
            self.assertEqual(feed_data['status'], 'ok')
            self.assertEqual(feed_data['failed_rows']['rows'][0]['status'], 'failed')
            self.assertIn('earlier', summary_text)
            self.assertIn('row-9', summary_text)
            self.assertIn('alon\\|x', summary_text)
            self.assertNotIn('he\nsecret', summary_text)
            combined = cloud.read_text() + feed.read_text() + summary_text
            self.assertNotIn('POST TEXT', combined)
            self.assertNotIn('SECRET', combined)
            self.assertNotIn('caption', combined)
            self.assertNotIn('MUST_NOT_TOUCH', summary_text)

    def test_failed_export_failure_is_sanitized_and_preserves_artifact(self):
        def fail(*args, **kwargs):
            raise RuntimeError('token SECRET')
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            cloud = root / 'social-health-cloud.json'
            missing_feed = root / 'sp_watchdog.json'
            summary = root / 'summary.md'
            cloud.write_text(json.dumps({'approvals': {'pending_count': 1}}))
            with patch.dict(os.environ, {'GITHUB_STEP_SUMMARY': str(summary)}):
                block = export_failed_ids(cloud, missing_feed, fail)
            text = cloud.read_text() + summary.read_text()
            self.assertFalse(block['complete'])
            self.assertEqual(block['error_type'], 'RuntimeError')
            self.assertEqual(block['rows'], [])
            self.assertEqual(json.loads(cloud.read_text())['approvals']['pending_count'], 1)
            self.assertFalse(missing_feed.exists())
            self.assertIn('RuntimeError', summary.read_text())
            self.assertNotIn('SECRET', text)
            stale = json.loads(cloud.read_text())['stale_failed_rows']
            self.assertFalse(stale['complete'])
            self.assertEqual(stale['error_type'], 'RuntimeError')
            self.assertNotIn('SECRET', json.dumps(stale))

    def test_stale_failed_rows_count_every_age_and_keep_recent_query(self):
        calls = []

        def read(method, path, params):
            calls.append((method, path, dict(params)))
            if params.get('limit') == '20':
                assert 'created_at' not in params
                assert 'offset' not in params
                return [{
                    'id': 'recent-only-shape', 'day': 1, 'network': 'facebook',
                    'account': 'a', 'lang': 'he', 'status': 'failed',
                    'caption': 'POST TEXT',
                }]
            assert params['limit'] == '500'
            assert params['status'] == 'eq.failed'
            assert params['select'] == 'id,day,network,account,lang,status'
            assert 'created_at' not in params
            offset = int(params['offset'])
            if offset == 0:
                return [{
                    'id': f'id-{i}', 'day': i, 'network': 'facebook', 'account': 'a',
                    'lang': 'he', 'status': 'failed', 'error': 'SECRET', 'caption': 'POST TEXT',
                } for i in range(500)]
            if offset == 500:
                return [{
                    'id': 'old-d4262229', 'day': 48, 'network': 'facebook',
                    'account': 'uproduction_spain', 'lang': 'es', 'status': 'failed',
                }]
            return []

        listed = collect_stale_failed_ids(read)
        self.assertEqual(listed['count'], 501)
        self.assertEqual(len(listed['rows']), 20)
        self.assertEqual(listed['rows'][0]['id'], 'id-0')
        self.assertNotIn('SECRET', json.dumps(listed))
        self.assertNotIn('POST TEXT', json.dumps(listed))
        self.assertTrue(all(call[2].get('limit') == '500' for call in calls))

        calls.clear()
        with tempfile.TemporaryDirectory() as directory:
            cloud = Path(directory) / 'social-health-cloud.json'
            export_failed_ids(cloud, Path(directory) / 'missing.json', read)
            saved = json.loads(cloud.read_text())
        recent = next(params for _method, _path, params in calls if params.get('limit') == '20')
        assert 'created_at' not in recent
        assert recent['status'] == 'eq.failed'
        self.assertEqual(saved['failed_rows']['count'], 1)
        self.assertEqual(saved['failed_rows']['rows'][0]['id'], 'recent-only-shape')
        self.assertEqual(saved['stale_failed_rows']['count'], 501)
        self.assertEqual(len(saved['stale_failed_rows']['rows']), 20)
