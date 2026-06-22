#!/usr/bin/env python3
"""
UPE Video Script Generator — autonomous Sofia Short scripts via the Claude API.

Generates ready-to-render short-form video scripts (hook + ~30s VO in HE & EN +
on-screen captions + viral posting caption + scene note) in UPE voice, into a
queue that the Sofia/Higgsfield render step consumes. Renders then publish as
DRAFTS to all networks for Alon's review (locked rule: every video reviewed).

Usage:
  python3 scripts/generate_video_scripts.py --count 3
  python3 scripts/generate_video_scripts.py --count 1 --dry-run
"""
import os, re, sys, json, glob, argparse, urllib.request, urllib.error

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "content", "video_scripts")
API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
MODEL = os.environ.get("GEN_MODEL", "claude-sonnet-4-6")

BRAND = """Uproduction Events (UPE) — B2B corporate event production & incentive travel.
"from business to pleasure". 2010 / 16 years / 1,500+ events / 130+ destinations /
25,000+ participants. Presenter: Sofia (UPE's recurring AI host) — confident, warm,
insider expert sharing "Insider Secrets" of event production to HR/marketing/sales leaders."""

TOPICS = [
    "an insider event-production secret most companies get wrong",
    "how to pick a destination that wows without blowing the budget",
    "the hidden costs of planning a corporate event in-house",
    "what makes an incentive trip actually drive results",
    "a behind-the-scenes moment from producing a 600-person event",
    "the one detail that separates a forgettable gala from a viral one",
    "why timing the date right changes everything for your event",
    "how to brief an event producer so you get exactly what you want",
]

RULES = """VIDEO RULES:
- 25-40 seconds of speech. Hook in the FIRST sentence (a bold claim, question, or pattern-interrupt).
- Spoken, punchy, one idea. End with a soft CTA ("DM us / comment / link in bio").
- Use only canonical facts (2010 / 16y / 1,500+ events / 130+ destinations / 25,000+ participants); never invent stats or name the year an event happened.
- Hebrew = natural spoken Hebrew; English = crisp and conversational.
- 3-5 short on-screen caption lines (key phrases, not the full script).
- post_caption: a viral, scroll-stopping caption for the feed with 4-6 relevant hashtags (emojis OK at line end).
- scene: one sentence describing the visual setting for Sofia (real location vibe, no LED screens, no AI-look)."""

SCHEMA = """Return ONLY a JSON object (no markdown):
{
  "topic": "<short topic>",
  "hook": "<the first spoken line>",
  "script_he": "<full ~30s spoken script in Hebrew>",
  "script_en": "<full ~30s spoken script in English>",
  "captions": ["<on-screen line>", "..."],
  "post_caption": "<viral feed caption with hashtags>",
  "scene": "<visual setting for Sofia>"
}"""


def next_idx():
    n = [int(m.group(1)) for f in glob.glob(os.path.join(OUT, "script-*.json"))
         if (m := re.search(r"script-(\d+)", os.path.basename(f)))]
    return (max(n) + 1) if n else 1


def call_claude(topic):
    prompt = f"""{BRAND}

{RULES}

Write a Sofia short-form video script about: {topic}.

{SCHEMA}"""
    body = json.dumps({"model": MODEL, "max_tokens": 2000,
                       "messages": [{"role": "user", "content": prompt}]}).encode()
    req = urllib.request.Request("https://api.anthropic.com/v1/messages", data=body, headers={
        "x-api-key": API_KEY, "anthropic-version": "2023-06-01", "content-type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as r:
        resp = json.loads(r.read().decode())
    text = "".join(b.get("text", "") for b in resp.get("content", [])).strip()
    if text.startswith("```"):
        text = re.sub(r"^```(json)?|```$", "", text, flags=re.MULTILINE).strip()
    return json.loads(text)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--count", type=int, default=3)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    if not API_KEY:
        print("ANTHROPIC_API_KEY not set"); return 1
    os.makedirs(OUT, exist_ok=True)
    start = next_idx()
    done = 0
    for i in range(a.count):
        idx = start + i
        topic = TOPICS[idx % len(TOPICS)]
        try:
            data = call_claude(topic)
            data["status"] = "pending_render"
            data["idx"] = idx
            if a.dry_run:
                print(f"  [dry-run] script-{idx}: {data.get('hook','')[:60]}")
            else:
                with open(os.path.join(OUT, f"script-{idx}.json"), "w") as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                print(f"✅ script-{idx} — \"{data.get('hook','')[:55]}\"")
            done += 1
        except Exception as e:
            print(f"❌ script-{idx}: {e}")
    print(f"\nGenerated {done}/{a.count} video scripts (start={start}).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
