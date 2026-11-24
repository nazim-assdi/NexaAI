# Nexa AI — Installable Offline Desktop Assistant

Nexa AI is a Windows x64 desktop app that includes its own CPU inference runtime and local language model. It does not require Python, Ollama, a terminal, an API key, or a separate model download on the user's PC.

## Install the software

1. Open the repository's Releases page: https://github.com/nazim-assdi/NexaAI/releases
2. Download NexaAI-Setup-1.0.0-Windows-x64.exe.
3. Double-click the installer and finish the setup.
4. Launch Nexa AI from the Start Menu or Desktop shortcut.

The installer bundles:
- Nexa AI desktop interface and local API.
- llama.cpp CPU runtime (starts automatically inside Nexa AI).
- Qwen2.5-1.5B-Instruct GGUF Q4_K_M local model (about 1.12 GB before installer compression).

After installation, Nexa AI launches its model locally. Disconnecting the internet does not stop normal chat or supported document analysis. The app stores chats and attachments under %LOCALAPPDATA%\NexaAI\Data.

## Local-only / offline behaviour

- No external model API is called in the desktop build.
- The bundled llama.cpp process binds only to 127.0.0.1 and runs with offline mode enabled.
- Nexa AI's local OpenAI-compatible API is available at http://127.0.0.1:8000/v1 while the app is open.
- The app closes its model process when the window exits.
- PDF files with selectable text and common text/code files can be attached locally.
- Scanned PDFs need OCR, and image/audio/video understanding is not included in this first desktop build.

## Performance and hardware

The default bundle uses a 1.5-billion-parameter Q4_K_M model to keep memory use manageable on ordinary CPU-only computers. It is intended for local chat, writing, explanations and basic coding help. It is smaller and less capable than large cloud models; generation speed depends on CPU and available RAM. Use a 64-bit Windows x64 PC. Keep at least 3 GB free for application files and additional working space; the installer itself is large because the model weights are included.

## Build the installer from source

The GitHub Actions workflow Build Nexa AI Windows Offline Installer downloads the official llama.cpp Windows CPU runtime and the Qwen model, validates the model SHA256, packages the desktop application with PyInstaller, and builds a single Inno Setup installer.

Run it from GitHub Actions, choose Build Nexa AI Windows Offline Installer, then select Run workflow. A successful build publishes an installer release and a downloadable Actions artifact.

## Development

Install the packages from requirements.txt, then run the compile and unit-test checks. The workflow runs these checks before building the Windows installer.

License notes for the bundled llama.cpp runtime and Qwen model are included in THIRD-PARTY-NOTICES.txt.
