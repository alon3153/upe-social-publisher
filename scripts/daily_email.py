#!/usr/bin/env python3
"""Daily approval email: pick next day, build per-account posts, virality-optimize,
enqueue in Supabase, send ONE email per post via Resend with Approve/Reject buttons."""
import os, sys, json, glob, datetime, urllib.request, urllib.error, urllib.parse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from publishers import queue
from publishers.content import find_image_path
from publishers.state import load_state, get_published_days

FN = (os.environ.get("SUPABASE_URL", "").rstrip("/")) + "/functions/v1/approve"
RESEND_KEY = os.environ.get("RESEND_API_KEY", "")
RESEND_FROM = os.environ.get("RESEND_FROM") or "uproduction <onboarding@resend.dev>"
TO = os.environ.get("APPROVAL_TO") or "alon@upe.co.il"
IMG_BASE = "https://cdn.jsdelivr.net/gh/alon3153/upe-social-publisher@main/content/images"
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"

# (network, account, platform_key_in_json, lang)
ACCOUNTS = [
    ("facebook",  "uproductionevents", "facebook",  "en"),
    ("facebook",  "uproduction_spain", "facebook",  "es"),
    ("instagram", "ig_uproductionevents", "instagram", "en"),
    ("instagram", "ig_uproduction_spain", "instagram", "es"),
    ("linkedin",  "alon3153",    "linkedin", "en"),  # English company page (default org)
    ("linkedin",  "li_personal", "linkedin", "he"),  # Alon's personal profile (HE)
    ("linkedin",  "li_natalia",  "linkedin", "he"),  # advocate — Natalia (personal, distinct HE variant)
    ("linkedin",  "li_danielle", "linkedin", "he"),  # advocate — Danielle (personal, distinct HE variant)
    ("linkedin",  "li_spain",    "linkedin", "es"),  # Uproduction Spain company page (ES)
]

# Employee-advocacy: each advocate posts a DISTINCT variant of the same HE topic
# (never an identical copy of Alon's post — that would read as a pod and get throttled).
ADVOCATE_NAMES = {"li_natalia": "נטליה", "li_danielle": "דניאל"}
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
GEN_MODEL = os.environ.get("GEN_MODEL", "claude-sonnet-4-6")


def advocate_variant(base_text, advocate_name):
    """Rewrite Alon's HE LinkedIn post into a distinct variant in the advocate's
    own voice (same topic/facts, different hook + phrasing). Falls back to the
    base text if the API key is missing or the call fails (never blocks the run)."""
    if not ANTHROPIC_API_KEY or not base_text:
        return base_text
    prompt = (
        f"להלן פוסט LinkedIn בעברית שאלון וקנין (מייסד Uproduction Events) מפרסם מהפרופיל שלו:\n\n"
        f"\"\"\"\n{base_text}\n\"\"\"\n\n"
        f"כתבי מחדש את הפוסט מזווית שונה ובקול אישי של {advocate_name}, אשת צוות בכירה ב-UPE שמשתפת "
        f"את הפרספקטיבה שלה על אותו נושא. אותם עובדות/מספרים, אבל הוק שונה, ניסוח שונה ופתיחה שונה — "
        f"כך שזה לא ייראה כמו העתק של הפוסט של אלון. עברית טבעית, אורך דומה. החזירי אך ורק את טקסט הפוסט, בלי הקדמות."
    )
    try:
        body = json.dumps({"model": GEN_MODEL, "max_tokens": 1500,
                           "messages": [{"role": "user", "content": prompt}]}).encode()
        req = urllib.request.Request("https://api.anthropic.com/v1/messages", data=body, headers={
            "x-api-key": ANTHROPIC_API_KEY, "anthropic-version": "2023-06-01", "content-type": "application/json"})
        with urllib.request.urlopen(req, timeout=120) as r:
            resp = json.loads(r.read().decode())
        out = "".join(b.get("text", "") for b in resp.get("content", [])).strip()
        return out or base_text
    except Exception as e:
        print(f"  advocate_variant({advocate_name}) failed, using base text: {e}")
        return base_text
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


def post_card(r):
    """Inner card for a single post inside the consolidated digest email."""
    approve = f"{FN}?id={r['id']}&token={r['token']}&action=approve"
    reject = f"{FN}?id={r['id']}&token={r['token']}&action=reject"
    cap = (r.get("caption") or "").replace("&", "&amp;").replace("<", "&lt;").replace("\n", "<br>")
    net = NET_HE.get(r["network"], r["network"])
    img = r.get("image_url") or ""
    return f"""<div dir="rtl" style="border:1px solid #eee;border-radius:12px;padding:16px;margin-bottom:16px;">
   <div style="font-size:16px;font-weight:bold;color:#141414;margin-bottom:10px;">{net} <span style="font-size:12px;color:#888;font-weight:normal;">· {r.get('lang','')}</span></div>
   <img src="{img}" alt="post" style="width:100%;border-radius:8px;display:block;margin-bottom:12px;">
   <div dir="ltr" style="direction:ltr;text-align:left;background:#f7f7f7;border-radius:8px;padding:12px;font-size:13px;line-height:1.55;color:#222;">{cap}</div>
   <table dir="rtl" style="width:100%;margin-top:12px;border-collapse:collapse;"><tr>
     <td style="text-align:center;padding:4px;"><a href="{approve}" style="display:block;background:#2fa84f;color:#fff;text-decoration:none;font-size:14px;font-weight:bold;padding:11px 0;border-radius:8px;">✅ אשר</a></td>
     <td style="text-align:center;padding:4px;"><a href="{reject}" style="display:block;background:#e0533d;color:#fff;text-decoration:none;font-size:14px;font-weight:bold;padding:11px 0;border-radius:8px;">🚫 דחה</a></td>
   </tr></table>
 </div>"""


def email_html_digest(day, approve_all_url, rows):
    """ONE consolidated email: 'approve all' button on top + a card per post."""
    n = len(rows)
    cards = "".join(post_card(r) for r in rows)
    return f"""<html dir="rtl" lang="he"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"></head>
<body dir="rtl" style="font-family:Arial,Helvetica,sans-serif;font-size:14px;direction:rtl;text-align:right;background:#f2f2f2;margin:0;padding:0;">
<div dir="rtl" style="max-width:600px;margin:0 auto;background:#fff;">
 <div dir="rtl" style="background:#141414;padding:18px 24px;text-align:right;">
   <span style="color:#FBCE0A;font-size:20px;font-weight:bold;">uproduction</span>
   <span style="color:#bbb;font-size:12px;"> &nbsp;from business to pleasure</span></div>
 <div dir="rtl" style="padding:20px 24px;direction:rtl;text-align:right;">
   <div style="font-size:13px;color:#888;">פוסטים לאישור · יום {day}</div>
   <div style="font-size:20px;font-weight:bold;color:#141414;margin:4px 0 14px;">{n} פוסטים ממתינים לאישור</div>
   <a href="{approve_all_url}" style="display:block;background:#2fa84f;color:#fff;text-decoration:none;font-size:18px;font-weight:bold;padding:16px 0;border-radius:12px;text-align:center;margin-bottom:8px;">✅ אשר הכל ({n} פוסטים)</a>
   <div style="font-size:12px;color:#999;margin-bottom:22px;text-align:center;">או אשר / דחה כל פוסט בנפרד למטה.</div>
   {cards}
   <div style="font-size:12px;color:#999;margin-top:6px;text-align:center;">לחיצה על "אשר" → הפוסט יפורסם אוטומטית בריצת הפרסום הקרובה.</div>
 </div></div></body></html>"""


def send_graph_html(subject, html):
    """Send via Microsoft Graph (client-credentials) from MS_GRAPH_FROM.
    Internal alon@upe.co.il sender → lands in Focused Inbox, unlike Resend's
    onboarding@resend.dev which gets filtered/buried. Returns (ok, info)."""
    tenant = os.environ.get("MS_GRAPH_TENANT_ID")
    client_id = os.environ.get("MS_GRAPH_CLIENT_ID")
    secret = os.environ.get("MS_GRAPH_CLIENT_SECRET")
    sender = os.environ.get("MS_GRAPH_FROM")
    if not all([tenant, client_id, secret, sender]):
        return False, "graph creds missing"
    try:
        tok = urllib.parse.urlencode({
            "client_id": client_id, "client_secret": secret,
            "scope": "https://graph.microsoft.com/.default",
            "grant_type": "client_credentials",
        }).encode()
        treq = urllib.request.Request(
            f"https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token",
            data=tok, headers={"Content-Type": "application/x-www-form-urlencoded"})
        with urllib.request.urlopen(treq, timeout=30) as r:
            access = json.loads(r.read().decode()).get("access_token")
        if not access:
            return False, "no access_token"
        payload = json.dumps({
            "message": {
                "subject": subject,
                "body": {"contentType": "HTML", "content": html},
                "toRecipients": [{"emailAddress": {"address": TO}}],
            },
            "saveToSentItems": True,
        }).encode()
        sreq = urllib.request.Request(
            f"https://graph.microsoft.com/v1.0/users/{sender}/sendMail",
            data=payload,
            headers={"Authorization": f"Bearer {access}", "Content-Type": "application/json"})
        with urllib.request.urlopen(sreq, timeout=30) as r:
            return True, f"graph {r.status}"
    except urllib.error.HTTPError as e:
        return False, f"graph {e.code} {e.read().decode()[:200]}"
    except Exception as e:
        return False, f"graph error {e}"


def send_resend(subject, html, attachment_path=None):
    payload = {"from": RESEND_FROM, "to": [TO], "subject": subject, "html": html}
    if attachment_path and os.path.isfile(attachment_path):
        import base64
        with open(attachment_path, "rb") as f:
            payload["attachments"] = [{
                "filename": os.path.basename(attachment_path),
                "content": base64.b64encode(f.read()).decode(),
                "content_type": "image/png",
            }]
    body = json.dumps(payload).encode()
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
    # Supabase is the real source of truth — the cloud publisher marks rows
    # published there but never writes back to state.json. Without this union,
    # pick_next_day reads the frozen state.json and re-enqueues the same day forever.
    try:
        published |= queue.published_days()
    except Exception as e:
        print(f"warn: could not read published_days from Supabase: {e}")
    today = datetime.date.today().isoformat()
    for day in range(1, 131):
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
        if account in ADVOCATE_NAMES:  # distinct per-advocate rewrite (no duplicate posts)
            text = advocate_variant(text, ADVOCATE_NAMES[account])
        rows.append({"day": day, "network": net, "account": account, "lang": lang,
                     "headline": data.get("theme") or data.get("title"),
                     "caption": text, "image_url": image_url, "scheduled_date": today})
    if not rows:
        print(f"No content for day {day}"); return 0
    inserted = queue.insert_rows(rows)
    if not inserted:
        print(f"No rows inserted for day {day}"); return 0
    # One 'approve all' link for the whole day; any row's token proves email receipt.
    approve_all_url = f"{FN}?action=approve_all&day={day}&token={inserted[0]['token']}"
    html = email_html_digest(day, approve_all_url, inserted)
    subj = f"אישור פוסטים — יום {day} · {len(inserted)} רשתות 📲"
    # Prefer Microsoft Graph (internal alon@upe.co.il → Focused Inbox); the
    # Resend onboarding@resend.dev sender gets filtered/buried. Fall back to
    # Resend only if Graph is unavailable.
    ok, info = send_graph_html(subj, html)
    if not ok:
        print(f"graph send failed ({info}); falling back to resend")
        ok, info = send_resend(subj, html, attachment_path=_p)
    print(f"{'OK ' if ok else 'ERR'} digest: {info[:120]}")
    print(f"Enqueued {len(inserted)} / emailed {1 if ok else 0} consolidated email for day {day}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
