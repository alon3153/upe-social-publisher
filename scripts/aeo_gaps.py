"""Turn a scorecard into a prioritized, capped list of content briefs."""

DIM_TO_TYPE = {"product_search": "category_guide", "comparison": "comparison", "reputation": "trust"}
DIM_TOPIC = {
    "product_search": "category guide on choosing a global corporate event & conference production company",
    "comparison": "comparison: boutique global event producer vs large networks — who is this for",
    "reputation": "trust page: Uproduction Events solutions, client proofs and FAQ by audience segment",
}
LANG_SET = ["he", "en", "es"]


def _worst_answer(model_block, dim):
    answers = model_block.get("answers", [])
    if not answers:
        return None
    return min(answers, key=lambda a: a["scores"].get(dim, 0))


def _all_briefs(scorecard, prev, targets):
    mins = targets["per_dimension_min"]
    briefs = []
    seen = set()
    for model, block in scorecard["models"].items():
        for dim, min_score in mins.items():
            score = block.get(dim, 0)
            if score >= min_score:
                continue
            if dim in seen:
                # dimension already weak on another model: keep the larger gap
                existing = next(b for b in briefs if b["target_dimension"] == dim)
                gap = min_score - score
                if gap > existing["priority"]:
                    existing["priority"] = gap
                continue
            seen.add(dim)
            gap = min_score - score
            priority = float(gap)
            if prev:
                pblock = prev["models"].get(model, {})
                if pblock.get(dim, score) > score:
                    priority += 0.5
            worst = _worst_answer(block, dim)
            comps = worst["competitors"] if worst else []
            note = worst["gap_note"] if worst else ""
            briefs.append({
                "type": DIM_TO_TYPE[dim],
                "topic": DIM_TOPIC[dim],
                "target_dimension": dim,
                "lang_set": list(LANG_SET),
                "why": note or f"{dim} scored {score} < target {min_score}",
                "competitors_to_beat": list(comps),
                "priority": priority,
            })
    briefs.sort(key=lambda b: b["priority"], reverse=True)
    return briefs


def build_briefs(scorecard, prev, targets, cap=3):
    return _all_briefs(scorecard, prev, targets)[:cap]


def briefs_with_overflow(scorecard, prev, targets, cap=3):
    allb = _all_briefs(scorecard, prev, targets)
    return allb[:cap], max(0, len(allb) - cap)
