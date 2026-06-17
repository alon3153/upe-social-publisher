#!/usr/bin/env python3
"""
Competitor scanner — finds viral posts from competitor IG accounts (via IG
Business Discovery API) over the last 7 days and emails Alon a weekly digest.

How it works:
  - Reads content/competitors.json — list of competitor IG handles
  - Uses UPE's IG Business Account + access token to query each competitor's
    recent media via /<ig_user_id>?fields=business_discovery.username(<handle>){
        followers_count, media{caption,like_count,comments_count,permalink,
        media_url,timestamp,media_type}
    }
  - For each competitor, identifies posts > 2× their own median engagement (viral)
  - Emails Alon a digest of top performers with captions for inspiration

Required env:
  IG_UPRODUCTIONEVENTS_USER_ID
  IG_UPRODUCTIONEVENTS_ACCESS_TOKEN
  RESEND_API_KEY / RESEND_FROM / APPROVAL_TO

LinkedIn / Facebook competitor monitoring is intentionally NOT included yet —
LinkedIn has no public-discovery API at all, and Facebook Page public posts
require the competitor to grant access. IG Business Discovery is the only
public-data API that works at scale.
"""
import datetime
import json
import os
import statistics
import sys
import urllib.error
import urllib.parse
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GRAPH = "https://graph.facebook.com/v22.0"
UA = "Mozilla/5.0 (UPE-CompetitorScanner)"


def load_competitors():
    with open(os.path.join(ROOT, "content", "competitors.json")) as f:
        return json.load(f).get("competitors", [])


def fetch_competitor_media(handle: str, ig_user_id: str, token: str):
    """Use IG Business Discovery API to get a competitor's recent posts.
       Returns dict with followers_count + media list (or {} on error)."""
    fields = (
        f"business_discovery.username({handle}){{"
        "followers_count,media_count,"
        "media{caption,like_count,comments_count,permalink,media_url,timestamp,media_type}"
        "}"
    )
    url = f"{GRAPH}/{ig_user_id}?fields={urllib.parse.quote(fields, safe='(){},')}" \
          f"&access_token={token}"
    try:
        with urllib.request.urlopen(urllib.request.Request(url), timeout=20) as r:
            data = json.load(r)
        return data.get("business_discovery", {})
    except urllib.error.HTTPError as e:
        msg = e.read().decode()[:300]
        print(f"  ⚠️ {handle}: HTTP {e.code} {msg}")
        return {}
    except Exception as e:
        print(f"  ⚠️ {handle}: {e}")
        return {}


def identify_viral(media: list, threshold_x: float = 2.0):
    """Return posts whose like+comment count is > threshold_x × median, from last 7 days."""
    if not media:
        return []
    cutoff = (datetime.datetime.utcnow() - datetime.timedelta(days=7)).isoformat() + "Z"
    recent = []
    for m in media:
        ts = m.get("timestamp", "")
        if ts >= cutoff:
            engagement = (m.get("like_count") or 0) + (m.get("comments_count") or 0)
            recent.append({"engagement": engagement, **m})
    if not recent:
        return []
    # Use all media (not just recent) for the baseline
    all_eng = [(m.get("like_count") or 0) + (m.get("comments_count") or 0) for m in media]
    if not all_eng:
        return []
    median = statistics.median(all_eng) or 1
    return [m for m in recent if m["engagement"] >= threshold_x * median]


def render_email_html(results):
    blocks = []
    total_viral = 0
    for comp_name, comp_handle, comp_data, viral_posts in results:
        if not viral_posts:
            blocks.append(
                f"""<div style="border-bottom:1px solid #eee;padding:14px 0;">
                  <b>{comp_name}</b>
                  <span style="color:#888;font-size:12px;"> · @{comp_handle} · {comp_data.get('followers_count', 0):,} followers</span><br>
                  <span style="color:#888;font-size:13px;">לא זוהו פוסטים ויראליים השבוע.</span>
                </div>""")
            continue
        total_viral += len(viral_posts)
        cards = []
        for p in sorted(viral_posts, key=lambda x: x["engagement"], reverse=True)[:5]:
            caption = (p.get("caption") or "")[:300].replace("&", "&amp;").replace("<", "&lt;")
            cards.append(f"""
              <div style="background:#fafafa;border-radius:8px;padding:12px;margin:8px 0;">
                <div style="font-size:13px;color:#666;">
                  ❤️ {p.get('like_count', 0):,} · 💬 {p.get('comments_count', 0):,}
                  · 📅 {p.get('timestamp', '')[:10]}
                  · <a href="{p.get('permalink', '#')}" target="_blank">צפה ב-IG</a>
                </div>
                <div dir="ltr" style="direction:ltr;text-align:left;font-size:13px;color:#222;margin-top:6px;">
                  {caption}{'...' if len(p.get('caption') or '') > 300 else ''}
                </div>
              </div>""")
        blocks.append(f"""
        <div style="border-bottom:1px solid #eee;padding:14px 0;">
          <b>{comp_name}</b>
          <span style="color:#888;font-size:12px;"> · @{comp_handle} · {comp_data.get('followers_count', 0):,} followers</span>
          <div style="background:#fffbeb;color:#92400e;border-radius:6px;padding:6px 10px;display:inline-block;margin:6px 0;font-size:12px;">
            🚀 {len(viral_posts)} פוסטים ויראליים השבוע (engagement &gt; 2× median)
          </div>
          {''.join(cards)}
        </div>""")
    return f"""<html dir="rtl" lang="he"><head><meta charset="utf-8"></head>
<body dir="rtl" style="font-family:Arial,Helvetica,sans-serif;font-size:14px;direction:rtl;text-align:right;background:#f2f2f2;margin:0;padding:0;">
<div dir="rtl" style="max-width:720px;margin:0 auto;background:#fff;">
  <div style="background:#141414;padding:18px 24px;text-align:right;">
    <span style="color:#FBCE0A;font-size:20px;font-weight:bold;">uproduction</span>
    <span style="color:#bbb;font-size:12px;"> &nbsp;competitive intelligence</span>
  </div>
  <div style="padding:20px 24px;">
    <h2 style="margin:0 0 6px;color:#141414;">🕵️ דוח מתחרים שבועי</h2>
    <p style="color:#666;">סריקה של {len(results)} מתחרים. {total_viral} פוסטים שעברו את סף הוויראליות (2× median engagement של אותו עמוד).</p>
    <div style="background:#eff6ff;border:1px solid #93c5fd;padding:10px 14px;border-radius:8px;margin:14px 0;font-size:13px;">
      💡 פוסטים ויראליים = הזדמנות. שקול לאמץ את הזווית/הפורמט שלהם לפוסט הבא של UPE — לא להעתיק טקסט, אלא ללמוד מה תפס.
    </div>
    {''.join(blocks)}
    <div style="color:#888;font-size:12px;margin-top:18px;text-align:center;">
      Source: Instagram Graph API · Business Discovery<br>
      רשימת מתחרים: <code>content/competitors.json</code>
    </div>
  </div>
</div></body></html>"""


def send_email(html, subject):
    import base64  # noqa
    body = json.dumps({
        "from": os.environ.get("RESEND_FROM", "onboarding@resend.dev"),
        "to": [os.environ.get("APPROVAL_TO", "alon@upe.co.il")],
        "subject": subject,
        "html": html,
    }).encode()
    req = urllib.request.Request(
        "https://api.resend.com/emails", data=body,
        headers={"Authorization": f"Bearer {os.environ['RESEND_API_KEY']}",
                 "Content-Type": "application/json", "User-Agent": UA},
    )
    with urllib.request.urlopen(req) as r:
        print(f"[resend] HTTP {r.status}: {r.read().decode()[:200]}")


def main():
    ig_user_id = os.environ["IG_UPRODUCTIONEVENTS_USER_ID"]
    ig_token = os.environ["IG_UPRODUCTIONEVENTS_ACCESS_TOKEN"]

    competitors = load_competitors()
    if not competitors:
        print("[scan] No competitors configured."); return 0

    results = []
    for comp in competitors:
        handle = comp.get("ig_handle", "").strip()
        if not handle:
            continue
        print(f"[scan] {comp['name']} (@{handle})...")
        data = fetch_competitor_media(handle, ig_user_id, ig_token)
        media = (data.get("media") or {}).get("data", []) if "media" in data else []
        viral = identify_viral(media)
        print(f"  followers={data.get('followers_count', 0):,}  recent_media={len(media)}  viral={len(viral)}")
        results.append((comp["name"], handle, data, viral))

    if not any(r[2] for r in results):
        print("[scan] All competitor lookups failed — check IG token and competitor handles.")
        return 1

    html = render_email_html(results)
    subj = f"🕵️ דוח מתחרים שבועי · {datetime.date.today().strftime('%d.%m.%Y')}"
    send_email(html, subj)
    print(f"[scan] Sent digest for {len(results)} competitors.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
