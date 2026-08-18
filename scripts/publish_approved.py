#!/usr/bin/env python3
"""Gated publisher: publish APPROVED + unpublished rows from the Supabase queue,
then mark them published. Replaces the un-gated daily cron."""
import os, re, sys, datetime
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from publishers import queue, facebook, instagram, linkedin
from publishers.content import find_image_path, find_image_url, get_day

# Anti-flood throttle: a personal LinkedIn PROFILE (Alon's, or an advocate's) must
# never receive a burst of posts — it kills reach and reads as spam (founder-led
# strategy = spaced, golden-hour posting). Two caps guard each personal profile:
#   * PER_DAY — total posts allowed per UTC day, counted against already-published
#     rows in the DB so it holds across the day's 2-hourly runs (conservative default 1)
#   * PER_RUN — extra safety cap within a single run
# Excess rows stay 'approved' and go out on a later run/day. Company pages unaffected.
LI_PERSONAL_MAX_PER_DAY = int(os.environ.get("LI_PERSONAL_MAX_PER_DAY", "1"))
LI_PERSONAL_MAX_PER_RUN = int(os.environ.get("LI_PERSONAL_MAX_PER_RUN", "1"))
LI_COMPANY_ACCOUNTS = {"alon3153", "li_english", "linkedin", "company"}
LI_SHARED_PERSONAL_ACCOUNTS = {"li_personal", "personal"}
LI_AUTH_ERROR_MARKERS = (
    "http 401", "http 403", "not authorized", "organizationugcauthorizations",
    "missing scope", "identity mismatch", "no approved posting role",
    "advocate not connected", "auth_blocked",
)


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


def _linkedin_target(account):
    """Resolve an account label to one exact credential + author destination.

    Never let an unknown ``li_*`` advocate fall through to the company token:
    that used to risk publishing employee copy on the Uproduction company page.
    """
    acc = (account or "").lower()
    if acc in LI_SHARED_PERSONAL_ACCOUNTS:
        expected = os.environ.get("LINKEDIN_MEMBER_URN", "")
        if not expected:
            return {"ok": False, "account": acc,
                    "message": "LINKEDIN_MEMBER_URN not configured"}
        return {"ok": True, "account": acc, "kind": "member", "token": None,
                "author_urn": expected}
    if "spain" in acc:
        org = os.environ.get("LINKEDIN_ORG_URN_SPAIN", "")
        if not org:
            return {"ok": False, "account": acc,
                    "message": "LINKEDIN_ORG_URN_SPAIN not configured"}
        return {"ok": True, "account": acc, "kind": "organization", "token": None,
                "author_urn": org}
    if acc in LI_COMPANY_ACCOUNTS:
        org = os.environ.get("LINKEDIN_ORG_URN", "")
        if not org:
            return {"ok": False, "account": acc,
                    "message": "LINKEDIN_ORG_URN not configured"}
        return {"ok": True, "account": acc, "kind": "organization", "token": None,
                "author_urn": org}
    if acc.startswith("li_"):
        adv = queue.get_advocate(acc)
        if not adv:
            return {"ok": False, "account": acc,
                    "message": f"advocate not connected: {acc}"}
        tok, urn = adv.get("access_token"), adv.get("member_urn")
        if not tok or not urn:
            return {"ok": False, "account": acc,
                    "message": f"advocate token incomplete: {acc}"}
        return {"ok": True, "account": acc, "kind": "member", "token": tok,
                "author_urn": urn}
    return {"ok": False, "account": acc,
            "message": f"unknown LinkedIn account route: {acc}"}


def _auth_cache_key(target):
    return (target.get("kind"), target.get("account"), target.get("author_urn"))


def _linkedin_authorized(target, cache=None):
    if not target.get("ok"):
        return {"ok": False, "code": "route_error", "message": target.get("message", "bad route")}
    key = _auth_cache_key(target)
    if cache is not None and key in cache:
        return cache[key]
    if target["kind"] == "organization":
        result = linkedin.preflight(token=target.get("token"), org_urn=target["author_urn"])
    else:
        result = linkedin.preflight(token=target.get("token"),
                                    member_urn_expected=target["author_urn"])
    if cache is not None:
        cache[key] = result
    return result


def _is_linkedin_auth_error(error):
    value = (error or "").lower()
    return any(marker in value for marker in LI_AUTH_ERROR_MARKERS)


# A publish call can fail for reasons that have nothing to do with the content:
# a Meta 5xx, an IG media-container race (the SAME image URL published fine to the
# sibling account seconds earlier), a timeout. Those rows were marked 'failed' and
# then never touched again — day 48's FB/IG rows sat failed from 12.06 onwards, and
# the watchdog only looks 3 days back, so nobody ever saw them. Retry them a bounded
# number of times; anything still failing is a real defect and stays failed.
TRANSIENT_MARKERS = (
    "http 500", "http 502", "http 503", "http 504",
    "an unknown error has occurred",
    "only photo or video can be accepted",   # IG fetcher race on a valid image
    "timed out", "timeout", "temporarily unavailable",
    "please retry", "try again later", "rate limit", "connection reset",
)
PUBLISH_MAX_RETRIES = int(os.environ.get("PUBLISH_MAX_RETRIES", "3"))
# Only retry recent failures. Re-publishing a two-month-old row would push stale
# content out with no warning — those need a human decision, not an auto-retry.
PUBLISH_RETRY_WINDOW_DAYS = int(os.environ.get("PUBLISH_RETRY_WINDOW_DAYS", "3"))
_RETRY_TAG = re.compile(r"^retry (\d+)/\d+ · ")


def _is_transient_error(error):
    value = (error or "").lower()
    return any(marker in value for marker in TRANSIENT_MARKERS)


def _retry_attempts(error):
    """How many auto-retries this row already had (encoded in its error text —
    the queue table has no attempts column)."""
    m = _RETRY_TAG.match(error or "")
    return int(m.group(1)) if m else 0


def _retry_transient_failures():
    """Requeue recent failures whose error looks transient, bounded by attempts."""
    cutoff = (datetime.date.today() - datetime.timedelta(days=PUBLISH_RETRY_WINDOW_DAYS)).isoformat()
    try:
        failed = queue._req("GET", "post_approvals", params={
            "select": "id,day,network,account,error,scheduled_date", "status": "eq.failed",
            "order": "day.asc"})
    except Exception as e:
        print(f"WARN could not inspect publish failures: {e}")
        return 0
    requeued, stale = 0, []
    for row in failed:
        err = row.get("error") or ""
        label = f"day{row.get('day')} {row.get('network')}/{row.get('account')}"
        if row.get("network") == "linkedin" and _is_linkedin_auth_error(err):
            continue  # handled by _recover_linkedin_auth_failures
        if not _is_transient_error(err):
            continue
        if (row.get("scheduled_date") or "")[:10] < cutoff:
            stale.append(label)
            continue
        attempts = _retry_attempts(err)
        if attempts >= PUBLISH_MAX_RETRIES:
            print(f"GIVE-UP {label} -> {PUBLISH_MAX_RETRIES} retries exhausted; stays failed")
            continue
        clean = _RETRY_TAG.sub("", err)
        queue.mark(row["id"], status="approved",
                   error=f"retry {attempts + 1}/{PUBLISH_MAX_RETRIES} · {clean}"[:400])
        print(f"RETRY {label} -> attempt {attempts + 1}/{PUBLISH_MAX_RETRIES} after: {clean[:90]}")
        requeued += 1
    if stale:
        print(f"STALE-FAILED (older than {PUBLISH_RETRY_WINDOW_DAYS}d, needs a human decision): "
              + ", ".join(stale))
    return requeued


def _recover_linkedin_auth_failures(auth_cache):
    """Requeue old auth failures only after their exact target passes preflight."""
    try:
        failed = queue._req("GET", "post_approvals", params={
            "select": "id,day,network,account,error", "status": "eq.failed",
            "network": "eq.linkedin", "order": "day.asc"})
    except Exception as e:
        print(f"WARN could not inspect LinkedIn auth failures: {e}")
        return 0
    recovered = 0
    for row in failed:
        if not _is_linkedin_auth_error(row.get("error")):
            continue
        target = _linkedin_target(row.get("account"))
        auth = _linkedin_authorized(target, auth_cache)
        label = f"day{row.get('day')} linkedin/{row.get('account')}"
        if auth.get("ok"):
            queue.mark(row["id"], status="approved", error=None)
            print(f"RECOVER {label} -> authorization restored; requeued")
            recovered += 1
        else:
            print(f"AUTH-HOLD {label} -> {auth.get('code')}: {auth.get('message')}")
    return recovered


def publish_row(r, linkedin_target=None):
    net, account, day = r["network"], r["account"], r["day"]
    text = r["caption"]
    _entry = get_day(day)
    _data = _entry["data"] if _entry else None  # honor real-archive image_file
    if net == "facebook":
        path = find_image_path(day, _data)
        return facebook.publish_post(account, text, path)
    if net == "instagram":
        ig_key = account.replace("ig_", "")
        video_url = r.get("video_url")
        if video_url:  # Sofia Reels (video posts)
            return instagram.publish_reel(ig_key, text, video_url, share_to_feed=True)
        url = r.get("image_url") or find_image_url(day, _data)
        return instagram.publish_post(ig_key, text, url)
    if net == "linkedin":
        video_url = r.get("video_url")
        url = r.get("image_url") or find_image_url(day, _data)
        target = linkedin_target or _linkedin_target(account)
        if not target.get("ok"):
            return {"success": False, "error": target.get("message", "LinkedIn route failed")}
        tok = target.get("token")
        org_urn = target["author_urn"]
        if video_url:  # brand-film / Sofia video posts
            return linkedin.publish_post(text, video_url=video_url, token=tok, org_urn=org_urn)
        return linkedin.publish_post(text, url, token=tok, org_urn=org_urn)
    # tiktok: pending app audit
    return {"success": False, "error": f"{net} publisher not configured yet"}


def main():
    dry = "--dry-run" in sys.argv
    auth_cache = {}
    recovered = _recover_linkedin_auth_failures(auth_cache) if not dry else 0
    requeued = _retry_transient_failures() if not dry else 0
    rows = queue.list_approved_unpublished()  # ordered day.asc -> oldest personal post goes first
    print(f"Approved & unpublished: {len(rows)} (recovered auth failures: {recovered}; "
          f"transient retries requeued: {requeued})")
    ok = 0
    published_today = _personal_published_today()  # personal key -> already published today (UTC)
    run_count = {}                                 # personal key -> published to it this run
    deferred = 0
    auth_held = 0
    for r in rows:
        label = f"day{r['day']} {r['network']}/{r['account']}"
        li_target = None
        if r.get("network") == "linkedin":
            li_target = _linkedin_target(r.get("account"))
            auth = _linkedin_authorized(li_target, auth_cache)
            if not auth.get("ok"):
                auth_held += 1
                reason = f"AUTH_HOLD[{auth.get('code')}]: {auth.get('message')}"
                if not dry:
                    queue.mark(r["id"], status="approved", error=reason[:400])
                print(f"AUTH-HOLD {label} -> {auth.get('code')}: {auth.get('message')}; stays approved")
                continue
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
            res = publish_row(r, linkedin_target=li_target)
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
            err = str(res.get("error"))
            if r.get("network") == "linkedin" and _is_linkedin_auth_error(err):
                err = "AUTH_BLOCKED: " + err
            queue.mark(r["id"], status="failed", error=err[:400])
            print(f"ERR {label} -> {res.get('error')}")
    holds = []
    if deferred:
        holds.append(f"held {deferred} personal-profile post(s) for next run")
    if auth_held:
        holds.append(f"held {auth_held} LinkedIn post(s) for authorization repair")
    tail = f" ({'; '.join(holds)})" if holds else ""
    print(f"Published {ok}/{len(rows) - deferred - auth_held}{tail}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
