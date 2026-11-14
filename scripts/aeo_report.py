"""RTL Hebrew summary email for each AEO loop run."""
import math

import aeo_probe

DIM_HE = {"product_search": "חיפוש מוצר", "comparison": "השוואה", "reputation": "מוניטין", "aeo": "ציון כולל",
          "mention_rate": "שיעור אזכור (KPI ראשי)", "citation_rate": "שיעור ציטוט"}
MODEL_HE = {"claude": "Claude", "chatgpt": "ChatGPT", "gemini": "Gemini"}


def _arrow(cur, prev, min_delta=0):
    """Suppress movement smaller than `min_delta`.

    With a 16-question battery each question was worth 6.25 points, so every "▼ -7" and
    "▲ +6" in the weekly email was a single question flipping. Over 13 runs ChatGPT's
    mention rate had a standard deviation of exactly 0.0 while the email kept drawing
    arrows. An arrow now requires at least two questions to move.
    """
    if prev is None or cur == prev:
        return "—"
    delta = cur - prev
    if abs(delta) < min_delta:
        return f"— (רעש: {delta:+d})"
    return f"▲ +{delta}" if delta > 0 else f"▼ {delta}"


def _min_delta(n_questions):
    """Two questions' worth of movement, rounded up."""
    if not n_questions:
        return 0
    return math.ceil(2 * 100 / n_questions)


def _ltr(url):
    return f'<span dir="ltr">{url}</span>'


def _comparable(scorecard, prev):
    """Deltas are only honest within one measurement methodology: a battery_version
    change (e.g. the 2026-07-05 grounding switch) resets the baseline."""
    if prev and prev.get("battery_version") == scorecard.get("battery_version"):
        return prev, ""
    note = ""
    if prev:
        note = ('<p dir="rtl" style="direction:rtl;text-align:right;color:#946200;">'
                "⚠️ baseline חדש — המתודולוגיה השתנתה (battery "
                f'<span dir="ltr">{scorecard.get("battery_version", "?")}</span>); '
                "אין השוואה לציונים ישנים.</p>")
    return None, note


def _outreach_html(scorecard, top=10):
    targets = aeo_probe.outreach_targets(scorecard, top=top)
    if not targets:
        return ""
    labels = {"competitor": "מתחרה — לא יעד פנייה", "editorial": "מקור מערכתי — לבדיקה לפני פנייה",
              "directory": "מדריך חברות — לבדיקה לפני רישום", "unverified": "טרם סווג — לא יעד פנייה"}
    items = "".join(
        f'<li dir="rtl" style="text-align:right;"><span dir="ltr">{t["domain"]}</span>'
        f' — {t["citations"]} ציטוטים · {labels[t["kind"]]}</li>' for t in targets)
    return ('<h3 dir="rtl">מי מצוטט — סוג המקור</h3>'
            f'<ul dir="rtl" style="direction:rtl;text-align:right;">{items}</ul>')


# Headline first, vanity last. `mention_rate` averages in four questions that NAME the
# company -- guaranteed hits that put a permanent 25% floor under the number and hid the
# fact that ChatGPT mentioned UPE in 0 of 12 non-branded questions for ten runs straight.
PRIMARY_DIMS = ("mention_rate_nonbranded", "citation_rate_nonbranded")
SECONDARY_DIMS = ("product_search", "comparison", "aeo", "brand_recall", "mention_rate")

DIM_HE.update({
    "mention_rate_nonbranded": "אזכור לא-ממותג (KPI ראשי)",
    "citation_rate_nonbranded": "ציטוט לא-ממותג",
    "brand_recall": "זיהוי מותג (ממותג — לא KPI)",
    "mention_rate": "שיעור אזכור (כולל ממותג — ישן)",
})


def _degraded_html(scorecard):
    bad = [(m, b) for m, b in scorecard.get("models", {}).items() if b.get("degraded")]
    if not bad:
        return ""
    items = "".join(
        f'<li dir="rtl" style="text-align:right;"><b>{MODEL_HE.get(m, m)}</b> — '
        f'חיפוש הרשת נכשל בכל השאלות; התשובות הגיעו מזיכרון האימון, לא מהאינטרנט. '
        f'<span dir="ltr">{(b.get("degraded_reason") or "")[:160]}</span></li>' for m, b in bad)
    return ('<div dir="rtl" style="direction:rtl;text-align:right;border:2px solid #b00;'
            'padding:8px;margin:8px 0;background:#fff5f5;">'
            '<h3 dir="rtl" style="margin:0 0 6px;color:#b00;">⛔ מכשיר תקול — הציונים למטה אינם מדידה</h3>'
            f'<ul dir="rtl" style="direction:rtl;text-align:right;">{items}</ul>'
            '<p dir="rtl" style="margin:6px 0 0;">אל תסיק מכאן ירידה בנראות. '
            'המנוע הזה לא נשאל באמת — יש לתקן את המתאם לפני שקוראים את המספרים שלו.</p></div>')


def build_email(scorecard, prev, shipped, queued, failures, pr_url, citations_status="",
                not_live=(), comparative=()):
    prev, baseline_note = _comparable(scorecard, prev)
    rows = ""
    for model, block in scorecard["models"].items():
        pblock = (prev or {}).get("models", {}).get(model, {}) if prev else {}
        degraded = block.get("degraded")
        md = _min_delta(block.get("n_nonbranded") or 0)
        label = MODEL_HE.get(model, model) + (" ⛔" if degraded else "")
        for dim in PRIMARY_DIMS + SECONDARY_DIMS:
            if dim not in block:
                continue
            cur = block.get(dim, 0)
            primary = dim in PRIMARY_DIMS
            arrow = "—" if degraded else _arrow(cur, pblock.get(dim) if pblock else None, md)
            # show the fraction, not just a percentage, so the reader can see how much
            # one question is worth
            frac = ""
            if dim == "mention_rate_nonbranded" and block.get("n_nonbranded"):
                frac = f' <span dir="ltr">({block.get("mentioned_nonbranded", 0)}/{block["n_nonbranded"]})</span>'
            weight = "font-weight:bold;" if primary else "color:#666;"
            rows += (f'<tr><td dir="rtl" style="padding:4px 8px;{weight}">{label}</td>'
                     f'<td dir="rtl" style="padding:4px 8px;{weight}">{DIM_HE.get(dim, dim)}</td>'
                     f'<td dir="rtl" style="padding:4px 8px;text-align:center;{weight}">{cur}{frac}</td>'
                     f'<td dir="rtl" style="padding:4px 8px;text-align:center;{weight}">{arrow}</td></tr>')

    shipped_html = "".join(
        f'<li dir="rtl" style="direction:rtl;text-align:right;">{p["title"]} — {_ltr(p["url"])}</li>'
        for p in shipped) or '<li dir="rtl">לא פורסמו עמודים בריצה זו</li>'

    # A PR is not a publication. Four consecutive weekly emails reported 27 pages as
    # shipped while PRs #99/#108/#112 sat closed unmerged and their URLs returned 404.
    notlive_html = ""
    if not_live:
        items = "".join(f'<li dir="rtl" style="text-align:right;">{p["title"]} — {_ltr(p["url"])}</li>'
                        for p in not_live)
        notlive_html = ('<h3 dir="rtl" style="color:#b00;">⚠️ נוצרו אך אינם חיים (לא נספרו כפרסום)</h3>'
                        f'<ul dir="rtl" style="direction:rtl;text-align:right;">{items}</ul>')

    comparative_html = ""
    if comparative:
        items = "".join(
            f'<li dir="rtl" style="text-align:right;"><span dir="ltr">{c["slug"]}</span> — '
            f'מזכיר: <span dir="ltr">{", ".join(c["competitors"])}</span></li>' for c in comparative)
        comparative_html = ('<h3 dir="rtl">עמודי השוואה שפורסמו (מזכירים מתחרים)</h3>'
                            '<p dir="rtl" style="direction:rtl;text-align:right;color:#666;">'
                            'עברו בדיקת ניטרליות: מתודולוגיה גלויה, תיאור עובדתי, ללא הכפשה וללא '
                            'סופרלטיב עצמי.</p>'
                            f'<ul dir="rtl" style="direction:rtl;text-align:right;">{items}</ul>')

    fails_html = ""
    if failures:
        items = "".join(f'<li dir="rtl" style="text-align:right;">{f}</li>' for f in failures)
        fails_html = ('<h3 dir="rtl" style="color:#b00;">תקלות</h3>'
                      f'<ul dir="rtl" style="direction:rtl;text-align:right;color:#b00;">{items}</ul>')

    pr_html = f'<p dir="rtl" style="direction:rtl;text-align:right;">PR: {_ltr(pr_url)}</p>' if pr_url else ""

    subject = f"דוח AEO שבועי — {scorecard['date']} ({len(shipped)} עמודים חיים, {queued} בתור)"
    html = f"""<html dir="rtl" lang="he">
<head><meta charset="utf-8"></head>
<body dir="rtl" style="font-family:Arial,Helvetica,sans-serif;font-size:14px;direction:rtl;text-align:right;">
<div dir="rtl" style="direction:rtl;text-align:right;">
<h2 dir="rtl">דוח AEO/GEO שבועי — {scorecard['date']}</h2>
{baseline_note}
{_degraded_html(scorecard)}
<table dir="rtl" style="border-collapse:collapse;border:1px solid #ddd;">
<tr><th dir="rtl" style="padding:4px 8px;">מודל</th><th dir="rtl" style="padding:4px 8px;">ממד</th>
<th dir="rtl" style="padding:4px 8px;">ציון</th><th dir="rtl" style="padding:4px 8px;">שינוי</th></tr>
{rows}
</table>
{_outreach_html(scorecard)}
{citations_status}
<h3 dir="rtl">מה פורסם השבוע (אומת חי)</h3>
<ul dir="rtl" style="direction:rtl;text-align:right;">{shipped_html}</ul>
{notlive_html}
{comparative_html}
<p dir="rtl" style="direction:rtl;text-align:right;">בתור לשבוע הבא: {queued} בריפים.</p>
{pr_html}
{fails_html}
</div>
</body>
</html>"""
    return subject, html


def _avg7_html(trends):
    """7-day unbranded-mention means. Each model contributes only days it ran."""
    if not trends:
        return ""
    bits = []
    for model in ("claude", "chatgpt", "gemini"):
        item = trends.get(model) or {}
        avg = item.get("avg7_mention_rate_nonbranded")
        n = item.get("avg7_mention_days") or 0
        label = MODEL_HE.get(model, model)
        if avg is None:
            bits.append(f"{label} —")
        else:
            bits.append(f'<span dir="ltr">{label} {avg}% ({n})</span>')
    return ('<p dir="rtl">ממוצע 7 ימים לאזכור לא-ממותג — רק ימים שהמודל נמדד בהם: '
            + " · ".join(bits) + "</p>")


def _he_date(iso):
    y, m, d = str(iso)[:10].split("-")
    return f'<span dir="ltr">{d}.{m}.{y}</span>'


def _gap_note(item):
    """Last real measurement and the failures since. Empty when there is nothing to say."""
    item = item or {}
    bits = []
    runs = item.get("failed_runs") or 0
    if runs and item.get("failed_since"):
        bits.append(f'⛔ כשל ב-{runs} ריצות רצופות מאז {_he_date(item["failed_since"])}')
    last = item.get("last_measured_date")
    if last:
        rate = item.get("last_mention_rate_nonbranded")
        tail = f' <span dir="ltr">({rate}%)</span>' if rate is not None else ""
        bits.append(f"מדידה אחרונה {_he_date(last)}{tail}")
    elif runs:
        bits.append("מעולם לא נמדד")
    return " · ".join(bits)


def _unmeasured_rows(scorecard, trends):
    """A model that failed outright is dropped from the scorecard, so it used to
    vanish from the table. Give it a row: failed is not the same as absent."""
    rows = ""
    for model in ("claude", "chatgpt", "gemini"):
        if model in scorecard.get("models", {}):
            continue
        item = trends.get(model) or {}
        if not item.get("failed_runs"):
            continue
        rows += (f'<tr><td dir="rtl" style="padding:4px 8px;">{MODEL_HE.get(model, model)} ⛔</td>'
                 f'<td dir="rtl" style="padding:4px 8px;text-align:center;">—</td>'
                 f'<td dir="rtl" style="padding:4px 8px;text-align:center;">—</td>'
                 f'<td dir="rtl" style="padding:4px 8px;text-align:center;">—</td>'
                 f'<td dir="rtl" style="padding:4px 8px;color:#b00;">לא נמדד היום · {_gap_note(item)}</td></tr>')
    return rows


def build_daily_email(scorecard, prev, keywords, failures, target=90, reminders=None, trends=None):
    """Report mentions and the judge rubric score; recommendation rank is unmeasured."""
    trends = trends or {}
    prev, baseline_note = _comparable(scorecard, prev)
    ran = [b for b in scorecard.get("models", {}).values() if aeo_probe.model_ran(b)]
    rows, all_at_target = "", bool(ran)
    for model, block in scorecard["models"].items():
        if aeo_probe.is_skipped_schedule(block):
            # Not a miss and not an outage. Keep it out of the failure banner.
            label = MODEL_HE.get(model, model)
            # An off day must not hide an outage: say when it was last measured.
            note = _gap_note(trends.get(model))
            gap = f" · {note}" if note else ""
            rows += (f'<tr><td dir="rtl" style="padding:4px 8px;">{label}</td>'
                     f'<td dir="rtl" style="padding:4px 8px;text-align:center;">—</td>'
                     f'<td dir="rtl" style="padding:4px 8px;text-align:center;">—</td>'
                     f'<td dir="rtl" style="padding:4px 8px;text-align:center;">—</td>'
                     f'<td dir="rtl" style="padding:4px 8px;">לא מתוזמן (not scheduled){gap}</td></tr>')
            continue
        pblock = (prev or {}).get("models", {}).get(model, {}) if prev else {}
        trend = trends.get(model) or {}
        if aeo_probe.model_ran(pblock):
            prev_ps = pblock.get("product_search")
        elif prev is not None:
            # Yesterday's row may be a scheduled skip. Compare to the last day it ran.
            prev_ps = trend.get("prev_product_search")
        else:
            prev_ps = None
        degraded = block.get("degraded")
        ps = block.get("product_search", 0)
        # the honest headline: mentions on questions that do NOT name the company
        mr = block.get("mention_rate_nonbranded", block.get("mention_rate"))
        n = block.get("n_nonbranded") or 0
        md = _min_delta(n)
        if ps < target:
            all_at_target = False
        if degraded:
            status = "⛔ מכשיר תקול — לא נמדד"
            arrow = "—"
            all_at_target = False
        else:
            status = "✅ יעד הציון הושג" if ps >= target else f"פער {target - ps} נקודות ליעד {target}"
            arrow = _arrow(ps, prev_ps, md)
        frac = f' <span dir="ltr">({block.get("mentioned_nonbranded", 0)}/{n})</span>' if n else ""
        mr_cell = f"{mr}%{frac}" if mr is not None else "—"
        label = MODEL_HE.get(model, model) + (" ⛔" if degraded else "")
        rows += (f'<tr><td dir="rtl" style="padding:4px 8px;">{label}</td>'
                 f'<td dir="rtl" style="padding:4px 8px;text-align:center;">{mr_cell}</td>'
                 f'<td dir="rtl" style="padding:4px 8px;text-align:center;">{ps}</td>'
                 f'<td dir="rtl" style="padding:4px 8px;text-align:center;">{arrow}</td>'
                 f'<td dir="rtl" style="padding:4px 8px;">{status}</td></tr>')

    rows += _unmeasured_rows(scorecard, trends)

    def _kwlist(items, ltr=False):
        if not items:
            return '<li dir="rtl">—</li>'
        if ltr:
            return "".join(f'<li dir="rtl"><span dir="ltr">{k}</span></li>' for k in items)
        return "".join(f'<li dir="rtl" style="text-align:right;">{k}</li>' for k in items)

    comps = ", ".join(keywords.get("competitors", [])) or "—"
    actions = "".join(f'<li dir="rtl" style="text-align:right;">{a}</li>'
                      for a in keywords.get("priority_actions", [])) or '<li dir="rtl">—</li>'
    headline = ("יעד ציון הבולטות הושג בכל המודלים שנמדדו" if all_at_target
                else "נראות UPE בתוצאות ה-AI — המדידה והצעדים")

    reminders_html = ""
    if reminders:
        items = "".join(f'<li dir="rtl" style="text-align:right;">{r}</li>' for r in reminders)
        reminders_html = ('<h3 dir="rtl" style="color:#b00;">⏰ ממתין לך מעל 72 שעות</h3>'
                          f'<ul dir="rtl" style="direction:rtl;text-align:right;">{items}</ul>')
    fails_html = (f'<p dir="rtl" style="color:#b00;">תקלות: {"; ".join(failures)}</p>' if failures else "")
    subject = f"מעקב AEO יומי — {scorecard['date']} ({'יעד הציון הושג' if all_at_target else 'מעקב נראות'})"
    html = f"""<html dir="rtl" lang="he">
<head><meta charset="utf-8"></head>
<body dir="rtl" style="font-family:Arial,Helvetica,sans-serif;font-size:14px;direction:rtl;text-align:right;">
<div dir="rtl" style="direction:rtl;text-align:right;">
<h2 dir="rtl">{headline}</h2>
<p dir="rtl">תאריך: {scorecard['date']} · מדד: ציון בולטות AI (<span dir="ltr">0–100</span>) לפי הערכת מודל שופט</p>
<p dir="rtl">יעד הציון: {target}. זהו סף עבודה פנימי, לא מיקום בתוצאות. דירוג ראשון לא נמדד.</p>
<table dir="rtl" style="border-collapse:collapse;border:1px solid #ddd;">
<tr><th dir="rtl" style="padding:4px 8px;">מודל</th><th dir="rtl" style="padding:4px 8px;">אזכור לא-ממותג</th>
<th dir="rtl" style="padding:4px 8px;">ציון בולטות AI</th>
<th dir="rtl" style="padding:4px 8px;">שינוי</th><th dir="rtl" style="padding:4px 8px;">סטטוס יעד הציון</th></tr>
{rows}
</table>
{_avg7_html(trends)}
{baseline_note}
{_degraded_html(scorecard)}
{_outreach_html(scorecard)}
{reminders_html}
<h3 dir="rtl">מתחרים שמובילים כרגע</h3>
<p dir="rtl" style="text-align:right;">{comps}</p>
<h3 dir="rtl">מילות מפתח לכבוש — עברית</h3>
<ul dir="rtl" style="text-align:right;">{_kwlist(keywords.get('he', []))}</ul>
<h3 dir="rtl">מילות מפתח לכבוש — אנגלית</h3>
<ul dir="rtl">{_kwlist(keywords.get('en', []), ltr=True)}</ul>
<h3 dir="rtl">צעדים מומלצים</h3>
<ul dir="rtl" style="text-align:right;">{actions}</ul>
{fails_html}
</div>
</body>
</html>"""
    return subject, html


def send(subject, html, send_fn=None):
    if send_fn is None:
        from daily_email import send_graph_html
        send_fn = send_graph_html
    return send_fn(subject, html)
