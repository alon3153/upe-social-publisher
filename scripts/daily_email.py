#!/usr/bin/env python3
"""Daily approval email: pick next day, build per-account posts, virality-optimize,
enqueue in Supabase, send ONE email per post via Resend with Approve/Reject buttons."""
import os, sys, json, glob, datetime, urllib.request, urllib.error

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from publishers import queue
from publishers.content import find_image_path
from publishers.state import load_state, get_published_days

FN = (os.environ.get("SUPABASE_URL", "").rstrip("/")) + "/functions/v1/approve"
RESEND_KEY = os.environ.get("RESEND_API_KEY", "")
RESEND_FROM = os.environ.get("RESEND_FROM") or "uproduction <onboarding@resend.dev>"
TO = os.environ.get("APPROVAL_TO") or "alon@upe.co.il"
IMG_BASE = "https://raw.githubusercontent.com/alon3153/upe-social-publisher/main/content/images"
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"

# (network, account, platform_key_in_json, lang)
ACCOUNTS = [
    ("facebook",  "uproductionevents", "facebook",  "en"),
    ("facebook",  "uproduction_spain", "facebook",  "es"),
    ("instagram", "ig_uproductionevents", "instagram", "en"),
    ("instagram", "ig_uproduction_spain", "instagram", "es"),
    ("linkedin",  "li_uproductionevents", "linkedin",  "en"),
]
NET_HE = {"facebook": "Facebook", "instagram": "Instagram", "linkedin": "LinkedIn", "tiktok": "TikTok"}
HASHTAGS = {
    "facebook": "", "instagram": "",
}


def load_day_lang(day, lang):
    for f in glob.glob(os.path.join(ROOT, "content", "days", f"*day{day}-*-{lang}.json")):
        return json.load(open(f))
    # fallback to en
    for f in glob.glob(os.path.join(ROOT, "content", "days", f"*day{day}-*-en.json")):
        return json.load(open(f))
    return None


def optimize_virality(text, network):
    """Light, non-destructive virality touch-ups. Strong copy already in source."""
    if not text:
        return text
    t = text.strip()
    # Instagram: ensure a save/share CTA near the end if absent
    if network == "instagram" and "share" not in t.lower() and "save" not in t.lower():
        t += "\n\n💬 Save this for your next planning meeting — and tag the HR lead who needs it."
    return t


def email_html(net, day, headline, rid, token, caption, image_url):
    approve = f"{FN}?id={rid}&token={token}&action=approve"
    reject = f"{FN}?id={rid}&token={token}&action=reject"
    cap = caption.replace("&", "&amp;").replace("<", "&lt;").replace("\n", "<br>")
    return f"""<html dir="rtl" lang="he"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"></head>
<body dir="rtl" style="font-family:Arial,Helvetica,sans-serif;font-size:14px;direction:rtl;text-align:right;background:#f2f2f2;margin:0;padding:0;">
<div dir="rtl" style="max-width:600px;margin:0 auto;background:#fff;">
 <div dir="rtl" style="background:#141414;padding:18px 24px;text-align:right;">
   <span style="color:#FBCE0A;font-size:20px;font-weight:bold;">uproduction</span>
   <span style="color:#bbb;font-size:12px;"> &nbsp;from business to pleasure</span></div>
 <div dir="rtl" style="padding:20px 24px;direction:rtl;text-align:right;">
   <div style="font-size:13px;color:#888;">פוסט לאישור · יום {day}</div>
   <div style="font-size:20px;font-weight:bold;color:#141414;margin:4px 0 14px;">{NET_HE.get(net,net)}</div>
   <img src="{image_url}" alt="post" style="width:100%;border-radius:10px;display:block;margin-bottom:16px;">
   <div style="font-size:13px;color:#888;margin-bottom:6px;">הטקסט שיפורסם:</div>
   <div dir="ltr" style="direction:ltr;text-align:left;background:#f7f7f7;border-radius:8px;padding:14px;font-size:14px;line-height:1.55;color:#222;">{cap}</div>
   <table dir="rtl" style="width:100%;margin-top:22px;border-collapse:collapse;"><tr>
     <td style="text-align:center;padding:6px;"><a href="{approve}" style="display:block;background:#2fa84f;color:#fff;text-decoration:none;font-size:17px;font-weight:bold;padding:15px 0;border-radius:10px;">✅ אשר ופרסם</a></td>
     <td style="text-align:center;padding:6px;"><a href="{reject}" style="display:block;background:#e0533d;color:#fff;text-decoration:none;font-size:17px;font-weight:bold;padding:15px 0;border-radius:10px;">🚫 דחה</a></td>
   </tr></table>
   <div style="font-size:12px;color:#999;margin-top:14px;text-align:center;">לחיצה על "אשר" → הפוסט יפורסם אוטומטית בריצת הפרסום הקרובה.</div>
 </div></div></body></html>"""


def send_resend(subject, html):
    body = json.dumps({"from": RESEND_FROM, "to": [TO], "subject": subject, "html": html}).encode()
    req = urllib.request.Request("https://api.resend.com/emails", data=body,
        headers={"Authorization": f"Bearer {RESEND_KEY}", "Content-Type": "application/json", "User-Agent": UA})
    try:
        with urllib.request.urlopen(req) as r:
            return True, r.read().decode()
    except urllib.error.HTTPError as e:
        return False, f"{e.code} {e.read().decode()[:200]}"


def pick_next_day():
    state = load_state()
    published = set()
    for acc in ["uproductionevents", "uproduction_spain", "ig_uproductionevents", "ig_uproduction_spain"]:
        published |= set(get_published_days(state, acc))
    today = datetime.date.today().isoformat()
    for day in range(1, 101):
        if not glob.glob(os.path.join(ROOT, "content", "days", f"*day{day}-*.json")):
            continue
        if day in published:
            continue
        if queue.day_enqueued(day, today):
            continue
        return day
    return None


def main():
    day = pick_next_day()
    if day is None:
        print("Nothing to enqueue."); return 0
    today = datetime.date.today().isoformat()
    _p = find_image_path(day)
    if not _p:
        print(f"No image for day {day}"); return 0
    image_url = f"{IMG_BASE}/{os.path.basename(_p)}"
    rows = []
    for net, account, pkey, lang in ACCOUNTS:
        data = load_day_lang(day, lang)
        if not data:
            continue
        block = data.get(pkey) or {}
        text = block.get("text") if isinstance(block, dict) else None
        if not text:
            continue
        text = optimize_virality(text, net)
        rows.append({"day": day, "network": net, "account": account, "lang": lang,
                     "headline": data.get("theme") or data.get("title"),
                     "caption": text, "image_url": image_url, "scheduled_date": today})
    if not rows:
        print(f"No content for day {day}"); return 0
    inserted = queue.insert_rows(rows)
    sent = 0
    for r in inserted:
        html = email_html(r["network"], r["day"], r.get("headline", ""), r["id"], r["token"],
                          r["caption"], r.get("image_url") or image_url)
        subj = f"אישור פוסט — {NET_HE.get(r['network'], r['network'])} ({r['lang']}) — יום {day} 📲"
        ok, info = send_resend(subj, html)
        print(f"{'OK ' if ok else 'ERR'} {r['network']}/{r['lang']}: {info[:80]}")
        sent += ok
    print(f"Enqueued {len(inserted)} / emailed {sent} for day {day}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
