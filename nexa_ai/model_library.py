from __future__ import annotations

import hashlib
import os
from pathlib import Path
from typing import Callable, Any

import httpx

MODEL_CATALOG: dict[str, dict[str, Any]] = {
    "qwen2.5-1.5b": {
        "id": "nexa-qwen2.5-1.5b",
        "name": "Qwen 2.5 1.5B Instruct",
        "description": "Balanced everyday chat, Bangla and English assistance.",
        "role": "Chat",
        "size_label": "1.12 GB",
        "minimum_bytes": 1_000_000_000,
        "filename": "qwen2.5-1.5b-instruct-q4_k_m.gguf",
        "bundled": True,
        "ram": "Works best on 8 GB RAM",
        "source": "Bundled with Nexa AI",
    },
    "qwen2.5-coder-1.5b": {
        "id": "nexa-qwen2.5-coder-1.5b",
        "name": "Qwen 2.5 Coder 1.5B",
        "description": "A coding-focused model for Python, JavaScript and debugging.",
        "role": "Coding",
        "size_label": "About 1.0 GB",
        "minimum_bytes": 900_000_000,
        "filename": "Qwen2.5-Coder-1.5B-Instruct-Q4_K_M.gguf",
        "url": "https://huggingface.co/tensorblock/Qwen2.5-Coder-1.5B-Instruct-GGUF/resolve/main/Qwen2.5-Coder-1.5B-Instruct-Q4_K_M.gguf",
        "ram": "Suitable for 8 GB RAM; one model loaded at a time",
        "source": "Hugging Face · tensorblock",
        "license": "Apache-2.0",
    },
    "smollm2-1.7b": {
        "id": "nexa-smollm2-1.7b",
        "name": "SmolLM2 1.7B Instruct",
        "description": "A compact alternative for general English chat and summarization.",
        "role": "Chat",
        "size_label": "About 1.1 GB",
        "minimum_bytes": 950_000_000,
        "filename": "SmolLM2-1.7B-Instruct-Q4_K_M.gguf",
        "url": "https://huggingface.co/bartowski/SmolLM2-1.7B-Instruct-GGUF/resolve/main/SmolLM2-1.7B-Instruct-Q4_K_M.gguf",
        "ram": "Suitable for 8 GB RAM; English-focused",
        "source": "Hugging Face · bartowski",
        "license": "Apache-2.0",
    },
    "qwen2.5-vl-3b": {
        "id": "nexa-qwen2.5-vl-3b",
        "name": "Qwen 2.5 VL 3B",
        "description": "Image understanding; can also inspect sampled video frames when the video plugin is enabled.",
        "role": "Vision",
        "size_label": "About 2.8 GB (model + projector)",
        "minimum_bytes": 1_800_000_000,
        "filename": "Qwen2.5-VL-3B-Instruct-Q4_K_M.gguf",
        "url": "https://huggingface.co/ggml-org/Qwen2.5-VL-3B-Instruct-GGUF/resolve/main/Qwen2.5-VL-3B-Instruct-Q4_K_M.gguf",
        "mmproj_filename": "mmproj-Qwen2.5-VL-3B-Instruct-Q8_0.gguf",
        "mmproj_url": "https://huggingface.co/ggml-org/Qwen2.5-VL-3B-Instruct-GGUF/resolve/main/mmproj-Qwen2.5-VL-3B-Instruct-Q8_0.gguf",
        "mmproj_minimum_bytes": 700_000_000,
        "ram": "Heavy for 8 GB RAM; best with 12–16 GB",
        "source": "Hugging Face · ggml-org",
        "license": "Apache-2.0",
        "warning": "Optional large vision model. Download only when image understanding is needed.",
    },
}


def model_directory(data_root: Path) -> Path:
    target = data_root / "models"
    target.mkdir(parents=True, exist_ok=True)
    return target


def model_paths(model_key: str, data_root: Path, bundled_model: Path) -> tuple[Path | None, Path | None]:
    item = MODEL_CATALOG.get(model_key)
    if not item:
        raise KeyError(f"Unknown model: {model_key}")
    if item.get("bundled"):
        return bundled_model, None
    folder = model_directory(data_root)
    model_path = folder / item["filename"]
    mmproj_path = folder / item["mmproj_filename"] if item.get("mmproj_filename") else None
    return model_path, mmproj_path


def model_is_installed(model_key: str, data_root: Path, bundled_model: Path) -> bool:
    item = MODEL_CATALOG.get(model_key)
    if not item:
        return False
    if item.get("bundled"):
        return bundled_model.is_file() and bundled_model.stat().st_size >= item["minimum_bytes"]
    model_path, mmproj_path = model_paths(model_key, data_root, bundled_model)
    if not model_path or not model_path.is_file() or model_path.stat().st_size < item["minimum_bytes"]:
        return False
    if mmproj_path:
        return mmproj_path.is_file() and mmproj_path.stat().st_size >= item["mmproj_minimum_bytes"]
    return True


def _download_one(
    url: str,
    destination: Path,
    minimum_bytes: int,
    progress: Callable[[str, int, int], None] | None = None,
    label: str = "model",
) -> None:
    partial = destination.with_suffix(destination.suffix + ".partial")
    destination.parent.mkdir(parents=True, exist_ok=True)
    partial.unlink(missing_ok=True)
    downloaded = 0
    expected = 0
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
                        downloaded += len(chunk)
                        if progress:
                            progress(label, downloaded, expected)
        if downloaded < minimum_bytes:
            raise RuntimeError(
                f"Downloaded file is incomplete ({downloaded:,} bytes; expected at least {minimum_bytes:,})."
            )
        partial.replace(destination)
    except Exception:
        partial.unlink(missing_ok=True)
        raise


def download_model(
    model_key: str,
    data_root: Path,
    bundled_model: Path,
    progress: Callable[[str, int, int], None] | None = None,
) -> tuple[Path, Path | None]:
    item = MODEL_CATALOG.get(model_key)
    if not item:
        raise KeyError(f"Unknown model: {model_key}")
    if item.get("bundled"):
        return bundled_model, None

    model_path, mmproj_path = model_paths(model_key, data_root, bundled_model)
    if not model_path:
        raise RuntimeError("Model target path could not be created.")

    if not model_path.exists() or model_path.stat().st_size < item["minimum_bytes"]:
        _download_one(item["url"], model_path, item["minimum_bytes"], progress, item["name"])

    if mmproj_path:
        if not mmproj_path.exists() or mmproj_path.stat().st_size < item["mmproj_minimum_bytes"]:
            _download_one(
                item["mmproj_url"], mmproj_path,
                item["mmproj_minimum_bytes"], progress,
                item["name"] + " vision projector",
            )

    return model_path, mmproj_path


def delete_model(model_key: str, data_root: Path, bundled_model: Path) -> None:
    item = MODEL_CATALOG.get(model_key)
    if not item or item.get("bundled"):
        raise ValueError("The bundled default model cannot be removed.")
    model_path, mmproj_path = model_paths(model_key, data_root, bundled_model)
    for path in (model_path, mmproj_path):
        if path:
            path.unlink(missing_ok=True)
