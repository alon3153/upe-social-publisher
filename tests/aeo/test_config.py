import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_question_battery_wellformed():
    data = json.loads((ROOT / "scripts" / "aeo_questions.json").read_text(encoding="utf-8"))
    assert isinstance(data["battery_version"], str) and data["battery_version"]
    qs = data["questions"]
    assert len(qs) >= 30, "a 16-question battery makes one flip worth 6.25 points"
    ids = [q["id"] for q in qs]
    assert len(ids) == len(set(ids)), "question ids must be unique"
    dims = {"product_search", "comparison", "reputation"}
    segs = {"beachhead", "expansion", "aspirational", "branded"}
    for q in qs:
        assert q["dimension"] in dims
        assert q["lang"] in {"he", "en", "es"}
        assert q["segment"] in segs
        assert q["text"].strip()
    assert dims.issubset({q["dimension"] for q in qs})
    assert segs.issubset({q["segment"] for q in qs})
    assert set(data["segment_weights"]) == segs
    assert data["segment_weights"]["branded"] == 0.0


def test_only_branded_questions_name_the_company():
    """A question that names UPE can only measure recall; it must be segmented as such."""
    data = json.loads((ROOT / "scripts" / "aeo_questions.json").read_text(encoding="utf-8"))
    for q in data["questions"]:
        named = "uproduction" in q["text"].lower()
        assert named == (q["segment"] == "branded"), q["id"]


def test_battery_covers_the_markets_upe_actually_serves():
    """The old battery had 7 global head-term questions, zero about Israel, zero in Spanish."""
    data = json.loads((ROOT / "scripts" / "aeo_questions.json").read_text(encoding="utf-8"))
    qs = data["questions"]
    by_seg = {}
    for q in qs:
        by_seg.setdefault(q["segment"], []).append(q)
    assert len(by_seg["beachhead"]) >= 10
    assert len(by_seg["expansion"]) >= 8
    assert any(q["lang"] == "es" for q in qs), "an /es site and a Barcelona office, and no ES question"
    nonbranded = [q for q in qs if q["segment"] != "branded"]
    assert 100 / len(nonbranded) < 4, "one question must be worth less than 4 points"


def test_aeo_targets_present():
    kpi = json.loads((ROOT / "scripts" / "kpi_targets.json").read_text(encoding="utf-8"))
    t = kpi["aeo_targets"]
    assert set(t["per_dimension_min"]) == {"product_search", "comparison", "reputation"}
    assert t["briefs_per_run"] == 3
