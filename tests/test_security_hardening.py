"""Regression tests for the OWASP Top 10:2025 hardening (audit of 2026-09).

Each test pins one fixed finding so it cannot silently come back:
  * A02 Security Misconfiguration — workflow permissions, dispatch inputs never
    interpolated into shell, actor gate on secret-bearing dispatch jobs.
  * A05 Injection — HTML built from LLM / DB / API text is escaped; the OAuth
    callback pages render URL values with DOM APIs only.
  * A03 Supply chain — dependency floor, no unpinned third-party import in the
    approve function.
  * A07 Authentication — the LinkedIn connect flow carries a CSRF nonce cookie.
  * A10 Exceptional conditions — every urllib call has a timeout.
"""
import ast
import glob
import json
import os
import re

import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORKFLOWS = sorted(glob.glob(os.path.join(ROOT, ".github", "workflows", "*.yml")))
INPUT_EXPR = re.compile(r"\$\{\{[^}]*\b(inputs|github\.event\.inputs)\b")


def _load(path):
    with open(path, encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def _text(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def test_every_workflow_declares_top_level_permissions():
    missing = [os.path.basename(p) for p in WORKFLOWS if "permissions" not in _load(p)]
    assert not missing, f"workflows relying on the default GITHUB_TOKEN grant: {missing}"


def test_dispatch_inputs_never_reach_a_run_block_unescaped():
    """`${{ inputs.x }}` inside `run:` is shell injection by whoever can dispatch.
    Inputs must be passed through `env:` and read as "$VAR"."""
    offenders = []
    for path in WORKFLOWS:
        wf = _load(path)
        for job_name, job in (wf.get("jobs") or {}).items():
            for step in job.get("steps") or []:
                run = step.get("run")
                if isinstance(run, str) and INPUT_EXPR.search(run):
                    offenders.append(f"{os.path.basename(path)}:{job_name}:{step.get('name') or 'run'}")
    assert not offenders, offenders


def test_secret_bearing_dispatch_jobs_are_gated_on_the_owner():
    """Manual runs that receive repository secrets are limited to the owner, so a
    future collaborator (or a compromised account with write access) cannot use
    workflow_dispatch to exercise publishing tokens or API keys."""
    ungated = []
    for path in WORKFLOWS:
        wf = _load(path)
        on = wf.get("on") or wf.get(True) or {}
        if "workflow_dispatch" not in (on if isinstance(on, dict) else {}) and on != "workflow_dispatch":
            continue
        for job_name, job in (wf.get("jobs") or {}).items():
            uses_secrets = "secrets." in json.dumps(job)
            if not uses_secrets:
                continue
            cond = str(job.get("if") or "")
            if "github.actor" not in cond:
                ungated.append(f"{os.path.basename(path)}:{job_name}")
    assert not ungated, ungated


def _urlopen_calls_without_timeout(path):
    tree = ast.parse(_text(path), filename=path)
    bad = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            fn = node.func
            name = fn.attr if isinstance(fn, ast.Attribute) else getattr(fn, "id", "")
            if name == "urlopen" and not any(k.arg == "timeout" for k in node.keywords):
                bad.append(f"{os.path.relpath(path, ROOT)}:{node.lineno}")
    return bad


def test_every_urlopen_has_a_timeout():
    files = glob.glob(os.path.join(ROOT, "publishers", "*.py")) + glob.glob(os.path.join(ROOT, "scripts", "*.py"))
    bad = [b for f in files for b in _urlopen_calls_without_timeout(f)]
    assert not bad, f"urllib calls that can hang a publisher run forever: {bad}"


def test_requests_calls_have_a_timeout():
    files = glob.glob(os.path.join(ROOT, "publishers", "*.py"))
    bad = []
    for f in files:
        tree = ast.parse(_text(f))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                if (isinstance(node.func.value, ast.Name) and node.func.value.id == "requests"
                        and node.func.attr in ("get", "post", "put", "patch", "delete")
                        and not any(k.arg == "timeout" for k in node.keywords)):
                    bad.append(f"{os.path.relpath(f, ROOT)}:{node.lineno}")
    assert not bad, bad


def test_daily_email_card_escapes_caption_and_attributes():
    from scripts import daily_email
    row = {"id": 1, "token": "t", "network": "linkedin", "lang": '"><b>x',
           "caption": '<script>alert(1)</script> "quoted" & more\nline2',
           "image_url": 'https://x/img.png" onerror="alert(1)'}
    html = daily_email.post_card(row)
    assert "<script>" not in html
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html
    assert 'onerror="alert' not in html
    assert "line2" in html and "<br>" in html  # newlines still become line breaks


def test_executor_digest_escapes_model_output():
    from scripts import executor
    it = {"id": "abc12345", "priority": "P0<img src=x>", "title": "<script>bad()</script>", "status": "in_progress"}
    res = {"summary": '"><iframe src=evil>', "open_questions": ["<b>q</b>"], "ready_for_approval": False}
    html = executor.render_html({it["id"]: it}, [(it, res)])
    for raw in ("<script>bad()", "<iframe", "<img src=x>", "<b>q</b>"):
        assert raw not in html
    assert "&lt;script&gt;bad()" in html


def test_watchdog_alert_email_escapes_issue_text(monkeypatch):
    from scripts import watchdog
    for var in ("MS_GRAPH_TENANT_ID", "MS_GRAPH_CLIENT_ID", "MS_GRAPH_CLIENT_SECRET", "MS_GRAPH_FROM"):
        monkeypatch.setenv(var, "x")
    sent = []

    class _Resp:
        status = 202
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def read(self): return json.dumps({"access_token": "tok"}).encode()

    def fake_urlopen(req, timeout=None):
        sent.append(req)
        return _Resp()

    monkeypatch.setattr(watchdog.urllib.request, "urlopen", fake_urlopen)
    assert watchdog.send_graph("subj", "🔴 day 1 — <script>alert(1)</script>\nline2") is True
    payload = json.loads(sent[-1].data.decode())
    content = payload["message"]["body"]["content"]
    assert "<script>" not in content
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in content


def test_sofia_email_escapes_caption_headline_and_url():
    from scripts import enqueue_sofia
    html = enqueue_sofia.email_html("uproduction_spain", "<h1>x</h1>", "id", "tok",
                                    '<img src=x onerror=alert(1)>', 'https://v/x.mp4" onclick="evil()')
    assert "<h1>x</h1>" not in html
    assert "<img src=x" not in html
    assert 'onclick="evil' not in html


def test_callback_pages_never_build_html_from_url_values():
    for page in ("linkedin-callback.html", "tiktok-callback.html", "r.html"):
        src = _text(os.path.join(ROOT, "docs", page))
        for sink in ("innerHTML", "outerHTML", "document.write", "onclick=", "insertAdjacentHTML", "eval("):
            assert sink not in src, f"{page} uses {sink}"


def test_requests_floor_excludes_known_vulnerable_versions():
    req = _text(os.path.join(ROOT, "requirements.txt"))
    m = re.search(r"^requests>=(\d+)\.(\d+)\.(\d+)", req, re.M)
    assert m, "requests pin missing"
    assert tuple(map(int, m.groups())) >= (2, 32, 4)


def test_edge_functions_are_self_contained_and_csrf_protected():
    approve = _text(os.path.join(ROOT, "supabase", "functions", "approve", "handler.ts"))
    # No third-party runtime dependency: the handler talks to PostgREST with fetch.
    assert "jsr:" not in approve and "npm:" not in approve
    assert not re.search(r"^import ", approve, re.M)
    oauth = _text(os.path.join(ROOT, "supabase", "functions", "linkedin-oauth", "handler.ts"))
    assert "HttpOnly" in oauth and "SameSite=Lax" in oauth
    assert "timingSafeEqual" in oauth and "timingSafeEqual" in approve
    for fn in ("approve", "linkedin-oauth"):
        index = _text(os.path.join(ROOT, "supabase", "functions", fn, "index.ts"))
        assert 'from "./handler.ts"' in index
        assert "jsr:" not in index


def test_sofia_queue_file_argument_cannot_escape_its_directory(monkeypatch, capsys):
    from scripts import enqueue_sofia
    monkeypatch.setattr("sys.argv", ["enqueue_sofia.py", "../../state/citations"])
    assert enqueue_sofia.main() == 1
    assert "refusing" in capsys.readouterr().out
