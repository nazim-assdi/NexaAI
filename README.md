# NexaAI 2.1.0 — NTech Edition · Offline Qwen + Online Gemini

NexaAI is a Windows x64 desktop assistant for Bengali/English chat, coding help, n8n workflow design, local chat history and voice. Its default offline coding model is Qwen2.5-Coder 1.5B, served by the Ollama runtime bundled with the installer. Gemini 3.8 Flash and Gemini 3.1 Flash-Lite are optional online choices.

## Install

1. Download and run **NexaAI-Setup-2.1.0-Windows-x64.exe**.
2. The installer copies NexaAI and its bundled Ollama runtime.
3. On first launch, NexaAI automatically downloads Qwen2.5-Coder 1.5B (about 986 MB) and shows download progress, speed and ETA.
4. After the model is installed, offline chat and coding assistance work without an internet connection.

The initial model download requires internet. Keep about 2 GB of free storage for the model and runtime. No separate Ollama installation or administrator permission is needed. NexaAI installs for the current Windows user.

## AI engines

**Offline — Qwen2.5-Coder 1.5B (Ollama tag: `qwen2.5-coder:1.5b`)**

- Approximately 986 MB model download.
- Coding-focused generation, code reasoning and debugging.
- Model files are stored under `%LOCALAPPDATA%\NexaAI\Engine\models`.
- The bundled Ollama service listens only on the private loopback address `127.0.0.1:11439`.
- Uses a conservative 4K context and CPU thread limit for low-memory Windows PCs.
- Once downloaded, Qwen works offline and needs no account, cloud provider or API key.

**Online — Google Gemini**

- Gemini 3.8 Flash for general reasoning and coding.
- Gemini 3.1 Flash-Lite as a faster, lighter online alternative.
- Requires the user's own Google AI Studio API key. The key is checked before saving and encrypted with Windows DPAPI for the current Windows user.
- Free-tier access, availability and request quotas are controlled by Google and can change. Google says prompts submitted on the free tier may be used to improve its products; avoid sending sensitive code, credentials or private information when using free-tier Gemini.

## Privacy

- Offline Qwen chat, chat history and supported text attachments stay on this PC.
- The bundled Ollama service is bound to the local loopback interface and uses a private app-specific port.
- If Gemini is selected, prompts and supported attachments are sent to Google's Gemini API. The key is encrypted locally with Windows DPAPI and is not written in plaintext into NexaAI preferences.
- Chat history, preferences, plugins and voice cache are stored under `%LOCALAPPDATA%\NexaAI`.
- Existing local chat history is retained during upgrades.
- The Qwen model cache is retained in the user profile when NexaAI is uninstalled, so it can be reused if the app is reinstalled.

## Chat workspace

- Refreshed NTech dark interface and premium-themed dropdowns.
- AI selector for offline Qwen2.5-Coder and online Gemini models.
- Local chat history, recent chats, conversation search and plugin manager.
- Streaming responses and up to four queued follow-up prompts.
- Quick, Balanced and Detailed response profiles.
- Supported text/code/PDF attachments work with both engines; image attachments are available to online Gemini, not offline Qwen.

## Voice Chat

Voice input uses faster-whisper base on CPU int8. The Whisper model is downloaded on first voice use (about 150 MB), then speech recognition runs offline. Speech replies use Windows SAPI voices already installed on the PC.

Voice cache: `%LOCALAPPDATA%\NexaAI\Voice`.

## n8n Workflow Studio

Describe an automation in Bangla or English. The selected AI generates n8n workflow JSON, checks basic node names and connection references, and lets you copy or export the JSON for import into n8n. Workflow JSON is generated and validated but is not executed or monitored by NexaAI.

## Plugins and attachments

- Plugin Manager can import a local plugin ZIP. Imported code runs with your Windows user permissions; only enable code you trust.
- Supported attachments include selectable-text PDFs and text/code files.
- Online Gemini additionally accepts common image formats. Offline Qwen2.5-Coder is text-only.
- Scanned-PDF OCR and video understanding are not included.

## Build from source

The GitHub Actions workflow **Build Nexa AI Windows Offline Installer** downloads and verifies the official Ollama Windows standalone runtime, prepares Qwen2.5-Coder's Apache 2.0 license notice, runs the unit tests, compiles the desktop app and produces one Windows x64 installer.

Run the optional local runtime smoke test after NexaAI has started its bundled Ollama service:

    python tools/smoke_test_runtime.py

See `THIRD-PARTY-NOTICES.txt` for third-party software and model license information.
