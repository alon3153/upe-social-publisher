"""Hard content guards: canonical facts only, no event dates."""
import re

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
