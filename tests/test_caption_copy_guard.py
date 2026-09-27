"""Fail if caption copy still has the broken figure-substitution patterns."""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTENT = ROOT / "content"
COPY_KEYS = {
    "text",
    "caption",
    "captions",
    "post_caption",
    "script_en",
    "script_he",
    "script_es",
    "copy",
}

# Client quotes stay. They are not company claims.
DAY132_QUOTES = (
    "I've partnered with a dozen event agencies over 15 years.",
    "First time in 15 years I didn't have to fix anything the morning after.",
    "I've worked with a dozen agencies over 15 years.",
    "He trabajado con muchas agencias en 15 años.",
    "Primera vez en 15 años que no tuve que resolver nada al día siguiente.",
    "Llevo 15 años trabajando con agencias de eventos.",
)

# CONTENT's own approved wording. The guard pattern is a substring of the sentence.
APPROVED_PHRASES = (
    "here's what we've learned since 2010 about corporate event ROI:",
    # E-2: this tagline was reviewed and left as-is.
    "Desde 2010 produciendo viajes de incentivo que van más allá de la experiencia.",
)

# במאז must not match במאזן ("in the balance sheet").
PATTERNS = (
    re.compile(r"ב-מאז"),
    re.compile(r"ו-מאז"),
    re.compile(r"ש-מאז"),
    re.compile(r"מ-מאז"),
    re.compile(r"במאז(?!ן)"),
    re.compile(r"אחרי מאז"),
    re.compile(r"מאז 2010 ויותר מ-"),
    re.compile(r"since 2010 ago"),
    re.compile(r"learned since 2010"),
    re.compile(r"Since 2010 producing"),
    re.compile(r"Con desde"),
    re.compile(r"de desde"),
    re.compile(r"más de desde"),
    re.compile(r"Desde 2010 produciendo"),
    re.compile(r"130\+ countries"),
    re.compile(r"130\+ países"),
    re.compile(r"130\+ מדינות"),
    re.compile(r"16 years"),
    re.compile(r"16 שנה"),
    re.compile(r"16 años"),
)


def _scrub(text):
    for phrase in DAY132_QUOTES + APPROVED_PHRASES:
        text = text.replace(phrase, "")
    return text


def _copy_strings(path: Path):
    if path.suffix == ".txt":
        yield path.read_text(encoding="utf-8")
        return
    data = json.loads(path.read_text(encoding="utf-8"))

    def walk(obj, in_copy):
        if isinstance(obj, dict):
            for key, value in obj.items():
                yield from walk(value, in_copy or key in COPY_KEYS)
        elif isinstance(obj, list):
            for value in obj:
                yield from walk(value, in_copy)
        elif isinstance(obj, str) and in_copy:
            yield obj

    yield from walk(data, False)


def broken_caption_hits():
    hits = []
    for path in sorted(CONTENT.rglob("*")):
        if path.suffix not in {".json", ".txt"}:
            continue
        rel = path.relative_to(ROOT).as_posix()
        for text in _copy_strings(path):
            cleaned = _scrub(text)
            for pattern in PATTERNS:
                match = pattern.search(cleaned)
                if match:
                    start = max(0, match.start() - 30)
                    hits.append(f"{rel}: {match.group()!r} in {cleaned[start:match.end() + 30]!r}")
    return hits


def test_caption_copy_has_no_broken_figure_patterns():
    hits = broken_caption_hits()
    assert hits == [], "\n".join(hits)


def test_guard_flags_the_listed_patterns():
    samples = [
        "ב-מאז 2010",
        "ו-מאז 2010",
        "ש-מאז 2010",
        "מ-מאז 2010",
        "במאז 2010",
        "אחרי מאז 2010",
        "מאז 2010 ויותר מ-1,500",
        "since 2010 ago",
        "what we've learned since 2010 us",
        "Since 2010 producing 1,500+ events",
        "Con desde 2010",
        "A lo largo de desde 2010",
        "con más de desde 2010",
        "Desde 2010 produciendo eventos.",
        "130+ countries",
        "130+ países",
        "130+ מדינות",
        "16 years of corporate events",
        "16 שנה",
        "16 años",
    ]
    for sample in samples:
        assert any(pattern.search(sample) for pattern in PATTERNS), sample
    assert not any(pattern.search("במאזן") for pattern in PATTERNS)
    for phrase in APPROVED_PHRASES:
        assert any(pattern.search(phrase) for pattern in PATTERNS)
        assert not any(pattern.search(_scrub(phrase)) for pattern in PATTERNS)
