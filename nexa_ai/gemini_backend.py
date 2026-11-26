from __future__ import annotations

import base64
import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import httpx

from .file_store import file_store


GEMINI_API_BASE = "https://generativelanguage.googleapis.com/v1beta"
GEMINI_MODELS = {
    "gemini-3.8-flash": "Gemini 3.8 Flash",
    "gemini-3.5-flash-lite": "Gemini 3.5 Flash-Lite",
}
MAX_INLINE_FILE_BYTES = 15 * 1024 * 1024
TEXT_EXTENSIONS = {".txt", ".md", ".csv", ".json", ".xml", ".py", ".js", ".html", ".css", ".log"}
IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp", "image/heic", "image/heif"}


def _gemini_error(response: httpx.Response) -> str:
    try:
        payload = response.json()
        error = payload.get("error", payload) if isinstance(payload, dict) else payload
        if isinstance(error, dict):
            code = error.get("code")
            message = str(error.get("message") or error)
            if code == 401 or response.status_code == 401:
                return "Gemini API key was rejected. Check the key in Google AI Studio."
            if code == 403 or response.status_code == 403:
                return "Gemini access was denied. Check your API key restrictions and Google AI Studio project."
            if code == 429 or response.status_code == 429:
                return "Gemini free-tier quota or rate limit reached. Wait for the quota to reset or switch to the other Gemini model."
            return message
        return str(error)
    except ValueError:
        return response.text[:600] or f"Gemini API returned HTTP {response.status_code}."


def test_api_key(api_key: str, model: str = "gemini-3.8-flash") -> None:
    key = str(api_key or "").strip()
    if not key:
        raise ValueError("Enter a Gemini API key from Google AI Studio.")
    if model not in GEMINI_MODELS:
        raise ValueError(f"Unsupported Gemini model: {model}")
    try:
        with httpx.Client(timeout=httpx.Timeout(20, connect=10)) as client:
            response = client.get(
                f"{GEMINI_API_BASE}/models/{model}",
                headers={"x-goog-api-key": key},
            )
        if response.is_error:
            raise RuntimeError(_gemini_error(response))
    except httpx.HTTPError as exc:
        raise RuntimeError(f"Could not reach Google Gemini API: {exc}") from exc


def _inline_file_part(file_id: str) -> dict[str, Any]:
    stored = file_store.get(file_id)
    if not stored:
        raise ValueError(f"Attachment not found in local storage: {file_id}")
    path = Path(stored.path)
    if not path.is_file():
        raise FileNotFoundError(f"Local attachment is missing: {stored.name}")
    if path.stat().st_size > MAX_INLINE_FILE_BYTES:
        raise ValueError(f"{stored.name} is larger than 15 MB. Choose a smaller file for Gemini.")

    if stored.mime_type.startswith("text/") or path.suffix.lower() in TEXT_EXTENSIONS:
        text = path.read_text(encoding="utf-8", errors="replace")
        return {"text": f"Attached file: {stored.name}\n\n{text[:24000]}"}

    if stored.mime_type not in IMAGE_TYPES | {"application/pdf"}:
        raise ValueError(f"Gemini chat does not support this attachment type: {stored.name}")

    return {
        "inlineData": {
            "mimeType": stored.mime_type,
            "data": base64.b64encode(path.read_bytes()).decode("ascii"),
        }
    }


def build_request(
    messages: list[dict[str, Any]],
    temperature: float = 0.55,
    max_tokens: int = 768,
) -> dict[str, Any]:
    system_parts: list[dict[str, str]] = []
    contents: list[dict[str, Any]] = []

    for message in messages:
        role = str(message.get("role", "user"))
        raw_content = message.get("content", "")
        if role == "system":
            if isinstance(raw_content, str) and raw_content.strip():
                system_parts.append({"text": raw_content})
            continue

        parts: list[dict[str, Any]] = []
        if isinstance(raw_content, str):
            if raw_content.strip():
                parts.append({"text": raw_content})
        elif isinstance(raw_content, list):
            for part in raw_content:
                if not isinstance(part, dict):
                    continue
                if part.get("type") in {"text", "input_text"}:
                    value = str(part.get("text", ""))
                    if value:
                        parts.append({"text": value})
                elif part.get("type") in {"file", "input_file"}:
                    parts.append(_inline_file_part(str(part.get("file_id", ""))))
        else:
            parts.append({"text": str(raw_content)})

        if parts:
            contents.append({
                "role": "model" if role == "assistant" else "user",
                "parts": parts,
            })

    if not contents:
        raise ValueError("Add a message before sending it to Gemini.")

    payload: dict[str, Any] = {
        "contents": contents,
        "generationConfig": {
            "temperature": max(0.0, min(2.0, float(temperature))),
            "maxOutputTokens": max(64, min(8192, int(max_tokens))),
        },
    }
    if system_parts:
        payload["systemInstruction"] = {"parts": system_parts}
    return payload


def stream_text(
    messages: list[dict[str, Any]],
    api_key: str,
    model: str = "gemini-3.8-flash",
    temperature: float = 0.55,
    max_tokens: int = 768,
) -> Iterator[str]:
    key = str(api_key or "").strip()
    if not key:
        raise RuntimeError("Gemini is not connected. Add your optional Google AI Studio API key.")
    if model not in GEMINI_MODELS:
        raise ValueError(f"Unsupported Gemini model: {model}")

    payload = build_request(messages, temperature, max_tokens)
    url = f"{GEMINI_API_BASE}/models/{model}:streamGenerateContent?alt=sse"
    timeout = httpx.Timeout(300, connect=20, read=120, write=60, pool=30)
    try:
        with httpx.Client(timeout=timeout) as client:
            with client.stream(
                "POST", url, headers={"x-goog-api-key": key}, json=payload,
            ) as response:
                if response.is_error:
                    raise RuntimeError(_gemini_error(response))
                for line in response.iter_lines():
                    if not line or not line.startswith("data:"):
                        continue
                    raw = line[5:].strip()
                    if not raw or raw == "[DONE]":
                        continue
                    try:
                        item = json.loads(raw)
                    except json.JSONDecodeError:
                        continue
                    if item.get("error"):
                        error = item["error"]
                        raise RuntimeError(str(error.get("message", error)) if isinstance(error, dict) else str(error))
                    for candidate in item.get("candidates", []) or []:
                        content = candidate.get("content") or {}
                        for part in content.get("parts", []) or []:
                            text = part.get("text")
                            if isinstance(text, str) and text:
                                yield text
                        if candidate.get("finishReason") == "SAFETY":
                            raise RuntimeError("Gemini blocked this response under its safety rules.")
    except httpx.HTTPError as exc:
        raise RuntimeError(f"Gemini connection failed: {exc}") from exc
