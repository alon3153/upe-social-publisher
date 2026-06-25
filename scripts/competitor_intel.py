#!/usr/bin/env python3
"""
UPE Competitor & Viral Intelligence — research what's working RIGHT NOW in the
corporate-events / incentive-travel space (competitors + viral angles) via the
Claude API web_search tool, then generate UPE-adapted posts from those proven
angles straight into the content bank.

"Copy what's viral, adapt it to UPE" — but original wording, UPE voice, UPE facts.
Generated posts enter the same human approval gate at publish time.

Usage:
  python3 scripts/competitor_intel.py --count 3
  python3 scripts/competitor_intel.py --count 3 --dry-run
"""
import os, re, sys, json, time, argparse, urllib.request, urllib.error

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
from generate_posts import (write_day, next_day, BRAND, RULES, SCHEMA_HINT,
                            API_KEY, MODEL)

COMBINED_PROMPT = """Search the web for what is working RIGHT NOW (2026) in B2B corporate-events,
incentive-travel and MICE marketing on LinkedIn, Instagram and TikTok — the angles, hooks and
post formats that top event agencies and competitors use to get high engagement, plus any viral
or fast-rising content themes.

Then ADAPT the strongest {n} angles into ORIGINAL Uproduction Events social posts (reuse the
psychological angle and format only — never copy wording). For each, write Facebook, Instagram
and LinkedIn copy in English (en), Spanish (es) and Hebrew (he).

{brand}

{rules}

Return ONLY a JSON array (no other text) of {n} objects, each:
{{"angle_used": "<the viral angle you adapted>", "theme": "<short English theme>",
  "image_prompt": "<one photographic sentence>",
  "en": {{"facebook": "...", "instagram": "...", "linkedin": "..."}},
  "es": {{"facebook": "...", "instagram": "...", "linkedin": "..."}},
  "he": {{"facebook": "...", "instagram": "...", "linkedin": "..."}}}}"""


def _api(messages, tools=None, max_tokens=4096):
    payload = {"model": MODEL, "max_tokens": max_tokens, "messages": messages}
    if tools:
        payload["tools"] = tools
    data = json.dumps(payload).encode()
    headers = {"x-api-key": API_KEY, "anthropic-version": "2023-06-01", "content-type": "application/json"}
    for attempt in range(5):
        try:
            req = urllib.request.Request("https://api.anthropic.com/v1/messages", data=data, headers=headers)
            with urllib.request.urlopen(req, timeout=180) as r:
                return json.loads(r.read().decode())
        except urllib.error.HTTPError as e:
            if e.code in (429, 529) and attempt < 4:
                wait = 8 * (attempt + 1)
                print(f"  rate-limited ({e.code}), retry in {wait}s...")
                time.sleep(wait)
                continue
            raise


def _extract_json_array(text):
    """Pull a JSON array out of model output, tolerating ```json fences and prose."""
    if not text:
        return None
    # strip code fences if present
    fenced = re.search(r"```(?:json)?\s*(\[.*?\])\s*```", text, re.DOTALL)
    candidate = fenced.group(1) if fenced else None
    if candidate is None:
        m = re.search(r"\[\s*\{.*\}\s*\]", text, re.DOTALL)
        candidate = m.group(0) if m else None
    if candidate is None:
        return None
    try:
        return json.loads(candidate)
    except json.JSONDecodeError:
        return None


REFORMAT_PROMPT = """Below is research about viral B2B event-marketing angles. Convert it into
ORIGINAL Uproduction Events social posts — reuse the psychological angle/format only, original wording, UPE voice.

{brand}

{rules}

RESEARCH:
{research}

Return ONLY a JSON array (no other text, no markdown fences) of {n} objects, each:
{{"angle_used": "<the viral angle>", "theme": "<short English theme>",
  "image_prompt": "<one photographic sentence>",
  "en": {{"facebook": "...", "instagram": "...", "linkedin": "..."}},
  "es": {{"facebook": "...", "instagram": "...", "linkedin": "..."}},
  "he": {{"facebook": "...", "instagram": "...", "linkedin": "..."}}}}"""


def research_and_adapt(n):
    """web-search viral angles AND return n adapted UPE posts.
    Step 1 lets the model research+narrate (web_search). If it doesn't emit clean JSON
    (common when the tool call makes it answer conversationally), Step 2 is a tool-less
    reformat call that reliably returns JSON-only."""
    resp = _api(
        [{"role": "user", "content": COMBINED_PROMPT.format(n=n, brand=BRAND, rules=RULES)}],
        tools=[{"type": "web_search_20250305", "name": "web_search", "max_uses": 3}],
        max_tokens=12000)
    text = "".join(b.get("text", "") for b in resp.get("content", []) if b.get("type") == "text")

    posts = _extract_json_array(text)
    if posts:
        return posts

    # Step 2 — reformat the research prose into JSON-only (no tools = no narration)
    print("  step-1 returned prose, not JSON — running JSON reformat call...")
    resp2 = _api(
        [{"role": "user", "content": REFORMAT_PROMPT.format(
            brand=BRAND, rules=RULES, research=text[:12000], n=n)}],
        max_tokens=12000)
    text2 = "".join(b.get("text", "") for b in resp2.get("content", []) if b.get("type") == "text")
    posts = _extract_json_array(text2)
    if posts:
        return posts

    raise RuntimeError(f"no posts JSON after reformat: {text2[:300] or text[:300]}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--count", type=int, default=3)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    if not API_KEY:
        print("ANTHROPIC_API_KEY not set"); return 1

    print(f"researching + adapting {a.count} viral angles (single web-search call)...")
    posts = research_and_adapt(a.count)
    start = next_day()
    done = 0
    for i, data in enumerate(posts[:a.count]):
        day = start + i
        try:
            write_day(day, "viral_adapted", data, a.dry_run)
            print(f"✅ day {day} (viral_adapted) — {data.get('theme','')[:45]} ← {data.get('angle_used','')[:40]}")
            done += 1
        except Exception as e:
            print(f"❌ day {day}: {e}")
    print(f"\nGenerated {done}/{len(posts)} viral-adapted days (start={start}).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
