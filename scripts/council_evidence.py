"""Evidence gates for council prose; never adjusts input metrics or their scores."""
import copy
import json
import re
from pathlib import Path
from urllib.parse import unquote, urlsplit

STATE = Path(__file__).resolve().parent.parent / 'state' / 'council_verified_actions.json'
NOTES = {
    'period': 'מדדי הפוסטים הם ערכים מצטברים לפי מועד פרסום; אין להסיק שפוסט יצא מהחלון או שהוא סיבת הירידה ללא בדיקת שני החלונות.',
    'approval': 'אישור יוזמה או מסמך תסריטים אינו אישור לפוסט מוגמר; יש לבדוק את הנכס ואת סטטוס האישור לפני פרסום.',
    'attribution': 'ייחוס מקור הליד מציג חלק מסך הלידים. שיעור המרה ורווחיות ערוץ אינם ידועים ללא נתוני תנועה והמרות תואמים; Web אינו בהכרח Google Organic.',
    'search_volume': 'נתוני GSC מתארים חשיפות של האתר בתקופה שנמדדה, ולא נפח חיפושים חודשי בשוק.',
    'aeo_scope': 'אזכורי AI נספרים לפי השאלות ומנוע הבדיקה שבמקור; מספר אזכורים אינו מספר מנועי AI.',
    'forecast': 'אין בנתונים בסיס לתחזית עוקבים או לתוספת מובטחת של קליקים ולידים. צעדי צמיחה הם ניסויים למדידה.',
    'benchmark': 'טענות על אלגוריתמים, שעות מועדפות ובנצ׳מרקים דורשות מקור מאומת; יעילותן עבור UPE דורשת ניסוי.',
    'site_evidence': 'המלצות לשינוי אתר חייבות להפנות לפער מתועד שטרם טופל ולכבד את מועד השינוי האחרון.',
}


def _key(url):
    parsed = urlsplit(str(url))
    return unquote(parsed.path).rstrip('/')


def load_state(path=None):
    try:
        result = json.loads(Path(path or STATE).read_text())
        return result if isinstance(result, dict) else {}
    except (OSError, ValueError):
        return {}


def _issue(text, sourced=False):
    text = str(text)
    if re.search(r'(?:נובעת|נובע|עזב|עזבה|יצא|יצאה|rolling out).{0,90}(?:חלון|מחזור)|(?:YouTube|יוטיוב).{0,100}(?:עזב|יצא|יצאה)', text, re.I):
        return 'period'
    if re.search(r'(?:אשר|שגר|publish).{0,30}(?:b7c0af4b|id\s+[a-f0-9]{8})', text, re.I):
        return 'approval'
    if re.search(r'חיפושים\s*(?:חודשיים|לחודש|/חודש)|חיפושים/חודש|monthly search(?:es| volume)', text, re.I):
        return 'search_volume'
    if re.search(r'ערוץ\s+(?:ה)?ממיר|proven converting|(?:Web|ווב).{0,100}(?:conversion rate|שיעור המרה|33%).{0,60}(?:מוכח|conversion|המרה)|(?:המרה|conversion).{0,60}(?:33%|3/9)', text, re.I):
        return 'attribution'
    if re.search(r'(?:[47]\s*(?:מנועי|מנועים)|[47]\s+AI engines)', text, re.I):
        return 'aeo_scope'
    if re.search(r'500\s*K|500[,.]?000|500 אלף|(?:יעד|תוספת|להוסיף|חדשים|gain).{0,30}\d[\d,\-– ]*.{0,20}(?:עוקבים|followers|קליקים)|\d[\d,\-– ]*\s*(?:followers|עוקבים)\s*חדשים|(?:ישיר|ישירה|מובטח).{0,30}(?:סגיר|לידים)', text, re.I):
        return 'forecast'
    if not sourced and re.search(r'algorithm memory|notification priority|reach גבוה משמעותית|האלגוריתם|אלגוריתם.{0,40}(?:מעדיף|מתגמל|זוכר)|(?:מחקר|בנצ.?מרק|benchmark).{0,50}2026|פיק הפעילות|(?:מעל|עולה על).{0,30}(?:2.?3%|בנצ)', text, re.I):
        return 'benchmark'
    return None


def sanitize(verdict, *, state=None, shipped=None, completed_keys=(), source_urls=()):
    """Drop unsupported advice, explaining omissions instead of asserting generated claims.

    Source URLs must originate in provider web-search citations, never model-written URLs.
    On-site changes also need an independently recorded open audit; a prose 'evidence' label
    cannot authorize rewriting a completed page.
    """
    out = copy.deepcopy(verdict)
    if out.get('error'):
        return out
    state = load_state() if state is None else state
    shipped = shipped or []
    pages = state.get('page_audits', [])
    completed = set(completed_keys) | set(state.get('completed_action_keys', []))
    notes = list(out.get('evidence_notes', []))
    rejected = list(out.get('withheld_advice', []))

    def note(issue):
        if NOTES[issue] not in notes:
            notes.append(NOTES[issue])

    for field in ('verdict_summary', 'what_worked', 'what_failed', 'follower_growth_plan', 'leads_actions'):
        value = out.get(field, '' if field == 'verdict_summary' else [])
        entries = [value] if isinstance(value, str) else value if isinstance(value, list) else []
        clean = []
        for entry in entries:
            issue = _issue(entry)
            if field in ('leads_actions', 'follower_growth_plan') and re.search(r'H1|title|schema|FAQPage|llms|word.count|עדכן|הוסף|הרחב|ערוך|אופטימיזציה|קישור', str(entry), re.I):
                if any(_key(p['url']).lstrip('/') in unquote(str(entry)) and not p.get('update_required') for p in pages):
                    issue = 'site_evidence'
            if issue:
                note(issue)
            elif isinstance(entry, str):
                clean.append(entry)
        out[field] = (' '.join(clean) or 'המסקנות המאומתות מופיעות בנתונים ובהערות המדידה להלן.') if field == 'verdict_summary' else clean

    for field in ('recommendations', 'auto_fixes'):
        clean = []
        for action in out.get(field, []) or []:
            if not isinstance(action, dict):
                continue
            action_key = action.get('action_key')
            text = ' '.join(str(action.get(k, '')) for k in ('action', 'detail', 'expected_impact', 'success_metric', 'evidence'))
            sourced = action.get('evidence_url') in source_urls
            issue = _issue(text, sourced=sourced)
            target = action.get('target_url', '')
            matched = [p for p in pages if _key(p['url']) and (_key(p['url']) in unquote(text) or _key(p['url']) == _key(target))]
            onsite = action.get('channel', '').startswith('google_organic') or bool(target and urlsplit(target).hostname == 'upe.co.il')
            if action_key in completed:
                issue = 'site_evidence'
            if onsite:
                needs_change = bool(re.search(r'H1|title|schema|FAQPage|llms|word.count|מילים|עדכן|הוסף|הרחב|ערוך|אופטימיזציה|קישור', text, re.I))
                if needs_change:
                    audit = next((p for p in pages if _key(p['url']) == _key(target)), None)
                    recently_changed = any(_key(p['url']) == _key(target) and p.get('cooldown') is not False for p in shipped)
                    if (not audit or audit.get('update_required') is not True or not audit.get('evidence') or recently_changed):
                        issue = 'site_evidence'
                elif matched and any(p.get('completed_at') for p in matched):
                    issue = 'site_evidence'
            if issue:
                note(issue)
                rejected.append({'action_key': action_key, 'reason': issue})
                continue
            clean.append(action)
        out[field] = clean[:5] if field == 'recommendations' else clean
    for cfg in (out.get('channel_cadence') or {}).values():
        if isinstance(cfg, dict) and _issue(cfg.get('reason', '')):
            cfg['reason'] = 'מכסה מוצעת לבדיקה בתקופת המדידה; אין מסקנה סיבתית על אלגוריתם.'
    out['evidence_notes'] = notes
    out['withheld_advice'] = rejected
    return out
