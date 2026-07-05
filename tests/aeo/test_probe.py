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
    # judge returns the dimension's own score per question id
    table = {"a": 60, "b": 80, "c": 40, "d": 100}

    def judge_fn(prompt):
        qid = next(k for k in table if f'qid="{k}"' in prompt)
        dim = {"a": "product_search", "b": "product_search", "c": "comparison", "d": "reputation"}[qid]
        return json.dumps({"product_search": 0, "comparison": 0, "reputation": 0, dim: table[qid],
                           "competitors": [], "gap_note": ""})

    sc = p.run_probe(questions, ["claude"], ask_fn, judge_fn)
    cm = sc["models"]["claude"]
    assert cm["product_search"] == 70   # mean(60,80)
    assert cm["comparison"] == 40
    assert cm["reputation"] == 100
    assert cm["aeo"] == 70              # round(mean(70,40,100))


def test_run_probe_skips_failing_model_not_fatal():
    questions = [{"id": "a", "dimension": "product_search", "text": "q1"}]

    def ask_fn(model, text):
        if model == "chatgpt":
            raise RuntimeError("HTTP 401: no billing")
        return "ok answer"

    judge_fn = lambda prompt: json.dumps({"product_search": 50, "comparison": 0,
                                          "reputation": 0, "competitors": [], "gap_note": ""})
    sc = p.run_probe(questions, ["claude", "chatgpt"], ask_fn, judge_fn)
    assert "claude" in sc["models"]
    assert "chatgpt" not in sc["models"]          # failing model dropped, not fatal
    assert any("chatgpt" in e for e in sc["errors"])


def test_append_history_creates_and_appends(tmp_path):
    f = tmp_path / "hist.json"
    p.append_history({"date": "2026-06-28"}, str(f))
    p.append_history({"date": "2026-07-05"}, str(f))
    data = json.loads(f.read_text())
    assert len(data) == 2 and data[1]["date"] == "2026-07-05"


def test_score_answer_retries_judge_once_on_bad_json():
    import scripts.aeo_probe as probe
    calls = []

    def judge(prompt):
        calls.append(1)
        if len(calls) == 1:
            return '{"product_search": 5, broken'
        return '{"product_search":5,"comparison":0,"reputation":0,"competitors":[],"gap_note":""}'

    q = {"id": "x", "dimension": "product_search", "text": "q?"}
    sc = probe.score_answer(q, "ans", judge)
    assert sc["product_search"] == 5 and len(calls) == 2


def test_run_probe_isolates_flaky_question():
    import scripts.aeo_probe as probe

    def ask(model, text):
        return "answer"

    state = {"n": 0}

    def judge(prompt):
        state["n"] += 1
        if 'qid="q2"' in prompt:
            raise RuntimeError("boom")
        return '{"product_search":50,"comparison":0,"reputation":0,"competitors":[],"gap_note":""}'

    questions = [{"id": "q1", "dimension": "product_search", "text": "a"},
                 {"id": "q2", "dimension": "product_search", "text": "b"},
                 {"id": "q3", "dimension": "product_search", "text": "c"}]
    out = probe.run_probe(questions, ["claude"], ask, judge)
    assert "claude" in out["models"]
    assert len(out["models"]["claude"]["answers"]) == 2
    assert any("claude/q2" in e for e in out["errors"])
    assert out["models"]["claude"]["product_search"] == 50
