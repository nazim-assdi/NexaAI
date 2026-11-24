# Nexa AI — Offline AI Desktop Assistant

Nexa AI is a Windows x64 desktop assistant with a local llama.cpp runtime. It is designed to work without Python, Ollama, a terminal, API keys, or cloud model APIs after setup and model downloads have completed.

## Install

1. Open the [Nexa AI Releases page](https://github.com/nazim-assdi/NexaAI/releases).
2. Download `NexaAI-Setup-1.2.0-Windows-x64.exe`.
3. Double-click the installer and finish setup.
4. Launch Nexa AI from the Start Menu or Desktop shortcut.

The base installer includes the desktop app, the llama.cpp CPU runtime, and the compact Qwen2.5 1.5B fallback model. The stronger Qwen3 model and voice recognition model are downloaded inside the app on first use, then stored locally.

## Recommended single model for coding and n8n

Open **Model Library** and download:

**Qwen3-4B-Instruct Q4_K_M** (about 2.5 GB).

This is the recommended all-rounder for Bengali/English chat, code generation, Python, JavaScript, debugging, JSON, reasoning and automation planning. Qwen3 supports tool/function-calling formats and more than 100 languages. It is not a specialist n8n model, but one balanced local model is more useful here than switching between several narrow models.

The app uses one model at a time and keeps the context at 4K tokens to reduce memory use. On an 8 GB RAM computer, especially one with memory reserved for integrated graphics, it can be slower and may need other applications closed. It is a small local model, not equivalent to a large cloud model.

Model file:
- Repository: https://huggingface.co/Qwen/Qwen3-4B-GGUF
- Quantization: Q4_K_M
- File: `Qwen3-4B-Q4_K_M.gguf`
- SHA-256: `7485fe6f11af29433bc51cab58009521f205840f5b4ae3a32fa7f92e8534fdf5`
- License: Apache-2.0

The Model Library verifies this SHA-256 during download. Once installed, Qwen3 runs locally without internet.

## Chat History

- Conversations are automatically saved as you send messages and receive replies.
- Open **Chat History** to browse, reopen, or delete previous conversations.
- New conversations are kept separate.
- History stays under `%LOCALAPPDATA%\NexaAI\Data\chats`.
- Old v1.0/v1.1 chat files are also recognised by the history list.

## Voice Chat

Press **Voice chat**, speak into your microphone, then press **Stop & send**.

- Speech recognition uses multilingual **faster-whisper small** locally on the CPU.
- The first voice-chat use downloads the speech model (roughly 500 MB). Later transcription is offline.
- After transcription, the recognized text is sent to the active local language model.
- **Speak voice-chat replies** uses Windows SAPI speech voices locally; no cloud TTS is used.
- Bengali speech output depends on whether a Bengali SAPI voice is installed in Windows. If not, Windows may use its default voice, which may pronounce Bangla poorly.
- Microphone recording and transcription require a working microphone and available RAM. On low-memory PCs, close other heavy applications.

Voice model cache: `%LOCALAPPDATA%\NexaAI\Voice`.

## n8n Workflow Studio

Open **n8n Workflow Studio** and describe an automation in Bangla or English. The active local model will:
1. Create an n8n workflow export JSON.
2. Validate the basic workflow structure, node names and connection references.
3. Let you copy the JSON or export it as a `.json` file.

The studio does not execute the workflow. Import the exported JSON into your own n8n instance. You can self-host n8n locally and use local/manual/schedule/webhook nodes offline, but nodes that call Gmail, Facebook, cloud APIs or other internet services still need network access and configured credentials. Nexa AI never fabricates credentials.

## Model Library

The built-in catalogue includes:
- **Qwen3 4B Q4_K_M** — recommended all-rounder for coding, Bengali/English chat and automation design.
- **Qwen2.5 1.5B Instruct** — compact fallback bundled with the installer.
- **Qwen2.5 Coder 1.5B** — lightweight coding specialist.
- **SmolLM2 1.7B** — compact English chat model.
- **Qwen2.5-VL 3B + projector** — optional vision model for image and sampled video-frame analysis.

Only one chat/vision model is loaded at a time. Optional model downloads happen from the Model Library and are stored under `%LOCALAPPDATA%\NexaAI\models`.

## Plugin Manager

Open **Plugin Manager** to review the optional local capability catalogue or import a third-party plugin ZIP. Imported plugins must include `plugin.json` and a Python entrypoint with `register(context)`. They remain disabled until explicitly enabled by you. Plugin code runs with the same Windows permissions as Nexa AI; only import plugins you trust.

A template is available under `plugin-template/`, and plugin author instructions are in `plugins/README.md`.

## Eye Comfort Themes

The default theme is **Eye Comfort Premium**. You can also select **OLED Midnight** or **Soft Paper**. Theme preference is saved locally.

## Privacy and Offline Behaviour

- Local chat and workflow generation use only the local model server bound to `127.0.0.1`.
- Chat history, models, voice cache, preferences and plugins are stored under `%LOCALAPPDATA%\NexaAI`.
- Qwen3 and the Whisper speech model require an initial download. Once downloaded, they work offline.
- The app does not upload conversations or files to a cloud API.
- External n8n integrations still need access to their corresponding external services.

## Build from Source

The GitHub Actions workflow **Build Nexa AI Windows Offline Installer** compiles the app, runs unit tests, packages the local runtime and creates an Inno Setup installer.

## Third-party Licences

See `THIRD-PARTY-NOTICES.txt` for the bundled application and model notices. Review each optional model and voice license before redistribution or commercial use.
