"""Read-only aggregate cloud evidence. No post bodies, IDs or credentials."""
import collections
import datetime as dt
import json
import os
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from publishers import queue


def collect(request=None, now=None):
    request = request or queue._req
    result = {'schema_version': 1, 'generated_at': (now or dt.datetime.now(dt.timezone.utc)).isoformat(),
              'workflow_run_id': os.environ.get('GITHUB_RUN_ID'), 'source': 'Supabase post_approvals aggregate GET',
              'approvals': {'complete': False, 'pending_count': None, 'status_counts': None}}
    counts = collections.Counter(); networks = collections.Counter()
    try:
        for offset in range(0, 100000, 500):
            rows = request('GET', 'post_approvals', params={'select': 'status,network',
                'status': 'in.(pending,approved,failed)', 'order': 'id.asc', 'limit': '500', 'offset': str(offset)})
            if not isinstance(rows, list): raise ValueError('invalid response')
            for row in rows:
                if row.get('status') not in ('pending','approved','failed'): raise ValueError('invalid status')
                counts[row['status']] += 1
                if row['status'] == 'pending': networks[row.get('network') or 'unknown'] += 1
            if len(rows) < 500: break
        else: raise ValueError('pagination incomplete')
        result['approvals'] = {'complete': True, 'pending_count': counts['pending'],
                              'status_counts': dict(counts), 'pending_by_network': dict(networks)}
    except Exception as exc:
        result['approvals']['error_type'] = type(exc).__name__
    return result


if __name__ == '__main__':
    out = Path('reports/social-health-cloud.json'); out.parent.mkdir(exist_ok=True)
    data = collect(); out.write_text(json.dumps(data, ensure_ascii=False, indent=2))
    print(json.dumps(data, ensure_ascii=False))
    sys.exit(0 if data['approvals']['complete'] else 1)
