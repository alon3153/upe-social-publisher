#!/usr/bin/env python3
"""Resend ONE approval email for posts stuck pending (the backlog the daily
email can't re-surface, because their day is already partly published so
pick_next_day skips it). Fetches the existing pending rows from Supabase and
re-emails them with their original id+token so the Approve/Reject links work.

Usage: python3 scripts/resend_pending.py [min_age_days]
  min_age_days  only resend rows older than this many days (default 0 = all pending)
"""
import os, sys, datetime
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from publishers import queue

# daily_email isn't a package module; load it by path to reuse its email helpers
import importlib.util


def _load_daily():
    spec = importlib.util.spec_from_file_location(
        "daily_email", os.path.join(ROOT, "scripts", "daily_email.py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def main():
    min_age = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    daily = _load_daily()
    rows = queue._req("GET", "post_approvals",
                      params={"select": "*", "status": "eq.pending", "order": "day.asc,network.asc"})
    if min_age > 0:
        cutoff = (datetime.date.today() - datetime.timedelta(days=min_age)).isoformat()
        rows = [r for r in rows if (r.get("scheduled_date") or "9999")[:10] <= cutoff]
    if not rows:
        print("No pending rows to resend.")
        return 0
    days = sorted({int(r["day"]) for r in rows if r.get("day") is not None})
    cards = "".join(daily.post_card(r) for r in rows)
    n = len(rows)
    html = f"""<html dir="rtl" lang="he"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"></head>
<body dir="rtl" style="font-family:Arial,Helvetica,sans-serif;font-size:14px;direction:rtl;text-align:right;background:#f2f2f2;margin:0;padding:0;">
<div dir="rtl" style="max-width:600px;margin:0 auto;background:#fff;">
 <div dir="rtl" style="background:#141414;padding:18px 24px;text-align:right;">
   <span style="color:#FBCE0A;font-size:20px;font-weight:bold;">uproduction</span>
   <span style="color:#bbb;font-size:12px;"> &nbsp;from business to pleasure</span></div>
 <div dir="rtl" style="padding:20px 24px;direction:rtl;text-align:right;">
   <div style="font-size:13px;color:#c0392b;font-weight:bold;">⏳ פוסטים תקועים בהמתנה (ימים: {', '.join(map(str, days))})</div>
   <div style="font-size:20px;font-weight:bold;color:#141414;margin:4px 0 14px;">{n} פוסטים ממתינים לאישור</div>
   <div style="font-size:12px;color:#999;margin-bottom:22px;text-align:center;">אשר / דחה כל פוסט בנפרד למטה.</div>
   {cards}
   <div style="font-size:12px;color:#999;margin-top:6px;text-align:center;">לחיצה על "אשר" → הפוסט יפורסם אוטומטית בריצת הפרסום הקרובה.</div>
 </div></div></body></html>"""
    subj = f"🔴 תזכורת: {n} פוסטים תקועים לאישור (ימים {', '.join(map(str, days))})"
    ok, info = daily.send_graph_html(subj, html)
    if not ok:
        print(f"graph send failed ({info}); falling back to resend")
        ok, info = daily.send_resend(subj, html)
    print(f"{'OK ' if ok else 'ERR'} resend {n} pending (days {days}): {info[:120]}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
