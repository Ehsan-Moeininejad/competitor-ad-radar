"""
Free-model LLM client with instant fallback.

Order (env LLM_CHAIN, comma separated; default below). Each provider is used only if its key exists:
  github     → GitHub Models, free, uses the workflow's own GITHUB_TOKEN (no key to create)
  gemini     → Google AI Studio free tier (GEMINI_API_KEY)
  openrouter → OpenRouter ':free' models (OPENROUTER_API_KEY); free model list is fetched live
  groq       → Groq free tier (GROQ_API_KEY)
  cerebras   → Cerebras free tier (CEREBRAS_API_KEY)
  mistral    → Mistral free 'experiment' tier (MISTRAL_API_KEY)

Rule asked for by the owner: if a model is busy (429/503), errors, or times out, go straight to the
NEXT model — no long waits. A provider whose key is rejected is dropped for the rest of the run.
Every call returns parsed JSON; callers must survive an exception (rule-based fallback).
"""
import base64
import json
import logging
import os
import re
import time

import requests

log = logging.getLogger("radar")

DEFAULT_CHAIN = "github,gemini,openrouter,groq,cerebras,mistral"
TIMEOUT = int(os.getenv("LLM_TIMEOUT", "75"))

PROVIDERS = {
    "github": {
        "key": "GITHUB_TOKEN", "url": "https://models.github.ai/inference/chat/completions",
        "models": ["openai/gpt-4.1-mini", "openai/gpt-4o-mini", "openai/gpt-4.1-nano", "meta/Llama-4-Scout-17B-16E-Instruct", "deepseek/DeepSeek-V3-0324"],
        "vision": ["openai/gpt-4.1-mini", "openai/gpt-4o-mini", "openai/gpt-4.1-nano", "meta/Llama-4-Scout-17B-16E-Instruct"],
        "max_in_chars": 24000,
    },
    "gemini": {
        "key": "GEMINI_API_KEY", "models": ["gemini-2.5-flash", "gemini-2.5-flash-lite", "gemini-2.0-flash"],
        "vision": "*", "max_in_chars": 200000,
    },
    "openrouter": {
        "key": "OPENROUTER_API_KEY", "url": "https://openrouter.ai/api/v1/chat/completions",
        "models": [],  # filled live from /models (only ':free')
        "prefer": ["deepseek", "qwen", "llama-3.3-70b", "gemini", "gemma-3-27b", "mistral-small", "llama-4"],
        "vision": [], "max_in_chars": 60000,
    },
    "groq": {
        "key": "GROQ_API_KEY", "url": "https://api.groq.com/openai/v1/chat/completions",
        "models": ["llama-3.3-70b-versatile", "meta-llama/llama-4-scout-17b-16e-instruct", "qwen/qwen3-32b", "llama-3.1-8b-instant"],
        "vision": ["meta-llama/llama-4-scout-17b-16e-instruct"], "max_in_chars": 20000,
    },
    "cerebras": {
        "key": "CEREBRAS_API_KEY", "url": "https://api.cerebras.ai/v1/chat/completions",
        "models": ["llama-3.3-70b", "qwen-3-32b", "llama3.1-8b"], "vision": [], "max_in_chars": 24000,
    },
    "mistral": {
        "key": "MISTRAL_API_KEY", "url": "https://api.mistral.ai/v1/chat/completions",
        "models": ["mistral-small-latest", "open-mistral-nemo"], "vision": ["mistral-small-latest"], "max_in_chars": 60000,
    },
}


class _Skip(Exception):
    """This model failed for this call → try next model."""


class _Dead(Exception):
    """Provider unusable for the whole run (bad key)."""


class LLM:
    def __init__(self):
        chain = (os.getenv("LLM_CHAIN") or DEFAULT_CHAIN).lower()
        self.slots = []        # [(provider, model)]
        self.dead = set()
        self.used = {}         # "provider:model" -> successful calls
        self.failures = {}     # "provider:model" -> failures
        for name in [c.strip() for c in chain.split(",") if c.strip()]:
            p = PROVIDERS.get(name)
            if not p or not os.getenv(p["key"]):
                continue
            models = list(p["models"])
            if name == "openrouter":
                models = _openrouter_free_models(p["prefer"])
            if name == "gemini":
                models = _gemini_models() or models
            override = os.getenv(f"{name.upper()}_MODELS")
            if override:
                models = [m.strip() for m in override.split(",") if m.strip()]
            for m in models[:6]:
                self.slots.append((name, m))
        self.available = bool(self.slots)
        if self.available:
            log.info("LLM chain (%d models): %s", len(self.slots), " → ".join(f"{p}:{m}" for p, m in self.slots[:10]))
        else:
            log.warning("No LLM key available — rule-based analysis only")

    # ------------------------------------------------------------------
    def json(self, system: str, user: str, max_tokens: int = 3000, image_b64: str | None = None):
        if not self.available:
            raise RuntimeError("no LLM configured")
        errors = []
        t_call = time.time()
        budget = float(os.getenv("LLM_CALL_BUDGET", "240"))
        order = sorted(self.slots, key=lambda s: self.failures.get(f"{s[0]}:{s[1]}", 0) >= 2)  # repeatedly failing models go last
        for prov, model in order:
            if prov in self.dead:
                continue
            if time.time() - t_call > budget:
                errors.append("call budget exhausted")
                break
            p = PROVIDERS[prov]
            if image_b64 and not (p["vision"] == "*" or model in p["vision"]):
                continue
            key = f"{prov}:{model}"
            u = user if len(user) <= p["max_in_chars"] else user[: p["max_in_chars"]] + "\n…(truncated)"
            t0 = time.time()
            try:
                raw = self._gemini(model, system, u, max_tokens, image_b64) if prov == "gemini" else \
                    self._openai(prov, model, system, u, max_tokens, image_b64)
                out = _parse_json(raw)
                if not isinstance(out, dict):
                    raise _Skip("answer is not a JSON object")
                self.used[key] = self.used.get(key, 0) + 1
                log.info("LLM ok %s (%.1fs)", key, time.time() - t0)
                return out
            except _Dead as e:
                self.dead.add(prov)
                errors.append(f"{key}: {e}")
                log.warning("LLM provider %s dropped: %s", prov, str(e)[:160])
            except (requests.Timeout, requests.ConnectionError):
                self.failures[key] = self.failures.get(key, 0) + 1
                errors.append(f"{key}: timeout/conn")
                log.warning("LLM %s timeout/connection (%.0fs) → next model", key, time.time() - t0)
            except Exception as e:  # noqa: BLE001  (busy, bad JSON, odd payload… → next model)
                self.failures[key] = self.failures.get(key, 0) + 1
                errors.append(f"{key}: {str(e)[:120]}")
                log.warning("LLM %s failed: %s → next model", key, str(e)[:160])
        raise RuntimeError("all LLM models failed: " + " | ".join(errors[-6:]))

    @property
    def summary(self) -> str:
        if not self.used:
            return "بدون مدل (تحلیل قاعده‌محور)"
        return "، ".join(f"{k} ({v})" for k, v in sorted(self.used.items(), key=lambda x: -x[1]))

    # ------------------------------------------------------------------
    def _openai(self, prov, model, system, user, max_tokens, image_b64):
        p = PROVIDERS[prov]
        headers = {"Authorization": f"Bearer {os.environ[p['key']]}", "Content-Type": "application/json"}
        if prov == "github":
            headers.update({"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"})
        if prov == "openrouter":
            headers.update({"HTTP-Referer": "https://github.com", "X-Title": "competitor-ad-radar"})
        content = user
        if image_b64:
            content = [{"type": "text", "text": user},
                       {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_b64}"}}]
        body = {"model": model, "max_tokens": min(max_tokens, 4000), "temperature": 0.2,
                "messages": [{"role": "system", "content": system + "\n\nAnswer with valid JSON only. No markdown fences, no commentary."},
                             {"role": "user", "content": content}]}
        if prov in ("groq", "mistral", "cerebras"):
            body["response_format"] = {"type": "json_object"}
        url = p["url"]
        for _ in range(3):  # follow redirects as POST
            r = requests.post(url, headers=headers, json=body, timeout=TIMEOUT, allow_redirects=False)
            if r.status_code in (301, 302, 307, 308) and r.headers.get("location"):
                url = requests.compat.urljoin(url, r.headers["location"])
                continue
            break
        if r.status_code in (401, 403):
            raise _Dead(f"HTTP {r.status_code} {r.text[:150]}")
        if r.status_code >= 400:
            raise _Skip(f"HTTP {r.status_code} {r.text[:150]}")
        data = r.json()
        msg = (data.get("choices") or [{}])[0].get("message") or {}
        text = msg.get("content") or ""
        if not text.strip():
            raise _Skip("empty answer")
        return text

    def _gemini(self, model, system, user, max_tokens, image_b64):
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
        parts = [{"text": user}]
        if image_b64:
            parts.append({"inline_data": {"mime_type": "image/jpeg", "data": image_b64}})
        gen = {"responseMimeType": "application/json", "maxOutputTokens": max(max_tokens, 4000), "temperature": 0.2}
        if "2.5" in model:
            gen["thinkingConfig"] = {"thinkingBudget": 0}
        body = {"systemInstruction": {"parts": [{"text": system}]}, "contents": [{"role": "user", "parts": parts}],
                "generationConfig": gen}
        r = requests.post(url, params={"key": os.environ["GEMINI_API_KEY"]}, json=body, timeout=TIMEOUT)
        if r.status_code == 400 and "thinking" in r.text.lower():
            gen.pop("thinkingConfig", None)
            r = requests.post(url, params={"key": os.environ["GEMINI_API_KEY"]}, json=body, timeout=TIMEOUT)
        if r.status_code in (401, 403) or (r.status_code == 400 and "API key" in r.text):
            raise _Dead(f"HTTP {r.status_code} {r.text[:150]}")
        if r.status_code >= 400:
            raise _Skip(f"HTTP {r.status_code} {r.text[:150]}")
        cand = (r.json().get("candidates") or [{}])[0]
        txt = "".join(x.get("text", "") for x in (cand.get("content") or {}).get("parts", []) if not x.get("thought"))
        if not txt.strip():
            raise _Skip(f"empty (finish={cand.get('finishReason')})")
        return txt


def _openrouter_free_models(prefer: list) -> list:
    try:
        r = requests.get("https://openrouter.ai/api/v1/models", timeout=30)
        ms = [m for m in r.json().get("data", []) if m.get("id", "").endswith(":free")
              and (m.get("context_length") or 0) >= 32000]
    except Exception as e:  # noqa: BLE001
        log.warning("OpenRouter model list failed: %s", e)
        return ["deepseek/deepseek-chat-v3-0324:free", "meta-llama/llama-3.3-70b-instruct:free", "qwen/qwen-2.5-72b-instruct:free"]

    def rank(m):
        mid = m["id"].lower()
        for i, p in enumerate(prefer):
            if p in mid:
                return i
        return len(prefer)
    ms.sort(key=lambda m: (rank(m), -(m.get("context_length") or 0)))
    vis = [m["id"] for m in ms if "image" in (m.get("architecture", {}).get("input_modalities") or [])]
    PROVIDERS["openrouter"]["vision"] = vis
    return [m["id"] for m in ms]


def _gemini_models() -> list:
    """Newest flash models this key can use (names change often, so ask the API)."""
    try:
        r = requests.get("https://generativelanguage.googleapis.com/v1beta/models",
                         params={"key": os.environ["GEMINI_API_KEY"], "pageSize": 200}, timeout=30)
        names = [m["name"].split("/", 1)[-1] for m in r.json().get("models", [])
                 if "generateContent" in m.get("supportedGenerationMethods", [])]
    except Exception as e:  # noqa: BLE001
        log.warning("Gemini model list failed: %s", e)
        return []
    skip = ("image", "tts", "audio", "live", "embedding", "learnlm", "gemma", "robotics", "computer", "exp", "preview", "thinking")
    names = [n for n in names if n.startswith("gemini-") and not any(k in n for k in skip)]
    def ver(n):
        m = re.search(r"gemini-(\d+(?:\.\d+)?)", n)
        return float(m.group(1)) if m else 0
    flash = sorted([n for n in names if "flash" in n], key=lambda n: (-ver(n), "lite" in n, len(n)))
    pro = sorted([n for n in names if "pro" in n], key=lambda n: -ver(n))
    return (flash[:4] + pro[:1]) or names[:4]


def _parse_json(text: str):
    text = re.sub(r"<think>.*?</think>", "", text or "", flags=re.S)
    text = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.M).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        starts = [i for i in (text.find("["), text.find("{")) if i != -1]
        if not starts:
            raise
        s = min(starts)
        e = max(text.rfind("]"), text.rfind("}"))
        return json.loads(text[s:e + 1])


def b64_file(path) -> str:
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode()
