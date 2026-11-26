# NexaAI 2.1.3 — NTech Edition · Offline Qwen2.5-Coder 3B

NexaAI is a Windows x64 desktop assistant for Bengali and English chat, coding help, n8n workflow design, local chat history, attachments and voice. It uses only the Qwen2.5-Coder 3B model through the Ollama runtime bundled with the installer. There is no cloud AI, online chat provider, API-key setting or account requirement.

## Install

1. Download and run **NexaAI-Setup-2.1.3-Windows-x64.exe**.
2. Review and accept the Qwen Research License in the installer. The model is licensed for non-commercial research and evaluation only.
3. On first launch, NexaAI automatically downloads Qwen2.5-Coder 3B (about 1.9 GB) and shows download progress.
4. After the model is installed, chat and coding assistance run locally without an internet connection.

The initial model download requires internet. Keep at least 3 GB free for the model and runtime. No separate Ollama installation, API key, cloud account or administrator permission is needed. NexaAI installs for the current Windows user.

## Offline AI engine

**Qwen2.5-Coder 3B (Ollama tag: `qwen2.5-coder:3b`)**

- Approximately 1.9 GB model download.
- Coding-focused generation, code reasoning and debugging.
- Model files are stored under `%LOCALAPPDATA%\NexaAI\Engine\models`.
- The bundled Ollama service listens only on the private loopback address `127.0.0.1:11439`.
- Uses a conservative 4K context and CPU thread limit for lower-memory Windows PCs.
- After the first download, chat works offline and requires no API key.

**Important model licence:** Qwen2.5-Coder 3B is provided under the Qwen Research License, not Apache 2.0. The license defines non-commercial use as research or evaluation only. Commercial use requires a separate license from Alibaba Cloud. The complete agreement and required attribution notice are included in the installer and installed app.

## Chat workspace

- Offline-only chat; no provider selector, API-key box or cloud requests.
- Centered message layout with readable user/assistant cards.
- Streaming text with a visible “Thinking…” state and a final full-answer render to prevent missing or clipped replies.
- Message cards recalculate their height after text wrapping and window resizing.
- Enter sends a message; Shift+Enter inserts a new line.
- Local chat history, recent chats, conversation search and plugin manager.
- Quick, Balanced and Detailed response profiles with expanded output limits.
- Supported text/code/PDF attachments are processed locally.
- Up to four queued follow-up prompts.

## Voice Chat

Voice input uses faster-whisper base on CPU int8. The Whisper model is downloaded on first voice use (about 150 MB), then speech recognition runs offline. Speech replies use Windows SAPI voices already installed on the PC.

Voice cache: `%LOCALAPPDATA%\NexaAI\Voice`.

## n8n Workflow Studio

Describe an automation in Bangla or English. The offline Qwen model generates n8n workflow JSON, checks basic node names and connection references, and lets you copy or export the JSON for import into your own n8n instance. Workflow JSON is generated and validated but is not executed or monitored by NexaAI.

## Plugins and attachments

- Plugin Manager can import a local plugin ZIP. Imported code runs with your Windows user permissions; only enable code you trust.
- Supported attachments include selectable-text PDFs and text/code files.
- Qwen2.5-Coder 3B is text-only; image and video understanding are not included.
- Scanned-PDF OCR is not included.

## Privacy

- Chat prompts, replies, history and supported attachments stay on this PC.
- No messages or files are sent to a cloud AI provider.
- The bundled Ollama service is bound to the local loopback interface and uses a private app-specific port.
- Existing local chat history and the downloaded model cache are retained during upgrades.

## Build from source

The GitHub Actions workflow **Build Nexa AI 2.1.3 Windows Offline Qwen 3B Installer** downloads and verifies the official Ollama Windows standalone runtime, obtains the official Qwen Research License and attribution notice, runs the unit tests, compiles the desktop app and produces one Windows x64 installer.

Run the optional local runtime smoke test after NexaAI has started its bundled Ollama service:

    python tools/smoke_test_runtime.py

See `THIRD-PARTY-NOTICES.txt` and `licenses/QWEN-RESEARCH-LICENSE.txt` for third-party software and model license information.
