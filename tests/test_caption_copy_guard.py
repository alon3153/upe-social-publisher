"""Fail if caption copy still has the broken figure-substitution patterns."""
import json
import re
from pathlib import Path

import pytest

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
    re.compile(r"Desde 2010 produciendo", re.IGNORECASE),
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

# TODO: case-insensitive "Desde 2010 produciendo" also matches CONTENT-approved
# "Llevamos desde 2010 produciendo…", and four ES/HE themes still say
# "130+ Destinations" in English. Do not rewrite those captions to clear the guard.
TODO_HITS = (
    (
        "content/days/day138-viral_adapted-es.json",
        "instagram",
        "Desde 2010 produciendo",
        "Llevamos desde 2010 produciendo eventos B2B y viajes de incentivo — conferencias, galas, lanzamientos de producto, retiros de equipo.",
    ),
    (
        "content/days/day169-founder_insight-es.json",
        "facebook",
        "Desde 2010 produciendo",
        "Llevamos desde 2010 produciendo eventos y la lección más importante no llegó en una sala de reuniones — llegó en una cena de gala.",
    ),
    (
        "content/days/day216-incentive_travel-es.json",
        "facebook",
        "Desde 2010 produciendo",
        "Llevamos desde 2010 produciendo eventos para empresas en más de 130 destinos.",
    ),
    (
        "content/days/day247-viral_adapted-es.json",
        "facebook",
        "Desde 2010 produciendo",
        "Llevamos desde 2010 produciendo más de 1.500 eventos corporativos en más de 130 destinos.",
    ),
    (
        "content/days/day257-viral_adapted-es.json",
        "linkedin",
        "Desde 2010 produciendo",
        "En Uproduction Events llevamos desde 2010 produciendo más de 1.500 eventos en más de 130 destinos para más de 25.000 participantes.",
    ),
    (
        "content/days/day266-incentive_travel-es.json",
        "instagram",
        "Desde 2010 produciendo",
        "Llevamos desde 2010 produciendo viajes de incentivo que van más allá de la experiencia.",
    ),
    (
        "content/days/day271-cta_lead-es.json",
        "facebook",
        "Desde 2010 produciendo",
        "En Uproduction Events llevamos desde 2010 produciendo eventos que generan resultados concretos: más de 1,500 eventos, 130+ destinos, 25,000+ participantes.",
    ),
    (
        "content/days/day41-cta_lead-es.json",
        "facebook",
        "Desde 2010 produciendo",
        "En Uproduction (UPE) llevamos 1,500+ eventos en 130+ destinos desde 2010 produciendo viajes de incentivo llave en mano, from business to pleasure.",
    ),
    (
        "content/days/day185-social_proof-es.json",
        "theme",
        "130+ destinations",
        "Client Trust Built Across 130+ Destinations",
    ),
    (
        "content/days/day185-social_proof-he.json",
        "theme",
        "130+ destinations",
        "Client Trust Built Across 130+ Destinations",
    ),
    (
        "content/days/day245-social_proof-es.json",
        "theme",
        "130+ destinations",
        "Trust Built Across 130+ Destinations",
    ),
    (
        "content/days/day245-social_proof-he.json",
        "theme",
        "130+ destinations",
        "Trust Built Across 130+ Destinations",
    ),
)
TODO_KEYS = {(path, platform, pattern) for path, platform, pattern, _sentence in TODO_HITS}
TODO_REASON = "TODO: CONTENT has not signed off on rewriting these. Do not edit the captions to clear the guard.\n" + "\n".join(
    f"{path} | {platform} | {sentence}" for path, platform, _pattern, sentence in TODO_HITS
)


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
            if es_or_he:
                patterns.append(ES_HE_DESTINATIONS)
            for pattern in patterns:
                for match in pattern.finditer(cleaned):
                    label = "130+ destinations" if pattern is ES_HE_DESTINATIONS else pattern.pattern
                    sentence = _sentence(cleaned, match.start(), match.end())
                    hits.append((rel, platform, label, sentence))
    return hits


def test_caption_copy_has_no_broken_figure_patterns():
    unexpected = [hit for hit in caption_guard_hits() if hit[:3] not in TODO_KEYS]
    assert unexpected == [], "\n".join(f"{path} | {platform} | {sentence}" for path, platform, _label, sentence in unexpected)


@pytest.mark.xfail(reason=TODO_REASON, strict=False)
def test_known_caption_guard_hits_still_need_content_review():
    remaining = [hit for hit in caption_guard_hits() if hit[:3] in TODO_KEYS]
    assert remaining == []


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
    seville = _scrub("Seville is what Barcelona was 15 years ago:", "content/days/week3-day20-seville-en.json")
    assert not any(pattern.search(seville) for pattern in PATTERNS)
