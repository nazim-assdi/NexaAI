from __future__ import annotations

import json
from collections.abc import Iterator
from typing import Any

import httpx

HF_CHAT_URL = "https://router.huggingface.co/v1/chat/completions"
DEFAULT_HF_MODEL = "Qwen/Qwen3-4B-Thinking-2507:cheapest"


def _headers(token: str) -> dict[str, str]:
    value = str(token or "").strip()
    if not value:
        raise RuntimeError("Connect a Hugging Face access token in Hybrid AI Settings to use cloud fallback.")
    return {"Authorization": f"Bearer {value}", "Content-Type": "application/json"}


def _payload(
    messages: list[dict[str, Any]],
    temperature: float | None,
    max_tokens: int | None,
    model: str | None,
    stream: bool,
) -> dict[str, Any]:
    return {
        "model": (model or DEFAULT_HF_MODEL).strip(),
        "messages": messages,
        "stream": stream,
        "temperature": 0.45 if temperature is None else float(temperature),
        "max_tokens": 3072 if max_tokens is None else int(max_tokens),
    }


def _response_error(response: httpx.Response) -> str:
    try:
        body = response.json()
        error = body.get("error", body) if isinstance(body, dict) else body
        return str(error.get("message") or error) if isinstance(error, dict) else str(error)
    except ValueError:
        return response.text[:800] or f"HTTP {response.status_code}"


def generate_text(
    messages: list[dict[str, Any]],
    token: str,
    temperature: float | None = None,
    max_tokens: int | None = None,
    model: str | None = None,
) -> str:
    payload = _payload(messages, temperature, max_tokens, model, False)
    with httpx.Client(timeout=httpx.Timeout(180, connect=15)) as client:
        response = client.post(HF_CHAT_URL, headers=_headers(token), json=payload)
    if response.is_error:
        raise RuntimeError(f"Hugging Face Inference Providers: {_response_error(response)}")
    data = response.json()
    choices = data.get("choices") if isinstance(data, dict) else None
    if not choices:
        raise RuntimeError(f"Hugging Face returned an unexpected response: {json.dumps(data)[:800]}")
    content = (choices[0].get("message") or {}).get("content", "")
    if isinstance(content, list):
        content = "".join(str(part.get("text", "")) for part in content if isinstance(part, dict))
    if not isinstance(content, str) or not content.strip():
        raise RuntimeError("Hugging Face returned an empty assistant message.")
    return content


def stream_text(
    messages: list[dict[str, Any]],
    token: str,
    temperature: float | None = None,
    max_tokens: int | None = None,
    model: str | None = None,
) -> Iterator[str]:
    payload = _payload(messages, temperature, max_tokens, model, True)
    timeout = httpx.Timeout(300, connect=15, read=180)
    with httpx.Client(timeout=timeout) as client:
        with client.stream("POST", HF_CHAT_URL, headers=_headers(token), json=payload) as response:
            if response.is_error:
                raise RuntimeError(f"Hugging Face Inference Providers: {_response_error(response)}")
            for line in response.iter_lines():
                if not line or not line.startswith("data:"):
                    continue
                raw = line[5:].strip()
                if raw == "[DONE]":
                    break
                try:
                    item = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                if "error" in item:
                    detail = item["error"]
                    raise RuntimeError(str(detail.get("message") or detail) if isinstance(detail, dict) else str(detail))
                choices = item.get("choices") or []
                if not choices:
                    continue
                delta = choices[0].get("delta") or {}
                content = delta.get("content", "")
                if isinstance(content, list):
                    content = "".join(str(part.get("text", "")) for part in content if isinstance(part, dict))
                if content:
                    yield str(content)
