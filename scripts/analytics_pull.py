#!/usr/bin/env python3
"""
UPE — analytics pull (the data heartbeat of the digital factory).

Captures a live Metricool snapshot and persists it two ways:
  - data/metrics/snapshot_YYYY-MM-DD.json  (full snapshot, one per run)
  - data/history.jsonl                      (one compact line per run, append-only)

The append-only history is what the weekly scorecard / control loop reads to
compute week-over-week deltas and growth velocity.

Run locally:   python3 scripts/analytics_pull.py
Run in CI:     same, with METRICOOL_* env vars set as GitHub secrets.
"""
import json
import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from analytics.metricool import MetricoolAnalytics  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
METRICS_DIR = ROOT / "data" / "metrics"
HISTORY = ROOT / "data" / "history.jsonl"


def compact(snap):
    """One flat row for the rolling history."""
    f = snap["followers"]
    a = snap["activity"]
    row = {"date": snap["captured"][:10]}
    total = 0
    for net, d in f.items():
        cur = d.get("current") or 0
        row[f"{net}_followers"] = cur
        total += cur
    row["total_followers"] = total
    row["ig_reel_views_90d"] = a.get("instagram_reel_views", {}).get("sum", 0)
    row["tiktok_views_90d"] = a.get("tiktok_video_views", {}).get("sum", 0)
    row["youtube_views_90d"] = a.get("youtube_views", {}).get("sum", 0)
    # derived health signals
    ig_views = row["ig_reel_views_90d"]
    ig_f = row.get("instagram_followers", 0) or 1
    row["ig_reach_pct"] = round(100 * (ig_views / 23) / ig_f, 2) if ig_views else 0
    return row


def main():
    snap = MetricoolAnalytics().snapshot()
    METRICS_DIR.mkdir(parents=True, exist_ok=True)
    HISTORY.parent.mkdir(parents=True, exist_ok=True)

    date = snap["captured"][:10]
    (METRICS_DIR / f"snapshot_{date}.json").write_text(
        json.dumps(snap, indent=2, ensure_ascii=False)
    )

    row = compact(snap)
    with HISTORY.open("a") as fh:
        fh.write(json.dumps(row, ensure_ascii=False) + "\n")

    print(f"✓ snapshot saved: data/metrics/snapshot_{date}.json")
    print(f"✓ history appended: total_followers={row['total_followers']:.0f} "
          f"(IG {row.get('instagram_followers',0):.0f} / "
          f"TT {row.get('tiktok_followers',0):.0f} / "
          f"FB {row.get('facebook_followers',0):.0f} / "
          f"LI {row.get('linkedin_followers',0):.0f} / "
          f"YT {row.get('youtube_followers',0):.0f})")


if __name__ == "__main__":
    main()
