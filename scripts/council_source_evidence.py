"""Source units and provenance for the council; no API calls or score changes."""
import datetime
import json
import re
from pathlib import Path
from urllib.parse import urlsplit

HISTORY = Path(__file__).resolve().parent / 'aeo_daily_history.json'
EXPECTED_MODELS = {'claude', 'chatgpt', 'gemini'}


def citation_basis(value):
    if not isinstance(value, str):
        return None
    value = value.strip()
    if re.fullmatch(r'(?:www\.)?upe\.co\.il/?', value, re.I):
        return 'grounded_source_domain'
    try:
        url = urlsplit(value)
        if url.scheme in ('https', 'http') and url.hostname in ('upe.co.il', 'www.upe.co.il'):
            return 'direct_url'
    except ValueError:
        pass
    return None


def engine_evidence(path=None, today=None):
    today = datetime.date.fromisoformat(today or datetime.date.today().isoformat())
    try:
        rows = json.loads(Path(path or HISTORY).read_text())
        latest = max(rows, key=lambda r: r.get('date', ''))
        age = (today - datetime.date.fromisoformat(latest['date'])).days
        if not 0 <= age <= 2:
            return {'ok': False, 'reason': 'AEO history outside 2-day freshness window'}
    except (OSError, ValueError, KeyError, TypeError):
        return {'ok': False, 'reason': 'AEO history unavailable or invalid'}
    engines = {}
    for name, model in latest.get('models', {}).items():
        if name not in EXPECTED_MODELS or model.get('degraded'):
            continue
        answers = [a for a in model.get('answers', [])
                   if a.get('grounded') is True and a.get('branded') is False]
        if not answers:
            continue
        direct = labels = 0
        for answer in answers:
            bases = {citation_basis(v) for v in answer.get('cited_urls', [])}
            if 'direct_url' in bases:
                direct += 1
            elif 'grounded_source_domain' in bases:
                labels += 1
        engines[name] = {'grounded_nonbranded_answers': len(answers),
                         'direct_url_answers': direct, 'source_domain_answers': labels,
                         'cited': direct + labels > 0}
    complete = set(engines) == EXPECTED_MODELS
    return {'ok': complete, 'reason': '' if complete else 'Partial grounded engine coverage',
            'date': latest['date'], 'battery_version': latest.get('battery_version'),
            'engines': engines, 'measured_engines': len(engines),
            'cited_engines': sum(v['cited'] for v in engines.values()),
            'definition': 'Distinct engines citing UPE in grounded nonbranded answers; direct URLs and grounding source-domain labels distinguished. Not recommendation rank.'}


def valid_week(window):
    try:
        return (datetime.date.fromisoformat(window['end']) -
                datetime.date.fromisoformat(window['start'])).days == 6 and window['days'] == 7
    except (KeyError, ValueError, TypeError):
        return False
