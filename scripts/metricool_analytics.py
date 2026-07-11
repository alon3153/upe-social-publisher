#!/usr/bin/env python3
"""
Metricool analytics pull for the UPE daily council — post-level performance across
all connected networks (Instagram, Facebook, TikTok, LinkedIn, YouTube).

Self-contained: credentials resolve from (in order)
  1. env  METRICOOL_TOKEN / METRICOOL_USER_ID / METRICOOL_BLOG_ID   (cloud / GH Actions)
  2. repo  upe-sp/secrets/metricool.json                            (local, if vendored)
  3. ~/.upe-jobs/reel_check/secrets/metricool.json                  (this Mac)

Returns plain dicts so the council can score them. Every endpoint degrades
gracefully — a single network erroring never aborts the pull.

CLI:
  python3 scripts/metricool_analytics.py snapshot          # print 7d snapshot JSON
  python3 scripts/metricool_analytics.py snapshot --days 30
"""
import os, sys, json, argparse, datetime, urllib.request, urllib.parse, urllib.error
from pathlib import Path

BASE = "https://app.metricool.com/api"
NETWORKS = ["instagram", "facebook", "tiktok", "linkedin", "youtube"]

# engagement fields we care about, per network post object (Metricool naming varies)
_METRIC_KEYS = ["impressionsTotal", "impressions", "reach", "interactions",
                "engagement", "likes", "comments", "shares", "saved", "views"]


def _load_creds():
    tok = os.environ.get("METRICOOL_TOKEN")
    uid = os.environ.get("METRICOOL_USER_ID")
    bid = os.environ.get("METRICOOL_BLOG_ID")
    if tok and uid and bid:
        return tok, uid, bid
    for p in [Path(__file__).resolve().parent.parent / "secrets" / "metricool.json",
              Path.home() / ".upe-jobs" / "reel_check" / "secrets" / "metricool.json"]:
        if p.exists():
            cfg = json.loads(p.read_text())
            return cfg["access_token"], cfg["user_id"], cfg["blog_id"]
    raise RuntimeError("Metricool creds not found (env METRICOOL_* or secrets/metricool.json)")


def _req(path, params, tok, uid):
    p = dict(params); p["userId"] = uid
    url = f"{BASE}{path}?" + urllib.parse.urlencode(p)
    r = urllib.request.Request(url, method="GET")
    r.add_header("X-Mc-Auth", tok)
    with urllib.request.urlopen(r, timeout=120) as resp:
        raw = resp.read().decode()
        return json.loads(raw) if raw else {}


def _dt(d):
    return d.strftime("%Y-%m-%dT%H:%M:%S")


def pull_posts(network, frm, to, tok, uid, bid):
    """Return list of post dicts for one network in [frm, to]; [] on any error."""
    try:
        j = _req(f"/v2/analytics/posts/{network}",
                 {"blogId": bid, "from": _dt(frm), "to": _dt(to)}, tok, uid)
        return j.get("data", []) if isinstance(j, dict) else (j if isinstance(j, list) else [])
    except urllib.error.HTTPError as e:
        sys.stderr.write(f"[{network}] HTTP {e.code}: {e.read().decode()[:160]}\n")
        return []
    except Exception as e:
        sys.stderr.write(f"[{network}] {e}\n")
        return []


def _num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


def _impressions(p):
    # Field names differ per network: TikTok uses viewCount; the rest use
    # impressionsTotal / impressions / views.
    return _num(p.get("impressionsTotal") or p.get("impressions")
                or p.get("views") or p.get("viewCount"))


def _interactions(p):
    # TikTok uses likeCount/commentCount/shareCount; FB reports reactions.
    explicit = _num(p.get("interactions"))
    if explicit:
        return explicit
    total = (_num(p.get("likes") or p.get("likeCount") or p.get("reactions"))
             + _num(p.get("comments") or p.get("commentCount"))
             + _num(p.get("shares") or p.get("shareCount"))
             + _num(p.get("saved")))
    return max(0.0, total)  # Metricool occasionally returns negatives (seen on YT)


def summarize(posts):
    """Aggregate a network's posts into headline numbers."""
    if not posts:
        return {"posts": 0, "impressions": 0, "reach": 0, "interactions": 0,
                "engagement_rate_pct": 0.0, "top": None}
    impressions = reach = interactions = 0.0
    for p in posts:
        impressions += _impressions(p)
        # FB has no "reach" key — its unique-viewers field is impressionsUnique
        reach += _num(p.get("reach") or p.get("impressionsUnique"))
        interactions += _interactions(p)
    # Per-network field gaps: some networks (e.g. TikTok) report reach but not
    # impressions. Use reach as the impressions denominator when impressions is 0.
    denom = impressions if impressions > 0 else reach
    er = (interactions / denom * 100) if denom else 0.0
    caveat = None
    if er > 100:  # cumulative/under-reported field (seen on FB) — flag, don't trust
        caveat = "engagement_rate unreliable (network under-reports impressions for this period)"
        er = min(er, 100.0)

    def _score(p):
        return _interactions(p) + _impressions(p)
    top = max(posts, key=_score)
    return {
        "posts": len(posts),
        "impressions": int(impressions),
        "reach": int(reach),
        "interactions": int(interactions),
        "engagement_rate_pct": round(er, 2),
        "caveat": caveat,
        "top": {
            "url": top.get("url"),
            "content": (top.get("content") or "")[:160],
            "impressions": int(_impressions(top)),
            "interactions": int(_interactions(top)),
        },
    }


def snapshot(days=7):
    tok, uid, bid = _load_creds()
    to = datetime.datetime.utcnow()
    frm = to - datetime.timedelta(days=days)
    out = {"generated_at": _dt(to), "period_days": days, "networks": {}}
    totals = {"posts": 0, "impressions": 0, "reach": 0, "interactions": 0}
    for net in NETWORKS:
        posts = pull_posts(net, frm, to, tok, uid, bid)
        s = summarize(posts)
        out["networks"][net] = s
        for k in totals:
            totals[k] += s.get(k, 0)
    totals["engagement_rate_pct"] = round(
        (totals["interactions"] / totals["impressions"] * 100) if totals["impressions"] else 0.0, 2)
    out["totals"] = totals
    return out


def _main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sp = sub.add_parser("snapshot")
    sp.add_argument("--days", type=int, default=7)
    a = ap.parse_args()
    if a.cmd == "snapshot":
        print(json.dumps(snapshot(a.days), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    _main()
