import json
import tempfile
from pathlib import Path
from unittest.mock import patch
from scripts import watchdog

def test_full_feed_recovery_and_sanitization():
    with tempfile.TemporaryDirectory() as d, patch.object(watchdog,'ROOT',d):
        watchdog.write_health_feed(['https://private.invalid/authorize?token=SECRET'])
        p=Path(d)/'reports/sp_watchdog.json'
        assert json.loads(p.read_text())['status']=='partial'
        assert 'SECRET' not in p.read_text()
        watchdog.write_health_feed(['🔴 failure'])
        assert json.loads(p.read_text())['status']=='error'
        assert json.loads(p.read_text())['findings'][0]['severity']=='crit'
        watchdog.write_health_feed([])
        assert json.loads(p.read_text())['status']=='ok'
