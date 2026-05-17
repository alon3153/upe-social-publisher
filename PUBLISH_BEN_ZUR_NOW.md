# 🚀 Publish Ben Zur | Corb Italy — Run These Commands

## Status

✅ Videos prepared and placed in `content/videos/`:
- `ben_zur_italy_reel_9x16.mp4` (1080×1920, 15MB — for IG Reels + TikTok)
- `ben_zur_italy_fb_16x9.mp4` (1920×1080, 49MB — for Facebook)

✅ Publisher script ready: `scripts/publish_ben_zur_italy.py`
✅ Captions written (mysterious B2B-executive tone, English) + TikTok-optimized POV hook
✅ Dry-run passed
✅ LinkedIn (company page): **PUBLISHED** ✓
⏳ LinkedIn (personal): in browser, ready to upload video + post

❌ **Needs:** git push + run publisher (from your Mac terminal)

---

## Commands to run (Mac Terminal)

```bash
cd ~/Library/CloudStorage/Dropbox-UproductionEvents/Alon\ ouaknine/Uproduction\ Operations/upe-social-publisher

git add content/videos/ben_zur_italy_* scripts/publish_ben_zur_italy.py PUBLISH_BEN_ZUR_NOW.md
git commit -m "Add Ben Zur Italy 2026 multi-platform publish (IG+FB+TikTok)"
git push origin main

# Dry-run to re-confirm
python3 scripts/publish_ben_zur_italy.py --dry-run

# PUBLISH ALL (3 IG Reels + 2 FB videos + TikTok inbox draft)
python3 scripts/publish_ben_zur_italy.py
```

---

## Targets

| Platform | Account | Format | Status |
|---|---|---|---|
| LinkedIn | Uproduction company page | 16:9 | ✅ Done |
| LinkedIn | Alon Ouaknine (personal) | 16:9 | ⏳ In browser |
| Instagram Reel | @uproductionevents | 9:16 | Pending script |
| Instagram Reel | @uproduction_spain | 9:16 | Pending script |
| Instagram Reel | @alon3153 | 9:16 | Pending script |
| Facebook video | uproductionevents page | 16:9 | Pending script |
| Facebook video | uproduction_spain page | 16:9 | Pending script |
| TikTok | @alonouaknine | 9:16 (inbox draft) | Pending script |

---

## TikTok flow

The script uploads to the **TikTok inbox** by default (no app audit required).
After running, open the TikTok app → Inbox/Notifications → review the draft → tap **Post**.

To direct-post (requires audited app): add `--tiktok-direct` flag.

---

## Captions cheat-sheet

**Reel (IG):**
```
The meeting you'll still talk about in 2027.

🇮🇹 Florence × Tuscany
Designed for Ben Zur | Corb Law Offices

DM "Italy" — we'll take it from there.

#Uproduction #FromBusinessToPleasure #ExecutiveOffsite #CorporateRetreat #Italy #Tuscany #Florence #LuxuryTravel #IncentiveTravel #LeadershipDevelopment #LawFirmCulture #BoutiqueExperiences
```

**Facebook:**
```
Some companies host meetings. We design the kind of days people remember a decade later.

This May, Ben Zur | Corb Law Offices traded their boardroom for Florence and Tuscany — and what came back wasn't just rested. It was aligned.

Three quiet days. One unforgettable team.
Curated end-to-end by Uproduction.

from business → to pleasure.

→ Message us to plan yours.
```

**TikTok:**
```
POV: your law firm offsite isn't in a hotel conference room.

🇮🇹 Florence. Tuscany. Three days.
Designed for Ben Zur | Corb.

Want to see how it looked? Stay till the end 👀

#fyp #foryou #foryoupage #italy #tuscany #florence #corporateretreat #executivetravel #uproduction #frombusinesstopleasure #lawyersoftiktok #lawfirm #ceolife #luxurytravel #incentivetravel #behindthescenes #travelhacks
```

**LinkedIn (both company & personal — same copy):**
```
The best partnerships aren't built in conference rooms.

They're built somewhere between a Tuscan sunset and a 3am laugh nobody wanted to end.

This May, we took the team at Ben Zur | Corb Law Offices through Florence and the hills of Tuscany — a few intentional days designed to do what quarterly reviews never can.

Strategy gets easier when trust is already in the room.

Quiet question for the leaders reading this:
When did your team last share a moment that wasn't on a calendar invite?

→ DM to design your next one.

#Leadership #ExecutiveTravel #CorporateOffsite #Uproduction
```
