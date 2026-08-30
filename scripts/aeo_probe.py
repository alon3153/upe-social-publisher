"""Probe answer engines with the question battery and score each answer with an LLM judge."""
import json, re, datetime
from pathlib import Path
from statistics import mean

DIMS = ("product_search", "comparison", "reputation")
ROOT = Path(__file__).resolve().parent

JUDGE_SYSTEM = (
    "You are a strict GEO/AEO auditor for the company 'Uproduction Events' (uproduction events, upe.co.il), "
    "a boutique global corporate event & conference production company. Given a question and an answer engine's "
    "answer, score 0-100 on three dimensions: product_search (did Uproduction surface unprompted for a category "
    "query, and how prominently), comparison (is Uproduction positioned correctly when comparing/choosing vendors), "
    "reputation (accurate brand recall). Score ONLY the dimension that applies to this question; set the others to 0. "
    "Also list competitor companies named in the answer, and one short gap_note. "
    'Reply with ONLY a JSON object: {"product_search":int,"comparison":int,"reputation":int,"competitors":[str],"gap_note":str}.'
)


def _extract_json(text):
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        raise ValueError(f"no json in judge output: {text[:200]}")
    return json.loads(m.group(0))


def score_answer(question, answer, judge_fn):
    prompt = (
        f'qid="{question["id"]}"\nDIMENSION: {question["dimension"]}\n'
        f'QUESTION: {question["text"]}\n\nANSWER:\n{answer}\n'
    )
    try:
        data = _extract_json(judge_fn(prompt))
    except (ValueError, json.JSONDecodeError):  # judge emitted malformed JSON — one retry
        data = _extract_json(judge_fn(prompt))
    return {
        "product_search": int(data.get("product_search", 0)),
        "comparison": int(data.get("comparison", 0)),
        "reputation": int(data.get("reputation", 0)),
        "competitors": data.get("competitors", []) or [],
        "gap_note": data.get("gap_note", "") or "",
    }


_UPE_RE = re.compile(r"uproduction|upe\.co\.il", re.I)


def is_branded(question_text):
    """A question that NAMES the company can only measure brand recall, never demand.

    Such a question is a guaranteed mention -- the engine simply reads it back. Averaging
    these into the headline puts a hard floor under the KPI (4 branded of 16 questions =
    a permanent 25%) and hides the number that matters: whether an engine recommends UPE
    to someone who has never heard of it.
    """
    return bool(_UPE_RE.search(question_text or ""))


def _mention_fields(text, citations):
    """Deterministic binary metrics — the primary KPI (LLM judge stays secondary color)."""
    return {
        "upe_mentioned": bool(_UPE_RE.search(text or "")),
        "upe_cited": any("upe.co.il" in (u or "") for u in citations),
        "cited_urls": list(citations),
    }


def _rate(hits, total):
    return round(100 * hits / total) if total else 0


def run_probe(questions, models, ask_fn, judge_fn):
    date = datetime.date.today().isoformat()
    battery_version = ""
    qpath = ROOT / "aeo_questions.json"
    if qpath.exists():
        battery_version = json.loads(qpath.read_text(encoding="utf-8")).get("battery_version", "")
    out = {"date": date, "battery_version": battery_version, "models": {}, "errors": []}
    for model in models:
        try:
            answers, per_dim = [], {d: [] for d in DIMS}
            for q in questions:
                try:
                    res = ask_fn(model, q["text"])
                    # ask_fn may return plain text or {"text", "citations"} (ask_meta)
                    ans = res["text"] if isinstance(res, dict) else res
                    citations = (res.get("citations") or []) if isinstance(res, dict) else []
                    grounded = bool(res.get("grounded")) if isinstance(res, dict) else False
                    gerr = res.get("grounded_error") if isinstance(res, dict) else None
                    sc = score_answer(q, ans, judge_fn)
                except Exception as e:  # one flaky question must not sink the whole model battery
                    out["errors"].append(f"{model}/{q['id']}: {type(e).__name__}: {str(e)[:200]}")
                    continue
                per_dim[q["dimension"]].append(sc[q["dimension"]])
                answers.append({"id": q["id"], "question": q["text"], "answer": ans,
                                "dimension": q["dimension"],
                                "lang": q.get("lang", ""),
                                "segment": q.get("segment", "aspirational"),
                                "branded": is_branded(q["text"]),
                                "grounded": grounded, "grounded_error": gerr,
                                "scores": sc, "competitors": sc["competitors"], "gap_note": sc["gap_note"],
                                **_mention_fields(ans, citations)})
            if not answers:  # nothing succeeded — drop the model instead of reporting fake zeros
                out["errors"].append(f"{model}: probe failed (all questions failed)")
                continue
            dim_scores = {d: (round(mean(per_dim[d])) if per_dim[d] else 0) for d in DIMS}
            mentioned = sum(1 for a in answers if a["upe_mentioned"])
            cited = sum(1 for a in answers if a["upe_cited"])
            nonbranded = [a for a in answers if not a["branded"]]
            branded = [a for a in answers if a["branded"]]

            # An engine whose grounded call failed answered from frozen training recall.
            # Its scores describe our instrument, not our visibility -- say so.
            gerrs = [a["grounded_error"] for a in answers if a.get("grounded_error")]
            n_grounded = sum(1 for a in answers if a.get("grounded"))
            grounding_attempted = bool(gerrs) or n_grounded > 0
            degraded = grounding_attempted and n_grounded == 0

            out["models"][model] = {**dim_scores,
                                    "aeo": round(mean(dim_scores.values())),
                                    "mention_rate": _rate(mentioned, len(answers)),
                                    "citation_rate": _rate(cited, len(answers)),
                                    # headline: does an engine recommend us unprompted?
                                    "mention_rate_nonbranded": _rate(
                                        sum(1 for a in nonbranded if a["upe_mentioned"]), len(nonbranded)),
                                    "citation_rate_nonbranded": _rate(
                                        sum(1 for a in nonbranded if a["upe_cited"]), len(nonbranded)),
                                    "n_nonbranded": len(nonbranded),
                                    "mentioned_nonbranded": sum(1 for a in nonbranded if a["upe_mentioned"]),
                                    # separate line: does it know us when named?
                                    "brand_recall": _rate(
                                        sum(1 for a in branded if a["upe_mentioned"]), len(branded)),
                                    "n_branded": len(branded),
                                    "grounded_rate": _rate(n_grounded, len(answers)),
                                    "degraded": degraded,
                                    "degraded_reason": (gerrs[0] if degraded and gerrs else ""),
                                    "answers": answers}
            if degraded:
                out["errors"].append(
                    f"{model}: DEGRADED — grounded search failed on every question; "
                    f"scores are instrument error, not visibility ({gerrs[0] if gerrs else 'no citations returned'})")
        except Exception as e:  # a model with a bad/unbilled key must not crash the whole loop
            out["errors"].append(f"{model}: probe failed ({type(e).__name__}: {str(e)[:500]})")
    return out


def outreach_targets(scorecard, top=15):
    """Rank the third-party pages answer engines actually cite (excluding our own domain).
    This IS the outreach target list: get UPE onto these pages/domains."""
    from collections import Counter
    from urllib.parse import urlparse
    counts, examples = Counter(), {}
    for md in scorecard.get("models", {}).values():
        for a in md.get("answers", []):
            for u in a.get("cited_urls", []):
                host = (urlparse(u).netloc or "").replace("www.", "")
                if not host or "upe.co.il" in host:
                    continue
                counts[host] += 1
                examples.setdefault(host, u)
    return [{"domain": d, "citations": n, "example": examples[d]} for d, n in counts.most_common(top)]


def append_history(scorecard, path):
    p = Path(path)
    data = json.loads(p.read_text()) if p.exists() else []
    data.append(scorecard)
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
