import json
import unittest
from scripts.social_health_snapshot import collect

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
