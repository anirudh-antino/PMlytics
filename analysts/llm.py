"""
Provider-agnostic LLM client (Anthropic / OpenAI / Google Gemini) with strict
JSON parsing and a single repair retry. Used by every phase of the report pipeline.
"""

from __future__ import annotations

import json
import os
import re
from typing import Any, Optional
from urllib.parse import quote

import httpx

DEFAULT_ANTHROPIC_MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-3-5-sonnet-20241022")
DEFAULT_OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
DEFAULT_GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-flash-latest")

ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
OPENAI_URL = "https://api.openai.com/v1/chat/completions"
GEMINI_API_BASE = "https://generativelanguage.googleapis.com/v1beta"


def extract_json_object(text: str) -> dict[str, Any]:
    """Pull the outermost JSON object from a model response.

    Tolerates leading/trailing markdown fences, extra prose, and stray text
    after the JSON. Raises ValueError with a useful message if no object is
    found or the JSON is unparseable.
    """
    raw = (text or "").strip()
    if not raw:
        raise ValueError("Model returned an empty response.")

    fenced = re.search(r"```(?:json)?\s*(.*?)```", raw, flags=re.DOTALL | re.IGNORECASE)
    if fenced:
        raw = fenced.group(1).strip()

    start = raw.find("{")
    if start == -1:
        snippet = (raw[:200] + "…") if len(raw) > 200 else raw
        raise ValueError(f"Model output had no JSON object. Got: {snippet!r}")

    try:
        decoder = json.JSONDecoder()
        obj, _ = decoder.raw_decode(raw[start:])
    except json.JSONDecodeError as exc:
        snippet = raw[start : start + 240]
        raise ValueError(
            f"Model output was not valid JSON ({exc.msg} at char {exc.pos}). "
            f"First chars: {snippet!r}"
        ) from exc

    if not isinstance(obj, dict):
        raise ValueError(
            f"Model returned JSON of type {type(obj).__name__}, expected object."
        )
    return obj


def _format_http_error(provider: str, model: str, response: httpx.Response) -> str:
    """Pull a useful message out of the LLM provider's error body."""
    body = ""
    try:
        data = response.json()
        if isinstance(data, dict):
            err = data.get("error") or data
            if isinstance(err, dict):
                body = err.get("message") or err.get("status") or err.get("type") or ""
            elif isinstance(err, str):
                body = err
    except Exception:
        body = (response.text or "")[:400]
    base = f"{provider} returned {response.status_code} for model {model!r}"
    if response.status_code == 404:
        base += (
            ". The model name is unknown to your account, or your key doesn't have "
            "access to it. Pick another model in Settings or type a custom one."
        )
    elif response.status_code == 401 or response.status_code == 403:
        base += ". The API key was rejected — check it in Settings."
    elif response.status_code == 429:
        base += ". You're being rate-limited or out of quota."
    if body:
        base += f" (provider said: {body})"
    return base


def _gemini_model_id(model: str) -> str:
    m = (model or "").strip()
    if m.startswith("models/"):
        m = m[len("models/") :]
    return m


async def anthropic_complete(
    system: str,
    user: str,
    api_key: str,
    *,
    model: str,
    max_tokens: int = 4096,
) -> str:
    payload = {
        "model": model,
        "max_tokens": max_tokens,
        "system": system,
        "messages": [{"role": "user", "content": user}],
    }
    headers = {
        "x-api-key": api_key.strip(),
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }
    async with httpx.AsyncClient(timeout=180.0) as client:
        r = await client.post(ANTHROPIC_URL, headers=headers, json=payload)
        if r.status_code >= 400:
            raise RuntimeError(_format_http_error("Anthropic", model, r))
        data = r.json()
    blocks = data.get("content") or []
    if not blocks:
        raise RuntimeError("Anthropic returned empty content.")
    return blocks[0].get("text", "")


async def openai_complete(
    system: str,
    user: str,
    api_key: str,
    *,
    model: str,
) -> str:
    payload = {
        "model": model,
        "temperature": 0.2,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    }
    headers = {
        "Authorization": f"Bearer {api_key.strip()}",
        "content-type": "application/json",
    }
    async with httpx.AsyncClient(timeout=180.0) as client:
        r = await client.post(OPENAI_URL, headers=headers, json=payload)
        if r.status_code >= 400:
            raise RuntimeError(_format_http_error("OpenAI", model, r))
        data = r.json()
    choices = data.get("choices") or []
    if not choices:
        raise RuntimeError("OpenAI returned no choices.")
    return choices[0]["message"]["content"]


async def gemini_complete(
    system: str,
    user: str,
    api_key: str,
    *,
    model: str,
) -> str:
    mid = _gemini_model_id(model)
    url = f"{GEMINI_API_BASE}/models/{quote(mid, safe='')}:generateContent"
    payload: dict[str, Any] = {
        "systemInstruction": {"parts": [{"text": system}]},
        "contents": [{"role": "user", "parts": [{"text": user}]}],
        "generationConfig": {
            "temperature": 0.2,
            "maxOutputTokens": 8192,
        },
    }
    headers = {
        "x-goog-api-key": api_key.strip(),
        "content-type": "application/json",
    }
    async with httpx.AsyncClient(timeout=180.0) as client:
        r = await client.post(url, headers=headers, json=payload)
        if r.status_code >= 400:
            raise RuntimeError(_format_http_error("Gemini", mid, r))
        data = r.json()
    candidates = data.get("candidates") or []
    if not candidates:
        raise RuntimeError("Gemini returned no candidates.")
    parts = (candidates[0].get("content") or {}).get("parts") or []
    texts = [
        p.get("text", "")
        for p in parts
        if isinstance(p, dict) and p.get("text")
    ]
    if not texts:
        raise RuntimeError("Gemini returned no text parts.")
    return "".join(texts)


def pick_provider(
    anthropic_key: Optional[str],
    openai_key: Optional[str],
    gemini_key: Optional[str] = None,
    preference: str = "auto",
) -> tuple[str, str]:
    """Resolve provider and API key.

    ``preference`` can be ``auto`` (Claude → OpenAI → Gemini) or a specific
    provider when the user chose it in the UI and that key is configured.
    """
    pref = (preference or "auto").strip().lower()
    if pref not in ("auto", "anthropic", "openai", "gemini"):
        pref = "auto"

    a = (anthropic_key or "").strip()
    o = (openai_key or "").strip()
    g = (gemini_key or "").strip()

    if pref == "anthropic" and a:
        return "anthropic", a
    if pref == "openai" and o:
        return "openai", o
    if pref == "gemini" and g:
        return "gemini", g

    if a:
        return "anthropic", a
    if o:
        return "openai", o
    if g:
        return "gemini", g
    raise ValueError(
        "Add an Anthropic, OpenAI, or Google (Gemini) API key in Settings."
    )


async def llm_text(
    system: str,
    user: str,
    *,
    anthropic_key: str,
    openai_key: str,
    gemini_key: str = "",
    anthropic_model: Optional[str] = None,
    openai_model: Optional[str] = None,
    gemini_model: Optional[str] = None,
    llm_provider: str = "auto",
) -> str:
    provider, key = pick_provider(
        anthropic_key, openai_key, gemini_key, preference=llm_provider
    )
    if provider == "anthropic":
        return await anthropic_complete(
            system, user, key, model=anthropic_model or DEFAULT_ANTHROPIC_MODEL
        )
    if provider == "openai":
        return await openai_complete(
            system, user, key, model=openai_model or DEFAULT_OPENAI_MODEL
        )
    return await gemini_complete(
        system, user, key, model=gemini_model or DEFAULT_GEMINI_MODEL
    )


async def llm_json(
    system: str,
    user: str,
    *,
    anthropic_key: str,
    openai_key: str,
    gemini_key: str = "",
    anthropic_model: Optional[str] = None,
    openai_model: Optional[str] = None,
    gemini_model: Optional[str] = None,
    llm_provider: str = "auto",
) -> dict[str, Any]:
    """Call the model and parse JSON, with one repair retry on failure."""
    text = await llm_text(
        system,
        user,
        anthropic_key=anthropic_key,
        openai_key=openai_key,
        gemini_key=gemini_key,
        anthropic_model=anthropic_model,
        openai_model=openai_model,
        gemini_model=gemini_model,
        llm_provider=llm_provider,
    )
    try:
        return extract_json_object(text)
    except Exception as first_err:
        repair_user = (
            "Your previous response could not be parsed as JSON. "
            "Reply with ONLY a single JSON object, no markdown, no commentary.\n\n"
            f"Previous output:\n{text[:6000]}\n\n"
            f"Original request:\n{user[:6000]}"
        )
        text2 = await llm_text(
            system,
            repair_user,
            anthropic_key=anthropic_key,
            openai_key=openai_key,
            gemini_key=gemini_key,
            anthropic_model=anthropic_model,
            openai_model=openai_model,
            gemini_model=gemini_model,
            llm_provider=llm_provider,
        )
        try:
            return extract_json_object(text2)
        except Exception:
            raise first_err
