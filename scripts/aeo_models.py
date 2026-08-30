"""Pluggable answer-engine adapters. Claude is live; OpenAI/Gemini are gated on key presence.

`grounded=True` asks each engine with live web search enabled (Claude web_search tool,
OpenAI Responses API web_search tool, Gemini google_search tool) so probes measure what real
answer engines return today, not frozen training-data recall.

A grounded call that fails still falls back to the plain call so a provider outage never
kills a run -- but the result is LABELLED (`grounded=False` + `grounded_error`) instead of
silently substituted. Callers must treat an ungrounded answer as a broken instrument, not
as data: an ungrounded model answers from frozen training recall and will report a
visibility collapse that never happened. This is exactly how ChatGPT's citation rate
silently fell to 0 on 2026-08-23 when `gpt-4o-search-preview` was retired (2026-07-23).
"""
import os, json, urllib.request, urllib.error

MODEL_LABELS = {"claude": "Claude", "chatgpt": "ChatGPT", "gemini": "Gemini"}
_KEY_ENV = {"claude": "ANTHROPIC_API_KEY", "chatgpt": "OPENAI_API_KEY", "gemini": "GEMINI_API_KEY"}


def available_models():
    return [m for m in ("claude", "chatgpt", "gemini") if os.environ.get(_KEY_ENV[m])]


def _post(url, data, headers):
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=180) as r:
            return r.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")[:400]
        raise RuntimeError(f"HTTP {e.code} from {url}: {body}") from None


def ask(model, prompt, system="", max_tokens=4096, _http=None, grounded=False):
    return ask_meta(model, prompt, system, max_tokens, _http, grounded)["text"]


def ask_meta(model, prompt, system="", max_tokens=4096, _http=None, grounded=False):
    """Like ask(), but returns {"text", "citations", "grounded", "grounded_error"}.

    `grounded` in the RESULT reports whether live web search actually ran -- never what was
    requested. When a grounded call fails we still answer (so one outage cannot void a run),
    but we say so, so the caller can mark the engine degraded and drop it from the scorecard.
    """
    if not grounded:
        return {**_ask_once(model, prompt, system, max_tokens, _http, grounded=False),
                "grounded": False, "grounded_error": None}
    try:
        return {**_ask_once(model, prompt, system, max_tokens, _http, grounded=True),
                "grounded": True, "grounded_error": None}
    except Exception as e:
        err = f"{type(e).__name__}: {e}"[:300]
    return {**_ask_once(model, prompt, system, max_tokens, _http, grounded=False),
            "grounded": False, "grounded_error": err}


def _dedup(urls):
    seen, out = set(), []
    for u in urls:
        if u and u not in seen:
            seen.add(u)
            out.append(u)
    return out


def _ask_once(model, prompt, system, max_tokens, _http, grounded):
    http = _http or _post
    if model == "claude":
        body = {
            "model": os.environ.get("AEO_MODEL") or "claude-sonnet-4-6",
            "max_tokens": max_tokens,
            "messages": [{"role": "user", "content": prompt}],
        }
        if system:
            body["system"] = system
        if grounded:
            body["tools"] = [{"type": "web_search_20250305", "name": "web_search", "max_uses": 3}]
        headers = {"x-api-key": os.environ.get("ANTHROPIC_API_KEY", ""),
                   "anthropic-version": "2023-06-01", "content-type": "application/json"}
        raw = http("https://api.anthropic.com/v1/messages", json.dumps(body).encode(), headers)
        data = json.loads(raw)
        text, cites = [], []
        for b in data.get("content", []):
            if b.get("type") == "text":
                text.append(b.get("text", ""))
                for c in b.get("citations") or []:
                    cites.append(c.get("url", ""))
            elif b.get("type") == "web_search_tool_result":
                for r in b.get("content") or []:
                    if isinstance(r, dict):
                        cites.append(r.get("url", ""))
        return {"text": "".join(text).strip(), "citations": _dedup(cites)}
    if model == "chatgpt":
        headers = {"authorization": f"Bearer {os.environ.get('OPENAI_API_KEY','')}", "content-type": "application/json"}
        if grounded:
            # Responses API + web_search tool. The old chat-completions
            # `gpt-4o-search-preview` was retired 2026-07-23; asking for it fails, and the
            # ungrounded fallback then answers from training recall.
            mdl = os.environ.get("AEO_OPENAI_SEARCH_MODEL") or "gpt-5.6"
            body = {"model": mdl,
                    "tools": [{"type": "web_search"}],
                    "max_output_tokens": max(max_tokens, 8192),
                    "input": ([{"role": "system", "content": system}] if system else []) +
                             [{"role": "user", "content": prompt}]}
            data = json.loads(http("https://api.openai.com/v1/responses", json.dumps(body).encode(), headers))
            text, cites = [], []
            for item in data.get("output", []):
                if item.get("type") != "message":
                    continue
                for c in item.get("content") or []:
                    if c.get("type") != "output_text":
                        continue
                    text.append(c.get("text", ""))
                    for a in c.get("annotations") or []:
                        if a.get("type") == "url_citation":
                            cites.append(a.get("url", ""))
            text = "".join(text).strip()
            if not text:
                # empty grounded answer is a failed instrument, not an empty opinion --
                # raise so ask_meta labels it instead of banking a blank as data
                raise RuntimeError(f"openai responses returned no text (status={data.get('status')!r})")
            return {"text": text, "citations": _dedup(cites)}
        body = {"model": os.environ.get("AEO_OPENAI_MODEL") or "gpt-4o",
                "max_tokens": max_tokens,
                "messages": ([{"role": "system", "content": system}] if system else []) +
                            [{"role": "user", "content": prompt}]}
        data = json.loads(http("https://api.openai.com/v1/chat/completions", json.dumps(body).encode(), headers))
        msg = data["choices"][0]["message"]
        cites = [a.get("url_citation", {}).get("url", "") for a in msg.get("annotations") or []
                 if a.get("type") == "url_citation"]
        return {"text": msg["content"].strip(), "citations": _dedup(cites)}
    if model == "gemini":
        mdl = os.environ.get("AEO_GEMINI_MODEL") or "gemini-2.5-flash"
        key = os.environ.get("GEMINI_API_KEY", "")
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{mdl}:generateContent?key={key}"
        body = {"contents": [{"parts": [{"text": (system + "\n\n" + prompt) if system else prompt}]}],
                "generationConfig": {"maxOutputTokens": max_tokens}}
        if grounded:
            body["tools"] = [{"google_search": {}}]
        data = json.loads(http(url, json.dumps(body).encode(), {"content-type": "application/json"}))
        cand = data["candidates"][0]
        parts = cand["content"]["parts"]
        chunks = (cand.get("groundingMetadata") or {}).get("groundingChunks") or []
        cites = []
        for c in chunks:
            web = c.get("web") or {}
            uri, title = web.get("uri", ""), web.get("title", "")
            # gemini masks sources behind a vertexaisearch redirect; title carries the real domain
            cites.append(title if ("vertexaisearch" in uri and title) else uri)
        return {"text": "".join(p.get("text", "") for p in parts).strip(), "citations": _dedup(cites)}
    raise ValueError(f"unknown model {model}")
