"""Read-only cloud evidence for post_approvals.

The default run writes aggregate counts only (status and network).
``--failed-ids`` adds at most 20 rows with status=failed, and only the
columns id, day, network, account, lang, status. No captions, errors, or credentials.
"""
import collections
import datetime as dt
import json
import os
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from publishers import queue

FAILED_COLUMNS = ('id', 'day', 'network', 'account', 'lang', 'status')
FAILED_SELECT = ','.join(FAILED_COLUMNS)
FAILED_LIMIT = 20


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


def _clean_failed_row(row):
    if not isinstance(row, dict) or row.get('status') != 'failed':
        raise ValueError('invalid row')
    return {key: row.get(key) for key in FAILED_COLUMNS}


def collect_failed_ids(request=None):
    """GET failed approval identities only. Never returns caption, error, or tokens.

    This query is unchanged: status=eq.failed, limit 20, no created_at filter.
    The 3-day window lives in the watchdog email, not in this key.
    """
    request = request or queue._req
    rows = request('GET', 'post_approvals', params={
        'select': FAILED_SELECT,
        'status': 'eq.failed',
        'order': 'id.asc',
        'limit': str(FAILED_LIMIT),
    })
    if not isinstance(rows, list):
        raise ValueError('invalid response')
    return [_clean_failed_row(row) for row in rows[:FAILED_LIMIT]]


def collect_stale_failed_ids(request=None):
    """Count every status=failed row, any age, and return a capped identity list.

    ``count`` is the full total. ``rows`` is at most FAILED_LIMIT. Same columns
    as failed_rows: no caption, error, or tokens, and no created_at filter.
    """
    request = request or queue._req
    kept = []
    total = 0
    for offset in range(0, 100000, 500):
        rows = request('GET', 'post_approvals', params={
            'select': FAILED_SELECT,
            'status': 'eq.failed',
            'order': 'id.asc',
            'limit': '500',
            'offset': str(offset),
        })
        if not isinstance(rows, list):
            raise ValueError('invalid response')
        for row in rows:
            cleaned = _clean_failed_row(row)
            total += 1
            if len(kept) < FAILED_LIMIT:
                kept.append(cleaned)
        if len(rows) < 500:
            break
    else:
        raise ValueError('pagination incomplete')
    return {'complete': True, 'limit': FAILED_LIMIT, 'count': total, 'rows': kept}


def _load_object(path):
    try:
        data = json.loads(Path(path).read_text())
    except Exception:
        return None
    return data if isinstance(data, dict) else None


def _summary_cell(value):
    text = '' if value is None else str(value)
    text = text.replace('\r', ' ').replace('\n', ' ').replace('|', '\\|')
    return text[:80]


def _summary_table(rows):
    lines = ['| id | day | network | account | lang | status |',
             '| --- | --- | --- | --- | --- | --- |']
    for row in rows:
        cells = ' | '.join(_summary_cell(row.get(key)) for key in FAILED_COLUMNS)
        lines.append(f'| {cells} |')
    return lines


def _summary_block(title, block, intro):
    lines = ['', f'### {title}', '']
    if not block.get('complete'):
        lines.append(
            f"Read failed ({block.get('error_type') or 'error'}). No row content was written.")
        return lines
    rows = block.get('rows') or []
    lines.append(intro)
    lines.append('')
    if not rows:
        lines.append('No failed rows.')
    else:
        lines.extend(_summary_table(rows))
        lines.append('')
        lines.append(f"{block.get('count', len(rows))} row(s).")
    return lines


def write_failed_summary(block, stale=None):
    """Append markdown tables to the GitHub Actions run summary when one is open."""
    path = os.environ.get('GITHUB_STEP_SUMMARY')
    if not path:
        return
    lines = _summary_block(
        'Failed post_approvals', block,
        f"Read-only rows with `status=failed` (cap {block.get('limit', FAILED_LIMIT)}). "
        'Columns: id, day, network, account, lang, status.')
    if stale is not None:
        lines.extend(_summary_block(
            'Failed post_approvals still open (all ages)', stale,
            f"All rows still `status=failed`, any age "
            f"(list cap {stale.get('limit', FAILED_LIMIT)}; count is the full total)."))
    with open(path, 'a', encoding='utf-8') as handle:
        handle.write('\n'.join(lines) + '\n')


def _failed_block(request, collector, page_count=False):
    try:
        loaded = collector(request)
        if page_count:
            rows = loaded
            return {'complete': True, 'limit': FAILED_LIMIT, 'count': len(rows), 'rows': rows}
        return loaded
    except Exception as exc:
        return {'complete': False, 'limit': FAILED_LIMIT, 'count': None,
                'rows': [], 'error_type': type(exc).__name__}


def export_failed_ids(cloud_path='reports/social-health-cloud.json',
                      feed_path='reports/sp_watchdog.json', request=None):
    """Merge failed-id lists into the watchdog artifact files.

    ``failed_rows`` stays the existing capped query. ``stale_failed_rows`` is
    every row still failed, with a full count and the same column cap.
    """
    block = _failed_block(request, collect_failed_ids, page_count=True)
    stale = _failed_block(request, collect_stale_failed_ids, page_count=False)
    cloud = Path(cloud_path)
    data = _load_object(cloud) or {}
    data['failed_rows'] = block
    data['stale_failed_rows'] = stale
    cloud.parent.mkdir(parents=True, exist_ok=True)
    cloud.write_text(json.dumps(data, ensure_ascii=False, indent=2))
    feed = Path(feed_path)
    if feed.exists():
        feed_data = _load_object(feed)
        if feed_data is not None:
            feed_data['failed_rows'] = block
            feed_data['stale_failed_rows'] = stale
            feed.write_text(json.dumps(feed_data, ensure_ascii=False, indent=2))
    write_failed_summary(block, stale)
    return block


if __name__ == '__main__':
    if '--failed-ids' in sys.argv:
        block = export_failed_ids()
        print(json.dumps({'failed_rows': {k: block[k] for k in ('complete', 'limit', 'count', 'error_type') if k in block}},
                         ensure_ascii=False))
        sys.exit(0 if block['complete'] else 1)
    out = Path('reports/social-health-cloud.json'); out.parent.mkdir(exist_ok=True)
    data = collect(); out.write_text(json.dumps(data, ensure_ascii=False, indent=2))
    print(json.dumps(data, ensure_ascii=False))
    sys.exit(0 if data['approvals']['complete'] else 1)
