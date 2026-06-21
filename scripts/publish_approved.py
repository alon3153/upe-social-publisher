#!/usr/bin/env python3
"""Gated publisher: publish APPROVED + unpublished rows from the Supabase queue,
then mark them published. Replaces the un-gated daily cron."""
import os, sys, datetime
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from publishers import queue, facebook, instagram, linkedin
from publishers.content import find_image_path, find_image_url


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
        url = r.get("image_url") or find_image_url(day)
        # Route by account to one of 3 destinations:
        #   li_personal  -> Alon's personal profile (HE)
        #   *spain*      -> Uproduction Spain company page (ES)
        #   else         -> English company page (LINKEDIN_ORG_URN); incl. legacy "alon3153"
        acc = (account or "").lower()
        if acc in ("li_personal", "personal"):
            org_urn = "__member__"
        elif "spain" in acc:
            org_urn = os.environ.get("LINKEDIN_ORG_URN_SPAIN")
        else:
            org_urn = os.environ.get("LINKEDIN_ORG_URN")
        return linkedin.publish_post(text, url, org_urn=org_urn)
    # tiktok: pending app audit
    return {"success": False, "error": f"{net} publisher not configured yet"}


def main():
    dry = "--dry-run" in sys.argv
    rows = queue.list_approved_unpublished()
    print(f"Approved & unpublished: {len(rows)}")
    ok = 0
    for r in rows:
        label = f"day{r['day']} {r['network']}/{r['account']}"
        if dry:
            print(f"[DRY] would publish {label}"); continue
        try:
            res = publish_row(r)
        except Exception as e:
            res = {"success": False, "error": str(e)}
        if res.get("success"):
            queue.mark(r["id"], status="published",
                       published_at=datetime.datetime.utcnow().isoformat() + "Z",
                       post_id=str(res.get("post_id", "")))
            print(f"OK  {label} -> {res.get('post_id')}"); ok += 1
        else:
            queue.mark(r["id"], status="failed", error=str(res.get("error"))[:400])
            print(f"ERR {label} -> {res.get('error')}")
    print(f"Published {ok}/{len(rows)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
