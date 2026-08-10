#!/usr/bin/env python3
"""
Weekly performance report — Sunday morning summary of last 7 days of posts.

For each published post in `post_approvals` over the last 7 days, pull insights
from Facebook + Instagram Graph API, aggregate into a ranked table, and email
Alon via Resend with the image of the top performer attached.

Env vars:
  SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY
  FB_UPRODUCTIONEVENTS_PAGE_TOKEN / FB_UPRODUCTION_SPAIN_PAGE_TOKEN
  IG_UPRODUCTIONEVENTS_ACCESS_TOKEN / IG_UPRODUCTION_SPAIN_ACCESS_TOKEN
  RESEND_API_KEY / RESEND_FROM / APPROVAL_TO
"""
import base64
import datetime
import json
import os
import sys
import urllib.error
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from publishers.content import find_image_path  # noqa: E402

GRAPH = "https://graph.facebook.com/v22.0"
UA = "Mozilla/5.0 (UPE-Reporter)"

FB_TOKENS = {
    "uproductionevents":  os.environ.get("FB_UPRODUCTIONEVENTS_PAGE_TOKEN", ""),
    "uproduction_spain":  os.environ.get("FB_UPRODUCTION_SPAIN_PAGE_TOKEN", ""),
}
IG_TOKENS = {
    "ig_uproductionevents":  os.environ.get("IG_UPRODUCTIONEVENTS_ACCESS_TOKEN", ""),
    "ig_uproduction_spain":  os.environ.get("IG_UPRODUCTION_SPAIN_ACCESS_TOKEN", ""),
}

NET_HE = {"facebook": "Facebook", "instagram": "Instagram", "linkedin": "LinkedIn"}


def supa(path):
    url = os.environ["SUPABASE_URL"].rstrip("/") + "/rest/v1" + path
    key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    req = urllib.request.Request(url, headers={"apikey": key, "Authorization": f"Bearer {key}"})
    with urllib.request.urlopen(req) as r:
        return json.load(r)


def fb_insights(post_id, token):
    """Return dict with reach, engagement, reactions, clicks for a FB post."""
    metrics = "post_impressions,post_engaged_users,post_clicks,post_reactions_by_type_total"
    url = f"{GRAPH}/{post_id}/insights?metric={metrics}&access_token={token}"
    try:
        with urllib.request.urlopen(urllib.request.Request(url), timeout=20) as r:
            data = json.load(r).get("data", [])
    except Exception as e:
        return {"error": str(e)[:120]}
    out = {}
    for m in data:
        name = m.get("name")
        values = m.get("values", [{}])[0].get("value", 0)
        out[name] = values
    reactions = sum((out.get("post_reactions_by_type_total") or {}).values()) \
        if isinstance(out.get("post_reactions_by_type_total"), dict) else 0
    return {
        "impressions": out.get("post_impressions", 0),
        "engaged":     out.get("post_engaged_users", 0),
        "clicks":      out.get("post_clicks", 0),
        "reactions":   reactions,
    }


def ig_insights(media_id, token):
    """Return dict with reach, impressions, likes, comments, saves, shares for IG."""
    metrics = "reach,impressions,likes,comments,saves,shares"
    url = f"{GRAPH}/{media_id}/insights?metric={metrics}&access_token={token}"
    try:
        with urllib.request.urlopen(urllib.request.Request(url), timeout=20) as r:
            data = json.load(r).get("data", [])
    except Exception as e:
        return {"error": str(e)[:120]}
    out = {m["name"]: m.get("values", [{}])[0].get("value", 0) for m in data}
    return {
        "reach":       out.get("reach", 0),
        "impressions": out.get("impressions", 0),
        "likes":       out.get("likes", 0),
        "comments":    out.get("comments", 0),
        "saves":       out.get("saves", 0),
        "shares":      out.get("shares", 0),
    }


def fetch_metrics(row):
    net, account, pid = row["network"], row["account"], row["post_id"]
    if not pid:
        return {}
    if net == "facebook" and account in FB_TOKENS and FB_TOKENS[account]:
        return fb_insights(pid, FB_TOKENS[account])
    if net == "instagram" and account in IG_TOKENS and IG_TOKENS[account]:
        return ig_insights(pid, IG_TOKENS[account])
    return {}


def score(metrics, net):
    """Single virality score for ranking — engagement-weighted."""
    if not metrics or "error" in metrics:
        return 0
    if net == "facebook":
        return metrics.get("reactions", 0) * 3 + metrics.get("clicks", 0) * 2 \
             + metrics.get("engaged", 0)
    if net == "instagram":
        return (metrics.get("likes", 0) + metrics.get("comments", 0) * 5
                + metrics.get("saves", 0) * 7 + metrics.get("shares", 0) * 6)
    return 0


def render_email_html(report_date, rows_with_metrics, top_pick):
    week_label = (datetime.date.today() - datetime.timedelta(days=7)).strftime("%d.%m")
    today_label = datetime.date.today().strftime("%d.%m.%Y")
    body = []
    for r, m in rows_with_metrics:
        net_he = NET_HE.get(r["network"], r["network"])
        if r["network"] == "facebook":
            mtxt = (f"👁 {m.get('impressions', 0):,} · 👤 {m.get('engaged', 0):,} · "
                    f"❤️ {m.get('reactions', 0):,} · 🔗 {m.get('clicks', 0):,}")
        elif r["network"] == "instagram":
            mtxt = (f"👁 {m.get('reach', 0):,} · ❤️ {m.get('likes', 0):,} · "
                    f"💬 {m.get('comments', 0):,} · 🔖 {m.get('saves', 0):,} · "
                    f"🔁 {m.get('shares', 0):,}")
        elif "error" in m:
            mtxt = f"⚠️ {m['error']}"
        else:
            mtxt = "—"
        body.append(f"""
        <tr>
          <td style="padding:8px;border-bottom:1px solid #eee;">{r['day']}</td>
          <td style="padding:8px;border-bottom:1px solid #eee;">{net_he}<br><small style='color:#888'>{r['account']}</small></td>
          <td style="padding:8px;border-bottom:1px solid #eee;font-size:13px;">{(r.get('headline') or '')[:50]}</td>
          <td style="padding:8px;border-bottom:1px solid #eee;direction:ltr;text-align:left;">{mtxt}</td>
        </tr>""")
    rows_html = "".join(body)
    top_block = ""
    if top_pick:
        r, m = top_pick
        top_block = f"""<div style="background:#fffbeb;border:1px solid #fbbf24;border-radius:8px;padding:14px;margin:14px 0;">
          🏆 <b>הפוסט הכי ויראלי השבוע:</b> יום {r['day']} · {NET_HE.get(r['network'], r['network'])}<br>
          <span style="color:#444;">{(r.get('headline') or '')[:80]}</span>
        </div>"""
    return f"""<html dir="rtl" lang="he"><head><meta charset="utf-8"></head>
<body dir="rtl" style="font-family:Arial,Helvetica,sans-serif;font-size:14px;direction:rtl;text-align:right;background:#f2f2f2;margin:0;padding:0;">
<div dir="rtl" style="max-width:680px;margin:0 auto;background:#fff;">
  <div dir="rtl" style="background:#141414;padding:18px 24px;text-align:right;">
    <span style="color:#FBCE0A;font-size:20px;font-weight:bold;">uproduction</span>
    <span style="color:#bbb;font-size:12px;"> &nbsp;from business to pleasure</span>
  </div>
  <div dir="rtl" style="padding:20px 24px;">
    <h2 style="margin:0 0 6px;color:#141414;">📊 דוח שבועי · {week_label}–{today_label}</h2>
    <p style="color:#666;">סיכום ביצועים של כל הפוסטים שעלו בשבוע האחרון.</p>
    {top_block}
    <table dir="rtl" style="width:100%;border-collapse:collapse;font-size:13px;">
      <thead><tr style="background:#f7f7f7;">
        <th style="padding:8px;text-align:right;">יום</th>
        <th style="padding:8px;text-align:right;">רשת</th>
        <th style="padding:8px;text-align:right;">נושא</th>
        <th style="padding:8px;text-align:right;">ביצועים</th>
      </tr></thead>
      <tbody>{rows_html}</tbody>
    </table>
    <div style="color:#888;font-size:12px;margin-top:18px;text-align:center;">
      Sources: Facebook Graph API + Instagram Graph API.<br>
      Score weighting — FB: reactions×3 + clicks×2 + engaged. IG: likes + comments×5 + saves×7 + shares×6.
    </div>
  </div>
</div></body></html>"""


def send_resend(subject, html, attachment_path=None):
    payload = {
        "from": os.environ.get("RESEND_FROM", "onboarding@resend.dev"),
        "to": [os.environ.get("APPROVAL_TO", "alon@upe.co.il")],
        "subject": subject,
        "html": html,
    }
    if attachment_path and os.path.isfile(attachment_path):
        with open(attachment_path, "rb") as f:
            payload["attachments"] = [{
                "filename": os.path.basename(attachment_path),
                "content": base64.b64encode(f.read()).decode(),
                "content_type": "image/png",
            }]
    body = json.dumps(payload).encode()
    req = urllib.request.Request(
        "https://api.resend.com/emails", data=body,
        headers={"Authorization": f"Bearer {os.environ['RESEND_API_KEY']}",
                 "Content-Type": "application/json", "User-Agent": UA},
    )
    with urllib.request.urlopen(req) as r:
        print(f"[resend] HTTP {r.status}: {r.read().decode()[:200]}")


def main():
    today = datetime.date.today()
    since = (today - datetime.timedelta(days=7)).isoformat()
    rows = supa(
        f"/post_approvals?status=eq.published&published_at=gte.{since}T00:00:00Z"
        f"&order=day,network&select=day,network,account,headline,post_id,image_url,published_at"
    )
    if not rows:
        print(f"[report] No published posts in the last 7 days.")
        return 0
    print(f"[report] Fetching insights for {len(rows)} posts...")
    enriched = []
    for r in rows:
        m = fetch_metrics(r)
        r["_score"] = score(m, r["network"])
        enriched.append((r, m))
    enriched.sort(key=lambda t: t[0]["_score"], reverse=True)
    top = enriched[0] if enriched and enriched[0][0]["_score"] > 0 else None

    img_path = find_image_path(top[0]["day"]) if top else None
    html = render_email_html(today.isoformat(), enriched, top)
    subj = f"📊 דוח שבועי UPE Publisher · {today.strftime('%d.%m.%Y')}"
    send_resend(subj, html, attachment_path=img_path)
    print(f"[report] Sent. Top: day {top[0]['day']} {top[0]['network']}" if top else "[report] Sent.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
