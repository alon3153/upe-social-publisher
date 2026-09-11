"""KIE (kie.ai) API client — thin wrapper around the REST API.

Authentication is a bearer token read from the KIE_API_KEY environment
variable (GitHub Secret in Actions, .env locally). The key itself is never
stored in this repo.

    from publishers import kie
    kie.api_key()          # -> str, raises if KIE_API_KEY is unset
    kie.credits()          # -> int remaining credits (also validates the key)
    kie.verify_key()       # -> (ok: bool, info: str)
"""
import os, json, urllib.request, urllib.error

API = os.environ.get("KIE_API_BASE", "https://api.kie.ai").rstrip("/")
UA = "upe-social-publisher/1.0"
TIMEOUT = 30


def api_key():
    k = os.environ.get("KIE_API_KEY", "").strip()
    if not k:
        raise RuntimeError("KIE_API_KEY not set")
    return k


def _req(method, path, body=None, timeout=TIMEOUT):
    """Call the KIE API and return the decoded JSON body.

    Raises RuntimeError with a readable message on HTTP or API-level errors
    (the key is never included in the message).
    """
    url = path if path.startswith("http") else f"{API}{path}"
    headers = {"Authorization": f"Bearer {api_key()}", "User-Agent": UA,
               "Accept": "application/json"}
    data = None
    if body is not None:
        data = json.dumps(body).encode()
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            txt = r.read().decode()
    except urllib.error.HTTPError as e:
        detail = ""
        try:
            detail = e.read().decode()[:300]
        except Exception:
            pass
        raise RuntimeError(f"KIE HTTP {e.code} on {path}: {detail or e.reason}") from None
    except urllib.error.URLError as e:
        raise RuntimeError(f"KIE network error on {path}: {e.reason}") from None
    out = json.loads(txt) if txt else {}
    code = out.get("code") if isinstance(out, dict) else None
    if code is not None and code != 200:
        raise RuntimeError(f"KIE API error {code} on {path}: {out.get('msg', '')}")
    return out


def credits():
    """Remaining account credits. A successful call proves the key is valid."""
    out = _req("GET", "/api/v1/chat/credit")
    data = out.get("data")
    if isinstance(data, dict):
        data = data.get("credits", data.get("credit"))
    try:
        return int(data)
    except (TypeError, ValueError):
        return data


def verify_key():
    """Return (ok, info) without raising — for health checks."""
    try:
        api_key()
    except RuntimeError as e:
        return False, str(e)
    try:
        c = credits()
    except RuntimeError as e:
        return False, str(e)
    return True, f"valid; {c} credits remaining"
