# Nexa AI 1.5.1 — NTech Edition · Verified Qwen3 Offline Assistant

Nexa AI is a Windows x64 desktop assistant built around **one and only one local chat model: Qwen3 4B Instruct Q4_K_M**. The same model handles Bengali/English chat, coding help, reasoning, JSON and n8n workflow design. There are no alternative chat, coder or vision LLMs in the app.

## Install

1. Open the [Nexa AI Releases page](https://github.com/nazim-assdi/NexaAI/releases).
2. Download \`NexaAI-Setup-1.5.1-Windows-x64.exe\`.
3. Install and launch Nexa AI.
4. On first launch, NexaAI downloads the official Qwen3 GGUF (about 2.5 GB) using parallel HTTP range connections when supported, resumes completed segments after interruption, and verifies its SHA-256. Keep the internet connection active until this finishes.

The installer includes the desktop application and the llama.cpp Windows CPU runtime. The large Qwen3 model is downloaded into \`%LOCALAPPDATA%\\NexaAI\\models\`, avoiding a multi-gigabyte installer. Once downloaded, Qwen3 runs fully offline. No Ollama, Python installation, command-line setup, API key or cloud model subscription is required.

## The only assistant model

**Qwen3 4B Instruct Q4_K_M**

- Model repository: https://huggingface.co/Qwen/Qwen3-4B-GGUF
- Exact file: \`Qwen3-4B-Q4_K_M.gguf\`
- Approximate download: 2.5 GB
- SHA-256: \`7485fe6f11af29433bc51cab58009521f205840f5b4ae3a32fa7f92e8534fdf5\`
- License: Apache-2.0

The app downloads and checks this exact file automatically at first start. It is the single model used for chat, coding, debugging, reasoning and n8n workflow generation. NexaAI does not offer model switching or optional alternative LLM downloads.

The engine automatically tries balanced 4K, low-memory 2K and minimum-memory 1K CPU profiles. It uses CPU-only inference, mmap loading and fewer threads on older processors. Each Windows release runs an end-to-end test with the exact Qwen3 GGUF, server health endpoint and local chat completion. An 8 GB RAM computer can run this quantized model, but performance depends on available memory; close browsers and other heavy apps before using it. Integrated graphics may reserve part of system RAM. Responses will generally be slower and less capable than large cloud models.

## Chat and coding

- Bengali and English conversation.
- Python, JavaScript, HTML/CSS, Windows troubleshooting and coding assistance.
- Explain, review and debug code; generate complete files and project structures.
- Local text and source-code file attachments.
- All model inference happens on the local computer after setup.

## Chat History

- Conversations are saved locally as you send messages and receive replies.
- Open **Chat History** to browse, reopen or delete previous conversations.
- History is stored under \`%LOCALAPPDATA%\\NexaAI\\Data\\chats\`.
- Existing v1.0/v1.1 history files are recognised.

## Voice Chat

Voice chat uses Qwen3 for the actual assistant conversation. Speech input needs a separate speech-to-text engine; this is not a second chat LLM.

- Microphone capture runs locally.
- Multilingual speech recognition uses faster-whisper **base** on CPU (int8). The speech model is downloaded on first voice use (roughly 150 MB), then recognition works offline.
- Speech replies use Windows SAPI voices already installed on the PC. No separate TTS model is required.
- Bengali speech output depends on an installed Bengali Windows voice. Without one, Windows may use its default voice and Bengali pronunciation may be poor.

Voice model cache: \`%LOCALAPPDATA%\\NexaAI\\Voice\`.

## n8n Workflow Studio

Describe an automation in Bangla or English. The same Qwen3 model creates a workflow JSON, checks basic node names and connection references, and lets you copy or export the JSON for import into n8n.

**The current studio generates and validates workflow JSON; it does not execute or monitor n8n workflows yet.** Import the JSON into your own n8n instance. A locally hosted n8n can run local workflows offline; nodes that contact Gmail, Facebook, cloud APIs or other internet services still require network access and configured credentials.

## Plugins and appearance

- **Plugin Manager:** import a local plugin ZIP, review it, and enable it explicitly. Plugin code runs with the same Windows permissions as NexaAI, so import only code you trust.
- **Eye Comfort Premium** is the default theme. OLED Midnight and Soft Paper themes are also available.
- Preferences are stored locally.

## Supported attachments and limitations

The one-model setup uses Qwen3 4B, a text-only model. It supports selectable-text PDFs and text/code documents. **Image/video understanding and scanned-PDF OCR are not included**, because they would require additional specialist models or OCR components. The app does not silently download another vision or coding LLM. Startup failures show recent llama.cpp log lines, process exit codes, available-RAM information, model checksum failures and port conflicts.

## Privacy and offline operation

- Qwen3 inference and the local API are bound to \`127.0.0.1\`.
- Chat history, models, voice cache, preferences and plugins stay under \`%LOCALAPPDATA%\\NexaAI\`.
- Internet is needed for the one-time Qwen3 download and first-time Whisper download. After those downloads, chat and voice recognition work locally.
- External services used by n8n workflows still require their own network access.
- NexaAI does not send conversations or attached text documents to a cloud AI API.

## Build from source

The GitHub Actions workflow **Build Nexa AI Windows Offline Installer** compiles the app, runs the unit tests and creates the Windows x64 installer.

See \`THIRD-PARTY-NOTICES.txt\` for upstream software and model licences.
