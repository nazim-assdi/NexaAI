from __future__ import annotations

import json
import os
import threading
from pathlib import Path
from typing import Any, Iterator

from . import local_backend
from .secure_store import delete_secret, get_secret, has_secret, save_secret

_APP_DIR = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local")) / "NexaAI"
_SETTINGS_PATH = _APP_DIR / "cloud-settings.json"
_ENV_LOCK = threading.RLock()

_PROVIDER_ENV = {
    "gemini": "GEMINI_API_KEY",
    "groq": "GROQ_API_KEY",
    "openrouter": "OPENROUTER_API_KEY",
    "zai": "ZAI_API_KEY",
    "mistral": "MISTRAL_API_KEY",
    "nvidia": "NVIDIA_API_KEY",
    "cohere": "COHERE_API_KEY",
    "cloudflare_token": "CLOUDFLARE_API_TOKEN",
    "cloudflare_account_id": "CLOUDFLARE_ACCOUNT_ID",
    "kilo": "KILO_API_KEY",
}
PROVIDER_LABELS = {
    "gemini": "Google Gemini",
    "groq": "Groq",
    "openrouter": "OpenRouter",
    "zai": "Z.ai",
    "mistral": "Mistral",
    "nvidia": "NVIDIA NIM",
    "cohere": "Cohere",
    "cloudflare_token": "Cloudflare API Token",
    "cloudflare_account_id": "Cloudflare Account ID",
    "kilo": "Kilo Gateway",
}
PROVIDER_URLS = {
    "gemini": "https://aistudio.google.com/apikey",
    "groq": "https://console.groq.com/keys",
    "openrouter": "https://openrouter.ai/keys",
    "zai": "https://z.ai/manage-apikey/apikey-list",
    "mistral": "https://console.mistral.ai/api-keys",
    "nvidia": "https://build.nvidia.com/settings/api-keys",
    "cohere": "https://dashboard.cohere.com/api-keys",
    "cloudflare_token": "https://dash.cloudflare.com/profile/api-tokens",
    "cloudflare_account_id": "https://dash.cloudflare.com/",
    "kilo": "https://app.kilo.ai",
}


def load_settings() -> dict[str, Any]:
    try:
        data = json.loads(_SETTINGS_PATH.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return {"allow_public_endpoints": bool(data.get("allow_public_endpoints", False))}
    except (OSError, ValueError):
        pass
    return {"allow_public_endpoints": False}


def save_settings(*, allow_public_endpoints: bool) -> None:
    _APP_DIR.mkdir(parents=True, exist_ok=True)
    temporary = _SETTINGS_PATH.with_suffix(".tmp")
    temporary.write_text(json.dumps({"allow_public_endpoints": bool(allow_public_endpoints)}, indent=2), encoding="utf-8")
    temporary.replace(_SETTINGS_PATH)


def save_provider_key(name: str, value: str) -> None:
    if name not in _PROVIDER_ENV:
        raise ValueError("Unknown FreeLM provider.")
    save_secret(name, value.strip())


def delete_provider_key(name: str) -> None:
    if name not in _PROVIDER_ENV:
        raise ValueError("Unknown FreeLM provider.")
    delete_secret(name)


def provider_status() -> dict[str, Any]:
    saved_ids = set()
    for name in PROVIDER_LABELS:
        try:
            if has_secret(name):
                saved_ids.add(name)
        except Exception:
            pass
    cloudflare_ready = {"cloudflare_token", "cloudflare_account_id"}.issubset(saved_ids)
    names = [PROVIDER_LABELS[name] for name in saved_ids if not name.startswith("cloudflare_")]
    if cloudflare_ready:
        names.append("Cloudflare Workers AI")
    allow_public = load_settings()["allow_public_endpoints"]
    return {
        "providers": sorted(names),
        "saved_fields": sorted(saved_ids),
        "allow_public_endpoints": allow_public,
        "configured": bool(names) or allow_public,
    }


def _build_client():
    try:
        from freelm import FreeLLM
    except ImportError as exc:
        raise RuntimeError("FreeLM cloud support is not installed in this build. Update NexaAI.") from exc

    with _ENV_LOCK:
        previous: dict[str, str | None] = {}
        try:
            for env_name in _PROVIDER_ENV.values():
                previous[env_name] = os.environ.get(env_name)
                os.environ.pop(env_name, None)
            for slot, env_name in _PROVIDER_ENV.items():
                value = get_secret(slot)
                if value:
                    os.environ[env_name] = value
            return FreeLLM.from_env(
                keyless=load_settings()["allow_public_endpoints"],
                strategy="quota_aware",
                timeout=150,
                max_attempts=12,
                hedge=False,
                wait=False,
                persist=True,
            )
        except Exception as exc:
            message = str(exc).lower()
            if "no provider keys found" in message or "no provider" in message:
                raise RuntimeError(
                    "No FreeLM provider is configured. Add a free provider API key in FreeLM Cloud Settings, "
                    "or explicitly allow public keyless endpoints there."
                ) from exc
            raise
        finally:
            for env_name, value in previous.items():
                if value is None:
                    os.environ.pop(env_name, None)
                else:
                    os.environ[env_name] = value


def generate_text(messages: list[dict[str, Any]], model: str | None = None,
                  temperature: float | None = None, max_tokens: int | None = None) -> str:
    prepared = local_backend.prepare_messages(messages)
    with _build_client() as llm:
        response = llm.chat(prepared, model=model or "chat:large",
                            temperature=temperature, max_tokens=max_tokens)
    answer = response.text.strip()
    if not answer:
        raise RuntimeError("FreeLM providers returned an empty response.")
    return answer


def stream_text(messages: list[dict[str, Any]], model: str | None = None,
                temperature: float | None = None, max_tokens: int | None = None) -> Iterator[str]:
    prepared = local_backend.prepare_messages(messages)
    with _build_client() as llm:
        yield from llm.stream(prepared, model=model or "chat:large",
                              temperature=temperature, max_tokens=max_tokens)


def test_connection() -> dict[str, str]:
    with _build_client() as llm:
        response = llm.chat([{"role": "user", "content": "Reply with the single word OK."}],
                            model="chat:fast", temperature=0, max_tokens=8)
    return {
        "provider": response.provider or "Unknown provider",
        "model": response.model or "FreeLM model",
        "response": response.text[:80],
    }
