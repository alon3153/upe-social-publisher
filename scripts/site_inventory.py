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

This module lists the astro `services` collection + key pages via the GitHub contents
API (same GH_PAT / repo the seo_geo snapshot uses) so the council prompt can say
"these are LIVE — optimize, don't recreate".

Env (same as seo_geo_source): GH_PAT, SEO_GEO_REPO (default alon3153/uproduction-astro).
Degrades gracefully: no token / error → ok=False, council simply omits the section.

CLI:  python3 scripts/site_inventory.py
"""
import os, json, urllib.request, urllib.error

PAT = os.environ.get("GH_PAT", "")
REPO = os.environ.get("SEO_GEO_REPO", "alon3153/uproduction-astro")
SERVICES_DIR = "src/content/services/he"
PAGES_DIR = "src/pages"
BLOG_DIRS = ["src/content/blog/he", "src/content/blog/en", "src/content/blog/es"]


def _list_dir(path):
    """Return list of entry names in a repo dir via GitHub contents API, or [] on error."""
    url = f"https://api.github.com/repos/{REPO}/contents/{path}"
    req = urllib.request.Request(url, headers={
        "Authorization": f"Bearer {PAT}",
        "Accept": "application/vnd.github+json",
        "User-Agent": "upe-council"})
    with urllib.request.urlopen(req, timeout=60) as r:
        items = json.loads(r.read().decode())
    return [it.get("name", "") for it in items if isinstance(it, dict)]


def fetch():
    if not PAT:
        return {"ok": False, "reason": "GH_PAT not set (cross-repo read to astro)"}
    try:
        services = [n[:-3] for n in _list_dir(SERVICES_DIR) if n.endswith(".md")]
        pages = _list_dir(PAGES_DIR)
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
                blog_count += sum(1 for n in _list_dir(d) if n.endswith((".md", ".mdx")))
            except urllib.error.HTTPError:
                pass
        return {"ok": True, "service_pages": sorted(services),
                "service_count": len(services), "key_pages": key_pages,
                "blog_article_count": blog_count}
    except urllib.error.HTTPError as e:
        return {"ok": False, "reason": f"GitHub {e.code} listing {REPO}"}
    except Exception as e:
        return {"ok": False, "reason": f"site_inventory error: {e}"}


if __name__ == "__main__":
    print(json.dumps(fetch(), ensure_ascii=False, indent=2))
