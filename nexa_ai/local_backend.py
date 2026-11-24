from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import httpx

from .config import settings
from .file_store import StoredFile, file_store


class LocalModelUnavailable(RuntimeError):
    pass


def _headers() -> dict[str, str]:
    headers = {"Content-Type": "application/json"}
    if settings.local_api_key:
        headers["Authorization"] = f"Bearer {settings.local_api_key}"
    return headers


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
            response = client.get(f"{settings.local_base_url}/models", headers=_headers())
            response.raise_for_status()
            payload = response.json()
    except Exception as exc:
        raise LocalModelUnavailable(f"Bundled local model is not ready: {exc}") from exc
    models = payload.get("data", []) if isinstance(payload, dict) else []
    return [item for item in models if isinstance(item, dict) and item.get("id")] if isinstance(models, list) else []


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
            raise ValueError(f"No selectable text was found in {stored.name}. Scanned PDF OCR is not included in this build.")
        return f"Attached PDF: {stored.name}\n{prompt}\n\n{extracted[:settings.max_pdf_chars]}"

    allowed_text = stored.mime_type.startswith("text/") or stored.mime_type in {
        "application/json", "application/xml", "application/javascript", "application/csv",
    }
    if allowed_text or path.suffix.lower() in {".txt", ".md", ".csv", ".json", ".xml", ".py", ".js", ".html", ".css", ".log"}:
        text = path.read_text(encoding="utf-8", errors="replace")
        return f"Attached file: {stored.name}\n{prompt}\n\n{text[:settings.max_pdf_chars]}"

    raise ValueError(f"This desktop build supports PDF and text/code files only: {stored.name}")


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
            part_type = part.get("type")
            if part_type in {"text", "input_text"}:
                text_parts.append(str(part.get("text", "")))
            elif part_type in {"file", "input_file"}:
                text_parts.append(_read_attachment(str(part.get("file_id", "")), " ".join(text_parts)))

        prepared.append({"role": role, "content": "\n\n".join(text_parts)})
    return prepared


def _parse_content(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return "".join(str(item.get("text", "")) for item in value if isinstance(item, dict))
    return ""


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
        "temperature": settings.temperature if temperature is None else temperature,
        "max_tokens": settings.max_output_tokens if max_tokens is None else max_tokens,
    }
    with httpx.Client(timeout=httpx.Timeout(settings.request_timeout, connect=10)) as client:
        response = client.post(f"{settings.local_base_url}/chat/completions", headers=_headers(), json=payload)
    if response.is_error:
        raise RuntimeError(_error_text(response))
    data = response.json()
    try:
        return _parse_content(data["choices"][0]["message"]["content"])
    except (KeyError, IndexError, TypeError) as exc:
        raise RuntimeError(f"Unexpected local model response: {json.dumps(data)[:800]}") from exc


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
        "temperature": settings.temperature if temperature is None else temperature,
        "max_tokens": settings.max_output_tokens if max_tokens is None else max_tokens,
    }
    with httpx.Client(timeout=httpx.Timeout(settings.request_timeout, connect=10)) as client:
        with client.stream("POST", f"{settings.local_base_url}/chat/completions", headers=_headers(), json=payload) as response:
            if response.is_error:
                raise RuntimeError(_error_text(response))
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
                    error = item["error"]
                    raise RuntimeError(error.get("message", str(error)) if isinstance(error, dict) else str(error))
                choices = item.get("choices") or []
                if choices:
                    text = _parse_content(choices[0].get("delta", {}).get("content"))
                    if text:
                        yield text
