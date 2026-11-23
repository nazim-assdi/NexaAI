# Nexa AI — Offline-first Local AI Assistant

Nexa AI is a Windows-friendly terminal AI assistant with a local OpenAI-compatible API. Its default provider is a model running on your own PC through **Ollama** or **llama.cpp**. In local mode, prompts and supported attachments are sent to the local model endpoint, not to Gemini or another cloud API.

## Important: What “offline” means

Nexa can chat offline **after** Python dependencies and a model have been downloaded and installed. The repository does not contain multi-gigabyte model weights. Initial installation/download therefore requires internet or a pre-populated offline package cache.

- **Offline chat and coding:** Ollama, llama.cpp, or another local OpenAI-compatible server.
- **Text, CSV, JSON and selectable-text PDF:** processed locally.
- **Images:** require a local vision-capable model.
- **Video:** FFmpeg extracts sample frames locally; a vision-capable model is required.
- **Audio:** optional local transcription through whisper.cpp and a downloaded Whisper model.
- **Gemini:** optional online mode only; it is not needed in the offline configuration.

## Quick start (Windows)

1. Install Python 3.10+ and [Ollama](https://ollama.com/download).
2. While internet is available, download a model once:
   ```powershell
   ollama pull qwen2.5:3b
   ```
3. Extract the project source ZIP from this repository.
4. Run `setup.bat` once to install Python packages.
5. Keep Ollama running and double-click `run.bat`. You can then disconnect from the internet and use local chat.

Default configuration: `NEXA_PROVIDER=local`, `http://127.0.0.1:11434/v1`, model `qwen2.5:3b`. For an 8 GB RAM computer, start with a small/quantized model. Model speed depends on CPU, RAM, quantization and context length.

For image understanding, install a compatible local vision model, for example `ollama pull qwen2.5vl:3b`, then set `NEXA_MODEL=qwen2.5vl:3b` in `.env`.

## Local API

Nexa exposes its own API at `http://127.0.0.1:8000/v1`:

- `GET /health`
- `GET /v1/models`
- `POST /v1/chat/completions` (streaming and non-streaming)
- `POST /v1/files` (stores attachments on this computer)
- `GET /v1/files/{file_id}`
- `DELETE /v1/files/{file_id}`

For llama.cpp, change `NEXA_LOCAL_BASE_URL=http://127.0.0.1:8080/v1` and set `NEXA_MODEL` to the model ID exposed by that server. Any OpenAI-compatible local server can be used.

## CLI commands

| Command | Purpose |
|---|---|
| `/attach "C:\\path\\file.png"` | Attach a local image, video, audio, PDF or text file |
| `/model` | Show the active model |
| `/model MODEL_NAME` | Switch model for this session |
| `/models` | List local models |
| `/clear` | Clear conversation |
| `/help` | Show commands |
| `/exit` | Save and exit |

## Optional online Gemini mode

Install optional dependencies with `pip install -r requirements-gemini.txt`, then set `NEXA_PROVIDER=gemini`, `GEMINI_API_KEY`, and `GEMINI_MODEL` in `.env`. This mode needs internet and is not offline.

## Privacy and safety

- The API listens on `127.0.0.1` by default.
- Chat history, upload files and metadata are stored locally under `.data/`.
- Local mode sends requests only to `NEXA_LOCAL_BASE_URL`.
- Do not expose port 8000 publicly without authentication, rate limits and HTTPS.
- The `.env` file is ignored by Git. Never commit API keys.

## Full source

Download `NexaAI-offline-source.zip` from the repository files. It contains the Python app, Windows launch/setup scripts, tests and GitHub Actions workflow. Extract the ZIP to a folder, then follow the Windows quick-start instructions above.

## Development checks

```powershell
.venv\Scripts\python.exe -m compileall nexa_ai run.py
.venv\Scripts\python.exe -m unittest discover -s tests -v
```

MIT License — see `LICENSE`.
