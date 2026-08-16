#!/usr/bin/env python3
"""
UPE — Metricool analytics client (read-only).

Pulls real follower + engagement timelines for every connected network so the
control loop can decide what is working and what to amplify.

Credentials (in priority order):
  1. Environment: METRICOOL_TOKEN, METRICOOL_USER_ID, METRICOOL_BLOG_ID
  2. Local dev fallback: ../Uproduction Operations/secrets/metricool.json
     (resolved relative to the UPE Dropbox; only used off-cloud)

Metric names below were verified live against the v2 API on 2026-06-06.
The timelines endpoint requires `from`/`to` (ISO, no tz suffix) and, for some
networks, a `subject` (account / reels / posts / ...).
"""
import json
import os
import urllib.request
import urllib.parse
import urllib.error
from pathlib import Path
from datetime import datetime, timedelta

BASE = "https://app.metricool.com/api"

# (network, subject, metric) verified valid on the v2 timelines endpoint.
FOLLOWER_METRICS = {
    "instagram": ("Instagram", "account", "followers"),
    "facebook": ("Facebook", "account", "pageFollows"),
    "linkedin": ("Linkedin", "account", "followers"),
    "tiktok": ("Tiktok", "account", "followers_count"),
    "youtube": ("Youtube", "account", "totalSubscribers"),
}

# Content-performance metrics (summed over the window) used by the control loop.
ACTIVITY_METRICS = {
    "instagram_reel_views": ("Instagram", "reels", "views"),
    "tiktok_video_views": ("Tiktok", "account", "video_views"),
    "tiktok_likes": ("Tiktok", "account", "likes"),
    "tiktok_shares": ("Tiktok", "account", "shares"),
    "facebook_posts": ("Facebook", "account", "postsCount"),
    "facebook_impressions": ("Facebook", "account", "pageImpressions"),
    "youtube_views": ("Youtube", "account", "views"),
}


def _load_creds():
    tok = os.environ.get("METRICOOL_TOKEN")
    uid = os.environ.get("METRICOOL_USER_ID")
    bid = os.environ.get("METRICOOL_BLOG_ID")
    if tok and uid and bid:
        return tok, uid, bid
    # local dev fallback — walk up to the Dropbox secrets file
    here = Path(__file__).resolve()
    for base in [
        Path.home() / "Library/CloudStorage/Dropbox-UproductionEvents/Alon ouaknine"
        / "Uproduction Operations/secrets/metricool.json",
    ]:
        if base.exists():
            cfg = json.loads(base.read_text())
            return cfg["access_token"], str(cfg["user_id"]), str(cfg["blog_id"])
    raise RuntimeError(
        "Metricool credentials not found. Set METRICOOL_TOKEN / METRICOOL_USER_ID "
        "/ METRICOOL_BLOG_ID or provide the local secrets file."
    )


class MetricoolAnalytics:
    def __init__(self):
        self.token, self.user_id, self.blog_id = _load_creds()

    def _get(self, path, params):
        p = dict(params)
        p["userId"] = self.user_id
        url = f"{BASE}{path}?{urllib.parse.urlencode(p)}"
        req = urllib.request.Request(url)
        req.add_header("X-Mc-Auth", self.token)
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                raw = r.read().decode()
                return json.loads(raw) if raw else {}
        except urllib.error.HTTPError as e:
            return {"_error": e.code, "_body": e.read().decode()[:200]}

    @staticmethod
    def _values(data):
        """Flatten any timeline shape into an ordered list of numeric values."""
        flat = []

        def walk(x):
            if isinstance(x, dict):
                if "value" in x and isinstance(x["value"], (int, float)):
                    flat.append(x["value"])
                for v in x.values():
                    walk(v)
            elif isinstance(x, list):
                for v in x:
                    walk(v)

        walk(data)
        return flat

    def timeline(self, network, metric, subject=None, days=120):
        end = datetime.now()
        start = end - timedelta(days=days)
        params = {
            "blogId": self.blog_id,
            "from": start.strftime("%Y-%m-%dT00:00:00"),
            "to": end.strftime("%Y-%m-%dT23:59:59"),
            "network": network,
            "metric": metric,
        }
        if subject:
            params["subject"] = subject
        return self._get("/v2/analytics/timelines", params)

    def followers(self, days=120):
        """Current + period-start follower count per network."""
        out = {}
        for key, (net, subj, metric) in FOLLOWER_METRICS.items():
            vals = self._values(self.timeline(net, metric, subj, days))
            out[key] = {
                "current": vals[-1] if vals else None,
                "period_start": vals[0] if vals else None,
                "delta": (vals[-1] - vals[0]) if len(vals) >= 2 else None,
                "points": len(vals),
            }
        return out

    def activity(self, days=90):
        """Summed content-performance metrics over the window."""
        out = {}
        for key, (net, subj, metric) in ACTIVITY_METRICS.items():
            vals = self._values(self.timeline(net, metric, subj, days))
            out[key] = {"sum": round(sum(vals), 2), "points": len(vals)}
        return out

    def snapshot(self, follower_days=120, activity_days=90):
        return {
            "captured": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "blog_id": self.blog_id,
            "follower_window_days": follower_days,
            "activity_window_days": activity_days,
            "followers": self.followers(follower_days),
            "activity": self.activity(activity_days),
        }


if __name__ == "__main__":
    snap = MetricoolAnalytics().snapshot()
    print(json.dumps(snap, indent=2, ensure_ascii=False))
