import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
import aeo_gaps as g


def answer(qid, mentioned, dim="product_search", lang="he", seg="beachhead",
           branded=False, competitors=(), note=""):
    return {"id": qid, "question": f"q-{qid}", "dimension": dim, "lang": lang,
            "segment": seg, "branded": branded, "upe_mentioned": mentioned,
            "competitors": list(competitors), "gap_note": note}


def scorecard(models):
    return {"models": models}


def test_brief_comes_from_the_question_we_lost():
    sc = scorecard({"claude": {"answers": [
        answer("bh_il_kenes", False, competitors=["Freeman", "GPJ"], note="named only global networks"),
        answer("bh_il_gala", True),
    ]}})
    briefs = g.build_briefs(sc)
    assert len(briefs) == 1
    b = briefs[0]
    assert b["intent"] == "bh_il_kenes"
    assert b["question"] == "q-bh_il_kenes"
    assert b["lang"] == "he"            # single language, not a he+en+es triplet
    assert b["competitors_named"] == ["Freeman", "GPJ"]
    assert b["lost_on"] == ["claude"]
    assert b["why"] == "named only global networks"


def test_branded_questions_never_produce_briefs():
    sc = scorecard({"claude": {"answers": [answer("rep_who_is", False, seg="branded", branded=True)]}})
    assert g.build_briefs(sc) == []


def test_segment_weighting_puts_beachhead_above_aspirational():
    sc = scorecard({"claude": {"answers": [
        answer("aspirational_q", False, seg="aspirational"),
        answer("beachhead_q", False, seg="beachhead"),
    ]}})
    assert [b["intent"] for b in g.build_briefs(sc)] == ["beachhead_q", "aspirational_q"]


def test_question_lost_on_more_engines_ranks_higher():
    a = answer("wide", False, seg="expansion")
    b = answer("narrow", False, seg="expansion")
    sc = scorecard({"claude": {"answers": [a, b]}, "gemini": {"answers": [a]}})
    briefs = g.build_briefs(sc)
    assert briefs[0]["intent"] == "wide"
    assert briefs[0]["lost_on"] == ["claude", "gemini"]


def test_degraded_model_never_briefs():
    """Its answers are frozen training recall — briefing from them writes content to fix an API bug."""
    sc = scorecard({"chatgpt": {"degraded": True, "answers": [answer("ghost", False)]}})
    assert g.build_briefs(sc) == []


def test_covered_intent_is_not_regenerated():
    """The treadmill: 27 URLs on one intent because nothing checked what was already published."""
    sc = scorecard({"claude": {"answers": [answer("done", False), answer("todo", False)]}})
    assert [b["intent"] for b in g.build_briefs(sc, covered=["done"])] == ["todo"]


def test_vetoed_intent_is_not_regenerated():
    sc = scorecard({"claude": {"answers": [answer("banned", False), answer("ok", False)]}})
    assert [b["intent"] for b in g.build_briefs(sc, vetoed=["banned"])] == ["ok"]


def test_overflow_is_a_real_backlog_not_a_constant_zero():
    answers = [answer(f"q{i}", False) for i in range(7)]
    briefs, still_open = g.briefs_with_overflow(scorecard({"claude": {"answers": answers}}), cap=3)
    assert len(briefs) == 3
    assert still_open == 4          # the old code returned max(0, 3-3) == 0 forever


def test_nothing_lost_means_nothing_to_write():
    sc = scorecard({"claude": {"answers": [answer("won", True)]}})
    assert g.briefs_with_overflow(sc) == ([], 0)
