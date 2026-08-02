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
import os, sys, json, re, argparse, datetime, urllib.request, urllib.error
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import metricool_analytics as ma
import leads_source
import seo_geo_source

API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
MODEL = os.environ.get("COUNCIL_MODEL") or "claude-sonnet-4-6"
TARGETS = json.loads((ROOT / "scripts" / "kpi_targets.json").read_text())
REPORT_DIR = ROOT / "reports" / "council"
METRICS_DIR = ROOT / "reports" / "metrics"
STATE_DIR = ROOT / "state"
DIRECTIVES = STATE_DIR / "council_directives.json"


def _today():
    return datetime.datetime.utcnow().strftime("%Y-%m-%d")


def digital_attributed_leads(leads, digital_sources):
    """Count opportunities whose LeadSource is a digital channel (case-insensitive).
    Digital = not Word-of-Mouth. Proves the digital engine converts (spec Part 3 metric,
    computable today from Salesforce by_source without a new form field)."""
    by_source = (leads or {}).get("by_source") or {}
    wanted = {s.lower() for s in digital_sources}
    return sum(n for src, n in by_source.items() if str(src).lower() in wanted)


def weighted_score(components, weights):
    """Deterministic 0-100. components[k] is a fraction-of-target in [0,1] or None
    (unavailable). Unavailable components are dropped and their weight is renormalized
    over what IS available, so a missing data source lowers confidence, not the score."""
    avail = {k: max(0.0, min(1.0, v)) for k, v in components.items() if v is not None}
    wsum = sum(weights[k] for k in avail)
    if not wsum:
        return 0
    return round(sum(weights[k] * avail[k] for k in avail) / wsum * 100)


# ---------------------------------------------------------------- scorecard ----
def build_scorecard(cur, prev, leads, seo_geo=None):
    """Deterministic weighted 0-100 scorecard. cur/prev are snapshot dicts.

    Five scored components (qualified_leads, digital_leads, organic, aeo,
    social_presence) feed weighted_score(). Engagement and impressions-growth
    move to context_rows (informational, not scored). Keeps rows/passed/total
    for backward compat (rows = scored_rows + context_rows; passed/total count
    scored_rows only)."""
    leads = leads or {}
    t = TARGETS["effectiveness_targets"]
    W = TARGETS["scorecard_weights"]
    org_t = TARGETS["organic_targets"]
    lead_target = TARGETS["primary_kpi"]["qualified_leads_per_month"]
    ct, pt = cur["totals"], prev["totals"]
    scored, context = [], []

    def row(bucket, label, value, target, ok, unit=""):
        bucket.append({"metric": label, "value": value, "target": target,
                       "unit": unit, "status": "✅" if ok else "❌"})

    comp = {}

    # 1) qualified leads (scored)
    if leads.get("ok"):
        ql = leads.get("qualified_leads") or 0
        comp["qualified_leads"] = ql / lead_target if lead_target else None
        row(scored, "לידים מוסמכים (30 ימים)", ql, lead_target, ql >= lead_target)
    else:
        comp["qualified_leads"] = None
        row(scored, "לידים מוסמכים/חודש", "לא מחובר", lead_target, False)

    # 2) digital-attributed leads (scored) — target = 3 of the 10
    dig_target = max(1, round(lead_target * 0.3))
    if leads.get("ok"):
        dl = digital_attributed_leads(leads, TARGETS["digital_lead_sources"])
        comp["digital_leads"] = dl / dig_target
        row(scored, "לידים מיוחסים לדיגיטל", dl, dig_target, dl >= dig_target)
    else:
        comp["digital_leads"] = None
        row(scored, "לידים מיוחסים לדיגיטל", "לא מחובר", dig_target, False)

    # 3) organic (scored) — clicks + top3 keywords, averaged
    if seo_geo and seo_geo.get("ok"):
        clicks = seo_geo.get("weekly_clicks") or 0
        top3 = seo_geo.get("top3_keywords") or 0
        f_clicks = min(1.0, clicks / org_t["weekly_clicks_min"])
        f_top3 = min(1.0, top3 / org_t["top3_keywords_min"])
        comp["organic"] = (f_clicks + f_top3) / 2
        row(scored, "קליקים אורגניים/שבוע", clicks, org_t["weekly_clicks_min"],
            clicks >= org_t["weekly_clicks_min"])
        row(scored, "מונחים ב-Top-3", top3, org_t["top3_keywords_min"],
            top3 >= org_t["top3_keywords_min"])
    else:
        comp["organic"] = None
        row(scored, "אורגני (GSC)", "לא מחובר", org_t["weekly_clicks_min"], False)

    # 4) AEO (scored) — cited in N engines out of 3
    if seo_geo and seo_geo.get("ok") and seo_geo.get("aeo_cited_engines") is not None:
        cited = seo_geo.get("aeo_cited_engines") or 0
        comp["aeo"] = min(1.0, cited / 3)
        row(scored, "נראות ב-AI (מנועים)", cited, 3, cited >= 3)
    else:
        comp["aeo"] = None
        row(scored, "נראות ב-AI (מנועים)", "לא מחובר", 3, False)

    # 5) social presence floor (scored) — cadence met, NOT growth
    posts_week = round(ct["posts"] / (cur["period_days"] / 7.0), 1) if cur["period_days"] else 0
    floor_ok = posts_week >= t["posts_per_week_min"]
    comp["social_presence"] = 1.0 if floor_ok else min(1.0, posts_week / t["posts_per_week_min"])
    row(scored, "נוכחות סושיאל (רצפה)", posts_week, t["posts_per_week_min"], floor_ok)

    # CONTEXT (not scored): engagement + impressions growth
    imp_growth = round(((ct["impressions"] - pt["impressions"]) / pt["impressions"] * 100)
                       if pt.get("impressions") else 0.0, 1)
    row(context, "צמיחת חשיפות", imp_growth, t["weekly_impressions_growth_pct"],
        imp_growth >= t["weekly_impressions_growth_pct"], "%")
    row(context, "Engagement rate", ct["engagement_rate_pct"], t["min_avg_engagement_rate_pct"],
        ct["engagement_rate_pct"] >= t["min_avg_engagement_rate_pct"], "%")
    row(context, "חשיפות (תקופה)", ct["impressions"], "↑", ct["impressions"] > 0)

    # attribution note (kept from old scorecard) as a context row
    if leads.get("ok") and leads.get("dominant_source"):
        if leads.get("attribution_gap"):
            row(context, "ייחוס לידים", "לא-מיוחס", "מקור אמיתי", False)
        else:
            row(context, f"ערוץ ממיר ({leads['dominant_source']})",
                leads.get("dominant_share_pct", 0), "↑", True, "%")

    weighted = weighted_score(comp, W)
    # Leads are the PRIMARY definition of winning (55% of intended weight). If BOTH
    # lead components are unavailable (Salesforce dark), the headline cannot honestly
    # read as a "winning" score no matter how the floor renormalizes — cap it so a
    # data outage never emails Alon a false green. (final review 2026-08-02)
    if comp.get("qualified_leads") is None and comp.get("digital_leads") is None:
        weighted = min(weighted, 40)
    passed = sum(1 for r in scored if r["status"] == "✅")
    return {"rows": scored + context, "scored_rows": scored, "context_rows": context,
            "components": comp, "weighted": weighted,
            "passed": passed, "total": len(scored),
            "impressions_growth_pct": imp_growth, "posts_per_week": posts_week,
            "lead_attribution": {"by_source": leads.get("by_source", {}),
                                 "dominant_source": leads.get("dominant_source"),
                                 "dominant_share_pct": leads.get("dominant_share_pct", 0),
                                 "attribution_gap": leads.get("attribution_gap", False),
                                 "note": leads.get("attribution_note", "")}}


# ---------------------------------------------------------------- the council --
COUNCIL_PROMPT = """You are the UPE Marketing Council — a panel of senior B2B/MICE growth strategists
auditing Uproduction Events' organic digital marketing. UPE is a B2B corporate-event production &
incentive-travel company (Israel-based, global ops). Audience = decision-makers (CMO/HR/CEO/event
leads) at companies in Israel and Europe that run events/conferences needing a production company
or local supplier.

GOALS (scored deterministically — do not invent your own overall number; the headline score
is computed from business outcomes, your "overall" is an advisory second opinion):
- PRIMARY: 10 real NEW qualified leads/month, of which >=3 are digital-attributed (LeadSource
  not Word-of-Mouth). This is what winning means.
- SECONDARY: Google-organic momentum (clicks + Top-3 Hebrew keywords) and AI/AEO citations.
- CONTEXT ONLY — engagement/impressions are CONTEXT, not goals. A low engagement rate on
  Israeli-B2B social is EXPECTED and must NOT dominate your assessment or the overall score.
- North-star: 500,000 organic followers over ~3 years (leading indicator, not a near-term target).

HARD CONSTRAINTS (UPE iron rules) — respect these when classifying actions:
- Nothing publishes without human approval; all client-facing content is reviewed first.
- So: action.category "safe_auto" = ONLY content angles, hashtag/topic strategy, posting-cadence
  guidance, or analytics/SEO-technical notes that feed the (already approval-gated) content pipeline.
  Anything that publishes, spends money, or is client-facing copy = category "gated".

Here is this period's real data (Metricool). Note caveats: some networks under-report impressions
(FB engagement_rate flagged unreliable; TikTok reports reach not impressions).
METHODOLOGY CAVEAT — impressions growth: post metrics are LIFETIME values bucketed by publish date
(current 7d window vs the 7d before it). A single viral post rolling out of the current window
produces a mechanical cliff in "growth" that is NOT a real audience collapse. Before declaring a
systemic crash, check whether most of the delta comes from one network / one top post (typically
YouTube) and say so explicitly in the verdict.

DATA:
{data}

DETERMINISTIC SCORECARD:
{scorecard}

LEAD ATTRIBUTION: the scorecard's "lead_attribution" shows where this month's pipeline actually
came from. If a REAL source dominates (e.g. Web/Linkedin/Word of mouth), treat it as the proven
converting channel and make "leads_actions" DOUBLE DOWN on it (Web ⇒ accelerate Hebrew commercial
SEO/content). Only if the dominant bucket is unattributed default (Advertisement/none) flag it as a
data-entry gap — do NOT recommend UTM tracking otherwise (UPE's deals are relationship/inbound B2B).

channel_cadence is MANDATORY and is a safe_auto-class decision (posting-cadence guidance): for EVERY
network above, set the max posts/week the approval-gated pipeline should schedule, based on the
measured data (integers 0-14). Local publishers enforce these caps mechanically, so be decisive —
an over-posted weak network (e.g. Facebook) should get a LOW cap.

Use web_search to find what is working RIGHT NOW (2026) for B2B/MICE organic growth and for the
specific networks where UPE is weakest. Be concrete and brutally honest about the weak numbers.

Be concise to stay within limits: MAX 6 items per list, each item ≤ 2 sentences. Output ONLY the
json — no preamble, no prose after it.

Return ONE json object (and nothing after it) in a ```json fenced block, all human-facing strings
in HEBREW, with EXACTLY these keys:
{{
  "verdict_summary": "2-4 sentence honest verdict in Hebrew",
  "scores": {{"instagram": 0-100, "facebook": 0-100, "tiktok": 0-100, "linkedin": 0-100, "youtube": 0-100, "google_organic_geo": 0-100, "overall": 0-100}},
  "what_worked": ["..."],
  "what_failed": ["..."],
  "auto_fixes": [{{"category": "safe_auto", "action": "Hebrew action", "detail": "what+why", "channel": "instagram|..."}}],
  "channel_cadence": {{"facebook": {{"max_posts_per_week": 2, "reason": "Hebrew"}}, "instagram": {{"max_posts_per_week": 7, "reason": "Hebrew"}}, "linkedin": {{"max_posts_per_week": 3, "reason": "Hebrew"}}, "tiktok": {{"max_posts_per_week": 3, "reason": "Hebrew"}}, "youtube": {{"max_posts_per_week": 2, "reason": "Hebrew"}}}},
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
        "max_tokens": 16000,
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
    parsed = _extract_json(text)
    if parsed:
        return parsed
    sys.stderr.write(f"[council] parse fail. stop_reason={resp.get('stop_reason')} "
                     f"len={len(text)}\n--- tail ---\n{text[-1500:]}\n")
    return {"error": "could not parse council JSON", "raw": text[:800]}


_INVALID_ESCAPE = re.compile(r'\\(?!["\\/bfnrtu])')
_TRAILING_COMMA = re.compile(r",(\s*[}\]])")


def _repair_json(blob):
    """Repair the JSON quirks Claude actually emits, then re-parse.

    Real failure, 24.07 + 26.07.2026: the council answered correctly and in full
    (stop_reason=end_turn, ~10.3k chars) but wrote Hebrew quotes as \\' inside
    strings — e.g. \\'האם יש לך קולגה...\\'. \\' is NOT a valid JSON escape
    (JSON allows only \\" \\\\ \\/ \\b \\f \\n \\r \\t \\uXXXX), so json.loads
    rejected the whole document and Alon got 'ציון —/100' with an empty verdict
    on an otherwise perfect run. Two wasted council days, no signal that
    anything had broken.

    Strips stray backslashes before non-escape characters and trailing commas.
    Returns None if it still will not parse."""
    try:
        return json.loads(_TRAILING_COMMA.sub(r"\1", _INVALID_ESCAPE.sub("", blob)))
    except json.JSONDecodeError:
        return None


def _extract_json(text):
    """Find the council's JSON. With web_search in the loop the reply is several
    text blocks and may contain interim/partial fenced blocks — the real answer
    is the LAST parseable one, so try fenced candidates last-first, then raw.
    Each candidate gets a strict parse first, then a repair pass."""
    candidates = [m.group(1) for m in re.finditer(r"```(?:json)?\s*(.*?)```", text, re.S)]
    for c in reversed(candidates) if candidates else []:
        s, e = c.find("{"), c.rfind("}")
        if s != -1 and e != -1:
            blob = c[s:e + 1]
            try:
                return json.loads(blob)
            except json.JSONDecodeError:
                repaired = _repair_json(blob)
                if repaired is not None:
                    sys.stderr.write("[council] recovered fenced JSON via repair pass\n")
                    return repaired
    s, e = text.find("{"), text.rfind("}")
    if s == -1 or e == -1:
        return None
    blob = text[s:e + 1]
    try:
        return json.loads(blob)
    except json.JSONDecodeError:
        repaired = _repair_json(blob)
        if repaired is not None:
            sys.stderr.write("[council] recovered raw JSON via repair pass\n")
        return repaired


# --------------------------------------------------------------- apply fixes ---
CADENCE_NETWORKS = ("facebook", "instagram", "linkedin", "tiktok", "youtube")


def validate_cadence(raw):
    """Clamp the council's channel_cadence to known networks / sane ints (0-14).
    Anything malformed is dropped — a missing cap fails open downstream."""
    out = {}
    for net, cfg in (raw or {}).items():
        if net not in CADENCE_NETWORKS or not isinstance(cfg, dict):
            continue
        cap = cfg.get("max_posts_per_week")
        if isinstance(cap, bool) or not isinstance(cap, (int, float)):
            continue
        out[net] = {"max_posts_per_week": max(0, min(14, int(cap))),
                    "reason": str(cfg.get("reason", ""))[:200]}
    return out


def apply_auto_fixes(verdict, dry_run):
    """Write safe auto-fix directives for the next content-generation run to consume.
    Does NOT publish — respects the approval gate. Returns (applied_fixes, cadence)."""
    fixes = [f for f in verdict.get("auto_fixes", []) if f.get("category") == "safe_auto"]
    cadence = validate_cadence(verdict.get("channel_cadence"))
    if not cadence:
        # one bad LLM day must not drop enforcement — carry yesterday's caps forward
        prev = {}
        try:
            prev = json.loads(DIRECTIVES.read_text())
        except Exception:
            pass
        cadence = validate_cadence(prev.get("channel_cadence"))
    if (not fixes and not cadence) or dry_run:
        return fixes, cadence
    scores = verdict.get("scores", {})
    channel_priority = sorted((n for n in CADENCE_NETWORKS if n in scores),
                              key=lambda n: scores[n], reverse=True)
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    payload = {"updated_at": _today(),
               "source": "daily-council",
               "directives": fixes,
               # consumed by upe_council_directives.py (Mac bridge) → Metricool publisher caps
               "channel_cadence": cadence,
               "channel_priority": channel_priority,
               "channel_plan_basis": [f"{n}: {c['reason']}" for n, c in cadence.items() if c.get("reason")],
               "follower_growth_plan": verdict.get("follower_growth_plan", []),
               "leads_actions": verdict.get("leads_actions", [])}
    DIRECTIVES.write_text(json.dumps(payload, ensure_ascii=False, indent=2))
    return fixes, cadence


# ------------------------------------------------------------------- report ----
def render_html(cur, scorecard, verdict, applied, cadence=None):
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
        f"<td>{r['target']}{r['unit']}</td><td>{r['status']}</td></tr>" for r in scorecard["scored_rows"])
    ctx_rows = "".join(
        f"<tr><td>{r['metric']}</td><td dir='ltr'>{r['value']}{r['unit']}</td>"
        f"<td dir='ltr'>{r['target']}{r['unit']}</td><td>{r['status']}</td></tr>"
        for r in scorecard.get("context_rows", []))
    recs = "".join(
        f"<li><b>[{r.get('priority','')}]</b> {r.get('action','')} "
        f"<span style='color:#555'>— {r.get('expected_impact','')}</span> "
        f"<span dir='ltr' style='color:#888'>({r.get('channel','')})</span></li>"
        for r in verdict.get("recommendations", []))
    applied_li = "".join(f"<li>{f.get('action','')} <span dir='ltr' style='color:#888'>({f.get('channel','')})</span></li>" for f in applied)
    # A failed LLM verdict used to render as a bare 'ציון —/100' with an empty
    # summary, which reads like a quiet day rather than a broken run (24.07,
    # 26.07.2026). Say so out loud instead — the scorecard below is still real.
    err_banner = ""
    if verdict.get("error"):
        err_banner = (
            "<p style=\"background:#fdecea;border-right:4px solid #c0392b;padding:10px;\">"
            "⚠️ <b>חוות דעת המועצה (LLM) נכשלה בריצה הזו — הציון והסיכום למטה ריקים.</b><br>"
            f"<span dir='ltr' style='color:#555;font-size:12px;'>{str(verdict.get('error'))[:300]}</span><br>"
            "מספרי ה-scorecard והערוצים למטה תקינים ונמדדו כרגיל.</p>")
    return f"""<html dir="rtl" lang="he"><head><meta charset="utf-8"></head>
<body dir="rtl" style="font-family:Arial,Helvetica,sans-serif;font-size:14px;direction:rtl;text-align:right;color:#111;">
<div dir="rtl" style="direction:rtl;text-align:right;max-width:680px;">
<h2>🏛️ מועצת השיווק — דוח יומי {d}</h2>
{err_banner}
<p style="font-size:16px;"><b>ציון כולל: {scorecard['weighted']}/100</b> · scorecard עבר {scorecard['passed']}/{scorecard['total']} · <span style="color:#888">קריאת המועצה (LLM): {sc.get('overall','—')}/100</span></p>
<p style="background:#f6f6f6;padding:10px;border-right:3px solid #333;">{verdict.get('verdict_summary','—')}</p>

<h3>תוצאות לפי ערוץ ({cur['period_days']} ימים)</h3>
<table dir="rtl" border="0" cellpadding="6" style="border-collapse:collapse;width:100%;font-size:13px;">
<tr style="background:#222;color:#fff;"><th>ערוץ</th><th>פוסטים</th><th>חשיפות</th><th>Reach</th><th>תגובות</th><th>ER</th><th>ציון</th></tr>
{net_rows}</table>

<h3>Scorecard מול יעדים</h3>
<table dir="rtl" border="0" cellpadding="6" style="border-collapse:collapse;width:100%;font-size:13px;">
<tr style="background:#222;color:#fff;"><th>מדד</th><th>ערך</th><th>יעד</th><th></th></tr>
{sb_rows}</table>

<h3>הקשר (לא נספר בציון)</h3>
<table dir="rtl" border="0" cellpadding="6" style="border-collapse:collapse;width:100%;font-size:13px;color:#555;">
<tr style="background:#666;color:#fff;"><th>מדד</th><th>ערך</th><th>יעד</th><th></th></tr>
{ctx_rows}</table>

<h3>✅ מה עבד</h3><ul>{chips(verdict.get('what_worked',[]))}</ul>
<h3>❌ מה נכשל</h3><ul>{chips(verdict.get('what_failed',[]))}</ul>

<h3>⏱️ קצב פרסום שבועי שנקבע (נאכף אוטומטית)</h3>
<ul>{"".join(f"<li>{net}: עד {c['max_posts_per_week']}/שבוע <span style='color:#555'>— {c.get('reason','')}</span></li>" for net, c in (cadence or {}).items()) or '<li>—</li>'}</ul>

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
            f"Overall (weighted): {scorecard['weighted']}/100 · scorecard {scorecard['passed']}/{scorecard['total']} · LLM read {verdict.get('scores',{}).get('overall','—')}/100\n\n"
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

    leads = leads_source.count(30)
    cur["leads"] = leads
    cur["seo_geo"] = seo_geo_source.fetch()
    scorecard = build_scorecard(cur, prev, leads, cur.get("seo_geo"))

    if a.no_llm:
        verdict = {"verdict_summary": "(--no-llm) scorecard only", "scores": {}, "what_worked": [],
                   "what_failed": [], "auto_fixes": [], "recommendations": [],
                   "follower_growth_plan": [], "leads_actions": []}
    else:
        verdict = run_council(cur, prev, scorecard)
        if verdict.get("error"):
            print(f"council LLM error: {verdict['error']}", file=sys.stderr)

    applied, cadence = apply_auto_fixes(verdict, a.dry_run)
    html = render_html(cur, scorecard, verdict, applied, cadence)
    md = render_md(cur, scorecard, verdict, applied)

    if a.dry_run:
        print(md)
        print(f"\n[dry-run] would email + write report. auto-fixes that would apply: {len(applied)}")
        return 0

    METRICS_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    (METRICS_DIR / f"{_today()}.json").write_text(json.dumps(cur, ensure_ascii=False, indent=2))
    (REPORT_DIR / f"{_today()}.md").write_text(md)

    # Persist gated recommendations for the executor agent-team to pick up & advance.
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    (STATE_DIR / "council_recommendations.json").write_text(json.dumps({
        "updated_at": _today(),
        "scores": verdict.get("scores", {}),
        "recommendations": verdict.get("recommendations", []),
        "follower_growth_plan": verdict.get("follower_growth_plan", []),
        "leads_actions": verdict.get("leads_actions", []),
    }, ensure_ascii=False, indent=2))

    subj = (f"🏛️ מועצת השיווק — דוח יומי {_today()} · "
            + ("⚠️ חוות הדעת נכשלה" if verdict.get("error")
               else f"ציון {verdict.get('scores', {}).get('overall', '—')}/100"))
    try:
        from daily_email import send_graph_html
        ok, info = send_graph_html(subj, html)
        print(f"email: {ok} ({info})")
    except Exception as e:
        print(f"email failed: {e}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
