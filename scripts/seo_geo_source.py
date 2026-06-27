#!/usr/bin/env python3
"""
Google-organic (GSC) + AI-GEO signal for the daily council.

The numbers are produced by the SEO/GEO guardian in the (private) uproduction-astro
repo, which has the GSC service account + SerpAPI + Perplexity creds. That job
writes a compact machine-readable snapshot to  reports/seo-geo-latest.json  in the
astro repo. This module fetches that snapshot via the GitHub contents API so the
council can score google_organic_geo on REAL data instead of guessing.

Credentials (env / GH secrets — add GH_PAT to upe-social-publisher to activate):
  GH_PAT        a GitHub token with read access to alon3153/uproduction-astro
  SEO_GEO_REPO  optional override, default alon3153/uproduction-astro
  SEO_GEO_PATH  optional override, default reports/seo-geo-latest.json

Degrades gracefully: no token / not-found / parse error → ok=False, council notes
the GEO data is unwired (never fabricates).

CLI:  python3 scripts/seo_geo_source.py
"""
import os, sys, json, base64, urllib.request, urllib.error

PAT = os.environ.get("GH_PAT", "")
REPO = os.environ.get("SEO_GEO_REPO", "alon3153/uproduction-astro")
PATH = os.environ.get("SEO_GEO_PATH", "reports/seo-geo-latest.json")


def fetch():
    if not PAT:
        return {"ok": False, "reason": "GH_PAT not set (cross-repo read to astro)"}
    url = f"https://api.github.com/repos/{REPO}/contents/{PATH}"
    req = urllib.request.Request(url, headers={
        "Authorization": f"Bearer {PAT}",
        "Accept": "application/vnd.github+json",
        "User-Agent": "upe-council"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            meta = json.loads(r.read().decode())
        content = base64.b64decode(meta.get("content", "")).decode()
        data = json.loads(content)
        data["ok"] = True
        return data
    except urllib.error.HTTPError as e:
        return {"ok": False, "reason": f"GitHub {e.code} fetching {REPO}/{PATH}"}
    except Exception as e:
        return {"ok": False, "reason": f"seo_geo fetch error: {e}"}


if __name__ == "__main__":
    print(json.dumps(fetch(), ensure_ascii=False, indent=2))
