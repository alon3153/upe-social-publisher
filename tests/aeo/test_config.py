import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_question_battery_wellformed():
    data = json.loads((ROOT / "scripts" / "aeo_questions.json").read_text(encoding="utf-8"))
    assert isinstance(data["battery_version"], str) and data["battery_version"]
    qs = data["questions"]
    assert len(qs) >= 15
    ids = [q["id"] for q in qs]
    assert len(ids) == len(set(ids)), "question ids must be unique"
    dims = {"product_search", "comparison", "reputation"}
    for q in qs:
        assert q["dimension"] in dims
        assert q["lang"] in {"he", "en"}
        assert q["text"].strip()
    # every dimension represented
    assert dims.issubset({q["dimension"] for q in qs})
    # non-branded for product_search/comparison: must NOT contain the brand
    for q in qs:
        if q["dimension"] in {"product_search", "comparison"}:
            assert "uproduction" not in q["text"].lower()


def test_aeo_targets_present():
    kpi = json.loads((ROOT / "scripts" / "kpi_targets.json").read_text(encoding="utf-8"))
    t = kpi["aeo_targets"]
    assert set(t["per_dimension_min"]) == {"product_search", "comparison", "reputation"}
    assert t["briefs_per_run"] == 3
