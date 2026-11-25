from __future__ import annotations

import base64
import json
import os
import subprocess
import tempfile
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import httpx

from .config import settings
from .file_store import file_store


class LocalModelUnavailable(RuntimeError):
    pass


def _parse_content(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return "".join(str(item.get("text", "")) for item in value if isinstance(item, dict))
    return ""

def _error_text(response: httpx.Response) -> str:
    try:
        payload = response.json()
        error = payload.get("error", payload) if isinstance(payload, dict) else payload
        if isinstance(error, dict):
            return str(error.get("message") or error)
        return str(error)
    except ValueError:
        return response.text[:600] or f"HTTP {response.status_code}"


def list_models() -> list[dict[str, Any]]:
    try:
        with httpx.Client(timeout=5) as client:
            response = client.get(f"{settings.local_base_url}/api/tags")
            response.raise_for_status()
            payload = response.json()
    except Exception as exc:
        raise LocalModelUnavailable(f"Ollama local model service is not ready: {exc}") from exc
    models = payload.get("models", []) if isinstance(payload, dict) else []
    return [
        {"id": str(item.get("name") or item.get("model")), "object": "model", "owned_by": "ollama"}
        for item in models
        if isinstance(item, dict) and (item.get("name") or item.get("model"))
    ]


def _require_vision_model() -> None:
    raise RuntimeError(
        "The selected Gemma 3 1B assistant is a text model. Image and video understanding are not enabled in this edition."
    )


def _read_attachment(file_id: str, prompt: str) -> str:
    stored = file_store.get(file_id)
    if not stored:
        raise ValueError(f"Attachment not found in local storage: {file_id}")
    path = Path(stored.path)
    if not path.is_file():
        raise FileNotFoundError(f"Local attachment is missing: {stored.name}")

    if stored.mime_type == "application/pdf" or path.suffix.lower() == ".pdf":
        try:
            from pypdf import PdfReader
        except ImportError as exc:
            raise RuntimeError("PDF reader is not bundled.") from exc
        reader = PdfReader(str(path))
        pages = [page.extract_text() or "" for page in reader.pages]
        extracted = "\n\n".join(f"[Page {i + 1}]\n{text}" for i, text in enumerate(pages))
        if not extracted.strip():
            raise ValueError(
                f"No selectable text was found in {stored.name}. Scanned PDF OCR needs the OCR plugin."
            )
        return f"Attached PDF: {stored.name}\n{prompt}\n\n{extracted[:settings.max_pdf_chars]}"

    image_types = {"image/jpeg", "image/png", "image/webp", "image/bmp"}
    video_types = {"video/mp4", "video/x-matroska", "video/quicktime", "video/x-msvideo", "video/webm"}
    if stored.mime_type in image_types or stored.mime_type in video_types:
        _require_vision_model()

    allowed_text = stored.mime_type.startswith("text/") or stored.mime_type in {
        "application/json", "application/xml", "application/javascript", "application/csv",
    }
    if allowed_text or path.suffix.lower() in {".txt", ".md", ".csv", ".json", ".xml", ".py", ".js", ".html", ".css", ".log"}:
        text = path.read_text(encoding="utf-8", errors="replace")
        return f"Attached file: {stored.name}\n{prompt}\n\n{text[:settings.max_pdf_chars]}"
    raise ValueError(f"Unsupported attachment type for this build: {stored.name}")


def prepare_messages(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    prepared: list[dict[str, Any]] = []
    for message in messages:
        role = str(message.get("role", "user"))
        content = message.get("content", "")
        if isinstance(content, str):
            prepared.append({"role": role, "content": content})
            continue
        if not isinstance(content, list):
            prepared.append({"role": role, "content": str(content)})
            continue
        text_parts: list[str] = []
        for part in content:
            if not isinstance(part, dict):
                continue
            if part.get("type") in {"text", "input_text"}:
                text_parts.append(str(part.get("text", "")))
            elif part.get("type") in {"file", "input_file"}:
                text_parts.append(_read_attachment(str(part.get("file_id", "")), " ".join(text_parts)))
        prepared.append({"role": role, "content": "\n\n".join(text_parts)})
    return prepared


def _options(temperature: float | None, max_tokens: int | None) -> dict[str, Any]:
    logical = os.cpu_count() or 4
    threads = max(1, min(4, (logical + 1) // 2))
    return {
        "temperature": settings.temperature if temperature is None else temperature,
        "num_predict": settings.max_output_tokens if max_tokens is None else int(max_tokens),
        "num_ctx": 4096,
        "num_thread": threads,
        "top_p": 0.9,
        "repeat_penalty": 1.08,
    }


def generate_text(
    messages: list[dict[str, Any]],
    model: str | None = None,
    temperature: float | None = None,
    max_tokens: int | None = None,
) -> str:
    payload = {
        "model": model or settings.model,
        "messages": prepare_messages(messages),
        "stream": False,
        "options": _options(temperature, max_tokens),
        "keep_alive": "30m",
    }
    with httpx.Client(timeout=httpx.Timeout(settings.request_timeout, connect=10)) as client:
        response = client.post(f"{settings.local_base_url}/api/chat", json=payload)
    if response.is_error:
        raise RuntimeError(_error_text(response))
    data = response.json()
    try:
        content = data["message"]["content"]
        if not isinstance(content, str) or not content.strip():
            raise RuntimeError("Gemma 3 1B returned an empty assistant message.")
        return content
    except (KeyError, TypeError) as exc:
        raise RuntimeError(f"Unexpected Ollama response: {json.dumps(data)[:800]}") from exc


def parse_ollama_stream_chunk(raw: str) -> tuple[str, bool]:
    """Parse one Ollama JSONL chunk into display text and completion state."""
    try:
        item = json.loads(raw)
    except json.JSONDecodeError:
        return "", False
    if item.get("error"):
        raise RuntimeError(str(item["error"]))
    message = item.get("message") or {}
    content = message.get("content", "")
    return (content if isinstance(content, str) else ""), bool(item.get("done"))

def stream_text(
    messages: list[dict[str, Any]],
    model: str | None = None,
    temperature: float | None = None,
    max_tokens: int | None = None,
) -> Iterator[str]:
    payload = {
        "model": model or settings.model,
        "messages": prepare_messages(messages),
        "stream": True,
        "options": _options(temperature, max_tokens),
        "keep_alive": "30m",
    }
    with httpx.Client(timeout=httpx.Timeout(settings.request_timeout, connect=10, read=180)) as client:
        with client.stream("POST", f"{settings.local_base_url}/api/chat", json=payload) as response:
            if response.is_error:
                raise RuntimeError(_error_text(response))
            for line in response.iter_lines():
                if not line:
                    continue
                text, done = parse_ollama_stream_chunk(line)
                if text:
                    yield text
                if done:
                    break
