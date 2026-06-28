import json
import scripts.aeo_competitor as comp


def scorecard_with(comps, ps=40):
    ans = [{"id": "a", "question": "best global event production company?",
            "scores": {"product_search": ps, "comparison": ps, "reputation": 90},
            "competitors": comps, "gap_note": "UPE not surfaced; competitors led"}]
    return {"date": "2026-06-28",
            "models": {"claude": {"product_search": ps, "comparison": ps, "reputation": 90,
                                  "aeo": 0, "answers": ans}}}


def test_collect_competitors_dedupes():
    sc = scorecard_with(["BCD", "Maritz", "BCD"])
    assert sorted(comp.collect_competitors(sc)) == ["BCD", "Maritz"]


def test_research_keywords_parses_he_en():
    def ask_fn(model, prompt):
        assert "BCD" in prompt              # competitors fed into the prompt
        return json.dumps({
            "he": ["הפקת כנסים בינלאומיים", "חברת הפקת אירועים לחברות"],
            "en": ["international conference production", "corporate event agency"],
            "competitors": ["BCD", "Maritz"],
            "priority_actions": ["publish a Hebrew category guide on conference production"],
        })
    out = comp.research_keywords(scorecard_with(["BCD", "Maritz"]), ask_fn)
    assert out["he"] and out["en"]
    assert "international conference production" in out["en"]
    assert out["priority_actions"]


def test_research_keywords_caps_to_top_per_lang():
    many_he = [f"מילה {i}" for i in range(30)]
    many_en = [f"keyword {i}" for i in range(40)]

    def ask_fn(model, prompt):
        return json.dumps({"he": many_he, "en": many_en, "competitors": ["BCD"], "priority_actions": ["a", "b", "c", "d", "e"]})

    out = comp.research_keywords(scorecard_with(["BCD"]), ask_fn)
    assert len(out["he"]) == comp.MAX_PER_LANG
    assert len(out["en"]) == comp.MAX_PER_LANG
    assert out["he"] == many_he[:comp.MAX_PER_LANG]      # keeps the top-ranked first
    assert len(out["priority_actions"]) <= comp.MAX_ACTIONS


def test_research_keywords_no_competitors_returns_empty():
    # all dimensions already strong → nothing to research
    strong = scorecard_with([], ps=95)
    out = comp.research_keywords(strong, lambda m, p: json.dumps({"he": [], "en": [], "competitors": [], "priority_actions": []}))
    assert out["he"] == [] and out["en"] == []
