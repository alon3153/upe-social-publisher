import scripts.aeo_gaps as g

TARGETS = {"per_dimension_min": {"product_search": 70, "comparison": 70, "reputation": 90}, "briefs_per_run": 3}


def scorecard(ps, cmp_, rep, comps=("BCD",)):
    ans = [{"id": "a", "question": "best event company?",
            "scores": {"product_search": ps, "comparison": cmp_, "reputation": rep},
            "competitors": list(comps), "gap_note": "UPE not surfaced; competitors led"}]
    return {"date": "2026-06-28", "models": {"claude": {"product_search": ps, "comparison": cmp_,
                                                        "reputation": rep, "aeo": 0, "answers": ans}}}


def test_weak_product_search_makes_category_brief():
    briefs = g.build_briefs(scorecard(40, 90, 100), None, TARGETS)
    types = {b["type"] for b in briefs}
    assert "category_guide" in types
    b = next(b for b in briefs if b["type"] == "category_guide")
    assert b["target_dimension"] == "product_search"
    assert "BCD" in b["competitors_to_beat"]


def test_strong_dimensions_make_no_briefs():
    assert g.build_briefs(scorecard(95, 95, 100), None, TARGETS) == []


def test_cap_and_overflow():
    # all three weak across model → 3 briefs, but cap=2 → 1 deferred
    sc = scorecard(10, 10, 10)
    briefs, deferred = g.briefs_with_overflow(sc, None, TARGETS, cap=2)
    assert len(briefs) == 2
    assert deferred == 1


def test_regression_raises_priority():
    cur = scorecard(60, 90, 100)
    prev = scorecard(75, 90, 100)   # product_search dropped 75->60
    b = g.build_briefs(cur, prev, TARGETS)[0]
    assert b["target_dimension"] == "product_search"
    assert b["priority"] >= (70 - 60) + 0.5
