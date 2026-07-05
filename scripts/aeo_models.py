"""Pluggable answer-engine adapters. Claude is live; OpenAI/Gemini are gated on key presence.

`grounded=True` asks each engine with live web search enabled (Claude web_search tool,
OpenAI *-search-preview model, Gemini google_search tool) so probes measure what real
answer engines return today, not frozen training-data recall. A grounded call that fails
falls back to the plain (ungrounded) call so a provider-side tool outage never kills a run.
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
    """Like ask(), but returns {"text": str, "citations": [url, ...]} so probes can
    see WHICH sources the engine retrieved (the outreach target list)."""
    if grounded:
        try:
            return _ask_once(model, prompt, system, max_tokens, _http, grounded=True)
        except Exception:
            pass  # grounded path failed (tool not enabled / model gone) -> plain call below
    return _ask_once(model, prompt, system, max_tokens, _http, grounded=False)


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
        if grounded:
            mdl = os.environ.get("AEO_OPENAI_SEARCH_MODEL") or "gpt-4o-search-preview"
            body = {"model": mdl,
                    "web_search_options": {},
                    "max_tokens": max_tokens,
                    "messages": ([{"role": "system", "content": system}] if system else []) +
                                [{"role": "user", "content": prompt}]}
        else:
            body = {"model": os.environ.get("AEO_OPENAI_MODEL") or "gpt-4o",
                    "max_tokens": max_tokens,
                    "messages": ([{"role": "system", "content": system}] if system else []) +
                                [{"role": "user", "content": prompt}]}
        headers = {"authorization": f"Bearer {os.environ.get('OPENAI_API_KEY','')}", "content-type": "application/json"}
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
        cites = [(c.get("web") or {}).get("uri", "") for c in chunks]
        return {"text": "".join(p.get("text", "") for p in parts).strip(), "citations": _dedup(cites)}
    raise ValueError(f"unknown model {model}")
