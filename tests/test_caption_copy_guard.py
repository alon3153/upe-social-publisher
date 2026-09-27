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
    "theme",
}
PLATFORMS = {"linkedin", "instagram", "facebook", "theme"}

# Client quotes stay. They are not company claims.
DAY132_QUOTES = (
    "I've partnered with a dozen event agencies over 15 years.",
    "First time in 15 years I didn't have to fix anything the morning after.",
    "I've worked with a dozen agencies over 15 years.",
    "He trabajado con muchas agencias en 15 años.",
    "Primera vez en 15 años que no tuve que resolver nada al día siguiente.",
    "Llevo 15 años trabajando con agencias de eventos.",
)

# במאז must not match במאזן ("in the balance sheet").
PATTERNS = (
    re.compile(r"ב-מאז", re.IGNORECASE),
    re.compile(r"ו-מאז", re.IGNORECASE),
    re.compile(r"ש-מאז", re.IGNORECASE),
    re.compile(r"מ-מאז", re.IGNORECASE),
    re.compile(r"במאז(?!ן)", re.IGNORECASE),
    re.compile(r"אחרי מאז", re.IGNORECASE),
    re.compile(r"מאז 2010 ויותר מ-", re.IGNORECASE),
    re.compile(r"since 2010 ago", re.IGNORECASE),
    re.compile(r"learned since 2010 us", re.IGNORECASE),
    re.compile(r"Since 2010 producing", re.IGNORECASE),
    re.compile(r"Con desde", re.IGNORECASE),
    re.compile(r"de desde", re.IGNORECASE),
    re.compile(r"más de desde", re.IGNORECASE),
    # Fixed-width lookbehind: Python's re cannot use llevamos\s+.
    re.compile(r"(?<!llevamos\s)Desde 2010 produciendo", re.IGNORECASE),
    re.compile(r"130\+ countries", re.IGNORECASE),
    re.compile(r"130\+ países", re.IGNORECASE),
    re.compile(r"130\+ מדינות", re.IGNORECASE),
    re.compile(r"16 years", re.IGNORECASE),
    re.compile(r"16 שנה", re.IGNORECASE),
    re.compile(r"16 años", re.IGNORECASE),
    re.compile(r"quince años", re.IGNORECASE),
    re.compile(r"dieciséis años", re.IGNORECASE),
    re.compile(r"200\+ events", re.IGNORECASE),
    re.compile(r"120 countries", re.IGNORECASE),
    re.compile(r"15 years", re.IGNORECASE),
)
ES_HE_DESTINATIONS = re.compile(r"130\+ destinations", re.IGNORECASE)


def _scrub(text, rel):
    for phrase in DAY132_QUOTES:
        text = text.replace(phrase, "")
    if rel.endswith("week3-day20-seville-en.json"):
        text = re.sub(r"15 years", "", text, flags=re.IGNORECASE)
    return text


def _fields(path: Path):
    if path.suffix == ".txt":
        yield "txt", path.read_text(encoding="utf-8")
        return
    data = json.loads(path.read_text(encoding="utf-8"))

    def walk(obj, in_copy, platform):
        if isinstance(obj, dict):
            for key, value in obj.items():
                next_platform = key if key in PLATFORMS else platform
                yield from walk(value, in_copy or key in COPY_KEYS, next_platform)
        elif isinstance(obj, list):
            for value in obj:
                yield from walk(value, in_copy, platform)
        elif isinstance(obj, str) and in_copy:
            yield platform or "text", obj

    yield from walk(data, False, "")


def _sentence(text, start, end):
    prev = max(text.rfind("\n", 0, start), text.rfind("!", 0, start), text.rfind("?", 0, start))
    # Ignore the decimal point in figures such as 1.500.
    dot = text.rfind(".", 0, start)
    if dot > prev and not (dot > 0 and text[dot - 1].isdigit()):
        prev = dot
    nxt = len(text)
    for sep in "\n!?":
        found = text.find(sep, end)
        if found != -1:
            nxt = min(nxt, found if sep == "\n" else found + 1)
    dot = text.find(".", end)
    while dot != -1 and dot + 1 < len(text) and text[dot + 1].isdigit():
        dot = text.find(".", dot + 1)
    if dot != -1:
        nxt = min(nxt, dot + 1)
    return " ".join(text[prev + 1 : nxt].split())


def caption_guard_hits():
    hits = []
    for path in sorted(CONTENT.rglob("*")):
        if path.suffix not in {".json", ".txt"}:
            continue
        rel = path.relative_to(ROOT).as_posix()
        es_or_he = rel.endswith("-es.json") or rel.endswith("-he.json")
        for platform, text in _fields(path):
            cleaned = _scrub(text, rel)
            patterns = list(PATTERNS)
            if es_or_he and platform != "theme":
                patterns.append(ES_HE_DESTINATIONS)
            for pattern in patterns:
                for match in pattern.finditer(cleaned):
                    label = "130+ destinations" if pattern is ES_HE_DESTINATIONS else pattern.pattern
                    sentence = _sentence(cleaned, match.start(), match.end())
                    hits.append((rel, platform, label, sentence))
    return hits


def test_caption_copy_has_no_broken_figure_patterns():
    hits = caption_guard_hits()
    assert hits == [], "\n".join(f"{path} | {platform} | {sentence}" for path, platform, _label, sentence in hits)


def test_guard_flags_the_listed_patterns():
    samples = [
        "ב-מאז 2010",
        "ו-מאז 2010",
        "ש-מאז 2010",
        "מ-מאז 2010",
        "במאז 2010",
        "אחרי מאז 2010",
        "מאז 2010 ויותר מ-1,500",
        "SINCE 2010 AGO",
        "what we've learned since 2010 us",
        "since 2010 producing 1,500+ events",
        "con desde 2010",
        "A lo largo de desde 2010",
        "con más de desde 2010",
        "desde 2010 produciendo eventos.",
        "130+ Countries",
        "130+ países",
        "130+ מדינות",
        "16 Years of corporate events",
        "16 שנה",
        "16 Años",
        "Quince años.",
        "Dieciséis años.",
        "200+ Events",
        "120 Countries",
        "15 Years",
    ]
    for sample in samples:
        assert any(pattern.search(sample) for pattern in PATTERNS), sample
    assert ES_HE_DESTINATIONS.search("Across 130+ Destinations")
    assert not any(pattern.search("במאזן") for pattern in PATTERNS)
    assert not any(pattern.search("here's what we've learned since 2010 about corporate event ROI:") for pattern in PATTERNS)
    assert not any(pattern.search("Llevamos desde 2010 produciendo eventos.") for pattern in PATTERNS)
    assert not any(pattern.search("EN UPRODUCTION EVENTS LLEVAMOS DESDE 2010 PRODUCIENDO eventos.") for pattern in PATTERNS)
    seville = _scrub("Seville is what Barcelona was 15 years ago:", "content/days/week3-day20-seville-en.json")
    assert not any(pattern.search(seville) for pattern in PATTERNS)
