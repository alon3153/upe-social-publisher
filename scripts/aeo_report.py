"""RTL Hebrew summary email for each AEO loop run."""

DIM_HE = {"product_search": "חיפוש מוצר", "comparison": "השוואה", "reputation": "מוניטין", "aeo": "ציון כולל",
          "mention_rate": "שיעור אזכור (KPI ראשי)", "citation_rate": "שיעור ציטוט"}
MODEL_HE = {"claude": "Claude", "chatgpt": "ChatGPT", "gemini": "Gemini"}


def _arrow(cur, prev):
    if prev is None or cur == prev:
        return "—"
    return f"▲ +{cur - prev}" if cur > prev else f"▼ {cur - prev}"


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
    import aeo_probe
    targets = aeo_probe.outreach_targets(scorecard, top=top)
    if not targets:
        return ""
    items = "".join(
        f'<li dir="rtl" style="text-align:right;"><span dir="ltr">{t["domain"]}</span>'
        f' — {t["citations"]} ציטוטים</li>' for t in targets)
    return ('<h3 dir="rtl">מי כן מצוטט (יעדי outreach)</h3>'
            f'<ul dir="rtl" style="direction:rtl;text-align:right;">{items}</ul>')


def build_email(scorecard, prev, shipped, queued, failures, pr_url, citations_status=""):
    prev, baseline_note = _comparable(scorecard, prev)
    rows = ""
    for model, block in scorecard["models"].items():
        pblock = (prev or {}).get("models", {}).get(model, {}) if prev else {}
        for dim in ("mention_rate", "citation_rate", "product_search", "comparison", "reputation", "aeo"):
            if dim not in block:
                continue
            cur = block.get(dim, 0)
            arrow = _arrow(cur, pblock.get(dim) if pblock else None)
            rows += (f'<tr><td dir="rtl" style="padding:4px 8px;">{MODEL_HE.get(model, model)}</td>'
                     f'<td dir="rtl" style="padding:4px 8px;">{DIM_HE[dim]}</td>'
                     f'<td dir="rtl" style="padding:4px 8px;text-align:center;">{cur}</td>'
                     f'<td dir="rtl" style="padding:4px 8px;text-align:center;">{arrow}</td></tr>')

    shipped_html = "".join(
        f'<li dir="rtl" style="direction:rtl;text-align:right;">{p["title"]} — {_ltr(p["url"])}</li>'
        for p in shipped) or '<li dir="rtl">לא פורסמו עמודים בריצה זו</li>'

    fails_html = ""
    if failures:
        fails_html = ('<p dir="rtl" style="direction:rtl;text-align:right;color:#b00;">'
                      "תקלות: " + "; ".join(failures) + "</p>")

    pr_html = f'<p dir="rtl" style="direction:rtl;text-align:right;">PR: {_ltr(pr_url)}</p>' if pr_url else ""

    subject = f"דוח AEO שבועי — {scorecard['date']} ({len(shipped)} עמודים, {queued} בתור)"
    html = f"""<html dir="rtl" lang="he">
<head><meta charset="utf-8"></head>
<body dir="rtl" style="font-family:Arial,Helvetica,sans-serif;font-size:14px;direction:rtl;text-align:right;">
<div dir="rtl" style="direction:rtl;text-align:right;">
<h2 dir="rtl">דוח AEO/GEO שבועי — {scorecard['date']}</h2>
<table dir="rtl" style="border-collapse:collapse;border:1px solid #ddd;">
<tr><th dir="rtl" style="padding:4px 8px;">מודל</th><th dir="rtl" style="padding:4px 8px;">ממד</th>
<th dir="rtl" style="padding:4px 8px;">ציון</th><th dir="rtl" style="padding:4px 8px;">שינוי</th></tr>
{rows}
</table>
{_outreach_html(scorecard)}
{citations_status}
<h3 dir="rtl">מה פורסם השבוע</h3>
<ul dir="rtl" style="direction:rtl;text-align:right;">{shipped_html}</ul>
<p dir="rtl" style="direction:rtl;text-align:right;">בתור לשבוע הבא: {queued} בריפים.</p>
{pr_html}
{fails_html}
</div>
</body>
</html>"""
    return subject, html


def build_daily_email(scorecard, prev, keywords, failures, target=90, reminders=None):
    """Daily #1-tracking email: per-model mention-rate (primary) + product_search
    vs the #1 target, delta vs yesterday, and competitor keyword opportunities."""
    prev, baseline_note = _comparable(scorecard, prev)
    rows, all_top = "", True
    for model, block in scorecard["models"].items():
        pblock = (prev or {}).get("models", {}).get(model, {}) if prev else {}
        ps = block.get("product_search", 0)
        mr = block.get("mention_rate")
        if ps < target:
            all_top = False
        status = "✅ #1" if ps >= target else f"פער {target - ps} ל-#1"
        arrow = _arrow(ps, pblock.get("product_search") if pblock else None)
        mr_cell = f"{mr}%" if mr is not None else "—"
        rows += (f'<tr><td dir="rtl" style="padding:4px 8px;">{MODEL_HE.get(model, model)}</td>'
                 f'<td dir="rtl" style="padding:4px 8px;text-align:center;">{mr_cell}</td>'
                 f'<td dir="rtl" style="padding:4px 8px;text-align:center;">{ps}</td>'
                 f'<td dir="rtl" style="padding:4px 8px;text-align:center;">{arrow}</td>'
                 f'<td dir="rtl" style="padding:4px 8px;">{status}</td></tr>')

    def _kwlist(items, ltr=False):
        if not items:
            return '<li dir="rtl">—</li>'
        if ltr:
            return "".join(f'<li dir="rtl"><span dir="ltr">{k}</span></li>' for k in items)
        return "".join(f'<li dir="rtl" style="text-align:right;">{k}</li>' for k in items)

    comps = ", ".join(keywords.get("competitors", [])) or "—"
    actions = "".join(f'<li dir="rtl" style="text-align:right;">{a}</li>'
                      for a in keywords.get("priority_actions", [])) or '<li dir="rtl">—</li>'
    headline = ("🥇 UPE מוביל (#1) בכל המודלים!" if all_top
                else "מטרה: UPE #1 בתוצאות ה-AI — הנה הפער והצעדים")

    reminders_html = ""
    if reminders:
        items = "".join(f'<li dir="rtl" style="text-align:right;">{r}</li>' for r in reminders)
        reminders_html = ('<h3 dir="rtl" style="color:#b00;">⏰ ממתין לך מעל 72 שעות</h3>'
                          f'<ul dir="rtl" style="direction:rtl;text-align:right;">{items}</ul>')
    fails_html = (f'<p dir="rtl" style="color:#b00;">תקלות: {"; ".join(failures)}</p>' if failures else "")
    subject = f"מעקב AEO יומי — {scorecard['date']} ({'#1 בכל המודלים' if all_top else 'בדרך ל-#1'})"
    html = f"""<html dir="rtl" lang="he">
<head><meta charset="utf-8"></head>
<body dir="rtl" style="font-family:Arial,Helvetica,sans-serif;font-size:14px;direction:rtl;text-align:right;">
<div dir="rtl" style="direction:rtl;text-align:right;">
<h2 dir="rtl">{headline}</h2>
<p dir="rtl">תאריך: {scorecard['date']} · מדד: חיפוש-מוצר (האם UPE צץ ראשון בשאלות קטגוריה)</p>
<table dir="rtl" style="border-collapse:collapse;border:1px solid #ddd;">
<tr><th dir="rtl" style="padding:4px 8px;">מודל</th><th dir="rtl" style="padding:4px 8px;">שיעור אזכור</th>
<th dir="rtl" style="padding:4px 8px;">חיפוש מוצר</th>
<th dir="rtl" style="padding:4px 8px;">שינוי</th><th dir="rtl" style="padding:4px 8px;">סטטוס #1</th></tr>
{rows}
</table>
{baseline_note}
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
