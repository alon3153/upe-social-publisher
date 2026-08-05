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


def normalize(data):
    """Map the guardian's NESTED snapshot schema onto the FLAT fields the council
    scorecard reads (council.py build_scorecard). The guardian writes:
        sites[].clicks, sites[].top_opportunities=[[term,pos,impr],...], geo.cited
    but the scorecard reads weekly_clicks / top3_keywords / aeo_cited_engines. Without
    this mapping every organic+AEO metric silently reads 0 / "not connected" even on
    live data — the field-name mismatch that pinned the daily score at 36 (05.08.2026).
    Only fills fields that are absent, so a future flat-schema guardian stays compatible."""
    if not data.get("ok"):
        return data
    sites = data.get("sites") or []
    if sites:
        if "weekly_clicks" not in data:
            # guardian reports the GSC-window click total per site
            data["weekly_clicks"] = sum((s.get("clicks") or 0) for s in sites)
        if "top3_keywords" not in data:
            # best-effort: count opportunities ranking at position <= 3. Guardian only
            # emits the top-N opportunities per site, so this can undercount — but it is
            # the honest floor and never fabricates a Top-3 that isn't there.
            t3 = 0
            for s in sites:
                for o in (s.get("top_opportunities") or []):
                    if len(o) >= 2 and o[1] is not None and o[1] <= 3:
                        t3 += 1
            data["top3_keywords"] = t3
    geo = data.get("geo") or {}
    if "aeo_cited_engines" not in data and geo.get("cited") is not None:
        data["aeo_cited_engines"] = geo.get("cited")
    return data


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
        return normalize(data)
    except urllib.error.HTTPError as e:
        return {"ok": False, "reason": f"GitHub {e.code} fetching {REPO}/{PATH}"}
    except Exception as e:
        return {"ok": False, "reason": f"seo_geo fetch error: {e}"}


if __name__ == "__main__":
    print(json.dumps(fetch(), ensure_ascii=False, indent=2))
