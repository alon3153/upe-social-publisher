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


def unbranded_mention_rates(path=None, date=None):
    """Info-only unbranded mention rates from an AEO history row.

    Returns None when that date has no mention_rate_nonbranded values. The
    council score counts engines checked, not this rate.
    """
    if not date:
        return None
    try:
        rows = json.loads(Path(path or HISTORY).read_text())
        row = next(item for item in rows if item.get("date") == date)
    except (OSError, ValueError, StopIteration, TypeError):
        return None
    by_engine = {}
    mentioned = measured = 0
    have_counts = True
    for name, block in (row.get("models") or {}).items():
        if name not in EXPECTED_MODELS or not isinstance(block, dict) or block.get("degraded"):
            continue
        rate = block.get("mention_rate_nonbranded")
        if isinstance(rate, bool) or not isinstance(rate, (int, float)):
            continue
        by_engine[name] = rate
        got = block.get("mentioned_nonbranded")
        asked = block.get("n_nonbranded")
        if isinstance(got, int) and not isinstance(got, bool) and isinstance(asked, int) and asked > 0:
            mentioned += got
            measured += asked
        else:
            have_counts = False
    if not by_engine:
        return None
    if have_counts and measured:
        pooled = round(100.0 * mentioned / measured, 1)
    else:
        pooled = round(sum(by_engine.values()) / len(by_engine), 1)
        mentioned = measured = None
    return {"date": date, "by_engine": by_engine, "pooled_pct": pooled,
            "mentioned_nonbranded": mentioned, "n_nonbranded": measured}


def valid_week(window):
    try:
        return (datetime.date.fromisoformat(window['end']) -
                datetime.date.fromisoformat(window['start'])).days == 6 and window['days'] == 7
    except (KeyError, ValueError, TypeError):
        return False
