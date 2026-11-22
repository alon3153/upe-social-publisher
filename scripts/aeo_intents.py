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
    """Intent keys that must not be briefed again.

    A live URL is covered. So is an unmerged PR (`pending_merge`): its 404 is not a
    dead page, and rewriting it produces a duplicate. An intent whose URL went dead,
    and that has no open PR, is NOT covered — it becomes a brief again.
    """
    covered_keys = set()
    for key, entry in load(path).get("intents", {}).items():
        if entry.get("pending_merge") or entry.get("live", True):
            covered_keys.add(key)
    return covered_keys


def record(pages, today, path=None, pending=False):
    """Mark intents as published. `pages` carry `intent` + frontmatter canonical.

    `pending=True` means the URL exists only on an unmerged PR. It is stored as
    `pending_merge` and must not replace a URL that is already live.
    """
    data = load(path)
    for page in pages:
        intent = page.get("intent")
        if not intent:
            continue
        url = (page.get("frontmatter") or {}).get("canonical", "")
        entry = data["intents"].get(intent, {})
        if pending and entry.get("live") and entry.get("url"):
            if entry.get("url") != url:
                entry["pending_url"] = url
                entry["pending_slug"] = page.get("slug", "")
                entry["pending_since"] = today
                entry["pending_merge"] = True
                data["intents"][intent] = entry
            continue
        entry.update({
            "slug": page.get("slug", ""),
            "url": url,
            "lang": page.get("lang", ""),
            "last_published": today,
            "live": not pending,   # a PR url is not live; verify() promotes it on 200
            "verified": False,
        })
        if pending:
            entry["pending_merge"] = True
            entry["pending_url"] = url
            entry["pending_since"] = today
        else:
            entry.pop("pending_merge", None)
            entry.pop("pending_url", None)
            entry.pop("pending_slug", None)
            entry.pop("pending_since", None)
        entry.setdefault("first_published", today)
        data["intents"][intent] = entry
    save(data, path, today)
    return data


def cover(intent, url, today, path=None):
    """Point an intent at a page that already exists on the site. Used when a freshly
    generated page duplicates a live one: the intent is covered by that page, so it
    stops coming back as a brief. verify() still re-checks the URL every run."""
    data = load(path)
    entry = data["intents"].get(intent, {})
    entry.update({"slug": url.rstrip("/").rsplit("/", 1)[-1], "url": url, "live": True,
                  "verified": False, "existing_page": True, "last_published": today})
    entry.setdefault("first_published", today)
    data["intents"][intent] = entry
    save(data, path, today)
    return data


def _clear_pending(entry):
    for key in ("pending_merge", "pending_url", "pending_slug", "pending_since"):
        entry.pop(key, None)


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
        pending_url = entry.get("pending_url")
        # The canonical URL is the unmerged PR itself. A 404 is "pending merge",
        # not "no longer live" — the latter drops the intent and the loop writes
        # another page.
        pr_is_canonical = bool(entry.get("pending_merge")) and (not pending_url or pending_url == url)
        if pr_is_canonical and st != "live":
            entry["live"] = False
            entry["verified"] = True
            entry["last_verified"] = today
            continue
        entry["live"] = st == "live"
        entry["verified"] = True
        entry["last_verified"] = today
        if entry["live"] and pr_is_canonical:
            _clear_pending(entry)
        if entry.get("pending_merge") and pending_url and pending_url != url:
            if _status(pending_url, opener) == "live":
                _clear_pending(entry)
        if entry["live"]:
            live.append(intent)
        elif entry.get("pending_merge"):
            pass  # the open PR still covers the intent
        else:
            dead.append(intent)
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
