#!/usr/bin/env python3
"""Enqueue Sofia presenter Reels into the Supabase approval queue and email Alon
ONE approval email per video (Approve/Reject buttons → same edge function → publish-approved).
Reads a queue JSON: content/sofia/queue/<file>.json (default week1.json).

Each entry: {id, headline, caption, video_url, watch_url, accounts:[ig keys], scheduled_date, day}
"""
import os, sys, json, urllib.request, urllib.error
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from publishers import queue

FN = (os.environ.get("SUPABASE_URL", "").rstrip("/")) + "/functions/v1/approve"
RESEND_KEY = os.environ.get("RESEND_API_KEY", "")
RESEND_FROM = os.environ.get("RESEND_FROM", "")
APPROVAL_TO = os.environ.get("APPROVAL_TO", "")
NET_HE = {"uproduction_spain": "Uproduction Spain", "uproductionevents": "Uproduction Events"}


def email_html(acc, headline, rid, token, caption, video_url):
    approve = f"{FN}?id={rid}&token={token}&action=approve"
    reject = f"{FN}?id={rid}&token={token}&action=reject"
    cap_html = caption.replace("\n", "<br>")
    return f"""<html dir="rtl" lang="he"><head><meta charset="utf-8"></head>
<body dir="rtl" style="font-family:Arial,Helvetica,sans-serif;font-size:14px;direction:rtl;text-align:right;background:#f4f4f4;padding:18px;">
<div dir="rtl" style="max-width:520px;margin:auto;background:#fff;border-radius:14px;overflow:hidden;">
  <div style="background:#1C1C1C;color:#FBCE0A;padding:16px 20px;font-size:18px;font-weight:bold;">🎬 Sofia — אישור סרטון לפרסום</div>
  <div dir="rtl" style="padding:20px;direction:rtl;text-align:right;">
    <p style="font-size:16px;font-weight:bold;margin:0 0 4px;">{headline}</p>
    <p style="color:#888;margin:0 0 14px;">חשבון: {NET_HE.get(acc, acc)} · Instagram Reels</p>
    <div dir="ltr" style="direction:ltr;text-align:center;margin:14px 0;">
      <a href="{video_url}" style="display:inline-block;background:#1C1C1C;color:#fff;text-decoration:none;font-size:15px;padding:12px 22px;border-radius:8px;">▶️ צפה בסרטון</a>
    </div>
    <div style="background:#faf8f0;border-radius:8px;padding:12px;font-size:13px;color:#333;white-space:normal;">{cap_html}</div>
    <table dir="rtl" style="width:100%;margin-top:18px;border-collapse:collapse;"><tr>
     <td style="text-align:center;padding:6px;"><a href="{approve}" style="display:block;background:#2fa84f;color:#fff;text-decoration:none;font-size:17px;font-weight:bold;padding:15px 0;border-radius:10px;">✅ אשר ופרסם</a></td>
     <td style="text-align:center;padding:6px;"><a href="{reject}" style="display:block;background:#e0533d;color:#fff;text-decoration:none;font-size:17px;font-weight:bold;padding:15px 0;border-radius:10px;">🚫 דחה</a></td>
    </tr></table>
  </div>
</div></body></html>"""


def send_resend(subj, html):
    body = json.dumps({"from": RESEND_FROM, "to": [APPROVAL_TO], "subject": subj, "html": html}).encode()
    req = urllib.request.Request("https://api.resend.com/emails", data=body,
                                 headers={"Authorization": f"Bearer {RESEND_KEY}", "Content-Type": "application/json",
                                          "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"})
    try:
        with urllib.request.urlopen(req) as r:
            return True, r.read().decode()[:80]
    except urllib.error.HTTPError as e:
        return False, f"{e.code} {e.read().decode()[:160]}"


def main():
    qfile = sys.argv[1] if len(sys.argv) > 1 else "week1"
    posts = json.load(open(f"{ROOT}/content/sofia/queue/{qfile}.json"))
    # Each Sofia video fans out to both Instagram (Reel) and Facebook (page video),
    # per account. LinkedIn org video + TikTok are pending OAuth/app-audit (see README).
    rows = []
    for p in posts:
        for i, acc in enumerate(p["accounts"]):
            lang = "es" if "spain" in acc else "en"
            base = p["day"] * 10 + i
            common = {"lang": lang, "headline": p["headline"], "caption": p["caption"],
                      "video_url": p["video_url"], "scheduled_date": p["scheduled_date"]}
            rows.append({"day": base, "network": "instagram", "account": f"ig_{acc}", **common})
            rows.append({"day": base + 5, "network": "facebook", "account": acc, **common})
    # Idempotency: skip rows whose video is already queued for that network+account,
    # so a recurring cron never re-sends or double-publishes the same clip.
    fresh = [r for r in rows
             if not queue.video_enqueued(r["video_url"], r["network"], r["account"])]
    skipped = len(rows) - len(fresh)
    if skipped:
        print(f"Skipped {skipped} already-enqueued rows")
    if not fresh:
        print("Nothing new to enqueue."); return 0
    rows = fresh
    inserted = queue.insert_rows(rows)
    print(f"Enqueued {len(inserted)} Sofia rows")
    sent = 0
    for r in inserted:
        net_he = NET_HE.get(r["network"], r["network"])
        subj = f"🎬 אישור סרטון Sofia — {net_he} ({r['lang']}) — {r.get('headline','')}"
        ok, info = send_resend(subj, email_html(f"{net_he} · {r['account']}", r.get('headline', ''),
                                                r['id'], r['token'], r['caption'], r['video_url']))
        print(f"{'OK ' if ok else 'ERR'} {r['network']}/{r['account']}: {info}")
        sent += ok
    print(f"Emailed {sent}/{len(inserted)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
