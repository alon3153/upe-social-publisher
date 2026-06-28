"""Competitor keyword-gap research: when UPE is not the #1 AI recommendation, find the
Hebrew + English keywords/phrases competitors win that UPE should target."""
import json, re

RESEARCH_SYSTEM = (
    "You are a GEO/AEO + SEO strategist for Uproduction Events (upe.co.il), a boutique global "
    "corporate event & conference production company. The goal is for Uproduction Events to become "
    "the #1 recommendation by AI answer engines for category queries — in BOTH Hebrew and English. "
    "Given the competitors currently winning those answers, identify the concrete keyword/phrase "
    "opportunities Uproduction should target on its site to overtake them. Be specific and realistic "
    "to how decision-makers actually search/ask. "
    'Reply with ONLY JSON: {"he":[str],"en":[str],"competitors":[str],"priority_actions":[str]}.'
)


def collect_competitors(scorecard):
    seen = []
    for block in scorecard.get("models", {}).values():
        for ans in block.get("answers", []):
            for c in ans.get("competitors", []) or []:
                if c not in seen:
                    seen.append(c)
    return seen


def _weak_notes(scorecard, min_score=90):
    notes = []
    for model, block in scorecard.get("models", {}).items():
        for dim in ("product_search", "comparison"):
            if block.get(dim, 0) < min_score:
                worst = min(block.get("answers", []), key=lambda a: a["scores"].get(dim, 0), default=None)
                if worst and worst.get("gap_note"):
                    notes.append(f"[{model}/{dim}] {worst['gap_note']}")
    return notes


def _extract_json(text):
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        raise ValueError(f"no json in research output: {text[:200]}")
    return json.loads(m.group(0))


def research_keywords(scorecard, ask_fn):
    competitors = collect_competitors(scorecard)
    notes = _weak_notes(scorecard)
    if not competitors and not notes:
        return {"he": [], "en": [], "competitors": [], "priority_actions": []}
    prompt = (
        f"Competitors currently winning AI answers over Uproduction: {', '.join(competitors) or 'unknown'}.\n"
        f"Observed gaps from the probe:\n" + ("\n".join(notes) or "(none)") + "\n\n"
        "Produce keyword/phrase opportunities (he + en) and concrete priority_actions to make "
        "Uproduction Events the #1 answer for corporate event/conference production, incentive travel and MICE."
    )
    data = _extract_json(ask_fn("claude", RESEARCH_SYSTEM + "\n\n" + prompt))
    return {
        "he": data.get("he", []) or [],
        "en": data.get("en", []) or [],
        "competitors": data.get("competitors", competitors) or competitors,
        "priority_actions": data.get("priority_actions", []) or [],
    }
