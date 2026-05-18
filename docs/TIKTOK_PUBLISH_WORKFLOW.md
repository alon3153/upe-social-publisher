# TikTok Publishing Workflow — @alonouaknine

**Last verified:** 2026-05-18 | **Account:** `@alonouaknine` | **App:** UPE Social Publisher (Sandbox)

This is the complete workflow for publishing a video to TikTok via the UPE Social Publisher pipeline. Follow this end-to-end whenever Alon asks "פרסם [סרטון] בטיקטוק" or similar.

---

## TL;DR — Standard publish (token still valid)

```bash
cd "Uproduction Operations/upe-social-publisher"

# 1. Make sure video is at content/videos/<name>.mp4
# 2. Edit script (or create new one) — set VIDEO_PATH + CAPTION
# 3. Run:
python3 scripts/publish_ab_dental_tiktok.py
```

Result: video lands in `@alonouaknine` TikTok Inbox + caption is on clipboard. User opens TikTok app, taps the inbox draft, pastes caption (Cmd/⌘V), presses Post.

---

## System architecture

| Component | Path | Purpose |
|-----------|------|---------|
| Repo root | `Uproduction Operations/upe-social-publisher/` | Git repo (alon3153/upe-social-publisher) |
| Env vars | `.env` (gitignored) | Credentials & tokens |
| Publisher lib | `publishers/tiktok.py` | API client — OAuth + upload |
| OAuth setup | `scripts/tiktok_oauth.py` | One-time browser OAuth |
| Video upload | `scripts/publish_ab_dental_tiktok.py` | Template — copy & customize |
| Callback page | `docs/tiktok-callback.html` → hosted at `alon3153.github.io/upe-social-publisher/tiktok-callback.html` | Shows auth code |
| Videos | `content/videos/*.mp4` | Source media |

---

## Credentials (in `.env`)

```env
TIKTOK_CLIENT_KEY=sbawv5tuk2byuijc9r          # Sandbox client key
TIKTOK_CLIENT_SECRET=XYR8pgixjudNbFRvpdM7gzV71NzjXPqK
TIKTOK_ENV=sandbox

TIKTOK_CLIENT_KEY_PROD=awx35v5zmh5z6zg0       # Production (Draft, not in use)
TIKTOK_CLIENT_SECRET_PROD=bPPwVPBTvzFY5hQYBAWZwFnwCVagC2FI

TIKTOK_ACCESS_TOKEN=act.xxxxx                 # 24h validity, auto-refreshed by script
TIKTOK_REFRESH_TOKEN=rft.xxxxx                # 365d validity
TIKTOK_OPEN_ID=-000oxMow0kzUIvvhW8oBM-W4HhvvWQOt_gy
TIKTOK_SCOPE=user.info.basic,video.upload
```

**Token rotation:** access_token expires every 24h, but `publish_ab_dental_tiktok.py` auto-refreshes via `refresh_token` (365d). Re-run OAuth is needed **once a year** — until **2027-05-18**.

---

## TikTok app setup (one-time, done)

- **App name:** UPE Social Publisher
- **App ID:** `7639350920673036309`
- **Sandbox ID:** `7640396709851891720`
- **Target user:** `@alonouaknine` (Active)
- **Products enabled:** Login Kit, Content Posting API
- **Scopes approved:** `user.info.basic`, `video.upload` (NOT `video.publish` — requires App Review)
- **Redirect URI:** `https://alon3153.github.io/upe-social-publisher/tiktok-callback.html`
- **App icon:** `assets/upe_app_icon_1024.png` (UPE logo, 1024×1024)
- **Developer Portal:** https://developers.tiktok.com/app/7639350920673036309/sandbox/7640396709851891720

---

## Two upload modes — pick one

### Mode A: INBOX (default, working today)
- Scope: `video.upload`
- API uploads video as a draft to user's TikTok Inbox
- **Caption is NOT sent via API** — TikTok security restriction
- User opens TikTok app → Inbox → draft → pastes caption → Post
- Works immediately, no app review needed
- Script auto-copies caption to OS clipboard right before upload

### Mode B: DIRECT POST (not yet available)
- Scope: `video.publish` (requires TikTok App Audit, takes days–weeks)
- Caption + privacy set via API; posts directly to feed
- Run with `--direct --privacy PUBLIC_TO_EVERYONE`
- Status: NOT approved for this app. Skip for now.

---

## Standard pipeline — to publish a NEW video

### 1. Verify video is in place
```bash
ls -la "Uproduction Operations/upe-social-publisher/content/videos/"
# Video must be .mp4, ideally 9:16 vertical for Reels, < 287MB
```

### 2. Copy + customize the template script
```bash
cd "Uproduction Operations/upe-social-publisher"
cp scripts/publish_ab_dental_tiktok.py scripts/publish_<event_slug>_tiktok.py
```

Edit the new script — change these two lines:
```python
VIDEO_PATH = ROOT / "content/videos/<your_video>.mp4"

CAPTION = """<hook line>

<2-3 short emoji lines>

הפקה: @alonouaknine
Uproduction Events
from business to pleasure 🎯

#fyp #foryou #foryoupage <event-specific tags> #uproductionevents #upe"""
```

### 3. Run the publish script
```bash
python3 scripts/publish_<event_slug>_tiktok.py
```

Expected output:
```
🎬 Video: <name>.mp4 (XX,XXX,XXXB)
📝 Caption: NNN chars
🎯 Mode: INBOX (draft)
📋 Caption copied to clipboard — paste in TikTok app
📤 Init inbox upload — size=… chunks=…
📦 publish_id: v_inbox_file~v2.…
⬆️  Uploading chunks…
✅ Upload complete, polling status…

🎉 SUCCESS!
   status: SEND_TO_USER_INBOX
```

### 4. Alon opens TikTok app → Inbox → draft → paste caption → Post

### 5. Commit the new script to GitHub
```bash
git add scripts/publish_<event_slug>_tiktok.py
git commit -m "feat: publish <event> reel to TikTok"
git push origin main
```

---

## Token refresh — automatic

The script handles expired access tokens automatically. If you ever see manual refresh needed:

```bash
python3 -c "
import os
from dotenv import load_dotenv
load_dotenv('.env')
from publishers.tiktok import refresh_access_token
tokens = refresh_access_token(
    os.environ['TIKTOK_CLIENT_KEY'],
    os.environ['TIKTOK_CLIENT_SECRET'],
    os.environ['TIKTOK_REFRESH_TOKEN']
)
print(tokens)
"
```

Then write the new `access_token` and `refresh_token` back into `.env`.

---

## Full OAuth re-authorization (only once per 365 days, or if `.env` lost)

```bash
cd "Uproduction Operations/upe-social-publisher"
python3 scripts/tiktok_oauth.py
```

Flow:
1. Browser opens TikTok authorize page (with Sandbox `client_key`)
2. Alon authorizes (must be logged in as `@alonouaknine` — the Sandbox target user)
3. Browser redirects to `alon3153.github.io/upe-social-publisher/tiktok-callback.html`
4. Page shows the auth code (with 📋 Copy button)
5. Alon copies code, pastes into terminal
6. Script exchanges code → tokens → saves to `.env`

---

## Troubleshooting — known errors and fixes

### `non_sandbox_target` on authorize page
**Cause:** Target user not properly added to Sandbox, OR not logged into `@alonouaknine`.

**Fix:**
1. TikTok Developer Portal → app → Sandbox tab → **Sandbox settings**
2. Under **Target users**: delete current entry if any
3. Click **Add account** — this opens a TikTok login flow
4. Log in as `@alonouaknine` and **Agree to Developer Terms of Service**
5. Status must show **Active** (not Pending)
6. **Apply changes**
7. Wait up to 1 hour for propagation
8. Retry OAuth

### `scope` error on authorize page
**Cause:** Requesting scopes that aren't approved on this Sandbox.

**Fix:** Reduce scope to what's actually approved. Edit `scripts/tiktok_oauth.py`:
```python
SCOPE = "user.info.basic,video.upload"   # remove video.publish if not approved
```

Or, ask Alon to enable additional scopes:
- Developer Portal → Scopes tab → check `user.info.basic`, `video.upload` → Apply changes
- `video.publish` requires App Audit submission

### `invalid_redirect_uri`
**Cause:** Redirect URI in Login Kit settings doesn't exactly match the one in the OAuth URL.

**Fix:** Developer Portal → Login Kit → Settings → Redirect URI = exactly:
```
https://alon3153.github.io/upe-social-publisher/tiktok-callback.html
```

### `access_token_invalid` / 401 on upload
**Cause:** Token expired (24h passed).

**Fix:** Script auto-refreshes. If refresh also fails, run full OAuth (`scripts/tiktok_oauth.py`).

### Video uploaded but caption is empty in TikTok
**Cause:** Inbox mode (current setup) doesn't accept captions via API.

**Fix:** Already implemented — script copies caption to OS clipboard before upload. Alon pastes it in the TikTok app when reviewing the draft.

### `unauthorized_client` on authorize page
**Cause:** App is in Production Draft, not Sandbox. Or wrong `client_key` is in `.env`.

**Fix:** Verify `TIKTOK_CLIENT_KEY=sbawv5tuk2byuijc9r` (Sandbox key, starts with `sb`). The Production key (`awx…`) won't work until App Audit completes.

---

## Caption style guide — for viral Hebrew TikTok

- **Hook in first line** — emotion or question, max 50 chars
- **Short emoji-heavy lines** — separated by blank lines
- **Mention `@alonouaknine`** as creator
- **End with brand line:** "Uproduction Events / from business to pleasure 🎯"
- **Hashtag mix:**
  - FYP boosters: `#fyp #foryou #foryoupage`
  - Hebrew niche: `#אירועיחברה #גאלה #קרוז #הפקתאירועים #ישראל`
  - Event-specific: `#abdental` etc.
  - Brand: `#uproductionevents #upe`
  - English niche: `#corporateevents #incentivetravel #eventproduction`
- **Total length:** 300–500 chars ideal, max 2200

---

## When Alon says "פרסם [event] בטיקטוק" — what Claude should do

1. **Identify** event + video file (ask if unclear which video)
2. **Verify** video is in `content/videos/` (move/copy if needed)
3. **Draft caption** following the style guide above — show to Alon for approval
4. **Create** a new `scripts/publish_<event_slug>_tiktok.py` based on the template
5. **Confirm** with Alon before running (UPE Iron Rule: "Never publish to social media without approval")
6. **Run** the script
7. **Tell Alon** to open TikTok app → Inbox → paste caption (already on clipboard) → Post
8. **Commit** the new script to GitHub
9. **Save observation** to memory after Alon confirms it published

---

## Files in this workflow

- `scripts/publish_ab_dental_tiktok.py` — reference template (working as of 2026-05-18)
- `scripts/publish_nirotek_reel.py` — older Instagram-only example
- `scripts/tiktok_oauth.py` — one-time OAuth setup
- `publishers/tiktok.py` — API library (don't modify unless API changes)
- `docs/TIKTOK_SETUP.md` — original setup notes
- `docs/tiktok-callback.html` — auth code display page (deployed via GitHub Pages)
