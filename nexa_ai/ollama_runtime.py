from __future__ import annotations

import os
import shutil
import subprocess
import time
from pathlib import Path
from typing import Callable, Any

import httpx


OLLAMA_BASE_URL = "http://127.0.0.1:11434"
OLLAMA_MODEL = "gemma3:1b"
OLLAMA_MODEL_NAME = "Gemma 3 1B"
OLLAMA_MODEL_SIZE = "About 806 MB"


class OllamaNotInstalled(RuntimeError):
    pass


class OllamaRuntime:
    def __init__(self, base_url: str = OLLAMA_BASE_URL, model: str = OLLAMA_MODEL) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.process: subprocess.Popen | None = None
        self.started_by_nexa = False

    @staticmethod
    def find_executable() -> Path | None:
        located = shutil.which("ollama")
        if located:
            candidate = Path(located)
            if candidate.is_file():
                return candidate
        local = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
        program_files = Path(os.environ.get("ProgramFiles", r"C:\Program Files"))
        candidates = (
            local / "Programs" / "Ollama" / "ollama.exe",
            program_files / "Ollama" / "ollama.exe",
            Path.home() / "AppData" / "Local" / "Programs" / "Ollama" / "ollama.exe",
        )
        return next((path for path in candidates if path.is_file()), None)

    def server_ready(self, timeout: float = 2.5) -> bool:
        try:
            with httpx.Client(timeout=timeout) as client:
                response = client.get(f"{self.base_url}/api/version")
                return response.is_success and isinstance(response.json(), dict)
        except (httpx.HTTPError, ValueError, OSError):
            return False

    def ensure_server(self, log_handle=None, timeout_seconds: int = 45) -> None:
        if self.server_ready():
            return
        executable = self.find_executable()
        if executable is None:
            raise OllamaNotInstalled(
                "Ollama is not installed. Install the official Windows version from https://ollama.com/download/windows, "
                "finish setup, then restart NexaAI."
            )
        environment = os.environ.copy()
        environment["OLLAMA_HOST"] = "127.0.0.1:11434"
        environment.setdefault("OLLAMA_KEEP_ALIVE", "30m")
        try:
            kwargs: dict[str, Any] = {
                "cwd": str(executable.parent),
                "stdin": subprocess.DEVNULL,
                "stdout": log_handle if log_handle is not None else subprocess.DEVNULL,
                "stderr": subprocess.STDOUT if log_handle is not None else subprocess.DEVNULL,
                "env": environment,
            }
            if os.name == "nt":
                kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)
            self.process = subprocess.Popen([str(executable), "serve"], **kwargs)
            self.started_by_nexa = True
        except OSError as exc:
            raise RuntimeError(f"Could not start Ollama: {exc}") from exc

        deadline = time.monotonic() + max(5, timeout_seconds)
        while time.monotonic() < deadline:
            if self.server_ready(timeout=2):
                return
            if self.process and self.process.poll() is not None:
                raise RuntimeError(f"Ollama server exited during startup (exit code {self.process.returncode}).")
            time.sleep(0.5)
        raise RuntimeError(
            "Ollama is installed but its local service did not become ready. "
            "Close any stuck Ollama process and restart NexaAI."
        )

    def installed_models(self) -> list[str]:
        with httpx.Client(timeout=10) as client:
            response = client.get(f"{self.base_url}/api/tags")
            response.raise_for_status()
            payload = response.json()
        models = payload.get("models", []) if isinstance(payload, dict) else []
        return [
            str(item.get("name") or item.get("model"))
            for item in models
            if isinstance(item, dict) and (item.get("name") or item.get("model"))
        ]

    def ensure_model(self, progress: Callable[[str, int, int, float], None] | None = None) -> None:
        if self.model in self.installed_models():
            return

        last_time = time.monotonic()
        last_bytes = 0
        timeout = httpx.Timeout(1800, connect=20, read=180, write=60, pool=30)
        with httpx.Client(timeout=timeout) as client:
            with client.stream(
                "POST", f"{self.base_url}/api/pull",
                json={"name": self.model, "stream": True},
            ) as response:
                if response.is_error:
                    try:
                        detail = response.json().get("error", response.text)
                    except ValueError:
                        detail = response.text
                    raise RuntimeError(f"Ollama model download failed: {detail}")
                for line in response.iter_lines():
                    if not line:
                        continue
                    try:
                        import json
                        item = json.loads(line)
                    except ValueError:
                        continue
                    if item.get("error"):
                        raise RuntimeError(f"Ollama model download failed: {item['error']}")
                    status = str(item.get("status", "Downloading Gemma 3 1B"))
                    completed = int(item.get("completed", 0) or 0)
                    total = int(item.get("total", 0) or 0)
                    now = time.monotonic()
                    elapsed = max(0.001, now - last_time)
                    speed = max(0.0, (completed - last_bytes) / elapsed)
                    if progress:
                        progress(status, completed, total, speed)
                    last_time, last_bytes = now, completed

        if self.model not in self.installed_models():
            raise RuntimeError("Ollama finished the model pull but Gemma 3 1B is not listed as installed.")

    def stop(self) -> None:
        if not self.started_by_nexa or not self.process or self.process.poll() is not None:
            return
        self.process.terminate()
        try:
            self.process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self.process.kill()
            try:
                self.process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                pass
        self.process = None
        self.started_by_nexa = False
