from __future__ import annotations

import argparse
import hashlib
import json
import socket
import subprocess
import sys
import time
from pathlib import Path
from urllib.request import Request, urlopen

import httpx

from nexa_ai.engine_config import build_engine_command, engine_profiles

MODEL_URL = "https://huggingface.co/Qwen/Qwen3-4B-GGUF/resolve/main/Qwen3-4B-Q4_K_M.gguf"
MODEL_SHA256 = "7485fe6f11af29433bc51cab58009521f205840f5b4ae3a32fa7f92e8534fdf5"
MINIMUM_BYTES = 2_300_000_000
MODEL_ID = "nexa-qwen3-4b"


def hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def ensure_model(path: Path) -> None:
    if path.is_file() and path.stat().st_size >= MINIMUM_BYTES and hash_file(path) == MODEL_SHA256:
        print(f"Using cached Qwen3 model: {path}", flush=True)
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    partial = path.with_suffix(path.suffix + ".partial")
    partial.unlink(missing_ok=True)
    digest = hashlib.sha256()
    size = 0
    with httpx.Client(follow_redirects=True, timeout=httpx.Timeout(1800, connect=30)) as client:
        with client.stream("GET", MODEL_URL) as response:
            response.raise_for_status()
            with partial.open("wb") as target:
                for chunk in response.iter_bytes(chunk_size=8 * 1024 * 1024):
                    if not chunk:
                        continue
                    target.write(chunk)
                    digest.update(chunk)
                    size += len(chunk)
                    if size // (256 * 1024 * 1024) != (size - len(chunk)) // (256 * 1024 * 1024):
                        print(f"Qwen3 smoke model: {size / (1024 ** 3):.2f} GiB", flush=True)
    if size < MINIMUM_BYTES or digest.hexdigest() != MODEL_SHA256:
        partial.unlink(missing_ok=True)
        raise RuntimeError(f"Qwen3 smoke model integrity check failed ({size:,} bytes).")
    partial.replace(path)


def unused_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def wait_ready(port: int, process: subprocess.Popen, seconds: int) -> bool:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if process.poll() is not None:
            return False
        try:
            with httpx.Client(timeout=3) as client:
                if client.get(f"http://127.0.0.1:{port}/health").status_code == 200:
                    return True
        except httpx.HTTPError:
            pass
        time.sleep(1)
    return False


def chat_test(port: int) -> str:
    payload = {
        "model": MODEL_ID,
        "messages": [{"role": "user", "content": "Reply with exactly: NEXA_OK"}],
        "temperature": 0,
        "max_tokens": 16,
        "stream": False,
    }
    request = Request(
        f"http://127.0.0.1:{port}/v1/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urlopen(request, timeout=240) as response:
        result = json.loads(response.read().decode("utf-8"))
    answer = result["choices"][0]["message"]["content"]
    if not isinstance(answer, str) or not answer.strip():
        raise RuntimeError(f"Chat endpoint returned empty content: {result!r}")
    return answer.strip()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runtime", required=True, type=Path)
    parser.add_argument("--model", required=True, type=Path)
    parser.add_argument("--log-dir", required=True, type=Path)
    args = parser.parse_args()

    runtime = args.runtime.resolve()
    model = args.model.resolve()
    args.log_dir.mkdir(parents=True, exist_ok=True)
    if not runtime.is_file():
        raise FileNotFoundError(runtime)
    ensure_model(model)

    failures: list[str] = []
    # The Core i3-friendly minimum-memory profile is tested first.
    profiles = list(reversed(engine_profiles(cpu_count=4)))
    for index, profile in enumerate(profiles, start=1):
        port = unused_port()
        log_path = args.log_dir / f"qwen3-smoke-{index}.log"
        command = build_engine_command(runtime, model, port, MODEL_ID, profile)
        print(
            f"Testing Qwen3 runtime: {profile['name']} "
            f"(ctx={profile['context']}, batch={profile['batch']}, threads={profile['threads']})",
            flush=True,
        )
        with log_path.open("w", encoding="utf-8", errors="replace") as log:
            process = subprocess.Popen(
                command,
                cwd=str(runtime.parent),
                stdin=subprocess.DEVNULL,
                stdout=log,
                stderr=subprocess.STDOUT,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            try:
                if not wait_ready(port, process, 420):
                    failures.append(f"{profile['name']}: health check failed, exit={process.poll()}, log={log_path}")
                    continue
                answer = chat_test(port)
                print(f"PASS: {profile['name']} started Qwen3 and returned: {answer[:100]}", flush=True)
                return 0
            except Exception as exc:
                failures.append(f"{profile['name']}: chat request failed: {exc}, log={log_path}")
            finally:
                if process.poll() is None:
                    process.terminate()
                    try:
                        process.wait(timeout=15)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait(timeout=10)

    raise RuntimeError("Qwen3 Windows end-to-end smoke test failed:\n" + "\n".join(failures))


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"QWEN3 WINDOWS SMOKE TEST FAILED: {exc}", file=sys.stderr, flush=True)
        raise
