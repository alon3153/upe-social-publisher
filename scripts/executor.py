#!/usr/bin/env python3
"""
UPE Marketing Executor — a TEAM OF AGENTS that autonomously advances every
council recommendation, continuously, in the background.

Each council recommendation / follower-plan step / leads-action becomes an
"initiative" with its own agent. On every run, each open initiative's agent
(Claude API + live web_search) produces or IMPROVES a concrete, ready-to-use
deliverable (draft posts, SEO page copy, YouTube descriptions, lead-magnet
outline, keyword maps, FAQ schema, outreach scripts…) written to deliverables/.

IRON-RULE BOUNDARY (UPE): agents do everything UP TO the publish/send/spend line,
then PARK at "awaiting_approval". They never publish, send, or spend — Alon takes
the finished draft live himself. Content stays review-gated.

Cost is bounded: at most MAX_PER_RUN initiatives advanced per run (P0→P1→P2→leads
→follower priority), each capped at MAX_REVISIONS improvement cycles before it
parks until approved.

State:
  state/council_recommendations.json   (input, written by council.py)
  state/initiatives.json               (the team's backlog + status)
  deliverables/<id>.md                 (each agent's work product)

Always exits 0. Emails Alon a digest of what advanced.

Usage:
  python3 scripts/executor.py                 # one cycle + email
  python3 scripts/executor.py --dry-run       # no writes/email, print plan
  python3 scripts/executor.py --max 3         # advance at most 3 this run
"""
import os, sys, json, hmac, hashlib, argparse, datetime, urllib.request, urllib.error, urllib.parse
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "scripts"))

API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
MODEL = os.environ.get("EXECUTOR_MODEL") or "claude-sonnet-4-6"

# Email-approval gate (Supabase + signed token → executor-approve edge function).
SUPA_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SUPA_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
HMAC_SECRET = os.environ.get("APPROVAL_HMAC_SECRET", "")
APPROVE_FN = f"{SUPA_URL}/functions/v1/executor-approve" if SUPA_URL else ""


def _token(iid):
    return hmac.new(HMAC_SECRET.encode(), iid.encode(), hashlib.sha256).hexdigest()[:32]


def _supa(method, path, body=None, params=None):
    url = f"{SUPA_URL}/rest/v1/{path}"
    if params:
        url += "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, method=method,
        data=json.dumps(body).encode() if body is not None else None,
        headers={"apikey": SUPA_KEY, "Authorization": f"Bearer {SUPA_KEY}",
                 "Content-Type": "application/json", "Prefer": "resolution=merge-duplicates,return=minimal"})
    with urllib.request.urlopen(req, timeout=30) as r:
        raw = r.read().decode()
        return json.loads(raw) if raw else None


def supa_fetch_approved():
    """ids approved (or rejected) via the email link — so the team stops working them."""
    if not (SUPA_URL and SUPA_KEY):
        return set(), set()
    try:
        rows = _supa("GET", "executor_approvals",
                     params={"select": "id,status", "status": "in.(approved,rejected)"})
        appr = {r["id"] for r in rows if r.get("status") == "approved"}
        rej = {r["id"] for r in rows if r.get("status") == "rejected"}
        return appr, rej
    except Exception as e:
        sys.stderr.write(f"supa fetch approved: {e}\n")
        return set(), set()


def supa_register(it):
    """Ensure a pending approval row exists (keeps status if already set)."""
    if not (SUPA_URL and SUPA_KEY and HMAC_SECRET):
        return
    try:
        _supa("POST", "executor_approvals", body={
            "id": it["id"], "token": _token(it["id"]),
            "title": it.get("title", "")[:300], "priority": it.get("priority", "")})
    except Exception as e:
        sys.stderr.write(f"supa register {it['id']}: {e}\n")


def approve_links(iid):
    if not APPROVE_FN or not HMAC_SECRET:
        return None, None
    t = _token(iid)
    return (f"{APPROVE_FN}?id={iid}&token={t}&action=approve",
            f"{APPROVE_FN}?id={iid}&token={t}&action=reject")
STATE_DIR = ROOT / "state"
DELIV_DIR = ROOT / "deliverables"
RECS_PATH = STATE_DIR / "council_recommendations.json"
INIT_PATH = STATE_DIR / "initiatives.json"
APPROVALS_PATH = STATE_DIR / "approvals.json"

MAX_PER_RUN = int(os.environ.get("EXECUTOR_MAX_PER_RUN", "6"))
MAX_REVISIONS = int(os.environ.get("EXECUTOR_MAX_REVISIONS", "3"))
PRIORITY_ORDER = {"P0": 0, "P1": 1, "P2": 2, "leads": 3, "follower": 4}


def _today():
    return datetime.datetime.utcnow().strftime("%Y-%m-%d")


def _iid(text):
    return hashlib.sha1(text.strip().lower().encode()).hexdigest()[:8]


# ---------------------------------------------------------- backlog assembly ---
def load_initiatives():
    try:
        return json.loads(INIT_PATH.read_text())
    except (OSError, ValueError):
        return {}


def load_approvals():
    try:
        return set(json.loads(APPROVALS_PATH.read_text()).get("approved", []))
    except (OSError, ValueError):
        return set()


def sync_backlog(inits):
    """Merge the latest council recommendations into the initiative backlog.
    New recs → new initiatives; existing (same text) keep status+history."""
    try:
        recs = json.loads(RECS_PATH.read_text())
    except (OSError, ValueError):
        return inits, "no council_recommendations.json yet"
    incoming = []
    for r in recs.get("recommendations", []):
        incoming.append((r.get("action", ""), {"kind": "recommendation",
                         "priority": r.get("priority", "P2"), "channel": r.get("channel", ""),
                         "expected_impact": r.get("expected_impact", "")}))
    for s in recs.get("leads_actions", []):
        incoming.append((s, {"kind": "leads_action", "priority": "leads", "channel": "leads"}))
    for s in recs.get("follower_growth_plan", []):
        incoming.append((s, {"kind": "follower_plan", "priority": "follower", "channel": "growth"}))
    seen = set()
    for title, meta in incoming:
        if not title.strip():
            continue
        iid = _iid(title); seen.add(iid)
        if iid not in inits:
            inits[iid] = {"id": iid, "title": title, "status": "todo", "revisions": 0,
                          "history": [], "created": _today(), "updated": _today(), **meta}
        else:
            inits[iid].update({k: v for k, v in meta.items() if v})
            if inits[iid].get("status") == "archived":
                inits[iid]["status"] = "todo"
    # recs that dropped off the latest council output → archive (keep artifacts)
    for iid, it in inits.items():
        if iid not in seen and it.get("status") not in ("done", "archived"):
            it["status"] = "archived"; it["updated"] = _today()
    return inits, None


def pick_to_advance(inits, approved, limit):
    open_states = ("todo", "in_progress", "awaiting_approval")
    cands = []
    for it in inits.values():
        if it["id"] in approved:
            it["status"] = "approved"; continue
        if it.get("status") not in open_states:
            continue
        if it.get("status") == "awaiting_approval" and it.get("revisions", 0) >= MAX_REVISIONS:
            continue  # parked — waiting for Alon
        cands.append(it)
    cands.sort(key=lambda it: (PRIORITY_ORDER.get(it.get("priority"), 5),
                               it.get("revisions", 0), it.get("updated", "")))
    return cands[:limit]


# ------------------------------------------------------------------ the agent --
AGENT_PROMPT = """You are a specialist execution agent on UPE's marketing team. UPE = B2B corporate
event production & incentive travel (Israel + global). Audience: CMO/HR/CEO/event leads at companies
in Israel & Europe that run conferences/conventions/incentive trips needing a production company.
Canonical facts: founded 2010, 1,500+ events, 130+ destinations, 25,000+ participants.

YOUR INITIATIVE (advance this ONE thing as far as possible):
  kind: {kind} | channel: {channel} | priority: {priority}
  task: {title}
  expected_impact: {impact}

{prior}

Produce the CONCRETE, READY-TO-USE DELIVERABLE — not advice about it. Examples by kind:
- a social/LinkedIn recommendation → the actual post drafts (HE + EN), ready to schedule.
- an SEO/pillar-page rec → the actual page: H1, meta title+description, full sections, internal links, target keywords.
- a YouTube rec → the rewritten titles + first-2-lines descriptions with CTA + links, per existing video theme.
- a lead-magnet rec → the full outline + the opening section copy + the opt-in form copy.
- an outreach rec → the exact connection note + follow-up message templates (HE + EN).
- a schema/technical rec → the actual JSON-LD / code block, ready to paste.
- keyword mapping → the actual table: keyword → target URL → current position → intent.

Use web_search for current (2026) best practices and any facts you need. Hebrew where the audience is
Israeli; English/Spanish where European. RTL-correct Hebrew. Follow UPE iron rules: this is a DRAFT for
human approval — do not assume anything is published.

If you previously produced a draft (shown above), IMPROVE it — sharper, more specific, fix weaknesses.

OUTPUT FORMAT (important):
1. First, output the FULL deliverable as markdown — this is the work product Alon will use.
2. Then, on the very last lines, a single small ```json block with ONLY metadata:
```json
{{"summary": "one Hebrew sentence on what you produced/improved", "ready_for_approval": true, "open_questions": []}}
```
Do NOT put the deliverable inside the json. The json is metadata only and must be the last thing you output."""


def run_agent(it):
    prior = ""
    dpath = DELIV_DIR / f"{it['id']}.md"
    if dpath.exists():
        prior = "PRIOR DRAFT (improve it):\n-----\n" + dpath.read_text()[:6000] + "\n-----"
    prompt = AGENT_PROMPT.format(kind=it.get("kind"), channel=it.get("channel"),
                                 priority=it.get("priority"), title=it.get("title"),
                                 impact=it.get("expected_impact", "—"), prior=prior or "(no prior draft)")
    body = {"model": MODEL, "max_tokens": 16000,
            "tools": [{"type": "web_search_20250305", "name": "web_search", "max_uses": 4}],
            "messages": [{"role": "user", "content": prompt}]}
    req = urllib.request.Request("https://api.anthropic.com/v1/messages",
        data=json.dumps(body).encode(),
        headers={"x-api-key": API_KEY, "anthropic-version": "2023-06-01", "content-type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=600) as r:
            resp = json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        return {"error": f"anthropic {e.code}: {e.read().decode()[:200]}"}
    except Exception as e:
        return {"error": f"anthropic {e}"}
    text = "".join(b.get("text", "") for b in resp.get("content", []) if b.get("type") == "text")
    if not text.strip():
        return {"error": f"empty (stop={resp.get('stop_reason')})"}
    # The deliverable is the markdown body; a small json metadata block trails it.
    meta, deliverable = {}, text
    if "```json" in text:
        deliverable, _, rest = text.rpartition("```json")
        blob = rest.split("```", 1)[0]
        s, e = blob.find("{"), blob.rfind("}")
        if s != -1 and e != -1:
            try:
                meta = json.loads(blob[s:e + 1])
            except json.JSONDecodeError:
                meta = {}
    deliverable = deliverable.strip()
    if not deliverable:
        return {"error": f"no deliverable body (stop={resp.get('stop_reason')})"}
    return {"deliverable_md": deliverable,
            "summary": meta.get("summary", "(no summary)"),
            "ready_for_approval": bool(meta.get("ready_for_approval", False)),
            "open_questions": meta.get("open_questions", [])}


# ------------------------------------------------------------------- digest ----
def render_html(inits, advanced):
    d = _today()
    counts = {}
    for it in inits.values():
        counts[it.get("status", "?")] = counts.get(it.get("status", "?"), 0) + 1
    summary = " · ".join(f"{k}: {v}" for k, v in sorted(counts.items()))
    rows = ""
    for it, res in advanced:
        oq = res.get("open_questions") or []
        oqh = ("<br><span style='color:#b00;font-size:12px;'>❓ " + "; ".join(oq) + "</span>") if oq else ""
        ap, rj = approve_links(it["id"])
        if ap and res.get("ready_for_approval"):
            act = (f"<a href='{ap}' style='background:#2fa84f;color:#fff;text-decoration:none;"
                   f"padding:7px 12px;border-radius:7px;font-size:13px;font-weight:bold;display:inline-block;'>✅ אשר</a> "
                   f"<a href='{rj}' style='color:#b00;text-decoration:none;font-size:12px;'>דחה</a>")
        elif ap:
            act = "<span style='color:#999;font-size:12px;'>✍️ בתהליך</span>"
        else:
            act = ("✅ מוכן" if res.get("ready_for_approval") else "✍️ בתהליך")
        rows += (f"<tr><td><b>{it.get('priority')}</b></td><td>{it.get('title')[:90]}</td>"
                 f"<td>{res.get('summary','—')}{oqh}</td>"
                 f"<td>{act}</td>"
                 f"<td><code>deliverables/{it['id']}.md</code></td></tr>")
    return f"""<html dir="rtl" lang="he"><head><meta charset="utf-8"></head>
<body dir="rtl" style="font-family:Arial,Helvetica,sans-serif;font-size:14px;direction:rtl;text-align:right;color:#111;">
<div dir="rtl" style="direction:rtl;text-align:right;max-width:720px;">
<h2>🤖 צוות הביצוע — דוח {d}</h2>
<p>קידמתי <b>{len(advanced)}</b> יוזמות בסבב הזה. מצב מצטבר: {summary}</p>
<p style="background:#f6f6f6;padding:10px;border-right:3px solid #333;font-size:12px;">
כל התוצרים הם <b>טיוטות לאישורך</b> — שום דבר לא פורסם/נשלח. התוצרים נשמרו ב-<code>deliverables/</code> ברפו.</p>
<table dir="rtl" cellpadding="6" style="border-collapse:collapse;width:100%;font-size:13px;">
<tr style="background:#222;color:#fff;"><th>עדיפות</th><th>יוזמה</th><th>מה נעשה</th><th>מצב</th><th>קובץ</th></tr>
{rows or '<tr><td colspan=5>—</td></tr>'}</table>
<p style="color:#555;font-size:12px;">אישור בלחיצה על "✅ אשר" ליד כל יוזמה מוכנה — הצוות יפסיק לשפר אותה. (אפשר גם להוסיף id ל-<code>state/approvals.json</code>.)</p>
<hr><p style="color:#888;font-size:11px;">UPE Marketing Executor · אוטומטי · {d}</p>
</div></body></html>"""


# --------------------------------------------------------------------- main ----
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--max", type=int, default=MAX_PER_RUN)
    a = ap.parse_args()
    if not API_KEY and not a.dry_run:
        print("ANTHROPIC_API_KEY not set", file=sys.stderr); return 0

    inits = load_initiatives()
    inits, warn = sync_backlog(inits)
    if warn:
        print(warn, file=sys.stderr)
    file_approved = load_approvals()
    supa_approved, supa_rejected = supa_fetch_approved()
    approved = file_approved | supa_approved
    for rid in supa_rejected:  # rejected via email → stop working it
        if rid in inits and inits[rid].get("status") not in ("done", "archived"):
            inits[rid]["status"] = "rejected"; inits[rid]["updated"] = _today()
    todo = pick_to_advance(inits, approved, a.max)
    print(f"backlog: {len(inits)} initiatives | advancing {len(todo)} this run "
          f"| approved {len(approved)} | rejected {len(supa_rejected)}")

    if a.dry_run:
        for it in todo:
            print(f"  [{it.get('priority')}] {it['id']} {it.get('title')[:70]} (rev {it.get('revisions',0)})")
        return 0

    DELIV_DIR.mkdir(parents=True, exist_ok=True); STATE_DIR.mkdir(parents=True, exist_ok=True)
    advanced = []
    for it in todo:
        res = run_agent(it)
        if res.get("error"):
            print(f"  ✗ {it['id']}: {res['error']}", file=sys.stderr)
            it["history"].append({"date": _today(), "error": res["error"]})
            continue
        (DELIV_DIR / f"{it['id']}.md").write_text(
            f"# {it.get('title')}\n\n_{it.get('priority')} · {it.get('channel')} · updated {_today()}_\n\n"
            + res.get("deliverable_md", ""))
        it["revisions"] = it.get("revisions", 0) + 1
        it["status"] = "awaiting_approval" if res.get("ready_for_approval") else "in_progress"
        it["updated"] = _today()
        it["history"].append({"date": _today(), "summary": res.get("summary", ""),
                              "ready": res.get("ready_for_approval", False)})
        advanced.append((it, res))
        print(f"  ✓ {it['id']} [{it.get('status')}] {res.get('summary','')[:60]}")

    INIT_PATH.write_text(json.dumps(inits, ensure_ascii=False, indent=2))

    for it, _ in advanced:  # ensure an approval row exists so the email links resolve
        supa_register(it)

    if advanced:
        try:
            from daily_email import send_graph_html
            ok, info = send_graph_html(f"🤖 צוות הביצוע — {_today()} · {len(advanced)} יוזמות קודמו",
                                       render_html(inits, advanced))
            print(f"email: {ok} ({info})")
        except Exception as e:
            print(f"email failed: {e}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
