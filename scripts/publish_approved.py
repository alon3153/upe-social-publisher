#!/usr/bin/env python3
"""Gated publisher: publish APPROVED + unpublished rows from the Supabase queue,
then mark them published. Replaces the un-gated daily cron."""
import os, sys, datetime
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from publishers import queue, facebook, instagram, linkedin
from publishers.content import find_image_path, find_image_url

# Anti-flood throttle: a personal LinkedIn PROFILE (Alon's, or an advocate's) must
# never receive a burst of posts — it kills reach and reads as spam (founder-led
# strategy = spaced, golden-hour posting). Two caps guard each personal profile:
#   * PER_DAY — total posts allowed per UTC day, counted against already-published
#     rows in the DB so it holds across the day's 2-hourly runs (conservative default 1)
#   * PER_RUN — extra safety cap within a single run
# Excess rows stay 'approved' and go out on a later run/day. Company pages unaffected.
LI_PERSONAL_MAX_PER_DAY = int(os.environ.get("LI_PERSONAL_MAX_PER_DAY", "1"))
LI_PERSONAL_MAX_PER_RUN = int(os.environ.get("LI_PERSONAL_MAX_PER_RUN", "1"))


def _personal_profile_key(r):
    """Return a stable key if the row targets a personal LinkedIn profile, else None."""
    if r.get("network") != "linkedin":
        return None
    acc = (r.get("account") or "").lower()
    if acc in ("li_personal", "personal") or acc.startswith("li_"):
        # li_english / li_spain are company pages, not personal profiles
        if acc in ("li_english", "li_spain"):
            return None
        return acc
    return None


def _personal_published_today():
    """Count today's (UTC) already-published personal-profile posts, keyed by profile.
    Lets the per-day cap survive across the multiple 2-hourly runs. Fails open (empty)
    so a transient DB hiccup never blocks publishing — the per-run cap still applies."""
    counts = {}
    try:
        start = datetime.datetime.utcnow().strftime("%Y-%m-%dT00:00:00")
        rows = queue._req("GET", "post_approvals", params={
            "select": "account,network", "status": "eq.published",
            "network": "eq.linkedin", "published_at": f"gte.{start}"})
        for r in rows:
            k = _personal_profile_key(r)
            if k:
                counts[k] = counts.get(k, 0) + 1
    except Exception as e:
        print(f"WARN could not read today's personal-post count (per-day cap degraded): {e}")
    return counts


def publish_row(r):
    net, account, day = r["network"], r["account"], r["day"]
    text = r["caption"]
    if net == "facebook":
        path = find_image_path(day)
        return facebook.publish_post(account, text, path)
    if net == "instagram":
        ig_key = account.replace("ig_", "")
        video_url = r.get("video_url")
        if video_url:  # Sofia Reels (video posts)
            return instagram.publish_reel(ig_key, text, video_url, share_to_feed=True)
        url = r.get("image_url") or find_image_url(day)
        return instagram.publish_post(ig_key, text, url)
    if net == "linkedin":
        video_url = r.get("video_url")
        url = r.get("image_url") or find_image_url(day)
        # Route by account to one of 3 destinations:
        #   li_personal  -> Alon's personal profile (HE)
        #   *spain*      -> Uproduction Spain company page (ES)
        #   else         -> English company page (LINKEDIN_ORG_URN); incl. legacy "alon3153"
        acc = (account or "").lower()
        # Advocate personal profiles (li_natalia / li_danielle): post with THEIR
        # own token + member URN (bypasses the cached LINKEDIN_MEMBER_URN env,
        # which is Alon's). One-click-connected via the linkedin-oauth edge fn.
        adv = queue.get_advocate(acc)
        if adv:
            tok, urn = adv.get("access_token"), adv.get("member_urn")
            if not tok or not urn:
                return {"success": False, "error": f"advocate {acc} not connected"}
            if video_url:
                return linkedin.publish_post(text, video_url=video_url, token=tok, org_urn=urn)
            return linkedin.publish_post(text, url, token=tok, org_urn=urn)
        if acc in ("li_personal", "personal"):
            org_urn = "__member__"
        elif "spain" in acc:
            org_urn = os.environ.get("LINKEDIN_ORG_URN_SPAIN")
        else:
            org_urn = os.environ.get("LINKEDIN_ORG_URN")
        if video_url:  # brand-film / Sofia video posts
            return linkedin.publish_post(text, video_url=video_url, org_urn=org_urn)
        return linkedin.publish_post(text, url, org_urn=org_urn)
    # tiktok: pending app audit
    return {"success": False, "error": f"{net} publisher not configured yet"}


def main():
    dry = "--dry-run" in sys.argv
    rows = queue.list_approved_unpublished()  # ordered day.asc -> oldest personal post goes first
    print(f"Approved & unpublished: {len(rows)}")
    ok = 0
    published_today = _personal_published_today()  # personal key -> already published today (UTC)
    run_count = {}                                 # personal key -> published to it this run
    deferred = 0
    for r in rows:
        label = f"day{r['day']} {r['network']}/{r['account']}"
        pkey = _personal_profile_key(r)
        if pkey is not None:
            day_total = published_today.get(pkey, 0) + run_count.get(pkey, 0)
            if day_total >= LI_PERSONAL_MAX_PER_DAY:
                deferred += 1
                print(f"HOLD {label} -> personal-profile cap ({LI_PERSONAL_MAX_PER_DAY}/day reached); stays approved for a later day")
                continue
            if run_count.get(pkey, 0) >= LI_PERSONAL_MAX_PER_RUN:
                deferred += 1
                print(f"HOLD {label} -> personal-profile cap ({LI_PERSONAL_MAX_PER_RUN}/run); stays approved for next run")
                continue
        if dry:
            if pkey is not None:
                run_count[pkey] = run_count.get(pkey, 0) + 1
            print(f"[DRY] would publish {label}"); continue
        try:
            res = publish_row(r)
        except Exception as e:
            res = {"success": False, "error": str(e)}
        if res.get("success"):
            queue.mark(r["id"], status="published",
                       published_at=datetime.datetime.utcnow().isoformat() + "Z",
                       post_id=str(res.get("post_id", "")))
            if pkey is not None:
                run_count[pkey] = run_count.get(pkey, 0) + 1
            print(f"OK  {label} -> {res.get('post_id')}"); ok += 1
        else:
            queue.mark(r["id"], status="failed", error=str(res.get("error"))[:400])
            print(f"ERR {label} -> {res.get('error')}")
    tail = f" (held {deferred} personal-profile post(s) for next run)" if deferred else ""
    print(f"Published {ok}/{len(rows) - deferred}{tail}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
