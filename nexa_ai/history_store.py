from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class HistoryStore:
    """Atomic, local-only storage for Nexa AI conversation history."""

    def __init__(self, data_dir: Path) -> None:
        self.folder = Path(data_dir) / "chats"
        self.folder.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _safe_id(conversation_id: str) -> str:
        value = str(conversation_id)
        if not re.fullmatch(r"[a-f0-9]{32}", value):
            raise ValueError("Invalid conversation ID.")
        return value

    def save(
        self,
        conversation_id: str,
        title: str,
        messages: list[dict[str, Any]],
        model_id: str = "",
    ) -> Path:
        safe_id = self._safe_id(conversation_id)
        payload = {
            "id": safe_id,
            "title": (title or "New conversation").strip()[:120],
            "model": str(model_id)[:160],
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "messages": messages,
        }
        destination = self.folder / f"{safe_id}.json"
        temporary = destination.with_suffix(".tmp")
        temporary.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        temporary.replace(destination)
        return destination

    def list_conversations(self, limit: int = 500) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        for path in self.folder.glob("*.json"):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(data, list):
                    # Import old v1.0/v1.1 chat files which were saved as message arrays.
                    messages = data
                    conversation_id = hashlib.md5(path.name.encode("utf-8")).hexdigest()
                    title = next(
                        (
                            str(message.get("content", "")).strip().replace("\\n", " ")[:120]
                            for message in messages
                            if isinstance(message, dict) and message.get("role") == "user"
                        ),
                        "Older conversation",
                    )
                    updated_at = datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat()
                    model = ""
                elif isinstance(data, dict):
                    messages = data.get("messages", [])
                    if not isinstance(messages, list):
                        continue
                    conversation_id = self._safe_id(data.get("id", path.stem))
                    title = str(data.get("title") or "Conversation")[:120]
                    updated_at = str(data.get("updated_at") or "")
                    model = str(data.get("model") or "")
                else:
                    continue
                if not any(m.get("role") == "user" for m in messages if isinstance(m, dict)):
                    continue
                items.append({
                    "id": conversation_id,
                    "title": title,
                    "model": model,
                    "updated_at": updated_at,
                    "message_count": len(messages),
                })
            except (OSError, ValueError, TypeError, AttributeError):
                continue
        items.sort(key=lambda item: item["updated_at"], reverse=True)
        return items[:max(1, min(int(limit), 2000))]

    def load(self, conversation_id: str) -> dict[str, Any]:
        safe_id = self._safe_id(conversation_id)
        path = self.folder / f"{safe_id}.json"
        if path.is_file():
            data = json.loads(path.read_text(encoding="utf-8"))
            messages = data.get("messages")
            if not isinstance(messages, list):
                raise ValueError("Conversation history is damaged.")
            return data
        for legacy_path in self.folder.glob("chat-*.json"):
            if hashlib.md5(legacy_path.name.encode("utf-8")).hexdigest() == safe_id:
                messages = json.loads(legacy_path.read_text(encoding="utf-8"))
                if not isinstance(messages, list):
                    raise ValueError("Legacy conversation history is damaged.")
                return {
                    "id": safe_id,
                    "title": next(
                        (str(m.get("content", ""))[:120] for m in messages if isinstance(m, dict) and m.get("role") == "user"),
                        "Older conversation",
                    ),
                    "model": "",
                    "messages": messages,
                    "updated_at": datetime.fromtimestamp(legacy_path.stat().st_mtime, timezone.utc).isoformat(),
                }
        raise FileNotFoundError("Conversation history was not found.")

    def delete(self, conversation_id: str) -> bool:
        safe_id = self._safe_id(conversation_id)
        path = self.folder / f"{safe_id}.json"
        if path.is_file():
            path.unlink()
            return True
        for legacy_path in self.folder.glob("chat-*.json"):
            if hashlib.md5(legacy_path.name.encode("utf-8")).hexdigest() == safe_id:
                legacy_path.unlink()
                return True
        return False
