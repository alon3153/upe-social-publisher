"""Hard content guards: canonical facts only, no event dates."""
import re

# Canon: operating since 2010 (incorporated 23.07.2012). Not "founded in 2010" and
# never a running age ("16 years") that goes stale every year.
CANON = {"operating_since": 2010, "events": "1,500+", "destinations": "130+", "participants": "25K+"}

# Non-canonical company-age / founding phrasing. Ported from uproduction-astro
# scripts/company-age-rule.mjs + founded-2010-rule.mjs (companyAgeRule, spelledClaimRule,
# foundingPhrasingRule, founded2010Rule) and widened with the variants AEO found on
# 18.10.2026 (maqaf/en-dash, "מאז הקמתה", "est.", "founded back in", "16-year").
# On the site these are warnings; for generated pages every one of them BLOCKS the run.
# The site script itself is also run before `gh pr create` (aeo_publish.py).
_HE = "\u0590-\u05FF"
_DASH = "[-\u05BE\u2013\u2014]"   # hyphen, Hebrew maqaf, en dash, em dash
_IN_2010 = rf"(?:בשנת\s+|ב\s*{_DASH}?\s*)2010"
_HE_END = rf"(?![{_HE}])"
CANON_VIOLATION_PATTERNS = [
    # rolling age: "16 years", "16-year", "16+ years", "16 años", "16 שנים/שנות/שנה" (not "16 שניות")
    (re.compile(rf"\b16\s*\+?\s*{_DASH}?\s*(?:years?|yrs|años)\b|16\s*\+?\s*שנ(?:ה|ים|ות)(?![{_HE}])", re.I),
     "'16 years' (canon: operating since 2010)"),
    (re.compile(r"\bsixteen[\s-]+years?\b|\bdiecis[eé]is\s+años\b|שש[\s-]עשרה\s+שנ(?:ה|ים|ות)", re.I),
     "spelled-out 'sixteen years' (canon: operating since 2010)"),
    (re.compile(r"\b\d{1,2}\+?\s*years?\s+of\s+(?:operation|operating|experience|activity)\b", re.I),
     "company age in years (canon: operating since 2010)"),
    (re.compile(rf"\d{{1,2}}\+?\s*שנות\s+(?:ניסיון|פעילות)"), "company age in years (canon: פועלת מאז 2010)"),
    # founding: founded / founded back in / established / est. / incorporated + 2010
    (re.compile(r"\b(?:founded|established|incorporated|est\.?)(?:\s+back)?(?:\s+in)?\s+\*{0,2}2010\b", re.I),
     "'founded in 2010' (canon: operating since 2010; incorporated 23.07.2012)"),
    (re.compile(r"\bsince\s+(?:its|our|the\s+company'?s)\s+(?:founding|foundation|establishment|inception)\s+in\s+2010\b"
                r"|\bfundada(?:\s+en)?\s+2010\b|desde\s+su\s+fundaci[oó]n\s+en\s+2010", re.I),
     "'since its founding in 2010' (canon: operating since 2010)"),
    (re.compile(rf"(?:נוסד(?:ה|ו)?|הוקמ(?:ה|ו)|הוקם)\s+{_IN_2010}"), "'נוסדה/הוקמה ב-2010' (canon: פועלת מאז 2010)"),
    (re.compile(rf"מאז\s+(?:הקמת(?:ה|ו|נו)|הקמת\s+החברה|היווסדות(?:ה|ו)?)\s+{_IN_2010}"),
     "'מאז הקמתה ב-2010' (canon: פועלת מאז 2010)"),
    (re.compile(r"\bfounded\s*:\s*\*{0,2}2010\b|\bfundada\s+en\s+el\s+año\s+2010\b", re.I),
     "'Founded: 2010' (canon: operating since 2010)"),
    (re.compile(rf"(?:ב|ל|מ)?[-\u05BE]?\d{{1,2}}\s+השנים\s+האחרונות|שישה?\s+עשר(?:ה)?\s+שנ(?:ה|ים|ות){_HE_END}"),
     "company age in years (canon: פועלת מאז 2010)"),
    (re.compile(r"\b\d{1,2}\+?\s*(?:years|años)\s+(?:of\s+)?(?:de\s+)?(?:experience|experiencia|operation|operating)\b"
                r"|\b(?:over|more\s+than|m[aá]s\s+de)\s+\d{1,2}\+?\s*(?:years|años)\b|\b\d{1,2}\+\s*(?:years|años)\b", re.I),
     "company age in years (canon: operating since 2010)"),
    (re.compile(r"\bdecade\s+and\s+a\s+half\b|\bd[eé]cada\s+y\s+media\b|עשור\s+וחצי", re.I),
     "company age 'a decade and a half' (canon: operating since 2010)"),
]

# A finished page ends with sentence punctuation. A final markdown table row or a
# short (<= 8 words) list/checklist item is also accepted (the stop_reason check is the primary
# truncation guard; this is the belt to its braces). Trailing markdown emphasis,
# quotes and brackets are ignored before checking.
_SENTENCE_END = set(".!?…:׃؟")
_TRAILING_WRAPPERS = "*_`'\"”’»)]} \t\r\n"
_LIST_ITEM = re.compile(r"^\s*(?:[-*+]\s+(?:\[[ xX]\]\s+)?|\d+[.)]\s+)\S")


def _ends_complete(text):
    raw = (text or "").rstrip()
    if not raw:
        return False
    last_line = raw.splitlines()[-1]
    if last_line.strip().startswith("|") and last_line.strip().endswith("|"):
        return True          # table row
    tail = raw.rstrip(_TRAILING_WRAPPERS)
    if _LIST_ITEM.match(last_line) and (tail[-1:] in _SENTENCE_END or len(last_line.split()) <= 8):
        # a short list/checklist label is a legitimate ending; a long prose item that
        # stops without punctuation is not (#203: "- **Force majeure** – ... מזג אוויר קי")
        return True
    tail = raw.rstrip(_TRAILING_WRAPPERS)
    return bool(tail) and tail[-1] in _SENTENCE_END


def completeness_violations(body, faqs=()):
    """Reject a body/FAQ answer that stops mid-sentence (e.g. '…מזג אוויר קי')."""
    out = []
    if not _ends_complete(body):
        tail = (body or "").rstrip()
        out.append(f"incomplete body: does not end with a sentence, table row or list item (ends {tail[-40:]!r})")
    for i, f in enumerate(faqs or []):
        ans = str((f or {}).get("answer") or "").rstrip(_TRAILING_WRAPPERS)
        if not ans or ans[-1] not in _SENTENCE_END:
            out.append(f"incomplete faq answer #{i + 1} (ends {ans[-40:]!r})")
    return out


BLOCKING_PREFIXES = ("incomplete", "canonical fact", "truncated", "policy:", "structure:", "site canonical-facts")


def is_blocking(violation):
    """Violations that must fail the run rather than silently drop one page."""
    return violation.startswith(BLOCKING_PREFIXES)


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
    for rx, label in CANON_VIOLATION_PATTERNS:
        m = rx.search(text)
        if m:
            violations.append(f"canonical fact: {label}: {m.group(0)!r}")
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
