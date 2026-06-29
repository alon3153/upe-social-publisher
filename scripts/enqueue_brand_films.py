#!/usr/bin/env python3
"""Enqueue the 3 UPE brand films into the LinkedIn 3-channel approval gate.
Personal(HE) / English page(EN) / Spain page(ES). Rows land as PENDING in
post_approvals → daily approval email → on approval, publish_approved.py posts
the VIDEO via the new linkedin._upload_video path (PR #19).

DRY-RUN by default. Pass --go to insert rows (requires PR #19 merged/deployed
+ SUPABASE_URL/SUPABASE_SERVICE_ROLE_KEY)."""
import os, sys, json
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

FAL = json.load(open("/tmp/upe_brand_fal_urls.json"))
def u(name): return next(v for k, v in FAL.items() if k.endswith(name))

ROWS = [
 {"day": 9001, "network": "linkedin", "account": "li_personal", "lang": "he",
  "headline": "UPE brand film — personal (HE)",
  "caption": ("16 שנה. 1,500+ אירועים. 130+ יעדים. 25,000+ משתתפים.\n\n"
              "כשהקמתי את Uproduction Events ב-2010, החזון היה פשוט: להפוך שאיפות של חברות "
              "לחוויות בלתי-נשכחות — הפקת אירועים וטיולי תמריץ ברמה עולמית.\nfrom business to pleasure.\n\n"
              "מתכננים את האירוע הבא? נשמח לדבר.\n🔗 upe.co.il\n\n"
              "#הפקתאירועים #אירועים #טיוליתמריץ #incentivetravel #eventproduction #uproduction"),
  "video_url": u("upe-brand-film-he-music.mp4"), "scheduled_date": "2026-07-06"},

 {"day": 9002, "network": "linkedin", "account": "li_english", "lang": "en",
  "headline": "UPE brand film — English page (EN)",
  "caption": ("16 years. 1,500+ events. 130+ destinations. 25,000+ participants.\n\n"
              "Since 2010, Uproduction Events turns corporate ambition into unforgettable "
              "experiences — world-class event production & incentive travel.\nFrom business to pleasure.\n\n"
              "Planning your next event? Let's talk.\n🔗 upe.co.il\n\n"
              "#eventproduction #incentivetravel #corporateevents #eventprofs #MICE #uproduction"),
  "video_url": u("upe-brand-film-music.mp4"), "scheduled_date": "2026-07-06"},

 {"day": 9003, "network": "linkedin", "account": "li_spain", "lang": "es",
  "headline": "UPE brand film — Spain page (ES)",
  "caption": ("16 años. 1.500+ eventos. 130+ destinos. 25.000+ participantes.\n\n"
              "Desde 2010, Uproduction Events convierte la ambición corporativa en experiencias "
              "inolvidables — producción de eventos y viajes de incentivo de clase mundial.\nFrom business to pleasure.\n\n"
              "¿Planificas tu próximo evento? Hablemos.\n🔗 upe-spain.com\n\n"
              "#produccióndeeventos #viajesdeincentivo #eventoscorporativos #MICE #incentivetravel"),
  "video_url": u("upe-brand-es-music.mp4"), "scheduled_date": "2026-07-06"},
]

ROUTE = {"li_personal": "Alon's personal profile", "li_english": "English company page (LINKEDIN_ORG_URN)",
         "li_spain": "Spain company page (LINKEDIN_ORG_URN_SPAIN)"}

def main():
    go = "--go" in sys.argv
    print("== " + ("GO (insert PENDING rows)" if go else "DRY-RUN") + " == LinkedIn 3-channel brand films\n")
    for r in ROWS:
        print(f"▶ {ROUTE[r['account']]}  [{r['lang']}]")
        print(f"   video: {r['video_url']}")
        print(f"   caption: {r['caption'].splitlines()[0]} …\n")
    if go:
        from publishers import queue
        ins = queue.insert_rows(ROWS)
        print(f"✅ enqueued {len(ins)} PENDING rows → they appear in the next approval email.")
    else:
        print("(dry-run — pass --go AFTER PR #19 is merged/deployed to insert into the live approval queue)")

main()
