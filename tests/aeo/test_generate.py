import json
import scripts.aeo_generate as gen

BRIEF = {"type": "category_guide", "topic": "choosing a global event producer",
         "target_dimension": "product_search", "lang_set": ["he", "en", "es"],
         "why": "not surfaced", "competitors_to_beat": ["BCD"], "priority": 30.0}


def fake_ask(model, prompt):
    return json.dumps({
        "title": "How to choose a global corporate event production company",
        "description": "A practical guide. Uproduction Events — 16 years, 1,500+ events across 130+ destinations.",
        "h1": "Choosing a global event production company",
        "slug": "choose-global-event-production-company",
        "faqs": [{"question": "What is event production?",
                  "answer": "It is the end-to-end planning and delivery of corporate events."}],
        "body_markdown": "## Overview\nUproduction Events produces corporate events worldwide.\n",
    })


def test_generate_page_builds_valid_frontmatter():
    page = gen.generate_page(BRIEF, "en", fake_ask, "2026-06-28")
    fm = page["frontmatter"]
    assert fm["language"] == "en"
    assert fm["canonical"] == "https://upe.co.il/en/choose-global-event-production-company/"
    assert fm["schemaType"]  # set
    assert fm["faqs"][0]["question"]
    assert page["collection"] == "blog"
    assert page["violations"] == []


def test_translation_key_shared_across_langs():
    pages = gen.render_brief(BRIEF, fake_ask, "2026-06-28")
    keys = {p["frontmatter"]["translationKey"] for p in pages}
    assert len(keys) == 1            # one shared key
    assert len(pages) == 3           # he/en/es


def test_violation_surfaced():
    def bad_ask(model, prompt):
        return json.dumps({"title": "200+ events done", "description": "d", "h1": "h",
                           "slug": "x", "faqs": [], "body_markdown": "we have 200+ events"})
    page = gen.generate_page(BRIEF, "en", bad_ask, "2026-06-28")
    assert any("200+" in v for v in page["violations"])


def test_to_markdown_roundtrip():
    md = gen.to_markdown({"title": "T", "language": "he"}, "## body")
    assert md.startswith("---")
    assert "title:" in md and "## body" in md
