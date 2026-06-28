"""RTL Hebrew summary email for each AEO loop run."""

DIM_HE = {"product_search": "חיפוש מוצר", "comparison": "השוואה", "reputation": "מוניטין", "aeo": "ציון כולל"}
MODEL_HE = {"claude": "Claude", "chatgpt": "ChatGPT", "gemini": "Gemini"}


def _arrow(cur, prev):
    if prev is None or cur == prev:
        return "—"
    return f"▲ +{cur - prev}" if cur > prev else f"▼ {cur - prev}"


def _ltr(url):
    return f'<span dir="ltr">{url}</span>'


def build_email(scorecard, prev, shipped, queued, failures, pr_url):
    rows = ""
    for model, block in scorecard["models"].items():
        pblock = (prev or {}).get("models", {}).get(model, {}) if prev else {}
        for dim in ("product_search", "comparison", "reputation", "aeo"):
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
<h3 dir="rtl">מה פורסם השבוע</h3>
<ul dir="rtl" style="direction:rtl;text-align:right;">{shipped_html}</ul>
<p dir="rtl" style="direction:rtl;text-align:right;">בתור לשבוע הבא: {queued} בריפים.</p>
{pr_html}
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
