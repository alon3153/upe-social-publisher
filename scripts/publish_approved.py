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
        url = r.get("image_url") or find_image_url(day)
        ig_key = account.replace("ig_", "")
        return instagram.publish_post(ig_key, text, url)
    if net == "linkedin":
        url = r.get("image_url") or find_image_url(day)
        return linkedin.publish_post(text, url)
    # tiktok: pending app audit
    return {"success": False, "error": f"{net} publisher not configured yet"}


def main():
    dry = "--dry-run" in sys.argv
    rows = queue.list_approved_unpublished()
    print(f"Approved & unpublished: {len(rows)}")

    # THROTTLING: only publish the LOWEST pending day per run.
    # Without this, a backlog of approvals floods all networks at once.
    if rows:
        min_day = min(r["day"] for r in rows)
        skipped = [r for r in rows if r["day"] != min_day]
        rows = [r for r in rows if r["day"] == min_day]
        print(f"Throttle: publishing day {min_day} only ({len(rows)} posts); "
              f"deferring {len(skipped)} posts from later days to next run.")

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
