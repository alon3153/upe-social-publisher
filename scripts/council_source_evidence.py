"""Source units and provenance for the council; no API calls or score changes."""
import datetime
import json
import re
from pathlib import Path
from urllib.parse import urlsplit

HISTORY = Path(__file__).resolve().parent / 'aeo_daily_history.json'
WEEKLY_HISTORY = Path(__file__).resolve().parent / 'aeo_history.json'
EXPECTED_MODELS = {'claude', 'chatgpt', 'gemini'}
PRODUCT_SEARCH_ENGINES = ('claude', 'chatgpt', 'gemini')
PRODUCT_SEARCH_LABELS = {'claude': 'Claude', 'chatgpt': 'ChatGPT', 'gemini': 'Gemini'}
PRODUCT_SEARCH_MISSING = 'אין נתון'


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


def _history_rows(path):
    try:
        rows = json.loads(Path(path).read_text())
    except (OSError, ValueError):
        return []
    return rows if isinstance(rows, list) else []


def _product_search_value(block):
    """A measured product_search score, or None when this engine has no usable value.

    Degraded blocks and missing or non-numeric scores stay empty. Callers must
    not fill them from another engine or an older row.
    """
    if not isinstance(block, dict) or block.get('degraded'):
        return None
    value = block.get('product_search')
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return int(value) if isinstance(value, float) and value.is_integer() else value


def product_search_entry(row):
    """Scores from one history row. Engines absent from that row stay None."""
    if not isinstance(row, dict) or not isinstance(row.get('date'), str) or not row.get('date'):
        return None
    models = row.get('models') if isinstance(row.get('models'), dict) else {}
    entry = {'date': row['date'],
             'scores': {name: _product_search_value(models.get(name))
                        for name in PRODUCT_SEARCH_ENGINES}}
    recorded = row.get('product_search_source')
    if isinstance(recorded, str) and recorded.strip():
        entry['product_search_source'] = recorded.strip()
    return entry


def _product_search_entries(path, source):
    entries = []
    for row in _history_rows(path):
        entry = product_search_entry(row)
        if entry:
            entries.append(dict(entry, source=source))
    return entries


def _last_on_date(entries, date):
    found = [entry for entry in entries if entry['date'] == date]
    return found[-1] if found else None


def product_search_for_date(date, daily_path=None, weekly_path=None):
    """The product_search row for one date.

    The weekly history wins when both files have that date, so engines are
    never mixed across the two batteries. Within one file, the last appended
    row for the date is the one shown.
    """
    weekly = _last_on_date(_product_search_entries(weekly_path or WEEKLY_HISTORY, 'weekly'), date)
    if weekly:
        return weekly
    return _last_on_date(_product_search_entries(daily_path or HISTORY, 'daily'), date)


def latest_product_search(daily_path=None, weekly_path=None):
    """Newest product_search entry across the daily and weekly histories.

    A same-day tie uses the weekly battery. A missing engine on that entry
    stays missing; it is not filled from the other file or an older date.
    """
    weekly = _product_search_entries(weekly_path or WEEKLY_HISTORY, 'weekly')
    daily = _product_search_entries(daily_path or HISTORY, 'daily')
    dates = [entry['date'] for entry in weekly + daily]
    if not dates:
        return None
    newest = max(dates)
    return _last_on_date(weekly, newest) or _last_on_date(daily, newest)


_SOURCE_LABELS = {
    'weekly': 'שבועי',
    'daily': 'יומי',
    'שבועי': 'שבועי',
    'יומי': 'יומי',
}


def product_search_source_label(entry):
    """Hebrew battery label. A recorded product_search_source wins over the file."""
    if not isinstance(entry, dict):
        return None
    raw = entry.get('product_search_source') or entry.get('source')
    if not isinstance(raw, str) or not raw.strip():
        return None
    key = raw.strip()
    if key in _SOURCE_LABELS:
        return _SOURCE_LABELS[key]
    lowered = key.casefold().replace('\\', '/')
    if 'aeo_daily_history' in lowered:
        return 'יומי'
    if 'aeo_history' in lowered or lowered.endswith('/aeo_history.json'):
        return 'שבועי'
    return None


def format_product_search(entry):
    """Claude 24 · ChatGPT 21 · Gemini 18 (27.09.2026, שבועי). Missing engines say אין נתון."""
    if not entry:
        return PRODUCT_SEARCH_MISSING
    parts = []
    for name in PRODUCT_SEARCH_ENGINES:
        score = (entry.get('scores') or {}).get(name)
        shown = PRODUCT_SEARCH_MISSING if score is None else str(score)
        parts.append(f"{PRODUCT_SEARCH_LABELS[name]} {shown}")
    shown_date = datetime.date.fromisoformat(entry['date']).strftime('%d.%m.%Y')
    label = product_search_source_label(entry)
    stamp = f'{shown_date}, {label}' if label else shown_date
    return ' · '.join(parts) + f' ({stamp})'


def valid_week(window):
    try:
        return (datetime.date.fromisoformat(window['end']) -
                datetime.date.fromisoformat(window['start'])).days == 6 and window['days'] == 7
    except (KeyError, ValueError, TypeError):
        return False
