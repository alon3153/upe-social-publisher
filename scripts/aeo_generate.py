"""Generate astro-schema markdown pages for a content brief, in he/en/es, with guards."""
import json, re
import aeo_guards

COLLECTION = {"category_guide": "blog", "comparison": "blog", "trust": "services"}
SCHEMA_TYPE = {"category_guide": "Article", "comparison": "Article", "trust": "WebPage"}

CANON_LINE = "Uproduction Events — 16 years, 1,500+ events across 130+ destinations, 25K+ participants."

BODY_DELIM = "===BODY==="

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


def generate_page(brief, lang, ask_fn, date):
    prompt = (
        f"LANGUAGE: {lang}\nPAGE TYPE: {brief['type']}\nTOPIC: {brief['topic']}\n"
        f"TARGET: improve '{brief['target_dimension']}' visibility.\n"
        f"Competitors to differentiate against (do not disparage): {', '.join(brief['competitors_to_beat']) or 'n/a'}\n"
        f"Include 3-5 FAQs (40-80 word answers). Write the body in {lang}."
    )
    payload, body = _split_meta_body(ask_fn("claude", GEN_SYSTEM + "\n\n" + prompt))
    slug_base = re.sub(r"[^a-z0-9-]+", "-", payload["slug"].lower()).strip("-")
    fm = {
        "title": payload["title"],
        "description": payload["description"],
        "h1": payload["h1"],
        "urlSlug": slug_base,
        "canonical": _canonical(lang, slug_base),
        "language": lang,
        "translationKey": f"aeo-{brief['target_dimension']}-{slug_base}",
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
            "frontmatter": fm, "body": body, "violations": violations}


def render_brief(brief, ask_fn, date):
    pages = []
    shared_key = None
    for lang in brief["lang_set"]:
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
