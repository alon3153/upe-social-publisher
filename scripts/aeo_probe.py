"""Probe answer engines with the question battery and score each answer with an LLM judge."""
import json, re, datetime
from pathlib import Path
from statistics import mean
try:
    from aeo_models import redact_obj
except ImportError:  # imported as scripts.aeo_probe (tests)
    from scripts.aeo_models import redact_obj

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


_FATAL_RE = re.compile(r"HTTP (401|403)\b|insufficient_quota|no credits remaining|"
                       r"credit balance is too low|API key not valid", re.I)


def _is_fatal(exc):
    """Auth/billing errors that will hit every question identically (not a transient 429)."""
    return bool(_FATAL_RE.search(str(exc)))


def run_probe(questions, models, ask_fn, judge_fn, on_date=None):
    # on_date is the run's calendar day (UTC in the daily workflow). Callers that
    # omit it keep the previous behaviour: the machine-local date.
    if on_date is None:
        date = datetime.date.today().isoformat()
    elif isinstance(on_date, datetime.datetime):
        date = on_date.date().isoformat()
    elif isinstance(on_date, datetime.date):
        date = on_date.isoformat()
    else:
        date = str(on_date)[:10]
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
                    if _is_fatal(e):  # dead key / no credit: every other question fails the same way
                        out["errors"].append(f"{model}: dead key or no credit, battery aborted "
                                             f"({type(e).__name__}: {str(e)[:300]})")
                        break
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


# Conservative reviewed domains: a citation alone does not establish outreach suitability.
EDITORIAL_DOMAINS = {'bizbash.com', 'ctech.com', 'calcalistech.com', 'pcma.org', 'mpi.org'}
DIRECTORY_DOMAINS = {'clutch.co', 'sortlist.com'}
COMPETITOR_DOMAINS = {'corporateoptics.com', 'gogather.com', 'naboo.app', 'pinchevents.co.il',
                      'bcdme.com', 'promarket.co.il', 'eron.co.il', 'mci-group.com', 'kenes.com'}


def citation_kind(host):
    for domains, kind in ((COMPETITOR_DOMAINS, 'competitor'), (EDITORIAL_DOMAINS, 'editorial'),
                          (DIRECTORY_DOMAINS, 'directory')):
        if any(host == d or host.endswith('.' + d) for d in domains):
            return kind
    return 'unverified'


def outreach_targets(scorecard, top=15):
    """Rank the third-party pages answer engines actually cite (excluding our own domain).
    Each domain is classified; only reviewed editorial/directory sources are candidates."""
    from collections import Counter
    from urllib.parse import urlparse
    counts, examples = Counter(), {}
    for md in scorecard.get("models", {}).values():
        if md.get("degraded"):
            continue
        for a in md.get("answers", []):
            for u in a.get("cited_urls", []):
                host = (urlparse(u).hostname or "").lower().removeprefix("www.")
                if not host or host == "upe.co.il" or host.endswith(".upe.co.il"):
                    continue
                counts[host] += 1
                examples.setdefault(host, u)
    return [{"domain": d, "citations": n, "example": examples[d], "kind": citation_kind(d),
             "outreach_eligible": citation_kind(d) in ("editorial", "directory")} for d, n in counts.most_common(top)]


def append_history(scorecard, path):
    p = Path(path)
    data = json.loads(p.read_text()) if p.exists() else []
    data.append(redact_obj(scorecard))  # never persist a key echoed in an error string
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


# ChatGPT is probed Monday, Wednesday and Friday only. The status is a
# non-measurement: readers must not treat it as a zero, a 429, or a failure.
SKIPPED_SCHEDULE = "skipped_schedule"
CHATGPT_WEEKDAYS = (0, 2, 4)  # Monday, Wednesday, Friday (date.weekday)
_MEASURED_FIELDS = ("mention_rate_nonbranded", "product_search")


def is_skipped_schedule(block):
    return isinstance(block, dict) and block.get("status") == SKIPPED_SCHEDULE


def model_ran(block):
    """A real probe result. Legacy rows have no status and still count.

    `skipped_schedule` is an intentional day off. It has no score, so it cannot
    enter an average or a trend.
    """
    if not isinstance(block, dict) or is_skipped_schedule(block):
        return False
    for field in _MEASURED_FIELDS:
        value = block.get(field)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return True
    return False


def skipped_schedule_block(model="chatgpt"):
    return {
        "status": SKIPPED_SCHEDULE,
        "reason": "not scheduled",
        "model": model,
        "schedule": "Mon/Wed/Fri 06:00 UTC",
    }


def chatgpt_scheduled(day):
    """True on Monday, Wednesday and Friday of the run's UTC calendar date."""
    if isinstance(day, datetime.datetime):
        if day.tzinfo is not None:
            day = day.astimezone(datetime.timezone.utc)
        day = day.date()
    elif isinstance(day, str):
        day = datetime.date.fromisoformat(day[:10])
    elif not isinstance(day, datetime.date):
        raise TypeError(f"expected a date, got {type(day).__name__}")
    return day.weekday() in CHATGPT_WEEKDAYS


def _as_date(value):
    if isinstance(value, datetime.datetime):
        return value.date()
    if isinstance(value, datetime.date):
        return value
    return datetime.date.fromisoformat(str(value)[:10])


def seven_day_stats(history, model, field, end_date, days=7, battery_version=None):
    """Mean of `field` over the inclusive window, using only days the model ran.

    Skipped-schedule rows are omitted from the sum and the count. When
    `battery_version` is set, rows from another methodology are omitted too.
    """
    end = _as_date(end_date)
    start = end - datetime.timedelta(days=days - 1)
    values = []
    for row in history or []:
        if not isinstance(row, dict):
            continue
        try:
            stamp = _as_date(row.get("date"))
        except (TypeError, ValueError):
            continue
        if stamp < start or stamp > end:
            continue
        if battery_version and row.get("battery_version") != battery_version:
            continue
        block = (row.get("models") or {}).get(model)
        if not model_ran(block):
            continue
        value = block.get(field)
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            continue
        values.append(value)
    average = round(sum(values) / len(values), 1) if values else None
    return {"average": average, "days": len(values)}


def last_ran(history, model, before_date):
    """Latest measured block strictly before `before_date`.

    Returns (block, iso_date, battery_version). Skipped days are not candidates.
    """
    try:
        cutoff = _as_date(before_date)
    except (TypeError, ValueError):
        return None, None, None
    found = found_date = found_battery = None
    for row in history or []:
        if not isinstance(row, dict):
            continue
        try:
            stamp = _as_date(row.get("date"))
        except (TypeError, ValueError):
            continue
        if stamp >= cutoff:
            continue
        block = (row.get("models") or {}).get(model)
        if not model_ran(block):
            continue
        if found_date is None or stamp > found_date:
            found, found_date, found_battery = block, stamp, row.get("battery_version")
    return found, (found_date.isoformat() if found_date else None), found_battery
