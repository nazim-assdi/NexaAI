from __future__ import annotations

import json
import mimetypes
import threading
from dataclasses import asdict, dataclass
from pathlib import Path
from uuid import uuid4

from .config import settings


@dataclass
class StoredFile:
    id: str
    name: str
    path: str
    mime_type: str
    size: int


class FileStore:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        settings.upload_dir.mkdir(parents=True, exist_ok=True)
        self._items: dict[str, StoredFile] = {}
        if settings.file_index.exists():
            try:
                payload = json.loads(settings.file_index.read_text(encoding="utf-8"))
                for key, value in payload.items():
                    self._items[key] = StoredFile(**value)
            except (OSError, ValueError, TypeError):
                self._items = {}

    def add(self, name: str, path: str, mime_type: str, size: int) -> StoredFile:
        item = StoredFile(
            id=f"file_{uuid4().hex}",
            name=Path(name).name,
            path=str(Path(path).resolve()),
            mime_type=mime_type,
            size=size,
        )
        with self._lock:
            self._items[item.id] = item
            self._save()
        return item

    def get(self, file_id: str) -> StoredFile | None:
        with self._lock:
            return self._items.get(file_id)

    def delete(self, file_id: str) -> StoredFile | None:
        with self._lock:
            item = self._items.pop(file_id, None)
            if item:
                self._save()
            return item

    def _save(self) -> None:
        settings.data_dir.mkdir(parents=True, exist_ok=True)
        tmp = settings.file_index.with_suffix(".tmp")
        tmp.write_text(
            json.dumps({key: asdict(value) for key, value in self._items.items()}, indent=2),
            encoding="utf-8",
        )
        tmp.replace(settings.file_index)


file_store = FileStore()


def guess_mime_type(filename: str, supplied: str | None = None) -> str:
    guessed, _ = mimetypes.guess_type(filename)
    return supplied or guessed or "application/octet-stream"
