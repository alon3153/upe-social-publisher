#!/usr/bin/env python3
"""
UPE — weekly scorecard & control loop.

Reads data/history.jsonl, compares the latest snapshot to ~7 days ago, computes
growth velocity per network, benchmarks it against the trajectory required to hit
the realistic target, and emits an actionable Hebrew RTL scorecard with
amplify / fix / cut decisions.

This is the "improve" half of the factory: it turns fresh data into decisions.

Run:  python3 scripts/weekly_scorecard.py            # prints scorecard
      python3 scripts/weekly_scorecard.py --email    # also emails via notify.py
"""
import json
import subprocess
import sys
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).resolve().parent.parent
HISTORY = ROOT / "data" / "history.jsonl"

# Realistic reframed target (engaged followers IG+TikTok carry the bulk).
TARGET_TOTAL = 200_000          # 12-month realistic stretch target
WEEKS = 52
REQUIRED_WEEKLY_PCT = ((TARGET_TOTAL / 46793) ** (1 / WEEKS) - 1) * 100  # ~2.8%/wk
VANITY_1M_WEEKLY_PCT = ((1_000_000 / 46793) ** (1 / WEEKS) - 1) * 100    # ~6.1%/wk

NET_HE = {
    "instagram": "Instagram", "tiktok": "TikTok", "facebook": "Facebook",
    "linkedin": "LinkedIn", "youtube": "YouTube",
}


def load():
    if not HISTORY.exists():
        sys.exit("No history yet — run scripts/analytics_pull.py first.")
    rows = [json.loads(l) for l in HISTORY.read_text().splitlines() if l.strip()]
    return rows


def pick_prev(rows, latest):
    """Closest row at least 5 days before latest; else the earliest."""
    ld = datetime.strptime(latest["date"], "%Y-%m-%d")
    candidates = []
    for r in rows[:-1]:
        try:
            d = datetime.strptime(r["date"], "%Y-%m-%d")
            if (ld - d).days >= 5:
                candidates.append((d, r))
        except ValueError:
            continue
    if candidates:
        return max(candidates, key=lambda x: x[0])[1]
    return rows[0] if len(rows) > 1 else None


def main():
    rows = load()
    latest = rows[-1]
    prev = pick_prev(rows, latest)

    lines = []
    lines.append(f"# 📊 כרטיס ניקוד שבועי — UPE Digital ({latest['date']})\n")

    if prev is None:
        lines.append("> נקודת מדידה ראשונה — אין עדיין שבוע קודם להשוואה. "
                     "מהשבוע הבא יוצגו דלתות צמיחה והחלטות.\n")
    else:
        lines.append(f"> השוואה מול {prev['date']}\n")

    lines.append("| ערוץ | עוקבים | Δ שבוע | קצב/שבוע | מול יעד |")
    lines.append("|------|--------|--------|----------|---------|")
    decisions = []
    for net in ["instagram", "tiktok", "linkedin", "facebook", "youtube"]:
        cur = latest.get(f"{net}_followers", 0) or 0
        if prev:
            p = prev.get(f"{net}_followers", 0) or 0
            d = cur - p
            pct = (d / p * 100) if p else 0
            pace = "✅" if pct >= REQUIRED_WEEKLY_PCT else ("➡️" if pct > 0 else "🔴")
            lines.append(f"| {NET_HE[net]} | {cur:,.0f} | {d:+.0f} | {pct:+.2f}% | {pace} |")
            if net in ("instagram", "tiktok") and pct < REQUIRED_WEEKLY_PCT:
                decisions.append(
                    f"⚠️ {NET_HE[net]} מתחת לקצב הנדרש ({pct:+.2f}% מול "
                    f"{REQUIRED_WEEKLY_PCT:.2f}% דרוש) — להגביר פורמט מנצח / Spark Ad")
        else:
            lines.append(f"| {NET_HE[net]} | {cur:,.0f} | — | — | — |")

    total = latest.get("total_followers", 0)
    lines.append(f"| **סה״כ** | **{total:,.0f}** | | | |\n")

    # Trajectory check
    lines.append("## מסלול מול יעד")
    lines.append(f"- יעד ריאלי 12 ח': **{TARGET_TOTAL:,}** עוקבים מעורבים → "
                 f"דרוש **{REQUIRED_WEEKLY_PCT:.2f}%/שבוע**")
    lines.append(f"- יעד נומינלי 1M: דרוש **{VANITY_1M_WEEKLY_PCT:.2f}%/שבוע** "
                 f"(פי ~{VANITY_1M_WEEKLY_PCT/REQUIRED_WEEKLY_PCT:.1f} — לא בר-השגה אורגנית)")

    # Content health signals (control-loop core)
    lines.append("\n## אותות תוכן (מה להגביר / לתקן)")
    ig_v = latest.get("ig_reel_views_90d", 0)
    tt_v = latest.get("tiktok_views_90d", 0)
    yt_v = latest.get("youtube_views_90d", 0)
    ig_reach = latest.get("ig_reach_pct", 0)
    lines.append(f"- IG reels reach: **{ig_reach}%** מבסיס העוקבים "
                 f"({'בריא' if ig_reach >= 15 else '🔴 קריטי — הפורמט לא מגיע לקהל חדש'})")
    lines.append(f"- TikTok צפיות 90d: **{tt_v:,.0f}** "
                 f"({'מתחיל לזוז' if tt_v > 20000 else '🔴 ערוץ-עופרת מוזנח — הכי הרבה פוטנציאל'})")
    lines.append(f"- YouTube צפיות 90d: **{yt_v:,.0f}** מול "
                 f"{latest.get('youtube_followers',0):.0f} מנויים "
                 f"({'🔴 נצפה אך לא ממיר למנויים — להוסיף CTA הרשמה + Shorts' if yt_v > 5000 else 'מת'})")

    if decisions:
        lines.append("\n## 🎯 החלטות השבוע")
        for d in decisions:
            lines.append(f"- {d}")

    lines.append("\n**צעד הבא:** להגביר את הקליפ/פורמט עם ה-reach הגבוה ביותר "
                 "(Spark Ad), ולתקן את הערוץ עם האות האדום הבולט ביותר.")

    out = "\n".join(lines)
    print(out)

    # Persist latest scorecard
    (ROOT / "reports").mkdir(exist_ok=True)
    (ROOT / "reports" / f"scorecard_{latest['date']}.md").write_text(out)

    if "--email" in sys.argv:
        try:
            subprocess.run(
                [sys.executable, str(ROOT / "scripts" / "notify.py"),
                 "--subject", f"📊 UPE Digital — כרטיס ניקוד שבועי {latest['date']}",
                 "--body", out],
                check=False,
            )
        except Exception as e:
            print(f"(email skipped: {e})")


if __name__ == "__main__":
    main()
