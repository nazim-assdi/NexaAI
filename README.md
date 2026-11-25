# NexaAI 1.9.0 — NTech Edition · Gemma Offline + FreeLM Cloud

NexaAI is a Windows x64 offline-first assistant for Bengali/English chat, coding help, n8n workflow design, local chat history and voice. This release replaces the bundled Qwen3/llama.cpp engine with **Ollama + Google Gemma 3 1B** to reduce model size and make local responses more practical on older CPUs.

## Install

1. Install the official Ollama for Windows application from https://ollama.com/download/windows.
2. Install and launch NexaAI 1.9.0.
3. NexaAI detects the local Ollama service, starts it when needed, and automatically downloads the Gemma 3 1B model on first launch (about 806 MB).
4. Keep the internet connected until the first model download finishes. Afterwards, chat and coding work locally without internet.

Ollama is a prerequisite and is installed separately; it is not bundled in the NexaAI installer. NexaAI opens the official Ollama download page if it cannot find Ollama. The application connects only to the local Ollama endpoint at 127.0.0.1:11434. It keeps the model warm for 30 minutes to reduce repeated cold starts.

## AI modes

**Offline mode — Google Gemma 3 1B (Ollama tag: `gemma3:1b`)** remains the default and keeps chat on this PC after initial setup.

**Cloud mode — FreeLM 0.5.2** routes requests through supported free-tier providers such as Google Gemini, Groq, OpenRouter, Z.ai, Mistral, NVIDIA NIM, Cohere and Cloudflare Workers AI. It supports streaming, quota-aware provider selection and failover between available providers. Cloud mode requires internet access and either a provider key or explicit permission to use public keyless endpoints. Free-tier quotas and model availability vary by provider and may change.

Open **FreeLM Cloud Settings** from the sidebar to add API keys. Keys are stored in Windows Credential Manager and are never written to NexaAI source code or preferences. Public Kilo Gateway / OVHcloud endpoints remain disabled until the user explicitly enables them. Those public endpoints may log prompts; do not send confidential information to them. API providers may process prompts under their own data-use terms.

Switch between **Offline · Gemma** and **Cloud · FreeLM** from the model selector in the top bar. Cloud model routing uses FreeLM's `chat:large` alias; the concrete provider/model may vary as free models change.

### Offline model details

**Google Gemma 3 1B — Ollama tag: gemma3:1b**

- Approximate model size: 806 MB
- Multilingual text model; supports more than 140 languages
- CPU-only local inference; NexaAI uses a 4K context window and a small CPU thread count
- One model handles chat, coding questions, reasoning, JSON and n8n workflow design

Gemma 3 1B is deliberately much smaller than Qwen3 4B. It is designed to be lighter and generally faster on older/low-memory PCs, but it is also less capable at difficult coding, long debugging sessions and large multi-file project work. It should not be expected to match larger local or cloud models. If advanced coding quality matters more than response speed, a larger model is preferable.

## Chat workspace and follow-up queue

- ChatGPT-inspired left sidebar, recent chats, conversation search, tools and a clean message composer.
- User messages appear on the right and assistant answers stream on the left.
- While NexaAI is answering, type your next question and press Enter or the Queue button. Up to four follow-up prompts are kept in order and sent automatically after the current answer finishes; a prompt is not silently discarded.
- The status changes from preparing to writing when the first answer text arrives, rather than remaining on a generic thinking label.
- Quick (384 tokens) is the default response profile. Balanced (768) and Detailed (1,280) are available when you need longer output.
- Recent context is limited for faster processing; the full conversation remains in local Chat History.
- Answers are fully scrollable, with copy controls and readable formatting for headings and fenced code.

## Chat History

- Conversations are saved locally as you send prompts and receive answers.
- Open Chat History to browse, reopen or delete conversations.
- History is stored under %LOCALAPPDATA%\NexaAI\Data\chats.
- Existing history files are retained when you update NexaAI.

## Voice Chat

Voice uses the same Gemma 3 1B assistant for the conversation; speech recognition and speech output are separate voice components, not extra chat LLMs.

- Microphone capture selects a sample rate supported by the Windows input device and resamples it to 16 kHz.
- Multilingual voice input uses faster-whisper base on CPU int8. The Whisper model is downloaded on first voice use (about 150 MB), then speech recognition runs offline.
- Speech replies use Windows SAPI voices already installed on the PC.
- Bengali TTS quality depends on whether a Bengali Windows voice is installed.

Voice cache: %LOCALAPPDATA%\NexaAI\Voice.

## n8n Workflow Studio

Describe an automation in Bangla or English. Gemma 3 1B creates workflow JSON, checks basic node names and connection references, and lets you copy or export the JSON for import into n8n.

The current studio generates and validates workflow JSON; it does not execute or monitor n8n workflows. Import the JSON into your own n8n instance. A locally hosted n8n can run local workflows offline; workflows that contact Gmail, Facebook or cloud APIs still need their own network access and credentials.

## Plugins, attachments and limits

- Plugin Manager can import a local plugin ZIP. Imported code runs with your Windows user permissions; only enable code you trust.
- Supported attachments: selectable-text PDFs and text/code documents. Images, video understanding and scanned-PDF OCR are not included in this Gemma 3 1B text-only edition.
- Eye Comfort, OLED Midnight and Soft Paper themes remain available.
- The previous Qwen3 model file, if present in %LOCALAPPDATA%\NexaAI\models, is not used or automatically deleted by this update. Remove it manually only if you no longer need it and want to reclaim disk space.

## Privacy and offline operation

- In Offline mode, NexaAI sends chat requests only to the local Ollama service on 127.0.0.1.
- In Cloud mode, chat content and selected text attachments are sent to the FreeLM provider selected for that request. Provider privacy and retention terms apply. Public keyless endpoints are disabled unless the user explicitly enables them.
- API keys are stored in the current Windows user's Credential Manager. Chat history, preferences, voice cache and plugins stay under %LOCALAPPDATA%\NexaAI.
- Internet is required for FreeLM Cloud mode, initial Ollama/model downloads and first-use Whisper setup. Offline chat and speech recognition continue to work without internet after setup.
- External n8n nodes and services may still require internet access.

## Build from source

The GitHub Actions workflow “Build Nexa AI Windows Offline Installer” compiles the app, runs the unit tests and creates the Windows x64 installer. Run the optional local smoke test with Ollama installed and Gemma 3 1B already pulled:

    python tools/smoke_test_runtime.py

See THIRD-PARTY-NOTICES.txt for software and model licence information.
