# NexaAI 2.0.0 — NTech Edition · Bundled Gemma Offline

NexaAI is a Windows x64 desktop assistant for Bengali/English chat, coding help, n8n workflow design, local chat history and voice. The single setup installer includes both the Ollama runtime and Google Gemma 3 1B model. There is no separate Ollama installation, cloud provider or API key system.

## Install

1. Download and run **NexaAI-Setup-2.0.0-Windows-x64.exe**.
2. The installer copies the application, embedded Ollama runtime and Gemma 3 1B model into their app folders.
3. Keep the installer open until setup completes, then launch NexaAI from the desktop shortcut.
4. NexaAI starts its private local AI engine automatically. The chat model is already installed; no first-run model download is needed.

The installer is larger than earlier versions because the AI model is included. Once installed, offline chat does not need an internet connection. No administrator permission is required; NexaAI installs for the current Windows user.

## AI engine

**Google Gemma 3 1B — Ollama tag: `gemma3:1b`**

- Approximate model download: 806 MB (included in the installer)
- Ollama Windows runtime is bundled inside NexaAI
- Model files are installed under `%LOCALAPPDATA%\NexaAI\Engine\models`
- NexaAI starts the private Ollama service at `127.0.0.1:11439`; it does not need the standard Ollama port
- CPU-friendly settings with a 4K context window and small thread count
- Chat, coding questions, lightweight reasoning, JSON and n8n workflow design all use this one local model

Gemma 3 1B is deliberately compact to work more comfortably on older and low-memory PCs. It is less capable for difficult coding, long debugging sessions and large multi-file projects. It is a text model: image/video understanding and scanned-PDF OCR are not included.

## Privacy

- All chat prompts, chat history and supported text attachments stay on this PC.
- NexaAI does not include cloud AI, FreeLM, provider API keys or a cloud mode.
- The bundled Ollama service listens only on the local loopback interface.
- Chat history, preferences, plugins and voice cache are stored under `%LOCALAPPDATA%\NexaAI`.
- Existing chat history is retained during upgrades.
- The Gemma model cache is kept in the user profile when NexaAI is uninstalled so it can be reused if the app is reinstalled.

## Chat workspace

- Updated NTech dark interface with a calmer navy palette and more spacious sidebar.
- Premium-styled theme and response-profile dropdowns with matching option lists.
- Recent chats, conversation search, local chat history and plugin manager.
- Messages stream as they are generated.
- Up to four follow-up prompts can be queued while the assistant is responding.
- Quick (384 tokens), Balanced (768 tokens) and Detailed (1,280 tokens) response profiles.
- Copy controls and readable formatting for headings and code blocks.

## Voice Chat

Voice input uses faster-whisper base on CPU int8. The Whisper model is downloaded on first voice use (about 150 MB), then speech recognition runs offline. Speech replies use Windows SAPI voices already installed on the PC. Bengali text-to-speech quality depends on whether a Bengali Windows voice is installed.

Voice cache: `%LOCALAPPDATA%\NexaAI\Voice`.

## n8n Workflow Studio

Describe an automation in Bangla or English. Gemma 3 1B creates workflow JSON, checks basic node names and connection references, and lets you copy or export the JSON for import into n8n.

The current studio generates and validates workflow JSON; it does not execute or monitor n8n workflows. Import the JSON into your own n8n instance. Workflows that contact Gmail, Facebook or cloud APIs still need their own network access and credentials.

## Plugins and attachments

- Plugin Manager can import a local plugin ZIP. Imported code runs with your Windows user permissions; only enable code you trust.
- Supported attachments: selectable-text PDFs and text/code documents.
- Images, video understanding and scanned-PDF OCR are not included in this Gemma 3 1B text-only edition.

## Build from source

The GitHub Actions workflow **Build Nexa AI Windows Offline Installer** downloads and verifies the official Ollama Windows standalone runtime, pre-downloads Gemma 3 1B, runs the unit tests, compiles the desktop app and produces one Windows x64 installer.

The optional runtime smoke test can be run after NexaAI has started its bundled Ollama service:

    python tools/smoke_test_runtime.py

See `THIRD-PARTY-NOTICES.txt` for third-party software and model license information.
