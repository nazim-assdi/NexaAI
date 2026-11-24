from __future__ import annotations

import os
from pathlib import Path
from typing import Any


def engine_profiles(cpu_count: int | None = None) -> list[dict[str, Any]]:
    logical_cpus = cpu_count or os.cpu_count() or 4
    normal_threads = max(2, min(4, logical_cpus))
    fallback_threads = max(1, min(2, logical_cpus))
    return [
        {"name": "Balanced", "context": 4096, "batch": 128, "ubatch": 64, "threads": normal_threads, "jinja": True},
        {"name": "Low memory", "context": 2048, "batch": 64, "ubatch": 32, "threads": fallback_threads, "jinja": False},
        {"name": "Minimum memory", "context": 1024, "batch": 32, "ubatch": 16, "threads": fallback_threads, "jinja": False},
    ]


def build_engine_command(executable: str | Path, model_path: str | Path, port: int, model_alias: str, profile: dict[str, Any]) -> list[str]:
    command = [
        str(executable), "-m", str(model_path),
        "--host", "127.0.0.1", "--port", str(port),
        "--ctx-size", str(profile["context"]),
        "--batch-size", str(profile["batch"]),
        "--ubatch-size", str(profile["ubatch"]),
        "--threads", str(profile["threads"]),
        "--threads-batch", str(profile["threads"]),
        "--n-gpu-layers", "0",
        "--parallel", "1",
        "--alias", model_alias,
        "--no-webui", "--offline",
    ]
    if profile.get("jinja", False):
        command.append("--jinja")
    return command
