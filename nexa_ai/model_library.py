from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Callable, Any

import httpx

QWEN3_MODEL_KEY = "qwen3-4b"
QWEN3_MODEL_ID = "nexa-qwen3-4b"
QWEN3_MODEL_NAME = "Qwen3 4B Instruct Q4_K_M"
QWEN3_MODEL_FILENAME = "Qwen3-4B-Q4_K_M.gguf"

# Exactly one local chat/coding/reasoning model is supported.
MODEL_CATALOG: dict[str, dict[str, Any]] = {
    QWEN3_MODEL_KEY: {
        "id": QWEN3_MODEL_ID,
        "name": QWEN3_MODEL_NAME,
        "description": "The only NexaAI assistant model for Bengali/English chat, coding, reasoning, JSON and n8n workflow design.",
        "role": "All-in-one assistant",
        "size_label": "About 2.5 GB",
        "minimum_bytes": 2_300_000_000,
        "filename": QWEN3_MODEL_FILENAME,
        "url": "https://huggingface.co/Qwen/Qwen3-4B-GGUF/resolve/main/Qwen3-4B-Q4_K_M.gguf",
        "sha256": "7485fe6f11af29433bc51cab58009521f205840f5b4ae3a32fa7f92e8534fdf5",
        "ram": "Use 4K context on 8 GB RAM and close heavy apps",
        "source": "Hugging Face · Qwen official",
        "license": "Apache-2.0",
        "recommended": True,
    },
}


def model_directory(data_root: Path) -> Path:
    target = data_root / "models"
    target.mkdir(parents=True, exist_ok=True)
    return target


def model_paths(model_key: str, data_root: Path, bundled_model: Path | None = None) -> tuple[Path, None]:
    item = MODEL_CATALOG.get(model_key)
    if not item:
        raise KeyError(f"Unknown model: {model_key}")
    return model_directory(data_root) / item["filename"], None


def model_is_installed(model_key: str, data_root: Path, bundled_model: Path | None = None) -> bool:
    item = MODEL_CATALOG.get(model_key)
    if not item:
        return False
    model_path, _ = model_paths(model_key, data_root)
    return model_path.is_file() and model_path.stat().st_size >= item["minimum_bytes"]


def _download_one(
    url: str,
    destination: Path,
    minimum_bytes: int,
    progress: Callable[[str, int, int], None] | None = None,
    label: str = "model",
    expected_sha256: str | None = None,
) -> None:
    partial = destination.with_suffix(destination.suffix + ".partial")
    destination.parent.mkdir(parents=True, exist_ok=True)
    partial.unlink(missing_ok=True)
    downloaded = 0
    expected = 0
    digest = hashlib.sha256()
    try:
        with httpx.Client(follow_redirects=True, timeout=httpx.Timeout(1200, connect=30)) as client:
            with client.stream("GET", url) as response:
                response.raise_for_status()
                try:
                    expected = int(response.headers.get("content-length", "0"))
                except ValueError:
                    expected = 0
                with partial.open("wb") as output:
                    for chunk in response.iter_bytes(chunk_size=1024 * 1024):
                        if not chunk:
                            continue
                        output.write(chunk)
                        digest.update(chunk)
                        downloaded += len(chunk)
                        if progress:
                            progress(label, downloaded, expected)
        if downloaded < minimum_bytes:
            raise RuntimeError(
                f"Downloaded file is incomplete ({downloaded:,} bytes; expected at least {minimum_bytes:,})."
            )
        actual_sha256 = digest.hexdigest().lower()
        if expected_sha256 and actual_sha256 != expected_sha256.lower():
            raise RuntimeError(
                f"Model checksum verification failed. Expected {expected_sha256}, got {actual_sha256}."
            )
        partial.replace(destination)
    except Exception:
        partial.unlink(missing_ok=True)
        raise


def download_model(
    model_key: str,
    data_root: Path,
    bundled_model: Path | None = None,
    progress: Callable[[str, int, int], None] | None = None,
) -> tuple[Path, None]:
    item = MODEL_CATALOG.get(model_key)
    if not item:
        raise KeyError(f"Unknown model: {model_key}")
    model_path, _ = model_paths(model_key, data_root)
    if not model_is_installed(model_key, data_root):
        _download_one(
            item["url"], model_path, item["minimum_bytes"], progress, item["name"],
            expected_sha256=item.get("sha256"),
        )
    return model_path, None


def delete_model(model_key: str, data_root: Path, bundled_model: Path | None = None) -> None:
    raise ValueError("Qwen3 4B is the only supported NexaAI model and cannot be removed from the app.")
