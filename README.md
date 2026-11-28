# NexaAI 2.2.0 — NTech Edition · Hugging Face Qwen 1.5B Hybrid

NexaAI is a Windows x64 desktop assistant with Bengali and English chat, coding help, n8n workflow design, local chat history, document attachments and voice. It uses a Hugging Face Qwen2.5 1.5B Instruct GGUF model locally by default, with optional Hugging Face Inference Providers as a cloud fallback.

## Install

1. Download and run **NexaAI-Setup-2.2.0-Windows-x64.exe**.
2. Accept the Apache 2.0 license shown by the installer.
3. On first launch, NexaAI automatically downloads **Qwen2.5-1.5B-Instruct-GGUF Q4_K_M** from Hugging Face (about 1.12 GB) into its private model folder.
4. After the model finishes downloading, local chats work offline. No separate Ollama installation or API key is needed for local mode.

Keep at least 2 GB free for the model download and runtime. The installer includes the Ollama Windows runtime.

## Default local model

**Hugging Face:** `Qwen/Qwen2.5-1.5B-Instruct-GGUF`  
**Quantization:** `Q4_K_M`  
**Ollama model reference:** `hf.co/Qwen/Qwen2.5-1.5B-Instruct-GGUF:Q4_K_M`  
**Approximate model size:** 1.12 GB  
**License:** Apache 2.0

The local model is text-only. It supports regular conversation, coding assistance and text-based document workflows. Image and video understanding are not included.

## Hybrid chat

Open **Hybrid AI Settings** from the sidebar:

- **Hybrid (Local first):** private local Qwen 1.5B first; use Hugging Face cloud only when the local model cannot answer due to an engine error.
- **Hugging Face cloud first:** use the configured hosted model first and fall back to local Qwen 1.5B if the cloud request fails before producing output.
- **Local only:** never send chat prompts to Hugging Face.

The optional cloud model defaults to `Qwen/Qwen3-4B-Thinking-2507:cheapest`. The Hugging Face Inference Providers router requires a Hugging Face access token with inference permission. Create one at https://huggingface.co/settings/tokens and paste it in Hybrid AI Settings. NexaAI encrypts the token at rest with Windows DPAPI for the current Windows account. Cloud requests send chat prompts and conversation context to Hugging Face; provider usage may be paid. Check your account's provider pricing and credits before enabling cloud-first mode. The 1.5B local model remains the default.

## Chat workspace

- Messenger-style user and assistant chat bubbles.
- Streaming responses with a visible Thinking state.
- Message cards grow to fit the full wrapped answer and reflow after window resizing.
- Vertical scrolling for long conversations and long assistant replies.
- Detailed response profile selected by default (up to 3,072 output tokens); Quick and Balanced remain available.
- Enter sends; Shift+Enter inserts a new line.
- Local chat history, recent chats, conversation search and plugin manager.
- Supported selectable-text PDFs and text/code attachments are processed on the PC.

## Voice Chat

Voice input uses faster-whisper base on CPU int8. The Whisper model is downloaded on first voice use (about 150 MB), then speech recognition runs offline. Speech replies use Windows SAPI voices already installed on the PC.

## n8n Workflow Studio

Describe an automation in Bangla or English. The local Qwen model generates n8n workflow JSON, checks basic node names and connection references, and lets you copy or export the JSON for import into your own n8n instance. Workflow JSON is generated and validated but is not executed or monitored by NexaAI.

## Privacy

- Local-only mode keeps chat prompts and responses on this PC.
- Hybrid local-first mode sends a prompt to Hugging Face only if the local model fails and a token is configured.
- Cloud-first mode sends prompts, recent conversation context and text extracted from attachments to Hugging Face Inference Providers.
- The Hugging Face access token is encrypted with Windows DPAPI and is not written to logs.
- The local Ollama service listens only on `127.0.0.1:11439`; NexaAI's private chat API listens on `127.0.0.1:8000`.
- Existing local chat history and compatible model cache are retained during upgrades.

## Build from source

GitHub Actions workflow **Build Nexa AI 2.2.0 Windows Hybrid Qwen 1.5B Installer** verifies the official Ollama standalone runtime, downloads the Qwen Apache 2.0 license, runs unit tests and produces a Windows x64 installer.

Run the optional local runtime smoke test after NexaAI has started its bundled Ollama service:

    python tools/smoke_test_runtime.py

See `THIRD-PARTY-NOTICES.txt` and `licenses/APACHE-2.0.txt` for third-party software and license details.
