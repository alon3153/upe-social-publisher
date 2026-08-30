"""Ledger of which buyer intents already have a page, and whether that page is really live.

Two failures this closes.

1. Nothing ever checked what had already been published, so the loop rewrote the same
   intent every week: 67 page-writes over its life covering 3 distinct intents, 27 URLs
   of them on "boutique vs large networks". Briefs are now filtered against this ledger
   BEFORE the model is called, so a covered intent costs nothing.
2. "Published" was recorded when a PR was opened. PRs #99/#108/#112 were closed unmerged
   and #120 failed its build, yet four straight weekly emails reported those pages as
   shipped and IndexNow was pinged for URLs that 404. An intent counts as covered only
   while its URL actually resolves.
"""
import json, datetime, urllib.request, urllib.error
from pathlib import Path

ROOT = Path(__file__).resolve().parent
STATE = ROOT.parent / "state" / "published_intents.json"
UA = "Mozilla/5.0 (compatible; UPE-AEO-verifier/1.0)"


def load(path=None):
    p = Path(path) if path else STATE
    if not p.exists():
        return {"updated": "", "intents": {}}
    return json.loads(p.read_text(encoding="utf-8"))


def save(data, path=None, today=None):
    p = Path(path) if path else STATE
    p.parent.mkdir(parents=True, exist_ok=True)
    data["updated"] = today or datetime.date.today().isoformat()
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def covered(path=None):
    """Intent keys whose page is believed live. An intent whose URL went dead is NOT
    covered — it becomes a brief again rather than a silent hole."""
    return {k for k, v in load(path).get("intents", {}).items() if v.get("live", True)}


def record(pages, today, path=None):
    """Mark intents as published. `pages` carry `intent` + frontmatter canonical."""
    data = load(path)
    for page in pages:
        intent = page.get("intent")
        if not intent:
            continue
        entry = data["intents"].get(intent, {})
        entry.update({
            "slug": page.get("slug", ""),
            "url": (page.get("frontmatter") or {}).get("canonical", ""),
            "lang": page.get("lang", ""),
            "last_published": today,
            "live": True,          # provisional until verify() confirms it
            "verified": False,
        })
        entry.setdefault("first_published", today)
        data["intents"][intent] = entry
    save(data, path, today)
    return data


def _status(url, opener=None):
    """200 -> 'live', 404/410 -> 'dead', anything else (timeout, 403, 5xx) -> 'unknown'.
    Unknown never demotes an intent: a flaky fetch must not trigger a rewrite."""
    fetch = opener or _fetch
    try:
        return "live" if fetch(url) == 200 else "dead"
    except urllib.error.HTTPError as e:
        return "dead" if e.code in (404, 410) else "unknown"
    except Exception:
        return "unknown"


def _encode(url):
    """Percent-encode a non-ASCII path. Half of UPE's money pages have Hebrew slugs, and
    urllib raises on the raw UTF-8 — which would report every Hebrew page as 'unknown'."""
    from urllib.parse import urlsplit, urlunsplit, quote
    parts = urlsplit(url)
    return urlunsplit((parts.scheme, parts.netloc, quote(parts.path, safe="/%"),
                       quote(parts.query, safe="=&%"), parts.fragment))


def _fetch(url):
    req = urllib.request.Request(_encode(url), headers={"User-Agent": UA}, method="GET")
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.status


def verify(today=None, path=None, opener=None):
    """Re-check every recorded URL. Returns (live, dead, unknown) intent-key lists."""
    today = today or datetime.date.today().isoformat()
    data = load(path)
    live, dead, unknown = [], [], []
    for intent, entry in data.get("intents", {}).items():
        url = entry.get("url")
        if not url:
            unknown.append(intent)
            continue
        st = _status(url, opener)
        if st == "unknown":
            unknown.append(intent)
            continue
        entry["live"] = st == "live"
        entry["verified"] = True
        entry["last_verified"] = today
        (live if entry["live"] else dead).append(intent)
    save(data, path, today)
    return live, dead, unknown


def filter_live(shipped, opener=None):
    """Split reported-shipped pages into (live, not_live).

    The weekly email must never again claim a 404 was published.
    """
    ok, bad = [], []
    for s in shipped:
        (ok if _status(s.get("url", ""), opener) == "live" else bad).append(s)
    return ok, bad
