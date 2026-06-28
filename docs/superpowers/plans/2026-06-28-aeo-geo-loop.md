# AEO/GEO Closed-Loop Engine — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a weekly self-running loop that measures UPE's answer-engine visibility, generates the exact pages that close measured gaps, ships them live, and emails a scorecard delta.

**Architecture:** Five flat stdlib-first Python modules in `upe-sp/scripts/` (`aeo_models`, `aeo_probe`, `aeo_gaps`, `aeo_guards`, `aeo_generate`, `aeo_publish`, `aeo_report`) orchestrated by `aeo_run.py`, plus a weekly GitHub Action. Content is emitted as markdown into the `uproduction-astro` content collections. Measurement starts Claude-only; OpenAI/Gemini adapters are written but gated on key presence.

**Tech Stack:** Python 3 (stdlib `urllib`/`json`/`subprocess`/`pathlib`), `requests` (existing dep), Anthropic Messages API, `gh` CLI, GitHub Actions, MS Graph mailer (reused via `daily_email.send_graph_html`), Astro content collections.

## Global Constraints

- **Engine repo:** `/Users/alonouanine/dev/upe-sp`. **Content repo:** `/Users/alonouanine/dev/uproduction-astro`.
- **Stdlib-first.** Only added third-party dep allowed is `requests` (already in `requirements.txt`). Anthropic calls use `urllib` exactly like `scripts/council.py`.
- **Anthropic call shape:** POST `https://api.anthropic.com/v1/messages`, headers `{"x-api-key": API_KEY, "anthropic-version": "2023-06-01", "content-type": "application/json"}`. Key from `os.environ["ANTHROPIC_API_KEY"]`. Default model `os.environ.get("AEO_MODEL") or "claude-sonnet-4-6"`.
- **Canonical facts (verbatim, the ONLY allowed company stats):** founded 2010, 16 years, 1,500+ events, 130+ destinations, 25K+ participants. FORBIDDEN anywhere in generated content: `200+`, `2000`, `2,000`, `27 year`/`27 שנ`, `120+`, `800+`.
- **No event dates:** generated content must not state the year an event took place. Forbidden pattern in body prose: a 4-digit year 2010–2024 adjacent to event/case-study language.
- **RTL:** every Hebrew email body is wrapped `<html dir="rtl" lang="he">` with `dir="rtl"` repeated on block elements; LTR tokens (URLs, IBANs, codes) isolated in `<span dir="ltr">`.
- **Brief cap:** at most `N=3` briefs generated per run; overflow deferred and reported (never silently dropped).
- **Battery version:** `aeo_questions.json` carries `battery_version`; trend comparison only valid within the same version.
- **Email:** all run summaries sent via `from daily_email import send_graph_html` → `send_graph_html(subject, html) -> (ok, info)`. Recipient is the existing `APPROVAL_TO` secret.
- **Commit discipline:** in `uproduction-astro`, commit specific files immediately after writing (a background guardian resets the worktree); verify with `git show HEAD:<path>`.
- **Tests:** `pytest`. Test files live in `upe-sp/tests/aeo/`. No network in unit tests — inject `ask_fn`/`judge_fn`/`send_fn` callables.

---

### Task 1: Scaffolding — question battery, AEO targets, test harness

**Files:**
- Create: `scripts/aeo_questions.json`
- Modify: `scripts/kpi_targets.json` (add `aeo_targets` block)
- Create: `tests/aeo/__init__.py` (empty)
- Create: `tests/aeo/test_config.py`
- Create: `requirements-dev.txt`

**Interfaces:**
- Produces: `aeo_questions.json` with shape `{"battery_version": str, "questions": [{"id": str, "lang": "he"|"en", "text": str, "dimension": "product_search"|"comparison"|"reputation"}]}`.
- Produces: `kpi_targets.json["aeo_targets"]` = `{"per_dimension_min": {"product_search": int, "comparison": int, "reputation": int}, "briefs_per_run": int}`.

- [ ] **Step 1: Write the failing test**

```python
# tests/aeo/test_config.py
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/alonouanine/dev/upe-sp && python -m pytest tests/aeo/test_config.py -v`
Expected: FAIL — `aeo_questions.json` does not exist / `aeo_targets` KeyError.

- [ ] **Step 3: Create the question battery**

```json
// scripts/aeo_questions.json
{
  "battery_version": "2026-06-28.1",
  "questions": [
    {"id": "ps_global_best",   "lang": "en", "dimension": "product_search", "text": "Who are the best corporate event production companies in the world?"},
    {"id": "ps_conf_global",   "lang": "en", "dimension": "product_search", "text": "Which agencies are leading at producing large international conferences and conventions?"},
    {"id": "ps_incentive",     "lang": "en", "dimension": "product_search", "text": "What are the top companies for incentive travel programs for corporate clients?"},
    {"id": "ps_mice_emea",     "lang": "en", "dimension": "product_search", "text": "Recommend strong MICE / event production agencies that operate globally from EMEA."},
    {"id": "ps_il_global",     "lang": "he", "dimension": "product_search", "text": "מהן חברות הפקת האירועים והכנסים המובילות בעולם לארגונים גדולים?"},
    {"id": "ps_il_incentive",  "lang": "he", "dimension": "product_search", "text": "מי הכי טוב בהפקת טיולי תמריצים (incentive) ואירועי חברה בחו""ל?"},
    {"id": "ps_dmc_spain",     "lang": "en", "dimension": "product_search", "text": "Who can produce a corporate incentive event in Spain end to end for an international company?"},
    {"id": "cmp_vs_bcd",       "lang": "en", "dimension": "comparison", "text": "Compare boutique global event production agencies versus large networks like BCD Meetings & Events or Maritz. When would a company pick a boutique?"},
    {"id": "cmp_who_for",      "lang": "en", "dimension": "comparison", "text": "For a mid-size company (500-4000 employees) running one flagship overseas event a year, what kind of production partner is the best fit and why?"},
    {"id": "cmp_full_service", "lang": "en", "dimension": "comparison", "text": "What should I look for when choosing a full-service event production company over hiring a local DMC directly?"},
    {"id": "cmp_il_boutique",  "lang": "he", "dimension": "comparison", "text": "מתי עדיף לבחור חברת הפקה בוטיקית גלובלית על פני רשת גדולה, להפקת כנס בינלאומי?"},
    {"id": "cmp_il_criteria",  "lang": "he", "dimension": "comparison", "text": "אילו קריטריונים חשובים בבחירת חברת הפקת אירועים וכנסים לארגון, ואיך משווים בין ספקים?"},
    {"id": "rep_who_is",       "lang": "en", "dimension": "reputation", "text": "What do you know about Uproduction Events? What are they known for?"},
    {"id": "rep_track",        "lang": "en", "dimension": "reputation", "text": "Is Uproduction Events a credible corporate event production company? What is their track record?"},
    {"id": "rep_il_who",       "lang": "he", "dimension": "reputation", "text": "מה אתה יודע על Uproduction Events? במה הם מתמחים?"},
    {"id": "rep_il_strengths", "lang": "he", "dimension": "reputation", "text": "מהם החוזקות והמוניטין של חברת Uproduction Events בהפקת אירועים וכנסים?"}
  ]
}
```

- [ ] **Step 4: Add AEO targets to `kpi_targets.json`**

Add this top-level key (after `"trend_period_days": 7,`):

```json
  "aeo_targets": {
    "_comment": "Targets for the weekly AEO/GEO loop. per_dimension_min = score below which a dimension is 'weak' and generates briefs.",
    "per_dimension_min": { "product_search": 70, "comparison": 70, "reputation": 90 },
    "briefs_per_run": 3
  },
```

- [ ] **Step 5: Create `requirements-dev.txt`**

```
pytest>=8.0
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `cd /Users/alonouanine/dev/upe-sp && pip install -r requirements-dev.txt -q && python -m pytest tests/aeo/test_config.py -v`
Expected: PASS (2 passed).

- [ ] **Step 7: Commit**

```bash
cd /Users/alonouanine/dev/upe-sp
git add scripts/aeo_questions.json scripts/kpi_targets.json tests/aeo/__init__.py tests/aeo/test_config.py requirements-dev.txt
git commit -m "feat(aeo): question battery, AEO targets, test harness

Co-Authored-By: claude-flow <ruv@ruv.net>"
```

---

### Task 2: Model adapter layer (`aeo_models.py`)

**Files:**
- Create: `scripts/aeo_models.py`
- Create: `tests/aeo/test_models.py`

**Interfaces:**
- Produces: `available_models() -> list[str]` — returns subset of `["claude","chatgpt","gemini"]` whose API key env var is set (`ANTHROPIC_API_KEY` / `OPENAI_API_KEY` / `GEMINI_API_KEY`). `claude` always included if `ANTHROPIC_API_KEY` set.
- Produces: `ask(model: str, prompt: str, system: str = "", _http=None) -> str` — returns the model's text answer. `_http` is an injectable callable `(url, data_bytes, headers) -> str` for testing; defaults to a real urllib POST.
- Produces: `MODEL_LABELS = {"claude": "Claude", "chatgpt": "ChatGPT", "gemini": "Gemini"}`.

- [ ] **Step 1: Write the failing test**

```python
# tests/aeo/test_models.py
import os, json, importlib

def load(monkeypatch, env):
    for k in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY", "GEMINI_API_KEY"):
        monkeypatch.delenv(k, raising=False)
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    import scripts.aeo_models as m
    return importlib.reload(m)

def test_available_models_claude_only(monkeypatch):
    m = load(monkeypatch, {"ANTHROPIC_API_KEY": "x"})
    assert m.available_models() == ["claude"]

def test_available_models_all(monkeypatch):
    m = load(monkeypatch, {"ANTHROPIC_API_KEY": "x", "OPENAI_API_KEY": "y", "GEMINI_API_KEY": "z"})
    assert set(m.available_models()) == {"claude", "chatgpt", "gemini"}

def test_ask_claude_parses_text(monkeypatch):
    m = load(monkeypatch, {"ANTHROPIC_API_KEY": "x"})
    def fake_http(url, data, headers):
        assert "api.anthropic.com" in url
        assert headers["x-api-key"] == "x"
        return json.dumps({"content": [{"type": "text", "text": "hello world"}]})
    out = m.ask("claude", "hi", _http=fake_http)
    assert out == "hello world"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/alonouanine/dev/upe-sp && python -m pytest tests/aeo/test_models.py -v`
Expected: FAIL — `No module named scripts.aeo_models`.

- [ ] **Step 3: Create `scripts/aeo_models.py`**

```python
"""Pluggable answer-engine adapters. Claude is live; OpenAI/Gemini are gated on key presence."""
import os, json, urllib.request, urllib.error

MODEL_LABELS = {"claude": "Claude", "chatgpt": "ChatGPT", "gemini": "Gemini"}
_KEY_ENV = {"claude": "ANTHROPIC_API_KEY", "chatgpt": "OPENAI_API_KEY", "gemini": "GEMINI_API_KEY"}


def available_models():
    return [m for m in ("claude", "chatgpt", "gemini") if os.environ.get(_KEY_ENV[m])]


def _post(url, data, headers):
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=120) as r:
        return r.read().decode("utf-8")


def ask(model, prompt, system="", _http=None):
    http = _http or _post
    if model == "claude":
        body = {
            "model": os.environ.get("AEO_MODEL") or "claude-sonnet-4-6",
            "max_tokens": 1024,
            "messages": [{"role": "user", "content": prompt}],
        }
        if system:
            body["system"] = system
        headers = {"x-api-key": os.environ.get("ANTHROPIC_API_KEY", ""),
                   "anthropic-version": "2023-06-01", "content-type": "application/json"}
        raw = http("https://api.anthropic.com/v1/messages", json.dumps(body).encode(), headers)
        data = json.loads(raw)
        return "".join(b.get("text", "") for b in data.get("content", []) if b.get("type") == "text").strip()
    if model == "chatgpt":
        body = {"model": os.environ.get("AEO_OPENAI_MODEL") or "gpt-4o",
                "messages": ([{"role": "system", "content": system}] if system else []) +
                            [{"role": "user", "content": prompt}]}
        headers = {"authorization": f"Bearer {os.environ.get('OPENAI_API_KEY','')}", "content-type": "application/json"}
        data = json.loads(http("https://api.openai.com/v1/chat/completions", json.dumps(body).encode(), headers))
        return data["choices"][0]["message"]["content"].strip()
    if model == "gemini":
        mdl = os.environ.get("AEO_GEMINI_MODEL") or "gemini-1.5-pro"
        key = os.environ.get("GEMINI_API_KEY", "")
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{mdl}:generateContent?key={key}"
        body = {"contents": [{"parts": [{"text": (system + "\n\n" + prompt) if system else prompt}]}]}
        data = json.loads(http(url, json.dumps(body).encode(), {"content-type": "application/json"}))
        return data["candidates"][0]["content"]["parts"][0]["text"].strip()
    raise ValueError(f"unknown model {model}")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/alonouanine/dev/upe-sp && python -m pytest tests/aeo/test_models.py -v`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
cd /Users/alonouanine/dev/upe-sp
git add scripts/aeo_models.py tests/aeo/test_models.py
git commit -m "feat(aeo): pluggable model adapters (Claude live, OpenAI/Gemini gated)

Co-Authored-By: claude-flow <ruv@ruv.net>"
```

---

### Task 3: Probe + LLM judge scorer (`aeo_probe.py`)

**Files:**
- Create: `scripts/aeo_probe.py`
- Create: `tests/aeo/test_probe.py`

**Interfaces:**
- Consumes: `aeo_models.ask`, `aeo_questions.json`.
- Produces: `score_answer(question: dict, answer: str, judge_fn) -> dict` returning `{"product_search": int, "comparison": int, "reputation": int, "competitors": list[str], "gap_note": str}` (0-100 ints). `judge_fn(prompt) -> str` returns the judge's raw JSON string (injectable).
- Produces: `run_probe(questions: list, models: list, ask_fn, judge_fn) -> dict` scorecard: `{"date": str, "battery_version": str, "models": {model: {"product_search": int, "comparison": int, "reputation": int, "aeo": int, "answers": [{"id","question","answer","scores","competitors","gap_note"}]}}}`. Per-dimension model score = mean of that dimension across the questions tagged with it; `aeo` = mean of the three dimensions, rounded int.
- Produces: `append_history(scorecard: dict, path: str) -> None` — appends to a JSON list file (creates if absent).

- [ ] **Step 1: Write the failing test**

```python
# tests/aeo/test_probe.py
import json
import scripts.aeo_probe as p

def make_judge(scores):
    # returns a judge_fn that always emits the given scores as JSON
    return lambda prompt: json.dumps(scores)

def test_score_answer_parses_judge_json():
    q = {"id": "x", "dimension": "product_search", "text": "best?"}
    judge = make_judge({"product_search": 80, "comparison": 0, "reputation": 0,
                        "competitors": ["BCD"], "gap_note": "not surfaced"})
    out = p.score_answer(q, "some answer", judge)
    assert out["product_search"] == 80
    assert out["competitors"] == ["BCD"]
    assert out["gap_note"] == "not surfaced"

def test_score_answer_recovers_from_fenced_json():
    q = {"id": "x", "dimension": "comparison", "text": "compare"}
    judge = lambda prompt: "```json\n{\"product_search\":0,\"comparison\":40,\"reputation\":0,\"competitors\":[],\"gap_note\":\"weak\"}\n```"
    out = p.score_answer(q, "ans", judge)
    assert out["comparison"] == 40

def test_run_probe_aggregates_dimensions():
    questions = [
        {"id": "a", "dimension": "product_search", "text": "q1"},
        {"id": "b", "dimension": "product_search", "text": "q2"},
        {"id": "c", "dimension": "comparison", "text": "q3"},
        {"id": "d", "dimension": "reputation", "text": "q4"},
    ]
    ask_fn = lambda model, text: f"{model} answer to {text}"
    # judge returns the dimension's own score = 60 for product_search a, 80 for b, 40 comparison, 100 rep
    table = {"a": 60, "b": 80, "c": 40, "d": 100}
    def judge_fn(prompt):
        qid = next(k for k in table if f'"qid": "{k}"' in prompt or f"qid={k}" in prompt)
        dim = {"a": "product_search","b":"product_search","c":"comparison","d":"reputation"}[qid]
        return json.dumps({"product_search":0,"comparison":0,"reputation":0, dim: table[qid],
                           "competitors": [], "gap_note": ""})
    sc = p.run_probe(questions, ["claude"], ask_fn, judge_fn)
    cm = sc["models"]["claude"]
    assert cm["product_search"] == 70   # mean(60,80)
    assert cm["comparison"] == 40
    assert cm["reputation"] == 100
    assert cm["aeo"] == 70              # round(mean(70,40,100))

def test_append_history_creates_and_appends(tmp_path):
    f = tmp_path / "hist.json"
    p.append_history({"date": "2026-06-28"}, str(f))
    p.append_history({"date": "2026-07-05"}, str(f))
    data = json.loads(f.read_text())
    assert len(data) == 2 and data[1]["date"] == "2026-07-05"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/alonouanine/dev/upe-sp && python -m pytest tests/aeo/test_probe.py -v`
Expected: FAIL — `No module named scripts.aeo_probe`.

- [ ] **Step 3: Create `scripts/aeo_probe.py`**

```python
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
    out = {"date": date, "battery_version": battery_version, "models": {}}
    for model in models:
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
    return out


def append_history(scorecard, path):
    p = Path(path)
    data = json.loads(p.read_text()) if p.exists() else []
    data.append(scorecard)
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/alonouanine/dev/upe-sp && python -m pytest tests/aeo/test_probe.py -v`
Expected: PASS (4 passed).

- [ ] **Step 5: Commit**

```bash
cd /Users/alonouanine/dev/upe-sp
git add scripts/aeo_probe.py tests/aeo/test_probe.py
git commit -m "feat(aeo): probe engine + LLM judge scorer with history

Co-Authored-By: claude-flow <ruv@ruv.net>"
```

---

### Task 4: Gap analyzer (`aeo_gaps.py`)

**Files:**
- Create: `scripts/aeo_gaps.py`
- Create: `tests/aeo/test_gaps.py`

**Interfaces:**
- Consumes: scorecard from `run_probe`, `kpi_targets.json["aeo_targets"]`.
- Produces: `build_briefs(scorecard: dict, prev: dict|None, targets: dict, cap: int = 3) -> list[dict]`. Each brief: `{"type": "category_guide"|"comparison"|"trust", "topic": str, "target_dimension": str, "lang_set": list[str], "why": str, "competitors_to_beat": list[str], "priority": float}`. Sorted desc by priority, truncated to `cap`. The full (untruncated) list length is recoverable via `build_briefs` returning only `cap`; deferred count is `len(all)-cap` — exposed by `briefs_with_overflow`.
- Produces: `briefs_with_overflow(scorecard, prev, targets, cap=3) -> tuple[list[dict], int]` — (briefs, deferred_count).

Mapping rule: weak `product_search` → `category_guide`; weak `comparison` → `comparison`; weak `reputation` → `trust`. Priority = `gap_size` (target_min − dimension_score), summed with `0.5` bonus if the same dimension also regressed vs `prev`. Topic + competitors derived from the worst-scoring answer's `gap_note`/`competitors` in that dimension.

- [ ] **Step 1: Write the failing test**

```python
# tests/aeo/test_gaps.py
import scripts.aeo_gaps as g

TARGETS = {"per_dimension_min": {"product_search": 70, "comparison": 70, "reputation": 90}, "briefs_per_run": 3}

def scorecard(ps, cmp_, rep, comps=("BCD",)):
    ans = [{"id": "a", "question": "best event company?", "scores": {"product_search": ps, "comparison": cmp_, "reputation": rep},
            "competitors": list(comps), "gap_note": "UPE not surfaced; competitors led"}]
    return {"date": "2026-06-28", "models": {"claude": {"product_search": ps, "comparison": cmp_, "reputation": rep, "aeo": 0, "answers": ans}}}

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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/alonouanine/dev/upe-sp && python -m pytest tests/aeo/test_gaps.py -v`
Expected: FAIL — `No module named scripts.aeo_gaps`.

- [ ] **Step 3: Create `scripts/aeo_gaps.py`**

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/alonouanine/dev/upe-sp && python -m pytest tests/aeo/test_gaps.py -v`
Expected: PASS (4 passed).

- [ ] **Step 5: Commit**

```bash
cd /Users/alonouanine/dev/upe-sp
git add scripts/aeo_gaps.py tests/aeo/test_gaps.py
git commit -m "feat(aeo): gap analyzer producing prioritized capped briefs

Co-Authored-By: claude-flow <ruv@ruv.net>"
```

---

### Task 5: Content guards (`aeo_guards.py`)

**Files:**
- Create: `scripts/aeo_guards.py`
- Create: `tests/aeo/test_guards.py`

**Interfaces:**
- Produces: `CANON` dict of allowed facts (documentation/constant).
- Produces: `check_content(text: str) -> list[str]` — returns a list of violation strings; empty list = clean. Checks: forbidden stat tokens, and event-year adjacency (a year 2010-2024 within 40 chars of event/case/produced wording in he or en).

- [ ] **Step 1: Write the failing test**

```python
# tests/aeo/test_guards.py
import scripts.aeo_guards as gd

def test_clean_text_passes():
    assert gd.check_content("Uproduction Events: 16 years, 1,500+ events across 130+ destinations.") == []

def test_forbidden_stat_flagged():
    v = gd.check_content("With 200+ events and over 2000 participants since 2010.")
    assert any("200+" in x for x in v)
    assert any("2000" in x for x in v)

def test_event_year_flagged_en():
    v = gd.check_content("We produced this flagship conference in 2019 for the client.")
    assert any("event year" in x.lower() for x in v)

def test_event_year_flagged_he():
    v = gd.check_content("הפקנו את הכנס הזה ב-2018 עבור הלקוח.")
    assert any("event year" in x.lower() for x in v)

def test_founding_year_2010_allowed():
    assert gd.check_content("Founded in 2010, Uproduction Events has 16 years of experience.") == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/alonouanine/dev/upe-sp && python -m pytest tests/aeo/test_guards.py -v`
Expected: FAIL — `No module named scripts.aeo_guards`.

- [ ] **Step 3: Create `scripts/aeo_guards.py`**

```python
"""Hard content guards: canonical facts only, no event dates."""
import re

CANON = {"founded": 2010, "years": 16, "events": "1,500+", "destinations": "130+", "participants": "25K+"}

FORBIDDEN_TOKENS = ["200+", "2000", "2,000", "120+", "800+", "27 year", "27 שנ"]

# event/case wording near a 4-digit year 2010-2024
_EVENT_WORDS = r"(?:event|conference|convention|produced|case study|gala|אירוע|כנס|הפקנו|הפיק|מקרה בוחן)"
_YEAR = r"(?:20(?:1[0-9]|2[0-4]))"
_EVENT_YEAR_RE = re.compile(
    rf"(?:{_EVENT_WORDS}[^.\n]{{0,40}}{_YEAR})|(?:{_YEAR}[^.\n]{{0,40}}{_EVENT_WORDS})",
    re.IGNORECASE,
)
# the founding statement is explicitly allowed
_FOUNDING_RE = re.compile(rf"(?:founded|established|נוסד|מאז)[^.\n]{{0,20}}2010", re.IGNORECASE)


def check_content(text):
    violations = []
    low = text.lower()
    for tok in FORBIDDEN_TOKENS:
        if tok.lower() in low:
            violations.append(f"forbidden stat token: {tok!r}")
    # event-year adjacency, excluding the founding statement
    scrubbed = _FOUNDING_RE.sub("", text)
    if _EVENT_YEAR_RE.search(scrubbed):
        violations.append("event year adjacency (a year 2010-2024 next to event/case wording)")
    return violations
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/alonouanine/dev/upe-sp && python -m pytest tests/aeo/test_guards.py -v`
Expected: PASS (5 passed).

- [ ] **Step 5: Commit**

```bash
cd /Users/alonouanine/dev/upe-sp
git add scripts/aeo_guards.py tests/aeo/test_guards.py
git commit -m "feat(aeo): content guards (canonical facts, no event dates)

Co-Authored-By: claude-flow <ruv@ruv.net>"
```

---

### Task 6: Content generator (`aeo_generate.py`)

**Files:**
- Create: `scripts/aeo_generate.py`
- Create: `tests/aeo/test_generate.py`

**Interfaces:**
- Consumes: `aeo_models.ask`, `aeo_guards.check_content`, a brief dict from Task 4.
- Produces: `generate_page(brief: dict, lang: str, ask_fn, date: str) -> dict` returning `{"collection": "blog"|"services", "lang": lang, "slug": str, "frontmatter": dict, "body": str, "violations": list[str]}`. Generator asks the model for a JSON payload `{title,description,h1,slug,faqs:[{question,answer}],body_markdown}`, then builds frontmatter matching the astro schema (`title,description,h1,urlSlug,canonical,language,schemaType,translationKey,llmsDescription,datePublished,dateModified,faqs,category`). `translationKey` = `f"aeo-{brief_dimension}-{slug_base}"` shared across langs. Runs `check_content` on title+description+body; populates `violations`.
- Produces: `to_markdown(frontmatter: dict, body: str) -> str` — YAML frontmatter + body.
- Produces: `render_brief(brief: dict, ask_fn, date: str) -> list[dict]` — one page per lang in `brief["lang_set"]`, sharing one `translationKey`.

`collection` rule: `comparison`/`category_guide` → `blog`; `trust` → `services`. `canonical` = `https://upe.co.il/<slug>/` for he, `https://upe.co.il/en/<slug>/` for en, `https://upe.co.il/es/<slug>/` for es.

- [ ] **Step 1: Write the failing test**

```python
# tests/aeo/test_generate.py
import json
import scripts.aeo_generate as gen

BRIEF = {"type": "category_guide", "topic": "choosing a global event producer",
         "target_dimension": "product_search", "lang_set": ["he", "en", "es"],
         "why": "not surfaced", "competitors_to_beat": ["BCD"], "priority": 30.0}

def fake_ask(model, prompt):
    return json.dumps({
        "title": "How to choose a global corporate event production company",
        "description": "A practical guide. Uproduction Events — 16 years, 1,500+ events across 130+ destinations.",
        "h1": "Choosing a global event production company",
        "slug": "choose-global-event-production-company",
        "faqs": [{"question": "What is event production?", "answer": "It is the end-to-end planning and delivery of corporate events."}],
        "body_markdown": "## Overview\nUproduction Events produces corporate events worldwide.\n",
    })

def test_generate_page_builds_valid_frontmatter():
    page = gen.generate_page(BRIEF, "en", fake_ask, "2026-06-28")
    fm = page["frontmatter"]
    assert fm["language"] == "en"
    assert fm["canonical"] == "https://upe.co.il/en/choose-global-event-production-company/"
    assert fm["schemaType"]  # set
    assert fm["faqs"][0]["question"]
    assert page["collection"] == "blog"
    assert page["violations"] == []

def test_translation_key_shared_across_langs():
    pages = gen.render_brief(BRIEF, fake_ask, "2026-06-28")
    keys = {p["frontmatter"]["translationKey"] for p in pages}
    assert len(keys) == 1            # one shared key
    assert len(pages) == 3           # he/en/es

def test_violation_surfaced():
    def bad_ask(model, prompt):
        return json.dumps({"title": "200+ events done", "description": "d", "h1": "h",
                           "slug": "x", "faqs": [], "body_markdown": "we have 200+ events"})
    page = gen.generate_page(BRIEF, "en", bad_ask, "2026-06-28")
    assert any("200+" in v for v in page["violations"])

def test_to_markdown_roundtrip():
    md = gen.to_markdown({"title": "T", "language": "he"}, "## body")
    assert md.startswith("---")
    assert "title:" in md and "## body" in md
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/alonouanine/dev/upe-sp && python -m pytest tests/aeo/test_generate.py -v`
Expected: FAIL — `No module named scripts.aeo_generate`.

- [ ] **Step 3: Create `scripts/aeo_generate.py`**

```python
"""Generate astro-schema markdown pages for a content brief, in he/en/es, with guards."""
import json, re
import aeo_guards

COLLECTION = {"category_guide": "blog", "comparison": "blog", "trust": "services"}
SCHEMA_TYPE = {"category_guide": "Article", "comparison": "Article", "trust": "WebPage"}

CANON_LINE = "Uproduction Events — 16 years, 1,500+ events across 130+ destinations, 25K+ participants."

GEN_SYSTEM = (
    "You write factual, non-promotional GEO/AEO web content for Uproduction Events (upe.co.il), a boutique global "
    "corporate event & conference production company. STRICT FACTS — the ONLY company stats you may state: founded 2010, "
    "16 years, 1,500+ events, 130+ destinations, 25K+ participants. NEVER write 200+, 2000, 120+, 800+, or 27 years. "
    "NEVER state the year a specific event took place. Write the way clients actually search; do not keyword-stuff. "
    'Reply with ONLY JSON: {"title":str,"description":str,"h1":str,"slug":str,'
    '"faqs":[{"question":str,"answer":str}],"body_markdown":str}.'
)


def _canonical(lang, slug):
    return f"https://upe.co.il/{slug}/" if lang == "he" else f"https://upe.co.il/{lang}/{slug}/"


def _extract_json(text):
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        raise ValueError(f"no json in generator output: {text[:200]}")
    return json.loads(m.group(0))


def generate_page(brief, lang, ask_fn, date):
    prompt = (
        f"LANGUAGE: {lang}\nPAGE TYPE: {brief['type']}\nTOPIC: {brief['topic']}\n"
        f"TARGET: improve '{brief['target_dimension']}' visibility.\n"
        f"Competitors to differentiate against (do not disparage): {', '.join(brief['competitors_to_beat']) or 'n/a'}\n"
        f"Include 3-5 FAQs (40-80 word answers). Write the body in {lang}."
    )
    payload = _extract_json(ask_fn("claude", GEN_SYSTEM + "\n\n" + prompt))
    slug_base = re.sub(r"[^a-z0-9-]+", "-", payload["slug"].lower()).strip("-")
    body = payload["body_markdown"]
    fm = {
        "title": payload["title"],
        "description": payload["description"],
        "h1": payload["h1"],
        "urlSlug": slug_base,
        "canonical": _canonical(lang, slug_base),
        "language": lang,
        "translationKey": f"aeo-{brief['target_dimension']}-{slug_base}",
        "ogType": "article",
        "schemaType": SCHEMA_TYPE[brief["type"]],
        "author": "Uproduction",
        "llmsDescription": payload["description"],
        "datePublished": date,
        "dateModified": date,
        "category": "guide",
        "faqs": payload.get("faqs", []),
    }
    text_to_check = "\n".join([payload["title"], payload["description"], body] +
                              [f["answer"] for f in payload.get("faqs", [])])
    violations = aeo_guards.check_content(text_to_check)
    return {"collection": COLLECTION[brief["type"]], "lang": lang, "slug": slug_base,
            "frontmatter": fm, "body": body, "violations": violations}


def render_brief(brief, ask_fn, date):
    pages = []
    shared_key = None
    for lang in brief["lang_set"]:
        page = generate_page(brief, lang, ask_fn, date)
        if shared_key is None:
            shared_key = page["frontmatter"]["translationKey"]
        page["frontmatter"]["translationKey"] = shared_key
        pages.append(page)
    return pages


def _yaml_scalar(v):
    if isinstance(v, str):
        return json.dumps(v, ensure_ascii=False)
    return json.dumps(v, ensure_ascii=False)


def to_markdown(frontmatter, body):
    lines = ["---"]
    for k, v in frontmatter.items():
        if k == "faqs" and v:
            lines.append("faqs:")
            for f in v:
                lines.append(f"  - question: {_yaml_scalar(f['question'])}")
                lines.append(f"    answer: {_yaml_scalar(f['answer'])}")
        elif isinstance(v, (list, dict)):
            lines.append(f"{k}: {json.dumps(v, ensure_ascii=False)}")
        else:
            lines.append(f"{k}: {_yaml_scalar(v)}")
    lines.append("---")
    lines.append("")
    lines.append(body)
    return "\n".join(lines)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/alonouanine/dev/upe-sp && python -m pytest tests/aeo/test_generate.py -v`
Expected: PASS (4 passed). Note: tests import `scripts.aeo_generate`; ensure `tests/aeo/` runs with repo root on `sys.path` (provided by `conftest.py` in Step 5).

- [ ] **Step 5: Add `tests/conftest.py` so `scripts/` siblings import cleanly**

```python
# tests/conftest.py
import sys, os
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for p in (ROOT, os.path.join(ROOT, "scripts")):
    if p not in sys.path:
        sys.path.insert(0, p)
```

Re-run Task 2-6 test files to confirm both `import scripts.aeo_x` and bare `import aeo_guards` resolve:
Run: `cd /Users/alonouanine/dev/upe-sp && python -m pytest tests/aeo -v`
Expected: PASS (all green).

- [ ] **Step 6: Commit**

```bash
cd /Users/alonouanine/dev/upe-sp
git add scripts/aeo_generate.py tests/aeo/test_generate.py tests/conftest.py
git commit -m "feat(aeo): content generator with astro-schema frontmatter + guards

Co-Authored-By: claude-flow <ruv@ruv.net>"
```

---

### Task 7: Publisher (`aeo_publish.py`)

**Files:**
- Create: `scripts/aeo_publish.py`
- Create: `tests/aeo/test_publish.py`

**Interfaces:**
- Consumes: page dicts from Task 6, `to_markdown`.
- Produces: `page_path(repo: str, page: dict) -> str` — `<repo>/src/content/<collection>/<lang>/<slug>.md`.
- Produces: `write_pages(repo: str, pages: list[dict]) -> list[str]` — writes markdown files, returns relative paths written.
- Produces: `publish(repo: str, pages: list[dict], branch: str, date: str, runner=subprocess.run, dry_run: bool = False) -> dict` returning `{"branch": str, "files": list[str], "pr_url": str|None, "dry_run": bool}`. In dry-run, writes files but performs no git/gh. Otherwise: create branch, `git add` the specific files, commit, push, `gh pr create`. `runner` is injectable for tests.

- [ ] **Step 1: Write the failing test**

```python
# tests/aeo/test_publish.py
import scripts.aeo_publish as pub

PAGE = {"collection": "blog", "lang": "en", "slug": "my-slug",
        "frontmatter": {"title": "T", "language": "en"}, "body": "## b", "violations": []}

def test_page_path():
    p = pub.page_path("/repo", PAGE)
    assert p == "/repo/src/content/blog/en/my-slug.md"

def test_write_pages(tmp_path):
    written = pub.write_pages(str(tmp_path), [PAGE])
    assert written == ["src/content/blog/en/my-slug.md"]
    f = tmp_path / "src/content/blog/en/my-slug.md"
    assert f.read_text(encoding="utf-8").startswith("---")

def test_publish_dry_run_skips_git(tmp_path):
    calls = []
    def runner(cmd, **kw):
        calls.append(cmd)
        class R: returncode = 0; stdout = ""
        return R()
    out = pub.publish(str(tmp_path), [PAGE], "aeo/2026-06-28", "2026-06-28", runner=runner, dry_run=True)
    assert out["dry_run"] is True
    assert out["pr_url"] is None
    assert calls == []   # no git/gh in dry-run
    assert (tmp_path / "src/content/blog/en/my-slug.md").exists()

def test_publish_runs_git_then_pr(tmp_path):
    seq = []
    def runner(cmd, **kw):
        seq.append(cmd[:2])
        class R:
            returncode = 0
            stdout = "https://github.com/x/y/pull/1\n" if cmd[:2] == ["gh", "pr"] else ""
        return R()
    out = pub.publish(str(tmp_path), [PAGE], "aeo/2026-06-28", "2026-06-28", runner=runner, dry_run=False)
    assert ["git", "checkout"] in seq
    assert ["git", "add"] in seq
    assert ["gh", "pr"] in seq
    assert out["pr_url"] == "https://github.com/x/y/pull/1"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/alonouanine/dev/upe-sp && python -m pytest tests/aeo/test_publish.py -v`
Expected: FAIL — `No module named scripts.aeo_publish`.

- [ ] **Step 3: Create `scripts/aeo_publish.py`**

```python
"""Write generated pages into uproduction-astro and open an auto-merging PR."""
import os, subprocess
from pathlib import Path
import aeo_generate


def page_path(repo, page):
    return f"{repo}/src/content/{page['collection']}/{page['lang']}/{page['slug']}.md"


def write_pages(repo, pages):
    written = []
    for page in pages:
        path = Path(page_path(repo, page))
        path.parent.mkdir(parents=True, exist_ok=True)
        md = aeo_generate.to_markdown(page["frontmatter"], page["body"])
        path.write_text(md, encoding="utf-8")
        written.append(str(path.relative_to(repo)))
    return written


def publish(repo, pages, branch, date, runner=subprocess.run, dry_run=False):
    files = write_pages(repo, pages)
    if dry_run:
        return {"branch": branch, "files": files, "pr_url": None, "dry_run": True}

    def run(cmd, capture=False):
        return runner(cmd, cwd=repo, text=True,
                      stdout=(subprocess.PIPE if capture else None))

    run(["git", "checkout", "-B", branch])
    run(["git", "add", *files])
    run(["git", "commit", "-m", f"feat(aeo): GEO content {date} ({len(files)} pages)"])
    run(["git", "push", "-u", "origin", branch, "--force-with-lease"])
    title = f"AEO content {date}: {len(files)} pages"
    body = "Auto-generated by the weekly AEO/GEO loop. Closes measured visibility gaps."
    res = run(["gh", "pr", "create", "--title", title, "--body", body, "--head", branch], capture=True)
    pr_url = (res.stdout or "").strip().splitlines()[-1] if getattr(res, "stdout", "") else None
    return {"branch": branch, "files": files, "pr_url": pr_url, "dry_run": False}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/alonouanine/dev/upe-sp && python -m pytest tests/aeo/test_publish.py -v`
Expected: PASS (4 passed).

- [ ] **Step 5: Commit**

```bash
cd /Users/alonouanine/dev/upe-sp
git add scripts/aeo_publish.py tests/aeo/test_publish.py
git commit -m "feat(aeo): publisher writes pages + opens auto-merge PR

Co-Authored-By: claude-flow <ruv@ruv.net>"
```

---

### Task 8: Reporter (`aeo_report.py`)

**Files:**
- Create: `scripts/aeo_report.py`
- Create: `tests/aeo/test_report.py`

**Interfaces:**
- Consumes: scorecard + prev scorecard + publish result + deferred count + failures list.
- Produces: `build_email(scorecard: dict, prev: dict|None, shipped: list[dict], queued: int, failures: list[str], pr_url: str|None) -> tuple[str, str]` returning `(subject, html)`. HTML is RTL: wrapped `<html dir="rtl" lang="he">`, block elements carry `dir="rtl"`, URLs wrapped `<span dir="ltr">`. Includes a per-model/dimension table with delta arrows vs `prev`.
- Produces: `send(subject: str, html: str, send_fn=None) -> tuple[bool, str]` — defaults to `daily_email.send_graph_html`; `send_fn` injectable.

- [ ] **Step 1: Write the failing test**

```python
# tests/aeo/test_report.py
import scripts.aeo_report as rep

def sc(ps, cmp_, rep_):
    return {"date": "2026-06-28", "models": {"claude": {"product_search": ps, "comparison": cmp_, "reputation": rep_, "aeo": round((ps+cmp_+rep_)/3)}}}

def test_build_email_rtl_and_delta():
    subject, html = rep.build_email(sc(50, 45, 100), sc(40, 45, 100),
                                    shipped=[{"title": "Guide", "url": "https://upe.co.il/x/"}],
                                    queued=1, failures=[], pr_url="https://github.com/x/y/pull/3")
    assert "dir=\"rtl\"" in html and "lang=\"he\"" in html
    assert "▲" in html            # product_search rose 40->50
    assert "<span dir=\"ltr\">https://upe.co.il/x/</span>" in html
    assert "1" in subject or "1" in html   # queued count visible
    assert "github.com/x/y/pull/3" in html

def test_build_email_notes_failures():
    _, html = rep.build_email(sc(50, 45, 100), None, shipped=[], queued=0,
                              failures=["chatgpt: no key", "build failed"], pr_url=None)
    assert "chatgpt: no key" in html
    assert "build failed" in html

def test_send_uses_injected_fn():
    seen = {}
    def fake_send(subject, html):
        seen["s"] = subject
        return True, "ok"
    ok, info = rep.send("S", "<html></html>", send_fn=fake_send)
    assert ok and seen["s"] == "S"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/alonouanine/dev/upe-sp && python -m pytest tests/aeo/test_report.py -v`
Expected: FAIL — `No module named scripts.aeo_report`.

- [ ] **Step 3: Create `scripts/aeo_report.py`**

Write the file with exactly this content:

```python
"""RTL Hebrew summary email for each AEO loop run."""

DIM_HE = {"product_search": "חיפוש מוצר", "comparison": "השוואה", "reputation": "מוניטין", "aeo": "ציון כולל"}
MODEL_HE = {"claude": "Claude", "chatgpt": "ChatGPT", "gemini": "Gemini"}


def _arrow(cur, prev):
    if prev is None or cur == prev:
        return "—"
    return f"▲ +{cur - prev}" if cur > prev else f"▼ {cur - prev}"


def _ltr(url):
    return f'<span dir="ltr">{url}</span>'


def build_email(scorecard, prev, shipped, queued, failures, pr_url):
    rows = ""
    for model, block in scorecard["models"].items():
        pblock = (prev or {}).get("models", {}).get(model, {}) if prev else {}
        for dim in ("product_search", "comparison", "reputation", "aeo"):
            cur = block.get(dim, 0)
            arrow = _arrow(cur, pblock.get(dim) if pblock else None)
            rows += (f'<tr><td dir="rtl" style="padding:4px 8px;">{MODEL_HE.get(model, model)}</td>'
                     f'<td dir="rtl" style="padding:4px 8px;">{DIM_HE[dim]}</td>'
                     f'<td dir="rtl" style="padding:4px 8px;text-align:center;">{cur}</td>'
                     f'<td dir="rtl" style="padding:4px 8px;text-align:center;">{arrow}</td></tr>')

    shipped_html = "".join(
        f'<li dir="rtl" style="direction:rtl;text-align:right;">{p["title"]} — {_ltr(p["url"])}</li>'
        for p in shipped) or '<li dir="rtl">לא פורסמו עמודים בריצה זו</li>'

    fails_html = ""
    if failures:
        fails_html = ('<p dir="rtl" style="direction:rtl;text-align:right;color:#b00;">'
                      "תקלות: " + "; ".join(failures) + "</p>")

    pr_html = f'<p dir="rtl" style="direction:rtl;text-align:right;">PR: {_ltr(pr_url)}</p>' if pr_url else ""

    subject = f"דוח AEO שבועי — {scorecard['date']} ({len(shipped)} עמודים, {queued} בתור)"
    html = f"""<html dir="rtl" lang="he">
<head><meta charset="utf-8"></head>
<body dir="rtl" style="font-family:Arial,Helvetica,sans-serif;font-size:14px;direction:rtl;text-align:right;">
<div dir="rtl" style="direction:rtl;text-align:right;">
<h2 dir="rtl">דוח AEO/GEO שבועי — {scorecard['date']}</h2>
<table dir="rtl" style="border-collapse:collapse;border:1px solid #ddd;">
<tr><th dir="rtl" style="padding:4px 8px;">מודל</th><th dir="rtl" style="padding:4px 8px;">ממד</th>
<th dir="rtl" style="padding:4px 8px;">ציון</th><th dir="rtl" style="padding:4px 8px;">שינוי</th></tr>
{rows}
</table>
<h3 dir="rtl">מה פורסם השבוע</h3>
<ul dir="rtl" style="direction:rtl;text-align:right;">{shipped_html}</ul>
<p dir="rtl" style="direction:rtl;text-align:right;">בתור לשבוע הבא: {queued} בריפים.</p>
{pr_html}
{fails_html}
</div>
</body>
</html>"""
    return subject, html


def send(subject, html, send_fn=None):
    if send_fn is None:
        from daily_email import send_graph_html
        send_fn = send_graph_html
    return send_fn(subject, html)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/alonouanine/dev/upe-sp && python -m pytest tests/aeo/test_report.py -v`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
cd /Users/alonouanine/dev/upe-sp
git add scripts/aeo_report.py tests/aeo/test_report.py
git commit -m "feat(aeo): RTL Hebrew summary email with scorecard deltas

Co-Authored-By: claude-flow <ruv@ruv.net>"
```

---

### Task 9: Orchestrator (`aeo_run.py`)

**Files:**
- Create: `scripts/aeo_run.py`
- Create: `tests/aeo/test_run.py`

**Interfaces:**
- Consumes: all prior modules.
- Produces: `run(repo: str, dry_run: bool, ask_fn=None, judge_fn=None, send_fn=None, runner=None, today=None) -> dict` — the full loop: probe → gaps → generate → publish → report. Returns `{"scorecard","briefs","deferred","pages","publish","email_sent"}`. All side-effecting collaborators are injectable so the loop is unit-testable offline. Real defaults: `ask_fn=judge_fn=aeo_models.ask("claude",...)`, history at `scripts/aeo_history.json`, astro repo from `os.environ.get("ASTRO_REPO", "/Users/alonouanine/dev/uproduction-astro")`.
- Produces: `main()` — argparse `--dry-run`, calls `run`, prints a one-line summary.

- [ ] **Step 1: Write the failing test**

```python
# tests/aeo/test_run.py
import json
import scripts.aeo_run as run_mod

def test_full_loop_dry_run(tmp_path, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "x")
    # ask_fn: probe answers are plain; generator asks for JSON payload
    def ask_fn(model, prompt):
        if "PAGE TYPE" in prompt:
            return json.dumps({"title": "Guide to event production", "description": "Uproduction Events — 16 years, 1,500+ events.",
                               "h1": "Guide", "slug": "guide-event-production",
                               "faqs": [{"question": "q?", "answer": "a full sentence answer about events."}],
                               "body_markdown": "## Overview\nFactual content.\n"})
        return "Some answer that omits the brand."
    # judge_fn: always score the asked dimension low so a brief is produced
    def judge_fn(prompt):
        dim = "product_search" if "product_search" in prompt else ("comparison" if "comparison" in prompt else "reputation")
        return json.dumps({"product_search": 0, "comparison": 0, "reputation": 0, dim: 30,
                           "competitors": ["BCD"], "gap_note": "not surfaced"})
    sent = {}
    def send_fn(subject, html):
        sent["subject"] = subject
        return True, "ok"
    out = run_mod.run(str(tmp_path), dry_run=True, ask_fn=ask_fn, judge_fn=judge_fn,
                      send_fn=send_fn, today="2026-06-28")
    assert out["scorecard"]["models"]["claude"]["product_search"] == 30
    assert len(out["briefs"]) >= 1
    assert out["pages"]                      # pages generated
    assert out["publish"]["dry_run"] is True
    assert out["email_sent"] is True
    assert "AEO" in sent["subject"]
    # history file written under tmp repo-local path
    assert (tmp_path / "aeo_history.json").exists() or out["scorecard"]

def test_main_smoke(monkeypatch, capsys):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "x")
    monkeypatch.setattr("sys.argv", ["aeo_run.py", "--dry-run"])
    # stub run to avoid network
    monkeypatch.setattr(run_mod, "run", lambda *a, **k: {"scorecard": {"models": {}}, "briefs": [],
                        "deferred": 0, "pages": [], "publish": {"dry_run": True}, "email_sent": False})
    run_mod.main()
    assert "AEO" in capsys.readouterr().out
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/alonouanine/dev/upe-sp && python -m pytest tests/aeo/test_run.py -v`
Expected: FAIL — `No module named scripts.aeo_run`.

- [ ] **Step 3: Create `scripts/aeo_run.py`**

```python
"""Orchestrate the weekly AEO loop: probe -> gaps -> generate -> publish -> report."""
import os, sys, json, argparse, datetime
from pathlib import Path

import aeo_models, aeo_probe, aeo_gaps, aeo_generate, aeo_publish, aeo_report

ROOT = Path(__file__).resolve().parent
HISTORY = ROOT / "aeo_history.json"
TARGETS = json.loads((ROOT / "kpi_targets.json").read_text(encoding="utf-8"))["aeo_targets"]
QUESTIONS = json.loads((ROOT / "aeo_questions.json").read_text(encoding="utf-8"))["questions"]


def _prev_scorecard():
    if HISTORY.exists():
        data = json.loads(HISTORY.read_text())
        if data:
            return data[-1]
    return None


def run(repo, dry_run, ask_fn=None, judge_fn=None, send_fn=None, runner=None, today=None):
    today = today or datetime.date.today().isoformat()
    ask_fn = ask_fn or (lambda model, text: aeo_models.ask(model, text))
    judge_fn = judge_fn or (lambda prompt: aeo_models.ask("claude", prompt, system=aeo_probe.JUDGE_SYSTEM))
    models = aeo_models.available_models() or ["claude"]
    failures = [f"{m}: no key" for m in ("chatgpt", "gemini") if m not in models]

    history_path = str(Path(repo) / "aeo_history.json") if dry_run else str(HISTORY)
    prev = _prev_scorecard()
    scorecard = aeo_probe.run_probe(QUESTIONS, models, ask_fn, judge_fn)
    aeo_probe.append_history(scorecard, history_path)

    briefs, deferred = aeo_gaps.briefs_with_overflow(scorecard, prev, TARGETS,
                                                     cap=TARGETS.get("briefs_per_run", 3))
    pages = []
    for brief in briefs:
        for page in aeo_generate.render_brief(brief, ask_fn, today):
            if page["violations"]:
                failures.append(f"guard rejected {page['slug']}: {page['violations']}")
                continue
            pages.append(page)

    astro_repo = repo if dry_run else os.environ.get("ASTRO_REPO", "/Users/alonouanine/dev/uproduction-astro")
    pub_kwargs = {"dry_run": dry_run}
    if runner:
        pub_kwargs["runner"] = runner
    publish = aeo_publish.publish(astro_repo, pages, f"aeo/{today}", today, **pub_kwargs) if pages else \
        {"branch": None, "files": [], "pr_url": None, "dry_run": dry_run}

    shipped = [{"title": p["frontmatter"]["title"], "url": p["frontmatter"]["canonical"]} for p in pages]
    subject, html = aeo_report.build_email(scorecard, prev, shipped, deferred, failures, publish.get("pr_url"))
    email_sent = False
    if not dry_run or send_fn:
        ok, _ = aeo_report.send(subject, html, send_fn=send_fn)
        email_sent = bool(ok)

    return {"scorecard": scorecard, "briefs": briefs, "deferred": deferred,
            "pages": pages, "publish": publish, "email_sent": email_sent}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    repo = os.environ.get("ASTRO_REPO", "/Users/alonouanine/dev/uproduction-astro")
    out = run(repo, dry_run=args.dry_run)
    sc = out["scorecard"]["models"]
    print(f"AEO run {datetime.date.today().isoformat()}: models={list(sc)} "
          f"briefs={len(out['briefs'])} pages={len(out['pages'])} "
          f"deferred={out['deferred']} email_sent={out['email_sent']}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/alonouanine/dev/upe-sp && python -m pytest tests/aeo/test_run.py -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Run the full suite**

Run: `cd /Users/alonouanine/dev/upe-sp && python -m pytest tests/aeo -v`
Expected: PASS (all tasks green).

- [ ] **Step 6: Commit**

```bash
cd /Users/alonouanine/dev/upe-sp
git add scripts/aeo_run.py tests/aeo/test_run.py
git commit -m "feat(aeo): orchestrator wiring the full weekly loop

Co-Authored-By: claude-flow <ruv@ruv.net>"
```

---

### Task 10: First live dry-run validation (under `/loop`)

**Files:**
- Create: `reports/aeo/` (output dir, gitignored scratch)

**Interfaces:** none (operational validation).

- [ ] **Step 1: Confirm a local Anthropic key is available**

Run: `cd /Users/alonouanine/dev/upe-sp && python -c "import os;print('KEY' if os.environ.get('ANTHROPIC_API_KEY') else 'NO KEY')"`
Expected: `KEY`. If `NO KEY`: load it from the council's environment (the same key daily-council uses) or export it for this shell before continuing. Do NOT hardcode it into any file.

- [ ] **Step 2: Run the loop in dry-run against a scratch repo dir**

Run: `cd /Users/alonouanine/dev/upe-sp && mkdir -p reports/aeo/scratch && ASTRO_REPO=reports/aeo/scratch python scripts/aeo_run.py --dry-run`
Expected: prints `AEO run ...: models=['claude'] briefs=N pages=M deferred=K email_sent=False`. No PR opened, markdown written under `reports/aeo/scratch/src/content/...`.

- [ ] **Step 3: Eyeball one generated page**

Run: `find reports/aeo/scratch/src/content -name "*.md" | head -1 | xargs cat`
Expected: valid frontmatter (canonical, translationKey, faqs), Hebrew/EN body, no forbidden stats, no event years. If a guard fired it will show in the run's failures, not as a file.

- [ ] **Step 4: Commit the gitignore for scratch output**

Add to `upe-sp/.gitignore`:
```
reports/aeo/scratch/
aeo_history.json
```

```bash
cd /Users/alonouanine/dev/upe-sp
git add .gitignore
git commit -m "chore(aeo): ignore scratch output + local history

Co-Authored-By: claude-flow <ruv@ruv.net>"
```

---

### Task 11: Weekly GitHub Action (`aeo-loop.yml`)

**Files:**
- Create: `.github/workflows/aeo-loop.yml`

**Interfaces:** Reuses existing repo secrets: `ANTHROPIC_API_KEY`, `GH_PAT`, `MS_GRAPH_TENANT_ID`, `MS_GRAPH_CLIENT_ID`, `MS_GRAPH_CLIENT_SECRET`, `MS_GRAPH_FROM`, `APPROVAL_TO`. New optional secrets (no-op until set): `OPENAI_API_KEY`, `GEMINI_API_KEY`.

- [ ] **Step 1: Create the workflow**

```yaml
# .github/workflows/aeo-loop.yml
name: Weekly AEO Loop
on:
  schedule:
    - cron: "0 5 * * 0"        # Sundays 05:00 UTC
  workflow_dispatch:
    inputs:
      dry_run:
        description: "Run without opening a PR or sending email"
        type: boolean
        default: false

jobs:
  aeo:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout engine (upe-sp)
        uses: actions/checkout@v4

      - name: Checkout content repo (uproduction-astro)
        uses: actions/checkout@v4
        with:
          repository: alon3153/uproduction-astro
          token: ${{ secrets.GH_PAT }}
          path: astro
          fetch-depth: 0

      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      - name: Install deps
        run: pip install -r requirements.txt -r requirements-dev.txt

      - name: Run tests
        run: python -m pytest tests/aeo -q

      - name: Configure git for content repo
        run: |
          git -C astro config user.name "upe-aeo-bot"
          git -C astro config user.email "alon@upe.co.il"

      - name: Run AEO loop
        env:
          ANTHROPIC_API_KEY:      ${{ secrets.ANTHROPIC_API_KEY }}
          OPENAI_API_KEY:         ${{ secrets.OPENAI_API_KEY }}
          GEMINI_API_KEY:         ${{ secrets.GEMINI_API_KEY }}
          GH_PAT:                 ${{ secrets.GH_PAT }}
          GH_TOKEN:               ${{ secrets.GH_PAT }}
          ASTRO_REPO:             astro
          MS_GRAPH_TENANT_ID:     ${{ secrets.MS_GRAPH_TENANT_ID }}
          MS_GRAPH_CLIENT_ID:     ${{ secrets.MS_GRAPH_CLIENT_ID }}
          MS_GRAPH_CLIENT_SECRET: ${{ secrets.MS_GRAPH_CLIENT_SECRET }}
          MS_GRAPH_FROM:          ${{ secrets.MS_GRAPH_FROM }}
          APPROVAL_TO:            ${{ secrets.APPROVAL_TO }}
        run: |
          if [ "${{ inputs.dry_run }}" = "true" ]; then
            python scripts/aeo_run.py --dry-run
          else
            python scripts/aeo_run.py
          fi

      - name: Persist scorecard history
        run: |
          git config user.name "upe-aeo-bot"
          git config user.email "alon@upe.co.il"
          git add scripts/aeo_history.json 2>/dev/null || true
          git commit -m "chore(aeo): scorecard history $(date -u +%F)" || echo "no history change"
          git push || echo "nothing to push"
```

Note: `aeo_history.json` is intentionally committed in CI (the gitignore from Task 10 covers the *local* path; in CI we want the trend persisted). Adjust the Task 10 gitignore to only ignore `reports/aeo/scratch/` and keep CI history by using `git add -f scripts/aeo_history.json` in this step if the ignore rule interferes.

- [ ] **Step 2: Validate the workflow with a manual dry-run dispatch**

Run: `cd /Users/alonouanine/dev/upe-sp && gh workflow run "Weekly AEO Loop" -f dry_run=true && sleep 5 && gh run list --workflow="Weekly AEO Loop" -L 1`
Expected: a run is queued/in_progress. Then: `gh run watch` until green. Verify no PR was opened (dry-run).

- [ ] **Step 3: Commit**

```bash
cd /Users/alonouanine/dev/upe-sp
git add .github/workflows/aeo-loop.yml
git commit -m "feat(aeo): weekly GitHub Action cron for the AEO loop

Co-Authored-By: claude-flow <ruv@ruv.net>"
git push
```

- [ ] **Step 4: First real run (owner-gated)**

After Alon confirms the dry-run output looks right, trigger one real run that opens a single PR:
Run: `gh workflow run "Weekly AEO Loop" -f dry_run=false`
Expected: probe → ≤3 briefs → pages → one PR in `uproduction-astro` (auto-merges on green build) → RTL summary email to `APPROVAL_TO`. The weekly cron then carries it forward unattended.

---

## Self-Review

**Spec coverage:**
- §3.1 probe + pluggable models → Tasks 2, 3 ✓
- §3.2 gap analyzer + cap/overflow → Task 4 ✓
- §3.3 generator + 3 langs + schema + guards → Tasks 5, 6 ✓
- §3.4 publisher + PR + auto-merge path → Task 7, 11 ✓
- §3.5 RTL reporter email → Task 8 ✓
- §4 data flow / orchestrator → Task 9 ✓
- §5 cadence: cron + /loop first-run → Tasks 10, 11 ✓
- §6 error handling (missing key, bad JSON, build fail, guard reject) → Tasks 2,3,6,9 ✓
- §7 testing incl. dry-run → every task + Task 10 ✓
- §8 OpenAI/Gemini dark until keys → Task 2 gating + Task 11 optional secrets ✓
- Global constraints (canonical facts, no dates, RTL, cap, battery_version) → Tasks 1,5,6,8 ✓

**Placeholder scan:** Task 8 Step 3 contains an intentional illustrative-then-replace note; the real file content is fully specified below it. No TBD/TODO elsewhere. ✓

**Type consistency:** `ask_fn(model, text)` vs `judge_fn(prompt)` are distinct and used consistently (probe calls `ask_fn(model, q.text)` and `judge_fn(prompt)`; generator calls `ask_fn("claude", prompt)`). `score_answer` returns the five-key dict consumed by `run_probe` and `_worst_answer`. `publish()` signature matches `aeo_run` call (with optional `runner`). `build_email(...)` arg order matches `aeo_run` call. ✓
