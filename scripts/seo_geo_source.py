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
from pathlib import Path
from council_source_evidence import engine_evidence, valid_week

# Scored Top-3 uses this list, never the guardian's precomputed top3_keywords.
# The weekly cohort measures 30 Google queries, but those query strings are not
# in the SEO snapshot. The checked-in file is the live service-page query set.
_TRACKED_KEYWORD_FILES = (
    Path(__file__).resolve().parent / "organic_seo_weekly_keywords.json",
    Path(__file__).resolve().parent.parent / "state" / "organic_seo_weekly_keywords.json",
)

PAT = os.environ.get("GH_PAT", "")
REPO = os.environ.get("SEO_GEO_REPO", "alon3153/uproduction-astro")
PATH = os.environ.get("SEO_GEO_PATH", "reports/seo-geo-latest.json")


def _string_list(value):
    if isinstance(value, dict):
        value = value.get("keywords")
    if not isinstance(value, list) or not value:
        return None
    if not all(isinstance(item, str) and item.strip() for item in value):
        return None
    return [item.strip() for item in value]


def tracked_keywords(data):
    """Return the Organic SEO Weekly keyword list, or None if it is not stored.

    Accepted sources, in order: snapshot fields `tracked_keywords` /
    `organic_weekly_keywords`, query strings under `category_visibility`, then a
    JSON file in this repo. Category totals such as engines.google.total == 30
    are not a list of terms and are ignored.
    """
    data = data or {}
    for key in ("tracked_keywords", "organic_weekly_keywords"):
        found = _string_list(data.get(key))
        if found:
            return found
    visibility = data.get("category_visibility")
    if isinstance(visibility, dict):
        for key in ("queries", "keywords", "tracked_keywords"):
            found = _string_list(visibility.get(key))
            if found:
                return found
    for path in _TRACKED_KEYWORD_FILES:
        if not path.is_file():
            continue
        try:
            payload = json.loads(path.read_text())
        except (OSError, ValueError):
            continue
        found = _string_list(payload)
        if found:
            return found
    return None


def _query_text(term):
    if isinstance(term, (list, tuple)) and term and isinstance(term[0], str):
        return term[0].strip()
    if isinstance(term, str):
        return term.strip()
    return None


def split_top3(data):
    """Separate the scored tracked-keyword count from the all-query count.

    `top3_terms` / the legacy `top3_keywords` integer count every Search Console
    query in positions 1-3, including long questions with 0 clicks. That number
    is `all_queries` and must not enter the score. `tracked` counts only the
    Organic SEO Weekly keyword list. When that list is absent, `tracked` is
    None rather than a guessed list or the all-query count.
    """
    data = data or {}
    sites = [s for s in (data.get("sites") or []) if isinstance(s, dict)]
    terms_present = bool(sites) and all(isinstance(s.get("top3_terms"), list) for s in sites)
    if terms_present:
        all_queries = sum(len(s.get("top3_terms") or []) for s in sites)
    elif isinstance(data.get("top3_all_queries"), int) and not isinstance(data.get("top3_all_queries"), bool):
        all_queries = data["top3_all_queries"]
    elif isinstance(data.get("top3_keywords"), int) and not isinstance(data.get("top3_keywords"), bool):
        # Legacy snapshots stored the all-query count here. It is info only.
        all_queries = data["top3_keywords"]
    else:
        all_queries = None
    keywords = tracked_keywords(data)
    matched = []
    tracked = None
    if keywords and terms_present:
        wanted = {item.casefold() for item in keywords}
        seen = set()
        for site in sites:
            for term in site.get("top3_terms") or []:
                query = _query_text(term)
                key = query.casefold() if query else ""
                if key and key in wanted and key not in seen:
                    seen.add(key)
                    matched.append(query)
        tracked = len(matched)
    return {"all_queries": all_queries, "tracked": tracked, "matched": matched,
            "tracked_list_size": len(keywords) if keywords else None}


def measurement_window(data, key):
    """Shared from/to dates for one GSC window. Differing site windows stay unset."""
    sites = [s for s in ((data or {}).get("sites") or []) if isinstance(s, dict)]
    found = []
    for site in sites:
        window = (site.get("windows") or {}).get(key) or {}
        start, end = window.get("start"), window.get("end")
        if isinstance(start, str) and isinstance(end, str) and start and end:
            found.append((start[:10], end[:10]))
    unique = list(dict.fromkeys(found))
    if len(unique) == 1:
        return unique[0]
    return (None, None)


def weekly_average_28d(data):
    """Clicks per week across the 28-day GSC total. This is not the scored 7-day value."""
    if not isinstance(data, dict):
        return None
    clicks = data.get("clicks_28d")
    days = data.get("window_days")
    if (isinstance(clicks, (int, float)) and not isinstance(clicks, bool)
            and isinstance(days, (int, float)) and not isinstance(days, bool) and days >= 7):
        return round(float(clicks) / (float(days) / 7.0), 2)
    return None


def normalize(data):
    """Keep source units: weekly GSC windows and cited prompts are not engines."""
    if not data.get("ok"):
        return data
    data = dict(data)
    sites = data.get("sites") or []
    data["weekly_clicks"] = None
    valid_sites = [s for s in sites if isinstance(s.get("clicks_7d"), (int, float))
                   and valid_week(s.get("windows", {}).get("weekly", {}))]
    if sites and len(valid_sites) == len(sites):
        data["weekly_clicks"] = sum(s["clicks_7d"] for s in valid_sites)
        data["weekly_window_verified"] = True
    else:
        data["weekly_window_verified"] = False
    # The incoming top3_keywords integer is the guardian's all-query count.
    # Always replace it. Scoring reads the recomputed tracked count only.
    parts = split_top3(data)
    data["top3_all_queries"] = parts["all_queries"]
    data["top3_tracked_terms"] = parts["matched"]
    data["top3_keywords"] = parts["tracked"]
    data["tracked_keyword_list_size"] = parts["tracked_list_size"]
    avg_28d = weekly_average_28d(data)
    if avg_28d is not None:
        data["weekly_clicks_28d_avg"] = avg_28d
    geo = data.get("geo") or {}
    data["aeo_cited_questions"] = geo.get("cited")
    data["aeo_measured_questions"] = geo.get("measured", geo.get("total"))
    data["aeo_question_engine"] = "perplexity" if "perplexity" in geo.get("method", "") else "unspecified"
    # Old snapshots copied the question count into this field. Only the independent
    # grounded multi-engine evidence below may populate the engine-count KPI.
    data["aeo_cited_engines"] = None
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
        data = normalize(data)
        evidence = engine_evidence()
        data["aeo_engine_evidence"] = evidence
        if evidence["ok"]:
            data["aeo_cited_engines"] = evidence["cited_engines"]
        return data
    except urllib.error.HTTPError as e:
        return {"ok": False, "reason": f"GitHub {e.code} fetching {REPO}/{PATH}"}
    except Exception as e:
        return {"ok": False, "reason": f"seo_geo fetch error: {e}"}


if __name__ == "__main__":
    print(json.dumps(fetch(), ensure_ascii=False, indent=2))
