"""Supabase post_approvals queue helpers (service_role)."""
import os, json, urllib.request, urllib.parse, urllib.error

URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"


def _req(method, path, params=None, body=None, prefer=None):
    if not URL or not KEY:
        raise RuntimeError("SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY not set")
    q = ("?" + urllib.parse.urlencode(params)) if params else ""
    headers = {"apikey": KEY, "Authorization": f"Bearer {KEY}",
               "Content-Type": "application/json", "User-Agent": UA}
    if prefer:
        headers["Prefer"] = prefer
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(URL + "/rest/v1/" + path + q, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req) as r:
            txt = r.read().decode()
            return json.loads(txt) if txt else []
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"Supabase {method} {path}: {e.code} {e.read().decode()[:300]}")


def insert_rows(rows):
    return _req("POST", "post_approvals", body=rows, prefer="return=representation")


def day_enqueued(day, scheduled_date):
    r = _req("GET", "post_approvals",
             params={"select": "id", "day": f"eq.{day}", "scheduled_date": f"eq.{scheduled_date}", "limit": "1"})
    return len(r) > 0


def day_awaiting(day):
    """Day already has live rows (pending/approved/published) on ANY date.
    A day awaiting approval must not be re-enqueued the next morning — that
    creates duplicate rows, and one approve_all click then double-publishes
    (happened with day 75, 10-11.07.2026). Rejected-only days stay eligible."""
    r = _req("GET", "post_approvals",
             params={"select": "id", "day": f"eq.{day}",
                     "status": "in.(pending,approved,published)", "limit": "1"})
    return len(r) > 0


def list_approved_unpublished():
    return _req("GET", "post_approvals",
                params={"select": "*", "status": "eq.approved", "order": "day.asc"})


def published_days():
    """Days with at least one already-published row — the real source of truth
    for rotation (state.json is NOT updated by the cloud publisher)."""
    rows = _req("GET", "post_approvals", params={"select": "day", "status": "eq.published"})
    return {int(r["day"]) for r in rows if r.get("day") is not None}


def mark(id_, **fields):
    return _req("PATCH", "post_approvals", params={"id": f"eq.{id_}"},
                body=fields, prefer="return=minimal")


def get_oauth(provider):
    rows = _req("GET", "oauth_tokens", params={"select": "*", "provider": f"eq.{provider}"})
    return rows[0] if rows else None


def upsert_oauth(provider, **fields):
    return _req("POST", "oauth_tokens", body={"provider": provider, **fields},
                prefer="resolution=merge-duplicates,return=minimal")
