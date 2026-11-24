from __future__ import annotations
import concurrent.futures
import hashlib
import json
import math
import re
import shutil
import threading
import time
from pathlib import Path
from typing import Callable, Any
import httpx

QWEN3_MODEL_KEY = "qwen3-4b"
QWEN3_MODEL_ID = "nexa-qwen3-4b"
QWEN3_MODEL_NAME = "Qwen3 4B Instruct Q4_K_M"
QWEN3_MODEL_FILENAME = "Qwen3-4B-Q4_K_M.gguf"
DOWNLOAD_CHUNK_SIZE = 64 * 1024 * 1024
DOWNLOAD_WORKERS = 4

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
        "ram": "Automatic 4K/2K/1K CPU profiles based on available memory",
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


def _parse_content_range(value: str | None) -> tuple[int, int, int] | None:
    if not value:
        return None
    match = re.fullmatch(r"bytes\s+(\d+)-(\d+)/(\d+)", value.strip(), flags=re.IGNORECASE)
    if not match:
        return None
    start, end, total = (int(part) for part in match.groups())
    if start < 0 or end < start or total <= end:
        return None
    return start, end, total


def _hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().lower()


def _probe_range_support(url: str) -> int | None:
    """Probe one byte. If Range is ignored, close without reading the full file."""
    with httpx.Client(follow_redirects=True, timeout=httpx.Timeout(90, connect=30)) as client:
        with client.stream("GET", url, headers={"Range": "bytes=0-0"}) as response:
            if response.status_code != 206:
                return None
            content_range = _parse_content_range(response.headers.get("content-range"))
            if not content_range or content_range[:2] != (0, 0):
                return None
            next(response.iter_bytes(chunk_size=1), b"")
            return content_range[2]


def _download_parallel(url: str, destination: Path, total: int, progress, label: str) -> None:
    part_dir = destination.with_name(destination.name + ".parts")
    meta_path = part_dir / "download.json"
    part_dir.mkdir(parents=True, exist_ok=True)
    expected_meta = {"total": total, "chunk_size": DOWNLOAD_CHUNK_SIZE}
    try:
        current_meta = json.loads(meta_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        current_meta = None
    if current_meta != expected_meta:
        shutil.rmtree(part_dir, ignore_errors=True)
        part_dir.mkdir(parents=True, exist_ok=True)
        meta_path.write_text(json.dumps(expected_meta), encoding="utf-8")

    count = math.ceil(total / DOWNLOAD_CHUNK_SIZE)
    progress_by_index: dict[int, int] = {}
    for index in range(count):
        start = index * DOWNLOAD_CHUNK_SIZE
        expected = min(DOWNLOAD_CHUNK_SIZE, total - start)
        part = part_dir / f"chunk-{index:04d}.bin"
        size = part.stat().st_size if part.is_file() else 0
        progress_by_index[index] = expected if size == expected else 0
        if size != expected:
            part.unlink(missing_ok=True)

    lock = threading.Lock()
    last_report = [0.0]

    def report(index: int, current: int) -> None:
        if not progress:
            return
        now = time.monotonic()
        with lock:
            progress_by_index[index] = current
            if now - last_report[0] < 0.25 and current < min(DOWNLOAD_CHUNK_SIZE, total - index * DOWNLOAD_CHUNK_SIZE):
                return
            last_report[0] = now
            done = sum(progress_by_index.values())
        progress(label, done, total)

    def fetch_chunk(index: int) -> None:
        start = index * DOWNLOAD_CHUNK_SIZE
        end = min(total - 1, start + DOWNLOAD_CHUNK_SIZE - 1)
        expected = end - start + 1
        part = part_dir / f"chunk-{index:04d}.bin"
        if part.is_file() and part.stat().st_size == expected:
            return
        temp = part.with_suffix(".tmp")
        last_error = None
        for attempt in range(4):
            temp.unlink(missing_ok=True)
            received = 0
            try:
                with httpx.Client(
                    follow_redirects=True,
                    timeout=httpx.Timeout(600, connect=30, read=120, write=120, pool=30),
                ) as client:
                    with client.stream("GET", url, headers={"Range": f"bytes={start}-{end}"}) as response:
                        if response.status_code != 206:
                            raise RuntimeError(f"Range request returned HTTP {response.status_code}; expected 206.")
                        actual_range = _parse_content_range(response.headers.get("content-range"))
                        if actual_range != (start, end, total):
                            raise RuntimeError(f"Unexpected byte range: {response.headers.get('content-range', 'missing')}.")
                        with temp.open("wb") as target:
                            for chunk in response.iter_bytes(chunk_size=4 * 1024 * 1024):
                                if chunk:
                                    target.write(chunk)
                                    received += len(chunk)
                                    report(index, received)
                if received != expected:
                    raise RuntimeError(f"Segment {index + 1}/{count} incomplete ({received:,}/{expected:,} bytes).")
                temp.replace(part)
                report(index, expected)
                return
            except Exception as exc:
                last_error = exc
                temp.unlink(missing_ok=True)
                report(index, 0)
                if attempt < 3:
                    time.sleep(1.5 * (attempt + 1))
        raise RuntimeError(f"Segment {index + 1}/{count} failed after retries: {last_error}") from last_error

    with concurrent.futures.ThreadPoolExecutor(max_workers=min(DOWNLOAD_WORKERS, count), thread_name_prefix="NexaDownload") as pool:
        futures = [pool.submit(fetch_chunk, index) for index in range(count)]
        for future in concurrent.futures.as_completed(futures):
            future.result()

    partial = destination.with_suffix(destination.suffix + ".partial")
    with partial.open("wb") as target:
        for index in range(count):
            with (part_dir / f"chunk-{index:04d}.bin").open("rb") as source:
                shutil.copyfileobj(source, target, length=8 * 1024 * 1024)
    if partial.stat().st_size != total:
        raise RuntimeError(f"Merged model size mismatch ({partial.stat().st_size:,}/{total:,} bytes).")
    partial.replace(destination)
    shutil.rmtree(part_dir, ignore_errors=True)
    if progress:
        progress(label, total, total)


def _download_sequential(url: str, destination: Path, minimum_bytes: int, progress, label: str) -> None:
    partial = destination.with_suffix(destination.suffix + ".partial")
    for attempt in range(4):
        offset = partial.stat().st_size if partial.is_file() else 0
        headers = {"Range": f"bytes={offset}-"} if offset else {}
        try:
            with httpx.Client(
                follow_redirects=True,
                timeout=httpx.Timeout(1200, connect=30, read=120, write=120),
            ) as client:
                with client.stream("GET", url, headers=headers) as response:
                    response.raise_for_status()
                    content_range = _parse_content_range(response.headers.get("content-range"))
                    if offset and response.status_code == 206:
                        if not content_range or content_range[0] != offset:
                            raise RuntimeError("Server returned an invalid resume range.")
                        mode, total = "ab", content_range[2]
                    else:
                        mode, offset = "wb", 0
                        try:
                            total = int(response.headers.get("content-length", "0"))
                        except ValueError:
                            total = 0
                    done, last_report = offset, 0.0
                    with partial.open(mode) as target:
                        for chunk in response.iter_bytes(chunk_size=4 * 1024 * 1024):
                            if not chunk:
                                continue
                            target.write(chunk)
                            done += len(chunk)
                            now = time.monotonic()
                            if progress and (now - last_report >= 0.25 or (total and done >= total)):
                                progress(label, done, total)
                                last_report = now
            size = partial.stat().st_size
            if size >= minimum_bytes and (not total or size >= total):
                return
            raise RuntimeError(f"Download ended early ({size:,} bytes).")
        except Exception:
            if attempt >= 3:
                raise
            time.sleep(1.5 * (attempt + 1))


def _download_one(url: str, destination: Path, minimum_bytes: int, progress=None, label="model", expected_sha256=None) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    total = _probe_range_support(url)
    if total and total >= minimum_bytes:
        _download_parallel(url, destination, total, progress, label)
    else:
        _download_sequential(url, destination, minimum_bytes, progress, label)

    if not destination.is_file():
        partial = destination.with_suffix(destination.suffix + ".partial")
        if not partial.is_file():
            raise RuntimeError("Model download did not produce a local file.")
        partial.replace(destination)
    size = destination.stat().st_size
    if size < minimum_bytes:
        destination.unlink(missing_ok=True)
        raise RuntimeError(f"Downloaded file is incomplete ({size:,} bytes; expected at least {minimum_bytes:,}).")
    actual = _hash_file(destination)
    if expected_sha256 and actual != expected_sha256.lower():
        destination.unlink(missing_ok=True)
        shutil.rmtree(destination.with_name(destination.name + ".parts"), ignore_errors=True)
        raise RuntimeError(f"Model SHA-256 verification failed: expected {expected_sha256}, got {actual}.")


def download_model(model_key: str, data_root: Path, bundled_model: Path | None = None, progress=None) -> tuple[Path, None]:
    item = MODEL_CATALOG.get(model_key)
    if not item:
        raise KeyError(f"Unknown model: {model_key}")
    model_path, _ = model_paths(model_key, data_root)
    if not model_is_installed(model_key, data_root):
        _download_one(item["url"], model_path, item["minimum_bytes"], progress, item["name"], item.get("sha256"))
    return model_path, None


def delete_model(model_key: str, data_root: Path, bundled_model: Path | None = None) -> None:
    raise ValueError("Qwen3 4B is the only supported NexaAI model and cannot be removed from the app.")
