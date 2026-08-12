"""LinkedIn publisher (UGC Posts API).

Posts to the **company page** when LINKEDIN_ORG_URN is set (e.g.
urn:li:organization:12345) — requires a token with w_organization_social.
Otherwise falls back to the authorizing member's personal profile
(w_member_social). Run scripts/linkedin_org_oauth.py to obtain the org token+URN.
"""
import os, json, time, urllib.request, urllib.parse, urllib.error

API = "https://api.linkedin.com"
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
ORG_POST_ROLES = {
    "ADMINISTRATOR", "CONTENT_ADMINISTRATOR", "CONTENT_ADMIN",
    "DIRECT_SPONSORED_CONTENT_POSTER",
}


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


def _oauth_post(url, fields):
    data = urllib.parse.urlencode(fields).encode()
    req = urllib.request.Request(url, data=data, headers={
        "Content-Type": "application/x-www-form-urlencoded", "User-Agent": UA}, method="POST")
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode())


def introspect_token(token):
    """Return LinkedIn's token metadata without ever logging the token."""
    cid = os.environ.get("LINKEDIN_CLIENT_ID", "")
    secret = os.environ.get("LINKEDIN_CLIENT_SECRET", "")
    if not cid or not secret:
        raise RuntimeError("LINKEDIN_CLIENT_ID / LINKEDIN_CLIENT_SECRET not set")
    return _oauth_post("https://www.linkedin.com/oauth/v2/introspectToken", {
        "client_id": cid, "client_secret": secret, "token": token,
    })


def _scope_set(info):
    raw = info.get("scope") or info.get("scopes") or ""
    if isinstance(raw, str):
        decoded = urllib.parse.unquote_plus(raw)
        return {s for s in decoded.replace(",", " ").split() if s}
    if isinstance(raw, (list, tuple, set)):
        return {str(s) for s in raw}
    return set()


def _member_urn_for_token(token):
    """Resolve the member attached to *this* token (ignore cached env URNs)."""
    try:
        _, info = _req("GET", f"{API}/v2/userinfo", token)
        if info.get("sub"):
            return f"urn:li:person:{info['sub']}"
    except urllib.error.HTTPError:
        pass
    _, info = _req("GET", f"{API}/v2/me", token)
    if not info.get("id"):
        raise RuntimeError(f"no member id in LinkedIn identity response: {info}")
    return f"urn:li:person:{info['id']}"


def _organization_roles(token):
    """Return {organization_urn: approved roles} for the token's member."""
    url = (f"{API}/v2/organizationAcls?q=roleAssignee&projection="
           "(elements*(organization,role,state))")
    _, data = _req("GET", url, token)
    roles = {}
    for item in data.get("elements") or []:
        if str(item.get("state", "")).upper() != "APPROVED":
            continue
        org = item.get("organization")
        role = str(item.get("role", "")).upper()
        if org and role:
            roles.setdefault(org, set()).add(role)
    return roles


def preflight(token=None, member_urn_expected=None, org_urn=None):
    """Read-only authorization check for the exact target we are about to post.

    An OAuth token being ``active`` is not sufficient: the Aug-10 rotation
    produced an active token with no usable social-write authorization. This
    verifies scopes, member identity, and company-page role before any upload or
    post creation is attempted. The returned dict is safe to print/log.
    """
    try:
        token = token or _token()
        info = introspect_token(token)
        if info.get("active") not in (True, "true"):
            return {"ok": False, "code": "inactive", "message": "token is inactive"}
        scopes = _scope_set(info)
        required = {"w_organization_social"} if org_urn else {"w_member_social"}
        missing = sorted(required - scopes)
        if missing:
            return {"ok": False, "code": "missing_scope",
                    "message": "missing scope(s): " + ", ".join(missing),
                    "scopes": sorted(scopes)}

        if member_urn_expected:
            actual = _member_urn_for_token(token)
            expected = (member_urn_expected if member_urn_expected.startswith("urn:li:person:")
                        else f"urn:li:person:{member_urn_expected}")
            if actual != expected:
                return {"ok": False, "code": "identity_mismatch",
                        "message": f"token member {actual} does not match target {expected}",
                        "member_urn": actual, "scopes": sorted(scopes)}

        if org_urn:
            roles = _organization_roles(token).get(org_urn, set())
            if not roles.intersection(ORG_POST_ROLES):
                return {"ok": False, "code": "org_role_missing",
                        "message": f"no approved posting role for {org_urn}",
                        "roles": sorted(roles), "scopes": sorted(scopes)}

        return {"ok": True, "code": "ok", "message": "authorized",
                "scopes": sorted(scopes)}
    except urllib.error.HTTPError as e:
        detail = e.read().decode(errors="replace")[:240]
        return {"ok": False, "code": f"http_{e.code}",
                "message": f"authorization probe HTTP {e.code}: {detail}"}
    except Exception as e:
        return {"ok": False, "code": "probe_error", "message": str(e)}


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


def _asset_status(token, asset):
    """asset is 'urn:li:digitalmediaAsset:XXXX' — poll its recipe status."""
    aid = asset.rsplit(":", 1)[-1]
    _, res = _req("GET", f"{API}/v2/assets/{aid}", token)
    recipes = res.get("recipes") or []
    return (recipes[0].get("status") if recipes else res.get("status")) or "UNKNOWN"


def _upload_video(token, owner, video_url, poll_secs=180):
    """Register + upload a video, then wait for LinkedIn to transcode it to
    AVAILABLE before it can be attached to a UGC post."""
    reg = {"registerUploadRequest": {
        "recipes": ["urn:li:digitalmediaRecipe:feedshare-video"],
        "owner": owner,
        "serviceRelationships": [{"relationshipType": "OWNER", "identifier": "urn:li:userGeneratedContent"}]}}
    _, res = _req("POST", f"{API}/v2/assets?action=registerUpload", token, body=reg)
    val = res["value"]
    asset = val["asset"]
    upload_url = val["uploadMechanism"]["com.linkedin.digitalmedia.uploading.MediaUploadHttpRequest"]["uploadUrl"]
    # fetch the video bytes (local path or http URL)
    if video_url.startswith("http"):
        vreq = urllib.request.Request(video_url, headers={"User-Agent": UA})
        with urllib.request.urlopen(vreq) as r:
            vid = r.read()
    else:
        with open(video_url, "rb") as fh:
            vid = fh.read()
    _req("PUT", upload_url, token, raw=vid, ctype="video/mp4")
    # poll until transcoded (videos are not postable until AVAILABLE)
    deadline = time.time() + poll_secs
    status = "PROCESSING"
    while time.time() < deadline:
        status = _asset_status(token, asset)
        if status == "AVAILABLE":
            break
        time.sleep(5)
    if status != "AVAILABLE":
        raise RuntimeError(f"video asset not AVAILABLE after {poll_secs}s (status={status})")
    return asset


def publish_post(text, image_url=None, video_url=None, token=None, org_urn=None):
    """Publish to an explicit org page (org_urn), the default company page
    (LINKEDIN_ORG_URN), or the member's profile. Returns dict like other
    publishers."""
    try:
        token = token or _token()
        owner = _author(token, org_urn)
        media_cat = "NONE"
        media = []
        if video_url:
            asset = _upload_video(token, owner, video_url)
            media_cat = "VIDEO"
            media = [{"status": "READY", "media": asset}]
        elif image_url:
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
