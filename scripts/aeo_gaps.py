"""Turn a scorecard into content briefs — one per buyer question we actually lost.

Replaces the previous design, which mapped the three scoring dimensions onto a hardcoded
three-entry topic dict and fanned each brief across he+en+es. That system could only ever
express 3 topics x 3 languages, so it rewrote the same pages every week: across its whole
life it produced 67 page-writes covering 3 distinct intents, 27 URLs of which were one
intent ("boutique vs large networks"). Briefs now derive from the specific non-branded
questions where an engine failed to mention UPE, in that question's own language.
"""

DIM_TO_TYPE = {"product_search": "category_guide", "comparison": "comparison", "reputation": "trust"}
DEFAULT_WEIGHTS = {"beachhead": 3.0, "expansion": 2.0, "aspirational": 1.0, "branded": 0.0}


def _clean(items, limit=12):
    seen, out = set(), []
    for it in items:
        k = (it or "").strip()
        if k and k.lower() not in seen:
            seen.add(k.lower())
            out.append(k)
    return out[:limit]


def candidates(scorecard, weights=None):
    """Every non-branded question an engine answered without naming UPE, ranked.

    A degraded model is excluded outright: its answers came from frozen training recall,
    so briefing from them means writing content to fix a broken API client.
    """
    weights = weights or DEFAULT_WEIGHTS
    by_intent = {}
    for model, block in (scorecard.get("models") or {}).items():
        if block.get("degraded"):
            continue
        for a in block.get("answers", []):
            if a.get("branded") or a.get("upe_mentioned"):
                continue
            qid = a.get("id")
            if not qid:
                continue
            c = by_intent.setdefault(qid, {
                "intent": qid,
                "question": a.get("question", ""),
                "lang": a.get("lang") or "",
                "segment": a.get("segment") or "aspirational",
                "dimension": a.get("dimension", "product_search"),
                "lost_on": [],
                "competitors_named": [],
                "gap_notes": [],
            })
            c["lost_on"].append(model)
            c["competitors_named"].extend(a.get("competitors") or [])
            if a.get("gap_note"):
                c["gap_notes"].append(a["gap_note"])

    out = []
    for c in by_intent.values():
        c["competitors_named"] = _clean(c["competitors_named"])
        c["lost_on"] = sorted(set(c["lost_on"]))
        c["type"] = DIM_TO_TYPE.get(c["dimension"], "category_guide")
        c["why"] = (c["gap_notes"][0] if c["gap_notes"] else
                    f"no engine named UPE for this question ({', '.join(c['lost_on'])})")
        # a question lost on every engine is a bigger hole than one lost on one
        c["priority"] = round(weights.get(c["segment"], 1.0) * len(c["lost_on"]), 2)
        c.pop("gap_notes", None)
        out.append(c)
    out.sort(key=lambda b: (-b["priority"], b["intent"]))
    return out


def build_briefs(scorecard, targets=None, covered=(), vetoed=(), cap=3, weights=None):
    """Top `cap` uncovered, unvetoed intents. `covered`/`vetoed` are intent keys."""
    return _open_briefs(scorecard, covered, vetoed, weights)[:cap]


def _open_briefs(scorecard, covered, vetoed, weights):
    skip = {str(x) for x in covered} | {str(x) for x in vetoed}
    return [c for c in candidates(scorecard, weights) if c["intent"] not in skip]


def briefs_with_overflow(scorecard, targets=None, covered=(), vetoed=(), cap=3, weights=None):
    """(briefs, still_open) — `still_open` is a REAL backlog count.

    The old implementation returned max(0, len(all) - cap) where `all` was itself capped at
    3 by a per-dimension dedup, so the "queued for next week" figure in the weekly email was
    the constant 0 for the system's entire life.
    """
    allb = _open_briefs(scorecard, covered, vetoed, weights)
    return allb[:cap], max(0, len(allb) - cap)
