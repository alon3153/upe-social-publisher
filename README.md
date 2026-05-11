# UPE Social Publisher

Daily automated publishing to Facebook Pages and Instagram Business accounts via Meta Graph API. Runs on GitHub Actions — no Mac dependency, no browser automation.

**Schedule:** 09:00 IST every day (06:00 UTC cron).

## Accounts

| Platform | Account | Env vars (GitHub Secrets) |
|---|---|---|
| Facebook Page | `uproductionevents` | `FB_UPRODUCTIONEVENTS_PAGE_ID`, `FB_UPRODUCTIONEVENTS_PAGE_TOKEN` |
| Facebook Page | `uproduction_spain` | `FB_UPRODUCTION_SPAIN_PAGE_ID`, `FB_UPRODUCTION_SPAIN_PAGE_TOKEN` |
| Instagram Business | `@uproductionevents` | `IG_UPRODUCTIONEVENTS_USER_ID`, `IG_UPRODUCTIONEVENTS_ACCESS_TOKEN` |
| Instagram Business | `@uproduction_spain` | `IG_UPRODUCTION_SPAIN_USER_ID`, `IG_UPRODUCTION_SPAIN_ACCESS_TOKEN` |
| Instagram Business | `@alon3153` | `IG_ALON3153_USER_ID`, `IG_ALON3153_ACCESS_TOKEN` |

LinkedIn publisher will be added once the LinkedIn Developer App is approved (Phase C3).

## How publishing works

1. Cron triggers daily at 09:00 IST.
2. `scripts/publish.py` auto-selects the next day not yet successfully published to all accounts.
3. For each pending account, posts via the appropriate Graph API endpoint.
4. Per-account success/failure recorded in `state.json` — a single failure does not block the others, and a successful account is never re-posted.
5. Reports committed back to the repo under `reports/dayN.txt`; full artifact uploaded with each run.

Instagram requires public image URLs — `IMAGE_BASE_URL` is set to `https://raw.githubusercontent.com/{repo}/{branch}` so images in `content/images/` are served directly from the repo.

## Manual operations

```bash
# Status overview
python3 scripts/publish.py --status

# Preview without posting
python3 scripts/publish.py --dry-run

# Publish a specific day
python3 scripts/publish.py --day 27

# Restrict to one platform
python3 scripts/publish.py --platform facebook

# Catchup — post all overdue past days at once (use sparingly)
python3 scripts/publish.py --catchup
```

`workflow_dispatch` in GitHub Actions exposes all of the above as inputs.

## Setup checklist (one-time)

1. **Create GitHub repo** under your account (private or public — public allows simpler image hosting via raw.githubusercontent.com).
2. **Push this folder** to that repo.
3. **Add the secrets above** to the repo: Settings → Secrets and variables → Actions → New repository secret.
4. **Verify tokens** via Graph API Explorer or `curl https://graph.facebook.com/v22.0/{page_id}?access_token={token}`.
5. **Manually trigger** the workflow once: Actions tab → Daily Publish → Run workflow → check `dry_run: true` first.
6. **Confirm a successful dry run**, then run again with `dry_run: false`.

## Token notes

- **FB Page tokens** issued from Meta App should be **long-lived Page tokens** (no expiry, as long as the user token they were exchanged from stays valid). See `https://developers.facebook.com/docs/pages/access-tokens`.
- **IG access tokens** are the Page Access Tokens of the **linked Facebook Page**. Use the same token for both `FB_..._PAGE_TOKEN` and `IG_..._ACCESS_TOKEN`. The IG Business User ID is fetched via `GET /{page_id}?fields=instagram_business_account`.
- All tokens should have permissions: `pages_read_engagement`, `pages_manage_posts`, `instagram_basic`, `instagram_content_publish`.

## Local dev

```bash
pip install -r requirements.txt
# Create a .env or export env vars manually
export FB_UPRODUCTIONEVENTS_PAGE_ID=...
export FB_UPRODUCTIONEVENTS_PAGE_TOKEN=...
# ... etc
python3 scripts/publish.py --dry-run
```

## Content

- `content/days/*.json` — one file per day, contains LinkedIn / Instagram / Facebook texts
- `content/images/dayN_*_branded.png` — one image per day (must exist or the day is skipped)
- `state.json` — per-account publication history (committed back by the workflow)

## Migration history

- Until 2026-05-03: legacy browser-based publisher on a local Mac (`upe` user). Stopped working when LinkedIn + Instagram changed DOM and the Mac user migration broke launchd paths.
- 2026-05-11: cloud rewrite (this repo) — Graph API only. State pre-seeded with local publication history (Days 1-19 done across all accounts; Day 20 IG Spain done locally).
