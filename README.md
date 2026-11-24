# Nexa AI — Installable Offline Desktop Assistant

Nexa AI is a Windows x64 desktop application with a built-in CPU inference runtime. It does not require Python, Ollama, a terminal, an API key, or a separate model manager.

## Install

1. Open the [Nexa AI Releases page](https://github.com/nazim-assdi/NexaAI/releases).
2. Download `NexaAI-Setup-1.1.0-Windows-x64.exe`.
3. Double-click the installer and finish setup.
4. Launch Nexa AI from the Start Menu or Desktop shortcut.

The base installer contains the desktop app, llama.cpp CPU runtime and Qwen2.5-1.5B-Instruct Q4_K_M model. The base app works offline after installation.

## Model Library

Open **Model Library** in the left panel to install optional models. Downloads happen inside the app; no command line is needed. Once a model is downloaded it can be selected offline. Nexa loads one chat model at a time to limit RAM use.

Included model catalogue:
- **Qwen2.5 1.5B Instruct** — bundled general-purpose model.
- **Qwen2.5 Coder 1.5B Instruct Q4_K_M** — optional coding model.
- **SmolLM2 1.7B Instruct Q4_K_M** — optional compact general-purpose model.
- **Qwen2.5-VL 3B Q4_K_M + mmproj** — optional image/vision model pack. This is much larger and may exceed comfortable memory use on an 8 GB PC. It is used for local image understanding and sampled video-frame analysis.

Optional model downloads require internet once. They are stored under `%LOCALAPPDATA%\NexaAI\models`; afterwards, model loading is local.

## Plugin Manager

Open **Plugin Manager** from the left panel.

The built-in catalogue documents capability packs for:
- Vision and video understanding (image input and up to six sampled frames from a video; about one frame every eight seconds)
- Offline audio transcription (catalogue entry; runtime/model pack still required)
- Bangla and English OCR (catalogue entry; runtime/language pack still required)
- Offline image generation (catalogue entry; runtime/model pack still required)
- Motion-video clip creation (catalogue entry; FFmpeg workflow still required)
- Advanced AI video generation (requires high-end hardware and large models; not part of this build)

These catalogue cards describe requirements; a card is not a claim that its optional runtime/model pack is already installed. Nexa also supports importing third-party plugin ZIP packages. Imported plugins must contain a `plugin.json` manifest and a Python entrypoint that defines `register(context)`. Imported plugin code is disabled until explicitly enabled by the user. Only import code from developers you trust.

A minimal plugin package looks like this:

```text
example-plugin/
  plugin.json
  plugin.py
```

`plugin.json`:

```json
{
  "id": "example-plugin",
  "name": "Example Plugin",
  "entrypoint": "plugin.py"
}
```

`plugin.py`:

```python
def register(context):
    context.add_command("example.hello", lambda: "Hello from Nexa")
```

Plugin commands are registered in the plugin context. Future Nexa versions can expose additional UI panels and events through the same context API.

## Premium Eye Comfort Theme

The default theme is **Eye Comfort Premium**, using a muted warm green/charcoal palette and softened contrast. You can switch at the top of the window to:
- Eye Comfort Premium
- OLED Midnight
- Soft Paper

The selected theme is saved locally and restored on the next launch.

## Offline and privacy behaviour

- Local chat uses only the bundled/local model server; there is no cloud API in the desktop build.
- The bundled inference process listens only on `127.0.0.1`.
- Chat history, preferences, optional models and imported plugins are stored under `%LOCALAPPDATA%\NexaAI`.
- Optional models/plugins need internet for their initial download/import; installed local assets can then be used offline.

## Hardware notes

The default 1.5B Q4 model is intended for low-memory CPU PCs. The optional 1.5B/1.7B models also fit more comfortably than larger models, but only one is loaded at a time. The Qwen2.5-VL 3B vision pack is significantly larger and may be slow or memory-constrained on 8 GB RAM. Large offline image/video-generation models are not bundled in the base installer.

## Build from source

The GitHub Actions workflow **Build Nexa AI Windows Offline Installer**:
1. Downloads and checksum-verifies the official llama.cpp Windows CPU runtime.
2. Downloads and validates the bundled default model.
3. Installs Python dependencies, compiles source, and runs unit tests.
4. Packages the app, runtime and model with PyInstaller.
5. Creates a one-click Inno Setup installer and publishes a GitHub Release.

The installer is for Windows x64. The workflow can also be started manually from the GitHub Actions tab.

## Third-party licences

The default Qwen model and optional catalogue models are Apache-2.0; check each upstream model card before redistributing modified or additional weights. The llama.cpp runtime is MIT-licensed. See `THIRD-PARTY-NOTICES.txt` for the bundled notices.
