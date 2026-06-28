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
