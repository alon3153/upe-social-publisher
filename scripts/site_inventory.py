#!/usr/bin/env python3
"""
Live inventory of what ALREADY EXISTS on the upe.co.il Astro site, fed to the
daily council so it stops recommending the site build pages that are already live.

Root cause (05.08.2026): the council LLM has no view of the site, so every report
recommended "create a נופש-חברה / אירועי-קונספט / Brand-Hub / llms.txt page" — all of
which already exist as dedicated service pages. Acting on those P0s would have created
DUPLICATE pages that split ranking signal and push the originals further from Top-3
(the exact cannibalization Alon warns against). The real gap is optimization + internal
linking + off-page authority on the EXISTING pages, not creation.

Two read paths, same output shape:
  1. GitHub contents API with GH_PAT — the cloud runner's path, unchanged.
  2. LOCAL FILESYSTEM fallback — a checkout of uproduction-astro on this machine.

Why the fallback (07.08.2026): GH_PAT is a *cloud* secret. Every local/ad-hoc run of
council.py had no token, so fetch() returned {"ok": false, "reason": "GH_PAT not set"}
and the cannibalization guard was simply OFF — the council fell back to its site-blind
behaviour and could again recommend creating pages that already exist. The astro repo is
already checked out locally (and on the weekly aeo-loop runner, at $ASTRO_REPO), so the
same inventory can be read straight off disk with no token and no network.

Env:
  GH_PAT            GitHub token with read access to the astro repo (cloud path)
  SEO_GEO_REPO      repo override, default alon3153/uproduction-astro
  ASTRO_REPO        path to a local astro checkout (also used by aeo_run/aeo_publish)
  ASTRO_LOCAL_PATH  explicit override for this module only
Degrades gracefully: no token AND no local checkout → ok=False, council omits the
section. Never raises, never fabricates.

CLI:  python3 scripts/site_inventory.py
"""
import os, json, urllib.request, urllib.error
from pathlib import Path

PAT = os.environ.get("GH_PAT", "")
REPO = os.environ.get("SEO_GEO_REPO", "alon3153/uproduction-astro")
SERVICES_DIR = "src/content/services/he"
PAGES_DIR = "src/pages"
BLOG_DIRS = ["src/content/blog/he", "src/content/blog/en", "src/content/blog/es"]
DEFAULT_LOCAL = "/Users/alonouanine/dev/uproduction-astro"


def _list_dir(path):
    """Return list of entry names in a repo dir via GitHub contents API."""
    url = f"https://api.github.com/repos/{REPO}/contents/{path}"
    req = urllib.request.Request(url, headers={
        "Authorization": f"Bearer {PAT}",
        "Accept": "application/vnd.github+json",
        "User-Agent": "upe-council"})
    with urllib.request.urlopen(req, timeout=60) as r:
        items = json.loads(r.read().decode())
    return [it.get("name", "") for it in items if isinstance(it, dict)]


def local_root():
    """Path to a usable local astro checkout, or None.

    A candidate only counts if it actually contains the services collection — an empty
    or half-cloned directory must NOT be reported as an authoritative inventory, or the
    guard would tell the council "no service pages exist, go create them" (worse than
    having no inventory at all)."""
    for cand in (os.environ.get("ASTRO_LOCAL_PATH"), os.environ.get("ASTRO_REPO"), DEFAULT_LOCAL):
        if not cand:
            continue
        root = Path(cand).expanduser()
        if (root / SERVICES_DIR).is_dir():
            return root
    return None


def _local_lister(root):
    def _list(path):
        d = root / path
        if not d.is_dir():
            raise FileNotFoundError(str(d))
        return sorted(p.name for p in d.iterdir())
    return _list


def _build(list_dir, missing_exc):
    """Assemble the inventory from any directory lister (GitHub API or filesystem)."""
    services = [n[:-3] for n in list_dir(SERVICES_DIR) if n.endswith(".md")]
    pages = list_dir(PAGES_DIR)
    # key infra pages the council keeps recommending to "build"
    key_pages = {
        "llms.txt": any(p.startswith("llms.txt") for p in pages),
        "llms-full.txt": any(p.startswith("llms-full.txt") for p in pages),
        "faq": any(p.startswith("faq.") for p in pages),
        "services_index": "[service].astro" in pages or "שירותים" in "".join(pages),
        "brand_hub_trust": "why-uproduction-events-trust" in "".join(services),
    }
    blog_count = 0
    for d in BLOG_DIRS:
        try:
            blog_count += sum(1 for n in list_dir(d) if n.endswith((".md", ".mdx")))
        except missing_exc:
            pass
    return {"ok": True, "service_pages": sorted(services),
            "service_count": len(services), "key_pages": key_pages,
            "blog_article_count": blog_count}


def fetch():
    if PAT:
        try:
            out = _build(_list_dir, urllib.error.HTTPError)
            out["source"] = f"github:{REPO}"
            return out
        except Exception as e:
            reason = (f"GitHub {e.code} listing {REPO}"
                      if isinstance(e, urllib.error.HTTPError) else f"site_inventory error: {e}")
            # token present but the API refused/failed — try disk before giving up
            local = _fetch_local()
            if local["ok"]:
                local["note"] = f"github path failed ({reason}) — read from local checkout"
                return local
            return {"ok": False, "reason": reason}
    local = _fetch_local()
    if local["ok"]:
        return local
    return {"ok": False,
            "reason": f'GH_PAT not set (cross-repo read to astro) and {local["reason"]}'}


def _fetch_local():
    root = local_root()
    if root is None:
        return {"ok": False, "reason": f"no local astro checkout (tried $ASTRO_LOCAL_PATH, "
                                       f"$ASTRO_REPO, {DEFAULT_LOCAL})"}
    try:
        out = _build(_local_lister(root), (FileNotFoundError, NotADirectoryError, OSError))
        out["source"] = f"local:{root}"
        return out
    except Exception as e:
        return {"ok": False, "reason": f"local site_inventory error: {e}"}


if __name__ == "__main__":
    print(json.dumps(fetch(), ensure_ascii=False, indent=2))
