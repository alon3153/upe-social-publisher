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
    raw = judge_fn(prompt)
    data = _extract_json(raw)
    return {
        "product_search": int(data.get("product_search", 0)),
        "comparison": int(data.get("comparison", 0)),
        "reputation": int(data.get("reputation", 0)),
        "competitors": data.get("competitors", []) or [],
        "gap_note": data.get("gap_note", "") or "",
    }


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
                ans = ask_fn(model, q["text"])
                sc = score_answer(q, ans, judge_fn)
                per_dim[q["dimension"]].append(sc[q["dimension"]])
                answers.append({"id": q["id"], "question": q["text"], "answer": ans,
                                "scores": sc, "competitors": sc["competitors"], "gap_note": sc["gap_note"]})
            dim_scores = {d: (round(mean(per_dim[d])) if per_dim[d] else 0) for d in DIMS}
            out["models"][model] = {**dim_scores,
                                    "aeo": round(mean(dim_scores.values())),
                                    "answers": answers}
        except Exception as e:  # a model with a bad/unbilled key must not crash the whole loop
            out["errors"].append(f"{model}: probe failed ({type(e).__name__}: {str(e)[:500]})")
    return out


def append_history(scorecard, path):
    p = Path(path)
    data = json.loads(p.read_text()) if p.exists() else []
    data.append(scorecard)
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
