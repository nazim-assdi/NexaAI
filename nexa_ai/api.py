from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field

from .config import settings
from .file_store import file_store, guess_mime_type
from . import local_backend

app = FastAPI(title="Nexa AI Local API", version="2.1.0")


class ChatRequest(BaseModel):
    model: str | None = None
    messages: list[dict[str, Any]] = Field(default_factory=list)
    stream: bool = False
    temperature: float | None = None
    max_tokens: int | None = None


def _error(message: str, status_code: int = 400):
    return JSONResponse(
        status_code=status_code,
        content={"error": {"message": message, "type": "nexa_error"}},
    )


@app.get("/health")
def health():
    configured = False
    detail = ""
    try:
        local_backend.list_models()
        configured = True
    except Exception as exc:
        detail = str(exc)
    return {
        "ok": True,
        "service": "Nexa AI Local API",
        "provider": "local",
        "configured": configured,
        "detail": detail,
        "model": settings.model,
        "base_url": f"http://{settings.host}:{settings.port}/v1",
        "local_model_url": settings.local_base_url,
    }


@app.get("/v1/models")
def models():
    try:
        data = local_backend.list_models()
    except Exception:
        data = [{"id": settings.model, "object": "model", "owned_by": "local"}]
    return {"object": "list", "data": data}


@app.post("/v1/chat/completions")
def chat_completions(request: ChatRequest):
    if not request.messages:
        return _error("messages must contain at least one message.")
    request_id = f"chatcmpl-{uuid4().hex[:16]}"
    model = request.model or settings.model
    generate = local_backend.generate_text
    stream = local_backend.stream_text

    if request.stream:
        def event_stream():
            created = int(time.time())
            base = {"id": request_id, "object": "chat.completion.chunk", "created": created, "model": model}
            first = dict(base, choices=[{"index": 0, "delta": {"role": "assistant"}, "finish_reason": None}])
            yield f"data: {json.dumps(first, ensure_ascii=False)}\n\n"
            try:
                for piece in stream(request.messages, model, request.temperature, request.max_tokens):
                    chunk = dict(base, choices=[{"index": 0, "delta": {"content": piece}, "finish_reason": None}])
                    yield f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n"
                final = dict(base, choices=[{"index": 0, "delta": {}, "finish_reason": "stop"}])
                yield f"data: {json.dumps(final, ensure_ascii=False)}\n\n"
            except Exception as exc:
                error = {"error": {"message": str(exc), "type": "nexa_error"}}
                yield f"data: {json.dumps(error, ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"
        return StreamingResponse(
            event_stream(), media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    try:
        answer = generate(request.messages, model, request.temperature, request.max_tokens)
        return {
            "id": request_id,
            "object": "chat.completion",
            "created": int(time.time()),
            "model": model,
            "choices": [{"index": 0, "message": {"role": "assistant", "content": answer}, "finish_reason": "stop"}],
        }
    except Exception as exc:
        return _error(str(exc), 502)


@app.post("/v1/files")
async def upload_file(file: UploadFile = File(...)):
    filename = Path(file.filename or "upload.bin").name
    mime_type = guess_mime_type(filename, file.content_type)
    suffix = Path(filename).suffix.lower()
    text_extensions = {".txt", ".md", ".csv", ".json", ".xml", ".py", ".js", ".html", ".css", ".log"}
    allowed = (
        mime_type in {"image/jpeg", "image/png", "image/webp", "image/heic", "image/heif"}
        or mime_type.startswith("text/")
        or mime_type in {"application/pdf", "application/json", "application/xml", "application/javascript", "application/csv"}
        or suffix in text_extensions
    )
    if not allowed:
        raise HTTPException(
            status_code=415,
            detail="This edition supports Qwen2.5-Coder text/code files and online Gemini image attachments. Video attachments are not supported.",
        )

    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    suffix = Path(filename).suffix[:12]
    target_path = settings.upload_dir / f"{uuid4().hex}{suffix}"
    size = 0
    try:
        with target_path.open("wb") as target:
            while True:
                chunk = await file.read(1024 * 1024)
                if not chunk:
                    break
                size += len(chunk)
                if size > settings.max_upload_mb * 1024 * 1024:
                    raise HTTPException(status_code=413, detail=f"File exceeds the {settings.max_upload_mb} MB upload limit.")
                target.write(chunk)
        if size == 0:
            raise HTTPException(status_code=400, detail="The file is empty.")
        stored = file_store.add(filename, str(target_path), mime_type, size)
        return {
            "id": stored.id, "object": "file", "filename": stored.name,
            "bytes": stored.size, "mime_type": stored.mime_type, "status": "stored_locally",
        }
    except HTTPException:
        target_path.unlink(missing_ok=True)
        raise
    except Exception as exc:
        target_path.unlink(missing_ok=True)
        raise HTTPException(status_code=500, detail=f"Local file storage failed: {exc}") from exc
    finally:
        await file.close()


@app.get("/v1/files/{file_id}")
def get_file(file_id: str):
    stored = file_store.get(file_id)
    if not stored:
        raise HTTPException(status_code=404, detail="File not found.")
    return {"id": stored.id, "filename": stored.name, "bytes": stored.size, "mime_type": stored.mime_type}


@app.delete("/v1/files/{file_id}")
def delete_file(file_id: str):
    stored = file_store.delete(file_id)
    if not stored:
        raise HTTPException(status_code=404, detail="File not found.")
    Path(stored.path).unlink(missing_ok=True)
    return {"id": file_id, "deleted": True}
