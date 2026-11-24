from __future__ import annotations

import importlib.util
import json
import re
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable


PLUGIN_CATALOG: list[dict[str, Any]] = [
    {
        "id": "vision-video",
        "name": "Vision & Video Understanding",
        "category": "AI Vision",
        "description": "Uses the optional Qwen2.5-VL model to describe images and analyze selected video frames.",
        "requires": "Qwen2.5-VL 3B model + vision projector; FFmpeg for video",
        "default_enabled": False,
        "status": "Optional model pack",
    },
    {
        "id": "audio-transcription",
        "name": "Offline Audio Transcription",
        "category": "Audio",
        "description": "Transcribes speech locally with Whisper.cpp; supports multilingual audio.",
        "requires": "Whisper.cpp runtime + Whisper model",
        "default_enabled": False,
        "status": "Optional runtime pack",
    },
    {
        "id": "bangla-ocr",
        "name": "Bangla + English OCR",
        "category": "Documents",
        "description": "Extracts text from scanned images and PDF pages with local OCR.",
        "requires": "Tesseract runtime + Bengali and English language data",
        "default_enabled": False,
        "status": "Optional runtime pack",
    },
    {
        "id": "image-studio",
        "name": "Offline Image Studio",
        "category": "Generation",
        "description": "Local text-to-image generation using stable-diffusion.cpp and a compatible model.",
        "requires": "Stable Diffusion CPU runtime + image model; large downloads and slow CPU rendering",
        "default_enabled": False,
        "status": "Advanced optional pack",
    },
    {
        "id": "motion-studio",
        "name": "Motion Video Studio",
        "category": "Generation",
        "description": "Creates MP4 motion clips from images with pan, zoom and transition presets. This is not a full AI video diffusion model.",
        "requires": "FFmpeg runtime",
        "default_enabled": False,
        "status": "Lightweight optional pack",
    },
    {
        "id": "ai-video-generation",
        "name": "AI Video Generation",
        "category": "Generation",
        "description": "Future extension point for local video-diffusion models such as WAN/LTX. These models need much more RAM/VRAM than an 8 GB office PC can provide.",
        "requires": "Large video model + capable GPU / high system memory",
        "default_enabled": False,
        "status": "Hardware-limited · not installed",
    },
]


@dataclass
class PluginContext:
    data_dir: Path
    commands: dict[str, Callable[..., Any]]
    panels: dict[str, Callable[..., Any]]

    def add_command(self, name: str, handler: Callable[..., Any]) -> None:
        if not re.fullmatch(r"[a-z][a-z0-9_.-]{1,63}", name):
            raise ValueError("Plugin command name is invalid.")
        self.commands[name] = handler

    def add_panel(self, name: str, factory: Callable[..., Any]) -> None:
        if not name.strip():
            raise ValueError("Plugin panel name is required.")
        self.panels[name] = factory


class PluginManager:
    """Manages built-in and user-imported Nexa plugins.

    Imported plugin code is not executed during discovery. A user must explicitly
    enable an imported plugin before its entry point is imported and registered.
    Only import plugins from developers you trust.
    """

    def __init__(self, data_dir: Path) -> None:
        self.data_dir = data_dir
        self.plugins_dir = data_dir / "Plugins"
        self.plugins_dir.mkdir(parents=True, exist_ok=True)
        self.state_file = data_dir / "plugins.json"
        self.state: dict[str, bool] = {}
        self.commands: dict[str, Callable[..., Any]] = {}
        self.panels: dict[str, Callable[..., Any]] = {}
        self._load_state()

    def _load_state(self) -> None:
        try:
            loaded = json.loads(self.state_file.read_text(encoding="utf-8"))
            self.state = {str(key): bool(value) for key, value in loaded.items()}
        except (OSError, ValueError, AttributeError):
            self.state = {}

    def _save_state(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        tmp = self.state_file.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.state, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(self.state_file)

    def enabled(self, plugin_id: str) -> bool:
        item = next((p for p in PLUGIN_CATALOG if p["id"] == plugin_id), None)
        default = bool(item and item.get("default_enabled"))
        return self.state.get(plugin_id, default)

    def set_enabled(self, plugin_id: str, enabled: bool) -> None:
        self.state[plugin_id] = bool(enabled)
        self._save_state()

    def list_plugins(self) -> list[dict[str, Any]]:
        items = []
        for item in PLUGIN_CATALOG:
            entry = dict(item)
            entry["enabled"] = self.enabled(item["id"])
            entry["installed"] = True
            entry["kind"] = "built-in capability"
            items.append(entry)

        for folder in sorted(self.plugins_dir.iterdir()):
            if not folder.is_dir():
                continue
            manifest = folder / "plugin.json"
            if not manifest.is_file():
                continue
            try:
                data = json.loads(manifest.read_text(encoding="utf-8"))
                plugin_id = str(data.get("id", ""))
                if not re.fullmatch(r"[a-z0-9][a-z0-9_.-]{1,63}", plugin_id):
                    continue
                if any(p["id"] == plugin_id for p in items):
                    continue
                entrypoint = str(data.get("entrypoint", "plugin.py"))
                path = (folder / entrypoint).resolve()
                if folder.resolve() not in path.parents or not path.is_file():
                    continue
                items.append({
                    "id": plugin_id,
                    "name": str(data.get("name", plugin_id)),
                    "category": str(data.get("category", "Imported")),
                    "description": str(data.get("description", "User-imported extension.")),
                    "requires": "Imported plugin package",
                    "default_enabled": False,
                    "enabled": self.enabled(plugin_id),
                    "installed": True,
                    "kind": "imported extension",
                    "entrypoint_path": str(path),
                    "status": "Imported",
                })
            except (OSError, ValueError, TypeError):
                continue
        return items

    def import_plugin_zip(self, archive_path: Path) -> str:
        max_total = 50 * 1024 * 1024
        with zipfile.ZipFile(archive_path) as archive:
            infos = archive.infolist()
            total = sum(item.file_size for item in infos)
            if total > max_total:
                raise ValueError("Plugin ZIP is larger than the 50 MB safety limit.")
            names = [Path(item.filename) for item in infos]
            if any(name.is_absolute() or ".." in name.parts for name in names):
                raise ValueError("Plugin ZIP contains an unsafe file path.")
            manifests = [item for item in infos if item.filename.endswith("plugin.json")]
            if len(manifests) != 1:
                raise ValueError("Plugin ZIP must contain exactly one plugin.json manifest.")
            root = Path(manifests[0].filename).parent
            manifest = json.loads(archive.read(manifests[0]).decode("utf-8"))
            plugin_id = str(manifest.get("id", ""))
            if not re.fullmatch(r"[a-z0-9][a-z0-9_.-]{1,63}", plugin_id):
                raise ValueError("Plugin manifest has an invalid id.")
            entrypoint = str(manifest.get("entrypoint", "plugin.py"))
            entry_path = (root / entrypoint).as_posix()
            if entry_path not in {info.filename for info in infos}:
                raise ValueError("Plugin entrypoint is missing from the archive.")
            destination = self.plugins_dir / plugin_id
            destination.mkdir(parents=True, exist_ok=True)
            for info, name in zip(infos, names):
                target = (self.plugins_dir / name).resolve()
                if self.plugins_dir.resolve() not in target.parents:
                    raise ValueError("Plugin ZIP attempted to write outside the plugin folder.")
                target.parent.mkdir(parents=True, exist_ok=True)
                if info.is_dir():
                    target.mkdir(parents=True, exist_ok=True)
                    continue
                with archive.open(info) as src, target.open("wb") as dst:
                    dst.write(src.read())
            self.state.setdefault(plugin_id, False)
            self._save_state()
            return plugin_id

    def load_enabled_imported_plugins(self, data_dir: Path | None = None) -> PluginContext:
        context = PluginContext(data_dir or self.data_dir, self.commands, self.panels)
        for item in self.list_plugins():
            if item.get("kind") != "imported extension" or not item.get("enabled"):
                continue
            entrypoint = Path(item["entrypoint_path"])
            module_name = f"nexa_plugin_{item['id'].replace('-', '_').replace('.', '_')}"
            spec = importlib.util.spec_from_file_location(module_name, entrypoint)
            if not spec or not spec.loader:
                continue
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            register = getattr(module, "register", None)
            if callable(register):
                register(context)
        return context
