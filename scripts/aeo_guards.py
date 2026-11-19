"""Hard content guards: canonical facts only, no event dates."""
import re
from pathlib import Path

CANON = {"founded": 2010, "years": 16, "events": "1,500+", "destinations": "130+", "participants": "25K+"}

FORBIDDEN_TOKENS = ["200+", "2000", "2,000", "120+", "800+", "27 year", "27 שנ"]

# event/case wording near a 4-digit year 2011-2024.
# 2010 is the company's FOUNDING year (canonical fact) — allowed anywhere, so it is
# excluded from the year range to avoid false positives on tenure phrasing like
# "events since 2010" / "מאז 2010".
_EVENT_WORDS = r"(?:event|conference|convention|produced|case study|gala|אירוע|כנס|הפקנו|הפיק|מקרה בוחן)"
_YEAR = r"(?:20(?:1[1-9]|2[0-4]))"
_EVENT_YEAR_RE = re.compile(
    rf"(?:{_EVENT_WORDS}[^.\n]{{0,40}}{_YEAR})|(?:{_YEAR}[^.\n]{{0,40}}{_EVENT_WORDS})",
    re.IGNORECASE,
)


def check_content(text):
    violations = []
    low = text.lower()
    for tok in FORBIDDEN_TOKENS:
        if tok.lower() in low:
            violations.append(f"forbidden stat token: {tok!r}")
    # event-year adjacency (a specific event's year), 2011-2024
    if _EVENT_YEAR_RE.search(text):
        violations.append("event year adjacency (a year 2011-2024 next to event/case wording)")
    return violations


# Pages that name a competitor carry brand/legal risk and get a founder veto
# window instead of straight auto-merge (council decision 05.07).
COMPETITOR_NAMES = [
    "george p. johnson", "jack morton", "freeman", "encore", "uniplan", "mci group",
    "momentum worldwide", "sparks", "czarnowski", "bcd meetings", "maritz",
    "ita group", "bi worldwide", "one10", "creative group", "brightspot", "cwt",
]


def names_competitor(text):
    low = (text or "").lower()
    return [c for c in COMPETITOR_NAMES if c in low]


# Mirrors the blocking names in uproduction-astro/scripts/check-competitor-names.mjs.
# The destination's actual guard is also run before any push, so policy drift fails
# locally rather than creating an unmergeable weekly PR. Cvent remains warning-only.
_DESTINATION_ANY_CASE = (
    "george p. johnson", "jack morton", "bcd meetings", "mci group",
    "momentum worldwide", "czarnowski", "bi worldwide", "ita group",
    "one10", "brightspot", "uniplan", "maritz", "opus agency", "smyle",
    "production resource group", "dorier", "american express gbt",
)
_DESTINATION_PROPER_NOUN = ("Freeman", "Encore", "Sparks", "GPJ", "CWT")


def destination_violations(text):
    """Reject content the destination website cannot merge, including metadata."""
    hits = [name for name in _DESTINATION_ANY_CASE
            if re.search(r"\b" + re.escape(name) + r"\b", text or "", re.I)]
    hits += [name for name in _DESTINATION_PROPER_NOUN
             if re.search(r"\b" + re.escape(name) + r"\b", text or "")]
    return ["destination competitor guard: " + name for name in hits]


# --- comparative ("roster") pages -------------------------------------------------
#
# Legacy neutrality validator (30.08.2026). Passing these structural checks
# does NOT override destination_violations or the website publish preflight.
#
# Why the policy moved. Every third-party page answer engines cite for "who are the top
# corporate event production companies" is a roster naming 8-12 real firms — gogather,
# corporateoptics, centric.events and teamout all rank themselves #1 inside their own
# listicle. None of them accepts submissions. A page that describes only UPE cannot be
# cited for a "who are the top" query at all, so a blanket ban on naming competitors
# banned the single mechanism in evidence.
#
# What does NOT move is the legal reasoning. Naming a competitor is lawful; naming one
# and attaching an unverifiable weakness is what creates exposure under the Israeli
# Commercial Torts Law 5759-1999 and, for EN/ES pages, Directive 2006/114/EC. A machine
# cannot judge whether a claim is verifiable, so it enforces the structure instead:
# disclosed methodology, neutral descriptors, no disparagement adjacent to a name, and no
# self-superlative. A page that names competitors without meeting these is rejected and
# regenerated — never quietly published.

_METHODOLOGY_MARKERS = ["methodology", "how this list was", "selection criteria",
                        "מתודולוגיה", "איך נבחרה הרשימה", "קריטריונים לבחירה",
                        "metodología", "cómo se elaboró", "criterios de selección"]

# Negative claims that turn a neutral mention into a disparagement claim.
_DISPARAGE = [
    r"worse", r"worst", r"inferior", r"overpriced", r"too expensive", r"impersonal",
    r"unreliable", r"poor (?:service|quality)", r"fail(?:s|ed)? to", r"can'?t deliver",
    r"cannot deliver", r"bloated", r"bureaucratic", r"slow(?:er)? to respond",
    r"גרוע", r"נחות", r"יקר מדי", r"לא אמין", r"מסורבל", r"לא מספק", r"כושל",
    r"peor", r"inferior", r"demasiado caro", r"poco fiable", r"burocrátic",
]

# Superlatives about UPE itself. "The best" is exactly the unverifiable claim that makes
# a roster page look like an ad, and engines discount pages that read as ads.
_SELF_SUPERLATIVE = [
    r"(?:we are|uproduction (?:events )?is) (?:the )?(?:best|#1|number one|leading)\b",
    r"\bthe best (?:corporate )?event production company\b",
    r"החברה הטובה ביותר", r"מספר 1 בעולם", r"המובילה בעולם",
    r"la mejor (?:empresa|productora)",
]

_PROXIMITY = 180  # chars either side of a competitor name


def _windows(low, name):
    start = 0
    while True:
        i = low.find(name, start)
        if i < 0:
            return
        yield low[max(0, i - _PROXIMITY): i + len(name) + _PROXIMITY]
        start = i + len(name)


def comparative_violations(text, competitors=None):
    """Structural checks for a page that names competitors. Empty list == publishable."""
    low = (text or "").lower()
    names = competitors if competitors is not None else names_competitor(text)
    if not names:
        return []
    violations = []
    if not any(m in low for m in _METHODOLOGY_MARKERS):
        violations.append("names competitors without a disclosed methodology section")
    for name in names:
        for window in _windows(low, name):
            for pat in _DISPARAGE:
                if re.search(pat, window, re.IGNORECASE):
                    violations.append(f"disparaging claim near {name!r}: /{pat}/")
                    break
    for pat in _SELF_SUPERLATIVE:
        if re.search(pat, low, re.IGNORECASE):
            violations.append(f"unverifiable self-superlative: /{pat}/")
    # dedup, keep order
    seen, out = set(), []
    for v in violations:
        if v not in seen:
            seen.add(v)
            out.append(v)
    return out


# --- sourcing -------------------------------------------------------------------
#
# 175 of 278 live blog files carry a percentage with no source on the line, and 7 EN
# articles attribute events-industry claims to arxiv.org (a physics/CS preprint server).
# Two earlier commits scrubbed the output; neither touched the generator, so the next two
# waves reintroduced it. Guarding the generator is what makes the fix hold.

_STAT_RE = re.compile(r"\b\d{1,3}(?:\.\d+)?\s?%")
_LINK_RE = re.compile(r"\[[^\]]+\]\(https?://[^)]+\)")
# domains that cannot support a claim about the corporate-events industry
_BOGUS_SOURCES = ["arxiv.org", "example.com", "lorem", "wikipedia.org/wiki/Special:"]


def sourcing_violations(text):
    violations = []
    for line in (text or "").splitlines():
        if _STAT_RE.search(line) and not _LINK_RE.search(line):
            violations.append(f"uncited statistic: {line.strip()[:90]!r}")
    low = (text or "").lower()
    for dom in _BOGUS_SOURCES:
        if dom in low:
            violations.append(f"non-authoritative source for this industry: {dom}")
    seen, out = set(), []
    for v in violations:
        if v not in seen:
            seen.add(v)
            out.append(v)
    return out


# --- duplicate-topic check (mirrors uproduction-astro scripts/check-duplicate-topics.mjs) ---
# The astro CI guard rejects a PR that adds a page the site already has. The loop used
# to find that out only after opening the PR, so the intent never got a live URL, was
# re-briefed every week, and the same duplicate was regenerated and blocked again
# (PR #275, 18.11.2026). Checking here lets the loop point the intent at the live page.
_DUP_PUNCT = re.compile(r"[-_/|,.:;!?()\[\]\"'׳״“”–—]")
_DUP_THRESHOLD, _DUP_MIN_SIG, _DUP_MIN_SHARED = 0.75, 3, 2
_FAQ_PREFIX = re.compile(r"^(faq-|preguntas-frecuentes-)")


def _dup_stopwords(repo):
    """Read STOP from the site's own guard so the two checks never drift apart."""
    src = (Path(repo) / "scripts/check-duplicate-topics.mjs").read_text(encoding="utf-8")
    block = re.search(r"const STOP = new Set\(\[(.*?)\]\);", src, re.S).group(1)
    block = re.sub(r"//[^\n]*", "", block)
    return set(re.findall(r"'([^']*)'", block))


def _dup_tokens(text, stop):
    text = _DUP_PUNCT.sub(" ", (text or "").lower().split("|")[0])
    return {w for w in text.split() if len(w) > 1 and w not in stop and not w.isdigit()}


def _fm(src, name):
    m = re.search(rf"^{name}:\s*[\"']?(.*?)[\"']?\s*$", src, re.M)
    return m.group(1) if m else ""


def existing_topic_page(page, repo):
    """Canonical URL of a live site page the astro guard would call a duplicate, else None."""
    if not (Path(repo) / "scripts/check-duplicate-topics.mjs").is_file():
        return None
    stop = _dup_stopwords(repo)
    fm = page.get("frontmatter") or {}
    slug = fm.get("urlSlug") or page.get("slug", "")
    lang = fm.get("language") or page.get("lang") or "he"
    sig = _dup_tokens(slug, stop) | _dup_tokens(fm.get("h1") or fm.get("title"), stop)
    if len(sig) < _DUP_MIN_SIG:
        return None
    for path in sorted((Path(repo) / "src/content").rglob("*.md")):
        src = path.read_text(encoding="utf-8")
        other = _fm(src, "urlSlug")
        if (not other or other == slug or _fm(src, "migrationStatus") == "draft"
                or _fm(src, "canonicalOverride") or (_fm(src, "language") or "he") != lang
                or bool(_FAQ_PREFIX.match(slug)) or bool(_FAQ_PREFIX.match(other))):
            continue
        osig = _dup_tokens(other, stop) | _dup_tokens(_fm(src, "h1") or _fm(src, "title"), stop)
        if len(osig) < _DUP_MIN_SIG:
            continue
        shared = len(sig & osig)
        if shared >= _DUP_MIN_SHARED and shared / min(len(sig), len(osig)) >= _DUP_THRESHOLD:
            return _fm(src, "canonical") or f"https://upe.co.il/{other}/"
    return None
