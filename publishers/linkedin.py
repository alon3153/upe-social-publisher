"""LinkedIn publisher (UGC Posts API).

Posts to the **company page** when LINKEDIN_ORG_URN is set (e.g.
urn:li:organization:12345) — requires a token with w_organization_social.
Otherwise falls back to the authorizing member's personal profile
(w_member_social). Run scripts/linkedin_org_oauth.py to obtain the org token+URN.
"""
import os, json, urllib.request, urllib.error

API = "https://api.linkedin.com"
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"


def _token():
    # Prefer the auto-refreshed token stored in Supabase; fall back to env.
    if os.environ.get("SUPABASE_URL") and os.environ.get("SUPABASE_SERVICE_ROLE_KEY"):
        try:
            from publishers import queue
            row = queue.get_oauth("linkedin")
            if row and row.get("access_token"):
                return row["access_token"]
        except Exception:
            pass
    t = os.environ.get("LINKEDIN_ACCESS_TOKEN")
    if not t:
        raise RuntimeError("LINKEDIN_ACCESS_TOKEN not set")
    return t


def _req(method, url, token, body=None, raw=None, ctype="application/json", extra=None):
    headers = {"Authorization": f"Bearer {token}", "User-Agent": UA,
               "X-Restli-Protocol-Version": "2.0.0"}
    if extra:
        headers.update(extra)
    data = None
    if raw is not None:
        data = raw; headers["Content-Type"] = ctype
    elif body is not None:
        data = json.dumps(body).encode(); headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(req) as r:
        txt = r.read().decode() if method != "PUT" else ""
        return r.headers, (json.loads(txt) if txt else {})


def member_urn(token=None):
    # Prefer a cached URN — personal posting then needs only w_member_social,
    # not openid/profile (so a token re-auth that drops openid won't break it).
    cached = os.environ.get("LINKEDIN_MEMBER_URN")
    if cached:
        return cached if cached.startswith("urn:li:person:") else f"urn:li:person:{cached}"
    token = token or _token()
    _, info = _req("GET", f"{API}/v2/userinfo", token)
    sub = info.get("sub")
    if not sub:
        raise RuntimeError(f"no sub in userinfo: {info}")
    return f"urn:li:person:{sub}"


def _author(token=None, org_urn=None):
    """Explicit org URN if given, else the configured default org
    (LINKEDIN_ORG_URN), else the personal member URN. Pass the sentinel
    "__member__" to force the personal profile even when a default org is set."""
    if org_urn == "__member__":
        return member_urn(token)
    org = org_urn or os.environ.get("LINKEDIN_ORG_URN")
    if org:
        return org
    return member_urn(token)


def _upload_image(token, owner, image_url):
    # 1) register upload
    reg = {"registerUploadRequest": {
        "recipes": ["urn:li:digitalmediaRecipe:feedshare-image"],
        "owner": owner,
        "serviceRelationships": [{"relationshipType": "OWNER", "identifier": "urn:li:userGeneratedContent"}]}}
    _, res = _req("POST", f"{API}/v2/assets?action=registerUpload", token, body=reg)
    val = res["value"]
    asset = val["asset"]
    upload_url = val["uploadMechanism"]["com.linkedin.digitalmedia.uploading.MediaUploadHttpRequest"]["uploadUrl"]
    # 2) fetch image bytes
    ireq = urllib.request.Request(image_url, headers={"User-Agent": UA})
    with urllib.request.urlopen(ireq) as r:
        img = r.read()
    # 3) PUT bytes
    _req("PUT", upload_url, token, raw=img, ctype="image/png")
    return asset


def publish_post(text, image_url=None, token=None, org_urn=None):
    """Publish to an explicit org page (org_urn), the default company page
    (LINKEDIN_ORG_URN), or the member's profile. Returns dict like other
    publishers."""
    try:
        token = token or _token()
        owner = _author(token, org_urn)
        media_cat = "NONE"
        media = []
        if image_url:
            asset = _upload_image(token, owner, image_url)
            media_cat = "IMAGE"
            media = [{"status": "READY", "media": asset}]
        body = {"author": owner, "lifecycleState": "PUBLISHED",
                "specificContent": {"com.linkedin.ugc.ShareContent": {
                    "shareCommentary": {"text": text},
                    "shareMediaCategory": media_cat,
                    **({"media": media} if media else {})}},
                "visibility": {"com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"}}
        hdrs, res = _req("POST", f"{API}/v2/ugcPosts", token, body=body)
        pid = res.get("id") or hdrs.get("x-restli-id") or hdrs.get("X-RestLi-Id")
        return {"success": True, "post_id": pid}
    except urllib.error.HTTPError as e:
        return {"success": False, "error": f"HTTP {e.code}: {e.read().decode()[:200]}"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def verify_token():
    try:
        return True, member_urn()
    except Exception as e:
        return False, str(e)
