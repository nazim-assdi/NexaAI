from __future__ import annotations

import argparse
import json

import httpx

from nexa_ai.ollama_runtime import OLLAMA_BASE_URL, OLLAMA_MODEL, OllamaRuntime


def main() -> int:
    parser = argparse.ArgumentParser(description="Smoke-test the local Ollama Gemma 3 1B runtime.")
    parser.add_argument("--base-url", default=OLLAMA_BASE_URL)
    args = parser.parse_args()
    runtime = OllamaRuntime(base_url=args.base_url)
    if not runtime.server_ready():
        raise RuntimeError("Ollama is not running. Install/start Ollama before running this optional smoke test.")
    if OLLAMA_MODEL not in runtime.installed_models():
        raise RuntimeError("Gemma 3 1B is not installed. Pull gemma3:1b first.")
    payload = {
        "model": OLLAMA_MODEL,
        "messages": [{"role": "user", "content": "Reply with exactly NEXA_OK"}],
        "stream": False,
        "options": {"temperature": 0, "num_predict": 32, "num_ctx": 1024},
    }
    with httpx.Client(timeout=180) as client:
        response = client.post(f"{args.base_url.rstrip('/')}/api/chat", json=payload)
        response.raise_for_status()
        result = response.json()
    answer = str((result.get("message") or {}).get("content", "")).strip()
    if not answer:
        raise RuntimeError("Ollama returned an empty answer.")
    print(json.dumps({"model": OLLAMA_MODEL, "answer": answer}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
