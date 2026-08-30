"""Generate astro-schema markdown pages for a content brief, in he/en/es, with guards."""
import json, re
import aeo_guards

COLLECTION = {"category_guide": "blog", "comparison": "blog", "trust": "services"}
SCHEMA_TYPE = {"category_guide": "Article", "comparison": "Article", "trust": "WebPage"}

CANON_LINE = "Uproduction Events — 16 years, 1,500+ events across 130+ destinations, 25K+ participants."

BODY_DELIM = "===BODY==="

# Guard-rejected drafts are regenerated (not dropped) up to this many total attempts,
# feeding the exact offending tokens back to the model each retry. Never drop a page.
MAX_GEN_ATTEMPTS = 3

GEN_SYSTEM = (
    "You write factual, non-promotional GEO/AEO web content for Uproduction Events (upe.co.il), a boutique global "
    "corporate event & conference production company. STRICT FACTS — the ONLY company stats you may state: founded 2010, "
    "16 years, 1,500+ events, 130+ destinations, 25K+ participants. NEVER write 200+, 2000, 120+, 800+, or 27 years. "
    "NEVER state the year a specific event took place. Write the way clients actually search; do not keyword-stuff.\n"
    "Reply in EXACTLY this format and nothing else:\n"
    'A single-line JSON object with metadata: {"title":str,"description":str,"h1":str,"slug":str,'
    '"faqs":[{"question":str,"answer":str}]}\n'
    "Then a line containing only ===BODY===\n"
    "Then the article body in Markdown (free to use newlines, quotes, headings, lists).\n"
    "Keep every JSON string value on a single line with no raw newlines."
)


def _canonical(lang, slug):
    return f"https://upe.co.il/{slug}/" if lang == "he" else f"https://upe.co.il/{lang}/{slug}/"


def _extract_json(text):
    # non-greedy first balanced-looking object; metadata is a single-line JSON object
    m = re.search(r"\{.*?\}(?=\s*$|\s*\n)", text, re.S) or re.search(r"\{.*\}", text, re.S)
    if not m:
        raise ValueError(f"no json in generator output: {text[:200]}")
    return json.loads(m.group(0))


def _split_meta_body(raw):
    if BODY_DELIM in raw:
        head, body = raw.split(BODY_DELIM, 1)
        return _extract_json(head), body.strip()
    # fallback: legacy single-JSON payload with an embedded body field
    payload = _extract_json(raw)
    return payload, payload.get("body_markdown", "")


REQUIRED_KEYS = ("title", "description", "h1", "slug")


def _slugify(text):
    return re.sub(r"[^a-z0-9-]+", "-", (text or "").lower()).strip("-")


def _missing_keys(payload):
    return [k for k in REQUIRED_KEYS if not str(payload.get(k) or "").strip()]


def _dim(brief):
    return brief.get("dimension") or brief.get("target_dimension") or "product_search"


def _topic(brief):
    return brief.get("topic") or brief.get("question") or ""


def _normalize_payload(payload, brief):
    """Never crash on a malformed model payload — derive sensible fallbacks so a
    brief is always publishable (see MAX_GEN_ATTEMPTS / 'never drop a page')."""
    p = dict(payload)
    p.setdefault("faqs", [])
    title = (p.get("title") or p.get("h1") or brief["topic"]).strip()
    p["title"] = title
    p["h1"] = (p.get("h1") or title).strip()
    p["description"] = (p.get("description") or title).strip()
    p["slug"] = _slugify(p.get("slug") or p.get("h1") or title) or f"aeo-{_dim(brief)}"
    return p


def _missing_correction(missing):
    return (
        "\n\nYOUR PREVIOUS METADATA JSON was missing required field(s): "
        f"{', '.join(missing)}. Regenerate the ENTIRE page and include ALL of "
        'these keys as non-empty strings: "title", "description", "h1", "slug".'
    )


def _build_page(brief, lang, payload, body, date):
    slug_base = re.sub(r"[^a-z0-9-]+", "-", payload["slug"].lower()).strip("-")
    fm = {
        "title": payload["title"],
        "description": payload["description"],
        "h1": payload["h1"],
        "urlSlug": slug_base,
        "canonical": _canonical(lang, slug_base),
        "language": lang,
        "translationKey": f"aeo-{_dim(brief)}-{slug_base}",
        "ogType": "article",
        "schemaType": SCHEMA_TYPE[brief["type"]],
        "author": "Uproduction",
        "llmsDescription": payload["description"],
        "datePublished": date,
        "dateModified": date,
        "category": "guide",
        "faqs": payload.get("faqs", []),
    }
    text_to_check = "\n".join([payload["title"], payload["description"], body] +
                              [f["answer"] for f in payload.get("faqs", [])])
    violations = aeo_guards.check_content(text_to_check)
    return {"collection": COLLECTION[brief["type"]], "lang": lang, "slug": slug_base,
            "intent": brief.get("intent"),
            "frontmatter": fm, "body": body, "violations": violations}


def _correction(violations):
    return (
        "\n\nYOUR PREVIOUS DRAFT WAS REJECTED by an automated fact-guard with these violations: "
        f"{violations}. Regenerate the ENTIRE page and remove every offending token. "
        "State NO company statistic other than the five allowed facts (founded 2010, 16 years, "
        "1,500+ events, 130+ destinations, 25K+ participants); if you need a number for venue size, "
        "headcount or budget, rephrase to avoid 2000/2,000/200+/120+/800+, and never place a "
        "2011-2024 year next to an event/case mention."
    )


# ARCHETYPE (revised 30.08.2026 after the founder lifted the competitor-naming ban).
#
# The previous archetype forbade naming any firm, so every page described only the
# boutique MODEL versus "large global networks" in the abstract. That produced pages no
# engine can cite for the query they targeted: asked "who are the top corporate event
# production companies", an engine needs a page that CONTAINS the roster. Every cited
# third-party page does exactly this — gogather names Freeman, GPJ, Jack Morton, Maritz
# and ranks itself #1 among them.
#
# So category/list pages now name real firms, under the structural rules enforced by
# aeo_guards.comparative_violations: a disclosed methodology, neutral one-line
# descriptors, no disparagement, no self-superlative.

_ROSTER_TYPES = {"category_guide", "comparison"}

_ROSTER_RULES = (
    "Write this as a genuine REFERENCE LIST that a neutral researcher would cite, not as "
    "marketing copy about Uproduction Events.\n"
    "1. Name 8-12 real companies that actually serve this need, including the ones an "
    "answer engine already names: {competitors}.\n"
    "2. Give each company a NEUTRAL one-or-two-line descriptor: what they are strong at, "
    "who they suit, where they operate. Never state or imply that any of them is bad, "
    "overpriced, unreliable, slow or inferior — a negative claim about a named firm is a "
    "legal exposure under Israeli Commercial Torts Law 5759-1999 and EU Directive "
    "2006/114/EC. Positive, factual, comparable descriptions only.\n"
    "3. Include Uproduction Events as ONE entry among them, described in its true "
    "category (boutique global producer, senior ownership, Israel-based with a Barcelona "
    "office, strongest on incentive travel and conferences taken abroad). Do NOT claim it "
    "is the best, the leading, or number one.\n"
    "4. Open with a section headed 'Methodology' (or the equivalent in the page language) "
    "stating in 2-3 sentences how the list was assembled and what it is based on.\n"
    "5. Structure the roster so each company is a clear heading or list item — an engine "
    "must be able to lift a single entry.\n"
    "6. Every statistic you state must carry an inline markdown link to its source on the "
    "same line. If you do not have a real source, do not state the number at all. Never "
    "cite arxiv.org or any preprint server for an events-industry claim."
)


def _differentiation_line(brief):
    if brief["type"] in _ROSTER_TYPES:
        comps = brief.get("competitors_named") or brief.get("competitors_to_beat") or []
        return _ROSTER_RULES.format(competitors=", ".join(comps) or "the established global networks")
    return (
        "This is a trust/solutions page about Uproduction Events itself. Describe what it "
        "does, for whom, and with what proof. Do not name competing firms. Every statistic "
        "must carry an inline source link on the same line, or be omitted."
    )


def generate_page(brief, lang, ask_fn, date):
    prompt = (
        f"LANGUAGE: {lang}\nPAGE TYPE: {brief['type']}\n"
        f"THE BUYER QUESTION THIS PAGE MUST ANSWER: {_topic(brief)}\n"
        f"Write the page so that it is the best possible SOURCE for answering that exact "
        f"question. An answer engine asked it and did not mention Uproduction Events"
        + (f" (lost on: {', '.join(brief.get('lost_on') or [])})" if brief.get("lost_on") else "")
        + ".\n"
        f"{_differentiation_line(brief)}\n"
        f"Include 3-5 FAQs (40-80 word answers). Write the body in {lang}."
    )
    correction = ""
    page = None
    for attempt in range(MAX_GEN_ATTEMPTS):
        payload, body = _split_meta_body(ask_fn("claude", GEN_SYSTEM + "\n\n" + prompt + correction))
        missing = _missing_keys(payload)
        if missing and attempt < MAX_GEN_ATTEMPTS - 1:
            # prefer a clean model draft; feed the missing fields back and retry
            correction = _missing_correction(missing)
            continue
        payload = _normalize_payload(payload, brief)  # last resort: never crash / never drop a page
        page = _build_page(brief, lang, payload, body, date)
        if not page["violations"]:
            return page
        correction = _correction(page["violations"])
    return page  # retries exhausted: surface the last draft's violations rather than crash


def render_brief(brief, ask_fn, date):
    """One brief -> one page, in the language of the question that generated it.

    Briefs used to fan out over a fixed he+en+es set, so a single gap produced three pages
    on the same intent every week and the clusters compounded (8 live pages on
    "boutique vs large networks", 3 EN pages with byte-identical titles). A Hebrew buyer
    question is answered by a Hebrew page.
    """
    langs = brief.get("lang_set") or [brief.get("lang") or "he"]
    pages, shared_key = [], None
    for lang in langs:
        page = generate_page(brief, lang, ask_fn, date)
        if shared_key is None:
            shared_key = page["frontmatter"]["translationKey"]
        page["frontmatter"]["translationKey"] = shared_key
        pages.append(page)
    return pages


def _yaml_scalar(v):
    return json.dumps(v, ensure_ascii=False)


def to_markdown(frontmatter, body):
    lines = ["---"]
    for k, v in frontmatter.items():
        if k == "faqs" and v:
            lines.append("faqs:")
            for f in v:
                lines.append(f"  - question: {_yaml_scalar(f['question'])}")
                lines.append(f"    answer: {_yaml_scalar(f['answer'])}")
        elif isinstance(v, (list, dict)):
            lines.append(f"{k}: {json.dumps(v, ensure_ascii=False)}")
        else:
            lines.append(f"{k}: {_yaml_scalar(v)}")
    lines.append("---")
    lines.append("")
    lines.append(body)
    return "\n".join(lines)
