#!/usr/bin/env python3
"""
UPE Bank Generator — auto-replenish the social content bank with the Claude API.

Generates the next N days of posts (Facebook + Instagram + LinkedIn, in EN/ES/HE)
in UPE's brand voice, matching the existing content/days/ schema, and writes them
to the bank. Posts still go through the human approval gate at publish time
(daily_email.py), so this never auto-publishes — it only keeps the bank full.

Usage:
  python3 scripts/generate_posts.py --count 14          # next 14 days
  python3 scripts/generate_posts.py --count 7 --start 131
  python3 scripts/generate_posts.py --count 2 --dry-run # preview, don't write
"""
import os, re, sys, json, glob, argparse, urllib.request, urllib.error

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DAYS_DIR = os.path.join(ROOT, "content", "days")
DIRECTIVES_PATH = os.path.join(ROOT, "state", "council_directives.json")
API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
MODEL = os.environ.get("GEN_MODEL", "claude-sonnet-4-6")


def council_steering():
    """Inject the daily Marketing Council's latest safe directives so newly
    generated content reflects the strategy the council auto-decided. Returns a
    prompt block, or '' if no directives file exists. Closes the audit→improve loop."""
    try:
        d = json.load(open(DIRECTIVES_PATH))
    except (OSError, ValueError):
        return ""
    lines = []
    for f in d.get("directives", []):
        ch = f.get("channel", "")
        lines.append(f"- ({ch}) {f.get('action','')}: {f.get('detail','')}".strip())
    leads = d.get("leads_actions", [])[:3]
    block = ""
    if lines:
        block += ("\nCOUNCIL STEERING (auto-decided " + str(d.get("updated_at", "")) +
                  " — follow these when shaping angle/CTA/format):\n" + "\n".join(lines[:8]))
    if leads:
        block += "\nLEAD-GEN FOCUS (bias posts toward driving these):\n" + "\n".join(f"- {x}" for x in leads)
    return block

BRAND = """Uproduction Events (UPE) — B2B corporate event production & incentive travel.
Tagline: "from business to pleasure". Founded 2010 (16 years). 1,500+ events delivered,
130+ destinations, 25,000+ participants. Israel-based, global operations. Clients are
HR/marketing/sales leaders at companies running conferences, conventions, product
launches, gala dinners, incentive trips and team retreats. Brand voice: confident,
specific, results-driven, warm but not salesy; speaks peer-to-peer to senior decision
makers; concrete numbers over adjectives."""

# Per-network length/style; profiles must stay consistent with the existing bank.
PROFILES = {
    "facebook":  "Uproduction Events (Page)",
    "instagram": "@uproductionevents",
    "linkedin":  "Uproduction Events (Company Page)",
}
CATEGORIES = [
    "destination", "cta_lead", "testimonial", "behind_the_scenes", "expert_tip",
    "social_proof", "incentive_travel", "problem_solution", "seasonal_hook", "founder_insight",
]
# Real-archive imagery only. Client feedback: AI images made UPE look like it has
# no real events (see PR #30). New posts reuse a vetted real photo from the archive
# pool instead of generating an AI image. Provenance stays generic (no invented
# place label) and image_source is tagged 'real_archive_reused' for auditability.
IMAGES_DIR = os.path.join(ROOT, "content", "images")
REAL_CREDIT = {
    "en": "📷 A real frame from a Uproduction production",
    "es": "📷 Un fotograma real de una producción de Uproduction",
    "he": "📷 פריים אמיתי מהפקה של Uproduction",
}


def real_photo_pool():
    """Vetted real archive photos already committed to the repo (the *_real.jpg set
    from the real-photo campaign). Excludes legacy AI 'day{N}_*_branded.png'."""
    pool = sorted(
        f"content/images/{os.path.basename(p)}"
        for p in glob.glob(os.path.join(IMAGES_DIR, "*_real.jpg"))
    )
    return pool


def pick_real_photo(day, pool):
    """Deterministic round-robin so assignment is stable across re-runs and spreads
    across the pool rather than clustering."""
    return pool[day % len(pool)] if pool else ""


RULES = """HARD RULES:
- NEVER state the year/date an event took place; events read timeless.
- Use only the canonical facts above (2010 / 16 years / 1,500+ events / 130+ destinations / 25,000+ participants). Never invent other numbers.
- Hebrew (he) must be natural spoken Hebrew, not literary; correct for RTL; keep emojis at END of a line, never start.
- Each network text is self-contained with a clear hook + soft CTA (DM/comment). Instagram may add hashtags; LinkedIn peer-to-peer; Facebook conversational.
- Do NOT reuse wording across days; vary angle, hook and structure."""

SCHEMA_HINT = """Return ONLY a JSON object (no markdown) with this exact shape:
{
  "theme": "<short English theme title>",
  "en": {"facebook": "<text>", "instagram": "<text>", "linkedin": "<text>"},
  "es": {"facebook": "<text>", "instagram": "<text>", "linkedin": "<text>"},
  "he": {"facebook": "<text>", "instagram": "<text>", "linkedin": "<text>"}
}"""


def next_day():
    nums = []
    for f in glob.glob(os.path.join(DAYS_DIR, "*day*.json")):
        m = re.search(r"day(\d+)", os.path.basename(f))
        if m:
            nums.append(int(m.group(1)))
    return (max(nums) + 1) if nums else 1


def call_claude(category, day):
    prompt = f"""{BRAND}

{RULES}
{council_steering()}

Write a single corporate-social post for day {day}, category "{category}", for Uproduction Events.
Produce Facebook, Instagram and LinkedIn copy in THREE languages: English (en), Spanish (es), Hebrew (he).
Each network/language version conveys the same idea, adapted to that platform and language (not literal translations).

{SCHEMA_HINT}"""
    body = json.dumps({
        "model": MODEL, "max_tokens": 4096,
        "messages": [{"role": "user", "content": prompt}],
    }).encode()
    req = urllib.request.Request("https://api.anthropic.com/v1/messages", data=body, headers={
        "x-api-key": API_KEY, "anthropic-version": "2023-06-01", "content-type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as r:
        resp = json.loads(r.read().decode())
    text = "".join(b.get("text", "") for b in resp.get("content", []))
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(json)?|```$", "", text, flags=re.MULTILINE).strip()
    return json.loads(text)


def write_day(day, category, data, dry_run, pool=None):
    if pool is None:
        pool = real_photo_pool()
    image_file = pick_real_photo(day, pool)
    written = []
    for lang in ("en", "es", "he"):
        block = data.get(lang, {})
        doc = {
            "day": day, "category": category, "language": lang, "date": "", "weekday": "",
            "theme": data.get("theme", ""),
            "linkedin":  {"profile": PROFILES["linkedin"],  "text": block.get("linkedin", "")},
            "instagram": {"profile": PROFILES["instagram"], "text": block.get("instagram", "")},
            "facebook":  {"profile": PROFILES["facebook"],  "text": block.get("facebook", "")},
            "image_file": image_file, "image_source": "real_archive_reused",
            "image_credit": REAL_CREDIT[lang],
            "brand": {"colors": ["#1C1C1C", "#FBCE0A"], "font": "Comfortaa",
                      "logo": "uproduction_official_logo.png"},
        }
        path = os.path.join(DAYS_DIR, f"day{day}-{category}-{lang}.json")
        if dry_run:
            print(f"  [dry-run] {os.path.basename(path)} ({len(doc['facebook']['text'])} chars fb)")
        else:
            with open(path, "w") as f:
                json.dump(doc, f, ensure_ascii=False, indent=2)
            written.append(os.path.basename(path))
    return written


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--count", type=int, default=7)
    ap.add_argument("--start", type=int, default=None)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    if not API_KEY:
        print("ANTHROPIC_API_KEY not set"); return 1

    start = a.start or next_day()
    pool = real_photo_pool()
    if not pool:
        print("WARN: no *_real.jpg archive photos found — new posts would have no image");
    total = 0
    for i in range(a.count):
        day = start + i
        category = CATEGORIES[day % len(CATEGORIES)]
        try:
            data = call_claude(category, day)
            files = write_day(day, category, data, a.dry_run, pool)
            print(f"✅ day {day} ({category}) — theme: {data.get('theme','')[:50]} "
                  f"| 📷 {os.path.basename(pick_real_photo(day, pool))}")
            total += 1
        except urllib.error.HTTPError as e:
            print(f"❌ day {day}: HTTP {e.code} {e.read().decode()[:200]}")
        except Exception as e:
            print(f"❌ day {day}: {e}")
    print(f"\nGenerated {total}/{a.count} days (start={start}, model={MODEL})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
