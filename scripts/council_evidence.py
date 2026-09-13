"""Evidence gates for council prose; never adjusts input metrics or their scores."""
import copy
import json
import re
from pathlib import Path
from urllib.parse import unquote, urlsplit

STATE = Path(__file__).resolve().parent.parent / 'state' / 'council_verified_actions.json'
NOTES = {
    'metric_evidence': 'המלצות ללא התאמה למדד, לערך וליעד שנמדדו לא הועברו לביצוע. מועמדת לניסוי אינה הוכחה להשפעה.',
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
    if re.search(r'ROI|תשואה|יתרון תחרותי מוכח|היעד.{0,30}הושג בפועל|הליד החסר.{0,50}(?:כבר|מסומן)|יעד.{0,15}10.{0,10}לידים דיגיטליים|מצאתי.{0,15}(?:Google|גוגל)', text, re.I):
        return 'attribution'
    if re.search(r'\d[\d,\-– ]*\s*חיפושים|חיפושים.{0,12}\d', text, re.I):
        return 'search_volume'
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


def sanitize(verdict, *, state=None, shipped=None, completed_keys=(), source_urls=(), scorecard=None):
    """Drop unsupported advice, explaining omissions instead of asserting generated claims.

    Source URLs must originate in provider web-search citations, never model-written URLs.
    On-site changes also need an independently recorded open audit; a prose 'evidence' label
    cannot authorize rewriting a completed page.
    """
    out = copy.deepcopy(verdict)
    if out.get('error'):
        if scorecard is not None:
            out.update(scorecard_narrative(scorecard))
            out['narrative_source'] = 'deterministic_scorecard'
        return out
    state = load_state() if state is None else state
    shipped = shipped or []
    source_urls = set(source_urls) | set(out.get('verified_source_urls', []))
    out['verified_source_urls'] = sorted(source_urls)
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
            validated_metric = None
            if scorecard is not None:
                validated_metric = metric_evidence(action.get('evidence'), scorecard)
                if validated_metric is None:
                    issue = 'metric_evidence'
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
            if scorecard is not None:
                action['evidence'] = validated_metric
                action['status'] = 'candidate'
                action['expected_impact'] = 'מועמדת לניסוי; אין תחזית לתוספת לידים, קליקים או הכנסה.'
                action['detail'] = 'הצעה לבדיקה על בסיס המדד המתועד; לא בוצע שינוי.'
                action['success_metric'] = f"{validated_metric['metric']}: בסיס {validated_metric['value']}; יעד המדד {validated_metric['target']}. יש להשוות תקופות תואמות."
            clean.append(action)
        out[field] = clean[:5] if field == 'recommendations' else clean
    for cfg in (out.get('channel_cadence') or {}).values():
        if isinstance(cfg, dict):
            cfg['reason'] = 'מכסה מוצעת לבדיקה בתקופת המדידה; אין מסקנה סיבתית על אלגוריתם.'
    if scorecard is not None:
        out.update(scorecard_narrative(scorecard))
        out['leads_actions'] = factual_lead_actions(state)
        out['follower_growth_plan'] = []
        out['narrative_source'] = 'deterministic_scorecard'
        out['deliverables'] = copy.deepcopy(state.get('deliverables', []))
        if not out.get('recommendations'):
            out['recommendations'] = measured_candidates(scorecard, completed)
        note('attribution')
        note('search_volume')
        note('forecast')
    out['evidence_notes'] = notes
    out['withheld_advice'] = rejected
    return out


def scorecard_narrative(scorecard):
    """Describe measured rows only. A threshold result is never a causal finding."""
    worked, failed, unknown = [], [], []
    for row in scorecard.get('scored_rows', []):
        label, value, target = row.get('metric', ''), row.get('value'), row.get('target')
        unit = row.get('unit', '')
        if row.get('status') == '—' or value is None or value == 'לא נמדד':
            unknown.append(f'{label}: לא נמדד; אין מסקנה על עמידה ביעד.')
        else:
            line = f'{label}: {value}{unit}; יעד {target}{unit}.'
            (worked if row.get('status') == '✅' else failed).append(line)
    summary = (f"{scorecard.get('passed', 0)} מתוך {scorecard.get('total', 0)} מדדים הגיעו ליעד; "
               f"כיסוי הנתונים {scorecard.get('coverage_percent', 'לא זמין')}%. "
               'הפערים והעמידה ביעדים מפורטים להלן. אין בנתונים הוכחה לסיבת השינוי או לרווחיות ערוץ.')
    return {'verdict_summary': summary, 'what_worked': worked, 'what_failed': failed + unknown}


def metric_evidence(raw, scorecard):
    """Only accept a metric/value/target triple that exactly matches a measured row."""
    if not isinstance(raw, dict) or not {'metric', 'value', 'target'} <= raw.keys():
        return None
    for row in scorecard.get('scored_rows', []) + scorecard.get('context_rows', []):
        if (row.get('metric') == raw['metric'] and row.get('value') == raw['value']
                and type(row.get('value')) is type(raw['value']) and row.get('target') == raw['target']
                and row.get('status') != '—' and row.get('value') not in (None, 'לא נמדד')):
            return {'source': 'scorecard', 'metric': row['metric'], 'value': row['value'],
                    'target': row['target'], 'unit': row.get('unit', ''), 'status': row.get('status')}
    return None


def factual_lead_actions(state):
    items = []
    deliverable = next((d for d in state.get('deliverables', []) if d.get('action_key') == 'salesforce-attribution-fix'), None)
    if deliverable:
        items.append('טיוטת הנחיית ייחוס המקורות כבר הוכנה וממתינה לבדיקה. טרם הופצה; אין ליצור אותה מחדש.')
    items.extend([
        'בדוק את המקור של רשומות Web, Advertisement ו-Other מול ראיה מתועדת. שינוי תווית מקור אינו מוסיף ליד לספירה הכוללת.',
        'הבחן בין Google Organic לתנועה ממומנת באמצעות פרטי הפנייה והייחוס. תשובה כללית ״מצאתי בגוגל״ אינה מספיקה לסיווג כאורגני.',
        'עקוב אחרי הפניות הקיימות ותעד את שלב הטיפול. אין לשנות רשומות CRM או להפיץ הנחיות ללא ההרשאה המתאימה.',
    ])
    return items


def measured_candidates(scorecard, completed=()):
    """A useful bounded next step when generated recommendations lacked usable evidence."""
    key = 'organic-click-period-review'
    if key in completed:
        return []
    row = next((r for r in scorecard.get('scored_rows', [])
                if r.get('metric') == 'קליקים אורגניים/שבוע' and r.get('status') == '❌'), None)
    evidence = metric_evidence(row, scorecard) if row else None
    if not evidence:
        return []
    return [{'action_key': key, 'category': 'gated', 'status': 'candidate', 'priority': 'P1',
             'channel': 'google_organic_geo', 'owner': 'בדיקת נתונים',
             'action': 'השווה את קליקי האתר ב-GSC בין שתי תקופות באותו אורך, לפי עמוד ושאילתה. תעד פערים לפני החלטה על שינוי תוכן.',
             'evidence': evidence,
             'expected_impact': 'מועמדת לניסוי; אין תחזית לתוספת לידים, קליקים או הכנסה.',
             'detail': 'הצעה לבדיקה על בסיס המדד המתועד; לא בוצע שינוי.',
             'success_metric': f"{row['metric']}: בסיס {row['value']}; יעד המדד {row['target']}. יש להשוות תקופות תואמות."}]
