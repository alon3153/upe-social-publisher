import json
import scripts.aeo_generate as gen

BRIEF = {"type": "category_guide", "topic": "choosing a global event producer",
         "target_dimension": "product_search", "lang_set": ["he", "en", "es"],
         "why": "not surfaced", "competitors_to_beat": ["BCD"], "priority": 30.0}


def fake_ask(model, prompt):
    meta = json.dumps({
        "title": "How to choose a global corporate event production company",
        "description": "A practical guide. Uproduction Events — 16 years, 1,500+ events across 130+ destinations.",
        "h1": "Choosing a global event production company",
        "slug": "choose-global-event-production-company",
        "faqs": [{"question": "What is event production?",
                  "answer": "It is the end-to-end planning and delivery of corporate events."}],
    })
    return meta + "\n===BODY===\n## Overview\nUproduction Events produces corporate events worldwide.\n"


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
        meta = json.dumps({"title": "200+ events done", "description": "d", "h1": "h",
                           "slug": "x", "faqs": []})
        return meta + "\n===BODY===\nwe have 200+ events"
    page = gen.generate_page(BRIEF, "en", bad_ask, "2026-06-28")
    assert any("200+" in v for v in page["violations"])


def test_guard_violation_is_regenerated_not_dropped():
    # first draft trips the guard; the retry must produce a clean, publishable page
    calls = {"n": 0}

    def flaky_ask(model, prompt):
        calls["n"] += 1
        if calls["n"] == 1:
            meta = json.dumps({"title": "Over 2,000 events delivered", "description": "d",
                               "h1": "h", "slug": "guide-clean", "faqs": []})
            return meta + "\n===BODY===\nWe have produced 2,000 events."
        assert "REJECTED" in prompt and "2,000" in prompt  # correction was fed back
        meta = json.dumps({"title": "A global event production guide", "description": "d",
                           "h1": "h", "slug": "guide-clean", "faqs": []})
        return meta + "\n===BODY===\nUproduction Events — 16 years, 1,500+ events.\n"

    page = gen.generate_page(BRIEF, "en", flaky_ask, "2026-06-28")
    assert page["violations"] == []
    assert calls["n"] == 2


def test_unfixable_violation_surfaces_after_retries():
    calls = {"n": 0}

    def always_bad(model, prompt):
        calls["n"] += 1
        meta = json.dumps({"title": "200+ events", "description": "d", "h1": "h",
                           "slug": "x", "faqs": []})
        return meta + "\n===BODY===\nwe have 200+ events"

    page = gen.generate_page(BRIEF, "en", always_bad, "2026-06-28")
    assert any("200+" in v for v in page["violations"])
    assert calls["n"] == gen.MAX_GEN_ATTEMPTS


def test_body_with_unescaped_newlines_and_quotes_parses():
    # the real-world failure: a long markdown body that would break JSON if embedded
    def messy_ask(model, prompt):
        meta = json.dumps({"title": "T", "description": "d", "h1": "h", "slug": "guide-x", "faqs": []})
        body = '## Heading\n\nA paragraph with "quotes" and\nmultiple lines.\n\n- bullet\n- bullet'
        return meta + "\n===BODY===\n" + body
    page = gen.generate_page(BRIEF, "en", messy_ask, "2026-06-28")
    assert page["slug"] == "guide-x"
    assert '"quotes"' in page["body"]


def test_to_markdown_roundtrip():
    md = gen.to_markdown({"title": "T", "language": "he"}, "## body")
    assert md.startswith("---")
    assert "title:" in md and "## body" in md
