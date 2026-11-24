from __future__ import annotations

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
                messages = data.get("messages", [])
                if not isinstance(messages, list):
                    continue
                conversation_id = self._safe_id(data.get("id", path.stem))
                if not any(m.get("role") == "user" for m in messages if isinstance(m, dict)):
                    continue
                items.append({
                    "id": conversation_id,
                    "title": str(data.get("title") or "Conversation")[:120],
                    "model": str(data.get("model") or ""),
                    "updated_at": str(data.get("updated_at") or ""),
                    "message_count": len(messages),
                })
            except (OSError, ValueError, TypeError, AttributeError):
                continue
        items.sort(key=lambda item: item["updated_at"], reverse=True)
        return items[:max(1, min(int(limit), 2000))]

    def load(self, conversation_id: str) -> dict[str, Any]:
        safe_id = self._safe_id(conversation_id)
        path = self.folder / f"{safe_id}.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        messages = data.get("messages")
        if not isinstance(messages, list):
            raise ValueError("Conversation history is damaged.")
        return data

    def delete(self, conversation_id: str) -> bool:
        safe_id = self._safe_id(conversation_id)
        path = self.folder / f"{safe_id}.json"
        if not path.exists():
            return False
        path.unlink()
        return True
