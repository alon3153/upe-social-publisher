#!/usr/bin/env python3
import os, sys, json
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from publishers import queue
rows = queue._req("GET", "post_approvals",
                  params={"select": "id,day,network,account,lang,status,scheduled_date,caption,video_url,image_url",
                          "day": "in.(9001,9002,9003)", "order": "day.asc"})
for r in rows:
    cap = (r.get("caption") or "")[:60].replace("\n", " ")
    print(f"id={r['id']} day={r['day']} {r['network']}/{r['account']} lang={r.get('lang')} status={r['status']} "
          f"video={'Y' if r.get('video_url') else 'N'} img={'Y' if r.get('image_url') else 'N'} sched={r.get('scheduled_date')}")
    print(f"    cap: {cap}")
    print(f"    vid: {r.get('video_url')}")
