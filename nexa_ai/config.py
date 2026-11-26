from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

APP_DATA = Path(os.environ.get("NEXA_DATA_DIR", Path.home() / "AppData" / "Local" / "NexaAI" / "Data")).expanduser()
load_dotenv(override=False)


@dataclass(frozen=True)
class Settings:
    local_base_url: str = os.getenv("NEXA_LOCAL_BASE_URL", "http://127.0.0.1:11439").strip().rstrip("/")
    local_api_key: str = os.getenv("NEXA_LOCAL_API_KEY", "").strip()
    model: str = os.getenv("NEXA_MODEL", "qwen2.5-coder:1.5b").strip()
    host: str = os.getenv("NEXA_HOST", "127.0.0.1").strip()
    port: int = int(os.getenv("NEXA_PORT", "8000"))
    temperature: float = float(os.getenv("NEXA_TEMPERATURE", "0.7"))
    max_output_tokens: int = int(os.getenv("NEXA_MAX_OUTPUT_TOKENS", "1536"))
    max_upload_mb: int = int(os.getenv("NEXA_MAX_UPLOAD_MB", "100"))
    max_pdf_chars: int = int(os.getenv("NEXA_MAX_PDF_CHARS", "24000"))
    request_timeout: int = int(os.getenv("NEXA_REQUEST_TIMEOUT", "900"))
    data_dir: Path = APP_DATA

    @property
    def upload_dir(self) -> Path:
        return self.data_dir / "uploads"

    @property
    def file_index(self) -> Path:
        return self.data_dir / "file-index.json"


settings = Settings()
