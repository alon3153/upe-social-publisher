#!/usr/bin/env python3
"""
UPE Marketing Council — daily cross-channel audit + automatic improvement loop.

Runs every day in the background. Pipeline:
  1. PULL    real results from every channel (Metricool: IG/FB/TikTok/LI/YT)
             + previous period for trend.
  2. SCORE   deterministic scorecard vs KPI targets (kpi_targets.json):
             impressions growth, engagement rate, reach, cadence, 10-leads/mo.
  3. REVIEW  a multi-lens Claude council (with live web_search for what's working
             RIGHT NOW in B2B/MICE organic growth) returns: what worked / failed,
             SAFE auto-fixes, gated recommendations, and a follower-growth plan.
  4. APPLY   safe auto-fixes automatically (content angles/cadence directives →
             state/council_directives.json, consumed by the next content run).
             Anything touching live publishing / spend / client-facing copy stays
             GATED for Alon's approval (iron rule: review ALL content before publish).
  5. REPORT  write reports/council/YYYY-MM-DD.md + email Alon an RTL Hebrew digest.

Always exits 0 (a daemon must never break its own schedule); reports via email.

Usage:
  python3 scripts/council.py                 # full run + email
  python3 scripts/council.py --dry-run       # no email, no file writes, print report
  python3 scripts/council.py --no-llm        # scorecard only (skip Claude) — cheap smoke test
"""
import os, sys, json, argparse, datetime, urllib.request, urllib.error
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import metricool_analytics as ma

API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
MODEL = os.environ.get("COUNCIL_MODEL", "claude-sonnet-4-6")
TARGETS = json.loads((ROOT / "scripts" / "kpi_targets.json").read_text())
REPORT_DIR = ROOT / "reports" / "council"
METRICS_DIR = ROOT / "reports" / "metrics"
STATE_DIR = ROOT / "state"
DIRECTIVES = STATE_DIR / "council_directives.json"


def _today():
    return datetime.datetime.utcnow().strftime("%Y-%m-%d")


# ---------------------------------------------------------------- scorecard ----
def build_scorecard(cur, prev):
    """Deterministic pass/fail vs targets. cur/prev are snapshot dicts."""
    t = TARGETS["effectiveness_targets"]
    ct, pt = cur["totals"], prev["totals"]
    rows = []

    def grade(label, value, target, ok, unit=""):
        rows.append({"metric": label, "value": value, "target": target,
                     "unit": unit, "status": "✅" if ok else "❌"})

    imp_growth = round(((ct["impressions"] - pt["impressions"]) / pt["impressions"] * 100)
                       if pt["impressions"] else 0.0, 1)
    grade("חשיפות (תקופה)", ct["impressions"], "↑", ct["impressions"] > 0)
    grade("צמיחת חשיפות", imp_growth, t["weekly_impressions_growth_pct"],
          imp_growth >= t["weekly_impressions_growth_pct"], "%")
    grade("Engagement rate", ct["engagement_rate_pct"], t["min_avg_engagement_rate_pct"],
          ct["engagement_rate_pct"] >= t["min_avg_engagement_rate_pct"], "%")
    posts_week = round(ct["posts"] / (cur["period_days"] / 7.0), 1) if cur["period_days"] else 0
    grade("פוסטים/שבוע", posts_week, t["posts_per_week_min"],
          posts_week >= t["posts_per_week_min"])
    grade("לידים מוסמכים/חודש", "לא מחובר", TARGETS["primary_kpi"]["qualified_leads_per_month"], False)

    passed = sum(1 for r in rows if r["status"] == "✅")
    return {"rows": rows, "passed": passed, "total": len(rows),
            "impressions_growth_pct": imp_growth, "posts_per_week": posts_week}


# ---------------------------------------------------------------- the council --
COUNCIL_PROMPT = """You are the UPE Marketing Council — a panel of senior B2B/MICE growth strategists
auditing Uproduction Events' organic digital marketing. UPE is a B2B corporate-event production &
incentive-travel company (Israel-based, global ops). Audience = decision-makers (CMO/HR/CEO/event
leads) at companies in Israel and Europe that run events/conferences needing a production company
or local supplier.

GOALS:
- North-star: 500,000 organic followers over ~3 years (leading indicators matter more than the count).
- PRIMARY KPI: 10 real NEW qualified leads per month from NEW potential clients for substantial events.
- Maximize impressions, raise engagement, continuous measurable improvement.

HARD CONSTRAINTS (UPE iron rules) — respect these when classifying actions:
- Nothing publishes without human approval; all client-facing content is reviewed first.
- So: action.category "safe_auto" = ONLY content angles, hashtag/topic strategy, posting-cadence
  guidance, or analytics/SEO-technical notes that feed the (already approval-gated) content pipeline.
  Anything that publishes, spends money, or is client-facing copy = category "gated".

Here is this period's real data (Metricool). Note caveats: some networks under-report impressions
(FB engagement_rate flagged unreliable; TikTok reports reach not impressions).

DATA:
{data}

DETERMINISTIC SCORECARD:
{scorecard}

Use web_search to find what is working RIGHT NOW (2026) for B2B/MICE organic growth and for the
specific networks where UPE is weakest. Be concrete and brutally honest about the weak numbers.

Return ONE json object (and nothing after it) in a ```json fenced block, all human-facing strings
in HEBREW, with EXACTLY these keys:
{{
  "verdict_summary": "2-4 sentence honest verdict in Hebrew",
  "scores": {{"instagram": 0-100, "facebook": 0-100, "tiktok": 0-100, "linkedin": 0-100, "youtube": 0-100, "google_organic_geo": 0-100, "overall": 0-100}},
  "what_worked": ["..."],
  "what_failed": ["..."],
  "auto_fixes": [{{"category": "safe_auto", "action": "Hebrew action", "detail": "what+why", "channel": "instagram|..."}}],
  "recommendations": [{{"category": "gated", "priority": "P0|P1|P2", "action": "Hebrew", "expected_impact": "Hebrew", "channel": "..."}}],
  "follower_growth_plan": ["concrete Hebrew steps toward the 500K north-star, ordered"],
  "leads_actions": ["concrete Hebrew steps to hit 10 qualified leads/month, ordered"]
}}"""


def run_council(cur, prev, scorecard):
    if not API_KEY:
        return {"error": "ANTHROPIC_API_KEY not set"}
    prompt = COUNCIL_PROMPT.format(
        data=json.dumps({"current": cur, "previous_totals": prev["totals"]}, ensure_ascii=False),
        scorecard=json.dumps(scorecard, ensure_ascii=False))
    body = {
        "model": MODEL,
        "max_tokens": 6000,
        "tools": [{"type": "web_search_20250305", "name": "web_search", "max_uses": 6}],
        "messages": [{"role": "user", "content": prompt}],
    }
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=json.dumps(body).encode(),
        headers={"x-api-key": API_KEY, "anthropic-version": "2023-06-01",
                 "content-type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=600) as r:
            resp = json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        return {"error": f"anthropic {e.code}: {e.read().decode()[:300]}"}
    except Exception as e:
        return {"error": f"anthropic {e}"}
    text = "".join(b.get("text", "") for b in resp.get("content", []) if b.get("type") == "text")
    return _extract_json(text) or {"error": "could not parse council JSON", "raw": text[:800]}


def _extract_json(text):
    if "```json" in text:
        text = text.split("```json", 1)[1].split("```", 1)[0]
    elif "```" in text:
        text = text.split("```", 1)[1].split("```", 1)[0]
    s, e = text.find("{"), text.rfind("}")
    if s == -1 or e == -1:
        return None
    try:
        return json.loads(text[s:e + 1])
    except json.JSONDecodeError:
        return None


# --------------------------------------------------------------- apply fixes ---
def apply_auto_fixes(verdict, dry_run):
    """Write safe auto-fix directives for the next content-generation run to consume.
    Does NOT publish — respects the approval gate. Returns the applied list."""
    fixes = [f for f in verdict.get("auto_fixes", []) if f.get("category") == "safe_auto"]
    if not fixes or dry_run:
        return fixes
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    payload = {"updated_at": _today(),
               "source": "daily-council",
               "directives": fixes,
               "follower_growth_plan": verdict.get("follower_growth_plan", []),
               "leads_actions": verdict.get("leads_actions", [])}
    DIRECTIVES.write_text(json.dumps(payload, ensure_ascii=False, indent=2))
    return fixes


# ------------------------------------------------------------------- report ----
def render_html(cur, scorecard, verdict, applied):
    d = _today()
    sc = verdict.get("scores", {})
    def chips(items):
        return "".join(f"<li>{x}</li>" for x in items) or "<li>—</li>"
    net_rows = ""
    for net, s in cur["networks"].items():
        cav = f" <span style='color:#b00'>({s['caveat']})</span>" if s.get("caveat") else ""
        net_rows += (f"<tr><td>{net}</td><td>{s['posts']}</td><td>{s['impressions']:,}</td>"
                     f"<td>{s['reach']:,}</td><td>{s['interactions']:,}</td>"
                     f"<td>{s['engagement_rate_pct']}%{cav}</td><td>{sc.get(net,'—')}</td></tr>")
    sb_rows = "".join(
        f"<tr><td>{r['metric']}</td><td>{r['value']}{r['unit']}</td>"
        f"<td>{r['target']}{r['unit']}</td><td>{r['status']}</td></tr>" for r in scorecard["rows"])
    recs = "".join(
        f"<li><b>[{r.get('priority','')}]</b> {r.get('action','')} "
        f"<span style='color:#555'>— {r.get('expected_impact','')}</span> "
        f"<span dir='ltr' style='color:#888'>({r.get('channel','')})</span></li>"
        for r in verdict.get("recommendations", []))
    applied_li = "".join(f"<li>{f.get('action','')} <span dir='ltr' style='color:#888'>({f.get('channel','')})</span></li>" for f in applied)
    return f"""<html dir="rtl" lang="he"><head><meta charset="utf-8"></head>
<body dir="rtl" style="font-family:Arial,Helvetica,sans-serif;font-size:14px;direction:rtl;text-align:right;color:#111;">
<div dir="rtl" style="direction:rtl;text-align:right;max-width:680px;">
<h2>🏛️ מועצת השיווק — דוח יומי {d}</h2>
<p style="font-size:16px;"><b>ציון כולל: {sc.get('overall','—')}/100</b> · scorecard עבר {scorecard['passed']}/{scorecard['total']}</p>
<p style="background:#f6f6f6;padding:10px;border-right:3px solid #333;">{verdict.get('verdict_summary','—')}</p>

<h3>תוצאות לפי ערוץ ({cur['period_days']} ימים)</h3>
<table dir="rtl" border="0" cellpadding="6" style="border-collapse:collapse;width:100%;font-size:13px;">
<tr style="background:#222;color:#fff;"><th>ערוץ</th><th>פוסטים</th><th>חשיפות</th><th>Reach</th><th>תגובות</th><th>ER</th><th>ציון</th></tr>
{net_rows}</table>

<h3>Scorecard מול יעדים</h3>
<table dir="rtl" border="0" cellpadding="6" style="border-collapse:collapse;width:100%;font-size:13px;">
<tr style="background:#222;color:#fff;"><th>מדד</th><th>ערך</th><th>יעד</th><th></th></tr>
{sb_rows}</table>

<h3>✅ מה עבד</h3><ul>{chips(verdict.get('what_worked',[]))}</ul>
<h3>❌ מה נכשל</h3><ul>{chips(verdict.get('what_failed',[]))}</ul>

<h3>🤖 תיקונים אוטומטיים שבוצעו ({len(applied)})</h3>
<p style="color:#555;font-size:12px;">נכתבו ל-state/council_directives.json — נצרכים ע"י ייצור התוכן הבא. לא פורסם דבר ללא אישורך.</p>
<ul>{applied_li or '<li>—</li>'}</ul>

<h3>📋 המלצות לאישורך (gated)</h3><ul>{recs or '<li>—</li>'}</ul>

<h3>🎯 דרך ל-500K עוקבים</h3><ol>{chips(verdict.get('follower_growth_plan',[]))}</ol>
<h3>💼 דרך ל-10 לידים/חודש</h3><ol>{chips(verdict.get('leads_actions',[]))}</ol>

<hr><p style="color:#888;font-size:11px;">UPE Marketing Council · אוטומטי · {d}</p>
</div></body></html>"""


def render_md(cur, scorecard, verdict, applied):
    return (f"# UPE Marketing Council — {_today()}\n\n"
            f"Overall: {verdict.get('scores',{}).get('overall','—')}/100 · "
            f"scorecard {scorecard['passed']}/{scorecard['total']}\n\n"
            f"## Verdict\n{verdict.get('verdict_summary','—')}\n\n"
            f"## Totals\n```json\n{json.dumps(cur['totals'], ensure_ascii=False, indent=2)}\n```\n\n"
            f"## Auto-fixes applied\n" + "\n".join(f"- {f.get('action')} ({f.get('channel')})" for f in applied) +
            f"\n\n## Recommendations (gated)\n" +
            "\n".join(f"- [{r.get('priority')}] {r.get('action')} — {r.get('expected_impact')}"
                      for r in verdict.get("recommendations", [])) +
            f"\n\n## Follower plan\n" + "\n".join(f"{i+1}. {s}" for i, s in enumerate(verdict.get("follower_growth_plan", []))) +
            f"\n\n## Leads actions\n" + "\n".join(f"{i+1}. {s}" for i, s in enumerate(verdict.get("leads_actions", []))) + "\n")


# --------------------------------------------------------------------- main ----
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--no-llm", action="store_true")
    ap.add_argument("--days", type=int, default=TARGETS.get("review_period_days", 7))
    a = ap.parse_args()

    days = a.days
    cur = ma.snapshot(days)
    prev = ma.snapshot(days * 2)
    # previous-period totals = (2*days window) - (current window)
    for k in ("posts", "impressions", "reach", "interactions"):
        prev["totals"][k] = max(prev["totals"].get(k, 0) - cur["totals"].get(k, 0), 0)

    scorecard = build_scorecard(cur, prev)

    if a.no_llm:
        verdict = {"verdict_summary": "(--no-llm) scorecard only", "scores": {}, "what_worked": [],
                   "what_failed": [], "auto_fixes": [], "recommendations": [],
                   "follower_growth_plan": [], "leads_actions": []}
    else:
        verdict = run_council(cur, prev, scorecard)
        if verdict.get("error"):
            print(f"council LLM error: {verdict['error']}", file=sys.stderr)

    applied = apply_auto_fixes(verdict, a.dry_run)
    html = render_html(cur, scorecard, verdict, applied)
    md = render_md(cur, scorecard, verdict, applied)

    if a.dry_run:
        print(md)
        print(f"\n[dry-run] would email + write report. auto-fixes that would apply: {len(applied)}")
        return 0

    METRICS_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    (METRICS_DIR / f"{_today()}.json").write_text(json.dumps(cur, ensure_ascii=False, indent=2))
    (REPORT_DIR / f"{_today()}.md").write_text(md)

    subj = f"🏛️ מועצת השיווק — דוח יומי {_today()} · ציון {verdict.get('scores',{}).get('overall','—')}/100"
    try:
        from daily_email import send_graph_html
        ok, info = send_graph_html(subj, html)
        print(f"email: {ok} ({info})")
    except Exception as e:
        print(f"email failed: {e}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
