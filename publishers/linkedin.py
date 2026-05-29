"""LinkedIn personal-profile publisher (w_member_social, UGC Posts API)."""
import os, json, urllib.request, urllib.error

API = "https://api.linkedin.com"
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"


def _token():
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
    token = token or _token()
    _, info = _req("GET", f"{API}/v2/userinfo", token)
    sub = info.get("sub")
    if not sub:
        raise RuntimeError(f"no sub in userinfo: {info}")
    return f"urn:li:person:{sub}"


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


def publish_post(text, image_url=None, token=None):
    """Publish to the authorizing member's profile. Returns dict like other publishers."""
    try:
        token = token or _token()
        owner = member_urn(token)
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
