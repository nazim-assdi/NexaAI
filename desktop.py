from __future__ import annotations

import json
import os
import queue
import subprocess
import sys
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from tkinter.scrolledtext import ScrolledText

APP_NAME = "Nexa AI"
APP_VERSION = "1.0.0"
MODEL_ID = "nexa-qwen2.5-1.5b"
LOCAL_MODEL_PORT = 11435
API_PORT = 8000
SYSTEM_PROMPT = (
    "You are Nexa AI, a helpful offline desktop assistant. Reply naturally in the user's language. "
    "When the user writes Bangla, reply in natural Bangla. You run locally and do not have live internet access. "
    "Be honest about limitations. For coding requests, provide complete, usable solutions."
)


def resource_path(relative: str) -> Path:
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    return base / relative


def app_data_dir() -> Path:
    base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    target = base / "NexaAI"
    target.mkdir(parents=True, exist_ok=True)
    return target


def configure_environment() -> tuple[Path, Path, Path]:
    runtime_dir = resource_path("runtime")
    model_path = resource_path("models/qwen2.5-1.5b-instruct-q4_k_m.gguf")
    data_dir = app_data_dir() / "Data"
    data_dir.mkdir(parents=True, exist_ok=True)

    os.environ["NEXA_PROVIDER"] = "local"
    os.environ["NEXA_LOCAL_BASE_URL"] = f"http://127.0.0.1:{LOCAL_MODEL_PORT}/v1"
    os.environ["NEXA_LOCAL_API_KEY"] = ""
    os.environ["NEXA_MODEL"] = MODEL_ID
    os.environ["NEXA_HOST"] = "127.0.0.1"
    os.environ["NEXA_PORT"] = str(API_PORT)
    os.environ["NEXA_BASE_URL"] = f"http://127.0.0.1:{API_PORT}/v1"
    os.environ["NEXA_DATA_DIR"] = str(data_dir)
    os.environ["NEXA_MAX_OUTPUT_TOKENS"] = "1536"
    os.environ["NEXA_REQUEST_TIMEOUT"] = "900"
    os.environ["TOKENIZERS_PARALLELISM"] = "false"
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    os.environ["PATH"] = str(runtime_dir) + os.pathsep + os.environ.get("PATH", "")
    return runtime_dir, model_path, data_dir


class NexaDesktop:
    BG = "#0b1020"
    PANEL = "#111a2e"
    PANEL_2 = "#17233a"
    TEXT = "#e8eef9"
    MUTED = "#92a1bb"
    ACCENT = "#6d9eff"
    BORDER = "#253551"

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title(f"{APP_NAME} {APP_VERSION}")
        self.root.geometry("1120x760")
        self.root.minsize(820, 620)
        self.root.configure(bg=self.BG)
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

        self.runtime_dir, self.model_path, self.data_dir = configure_environment()
        self.log_path = app_data_dir() / "nexa-runtime.log"
        self.log_handle = self.log_path.open("a", encoding="utf-8", buffering=1)
        self.llama_process: subprocess.Popen | None = None
        self.api_server = None
        self.api_thread: threading.Thread | None = None
        self.ready = False
        self.busy = False
        self.uploading = False
        self.pending_files: list[dict[str, str]] = []
        self.messages: list[dict[str, Any]] = [{"role": "system", "content": SYSTEM_PROMPT}]
        self.events: queue.Queue[tuple[str, Any]] = queue.Queue()
        self._build_ui()
        self._append_message(
            "Nexa AI",
            "Starting your built-in offline model. The first startup may take a little while as the model loads into memory.",
            "assistant",
        )
        self.status_var.set("Starting local AI engine…")
        threading.Thread(target=self._boot_engine, daemon=True, name="NexaBoot").start()
        self.root.after(100, self._poll_events)

    def _build_ui(self) -> None:
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure(
            "Nexa.TButton", font=("Segoe UI", 10), padding=(12, 8),
            background=self.PANEL_2, foreground=self.TEXT, borderwidth=0,
        )
        style.map(
            "Nexa.TButton",
            background=[("active", "#263a5c"), ("disabled", "#1a2438")],
            foreground=[("disabled", "#61708a")],
        )
        style.configure(
            "Accent.TButton", font=("Segoe UI Semibold", 10), padding=(16, 9),
            background=self.ACCENT, foreground="#08101f", borderwidth=0,
        )
        style.map("Accent.TButton", background=[("active", "#8bb2ff"), ("disabled", "#40577e")])

        shell = tk.Frame(self.root, bg=self.BG)
        shell.pack(fill="both", expand=True)

        sidebar = tk.Frame(shell, bg=self.PANEL, width=235)
        sidebar.pack(side="left", fill="y")
        sidebar.pack_propagate(False)
        brand = tk.Frame(sidebar, bg=self.PANEL)
        brand.pack(fill="x", padx=20, pady=(24, 22))
        tk.Label(
            brand, text="N", bg=self.ACCENT, fg="#071226",
            font=("Segoe UI Semibold", 18), width=2, height=1,
        ).pack(side="left", padx=(0, 10))
        labels = tk.Frame(brand, bg=self.PANEL)
        labels.pack(side="left")
        tk.Label(labels, text="NEXA AI", bg=self.PANEL, fg=self.TEXT, font=("Segoe UI Semibold", 15)).pack(anchor="w")
        tk.Label(labels, text="PRIVATE · OFFLINE", bg=self.PANEL, fg=self.MUTED, font=("Segoe UI", 8)).pack(anchor="w", pady=(2, 0))

        ttk.Button(
            sidebar, text="＋   New conversation", style="Accent.TButton",
            command=self.new_conversation,
        ).pack(fill="x", padx=14, pady=(0, 18))
        tk.Label(sidebar, text="WORKSPACE", bg=self.PANEL, fg=self.MUTED, font=("Segoe UI Semibold", 8)).pack(anchor="w", padx=20, pady=(4, 10))
        tk.Label(sidebar, text="Local assistant", bg=self.PANEL, fg=self.TEXT, font=("Segoe UI", 10)).pack(anchor="w", padx=20, pady=5)
        tk.Label(sidebar, text="Chat & writing", bg=self.PANEL, fg=self.MUTED, font=("Segoe UI", 9)).pack(anchor="w", padx=20, pady=3)
        tk.Label(sidebar, text="Documents (PDF / text)", bg=self.PANEL, fg=self.MUTED, font=("Segoe UI", 9)).pack(anchor="w", padx=20, pady=3)
        tk.Frame(sidebar, bg=self.PANEL).pack(fill="both", expand=True)
        tk.Frame(sidebar, bg=self.BORDER, height=1).pack(fill="x", padx=16, pady=(0, 12))
        tk.Label(sidebar, text="MODEL", bg=self.PANEL, fg=self.MUTED, font=("Segoe UI Semibold", 8)).pack(anchor="w", padx=20)
        tk.Label(sidebar, text="Qwen 2.5 · 1.5B Q4", bg=self.PANEL, fg=self.TEXT, font=("Segoe UI Semibold", 10)).pack(anchor="w", padx=20, pady=(5, 3))
        tk.Label(sidebar, text="Runs on this PC", bg=self.PANEL, fg="#73d6a4", font=("Segoe UI", 9)).pack(anchor="w", padx=20, pady=(0, 18))

        main = tk.Frame(shell, bg=self.BG)
        main.pack(side="left", fill="both", expand=True)
        top = tk.Frame(main, bg=self.PANEL, height=66)
        top.pack(fill="x")
        top.pack_propagate(False)
        tk.Label(top, text="Assistant", bg=self.PANEL, fg=self.TEXT, font=("Segoe UI Semibold", 14)).pack(side="left", padx=22)
        self.status_var = tk.StringVar(value="Starting…")
        self.status_label = tk.Label(top, textvariable=self.status_var, bg=self.PANEL, fg=self.MUTED, font=("Segoe UI", 9))
        self.status_label.pack(side="right", padx=22)

        self.chat = ScrolledText(
            main, wrap="word", bg=self.BG, fg=self.TEXT, insertbackground=self.TEXT,
            selectbackground="#2e4f7a", relief="flat", borderwidth=0,
            font=("Segoe UI", 10), padx=26, pady=22, spacing1=2, spacing3=8,
            state="disabled",
        )
        self.chat.pack(fill="both", expand=True)
        self.chat.tag_configure("name_user", foreground="#9bbcff", font=("Segoe UI Semibold", 10))
        self.chat.tag_configure("name_ai", foreground="#83dcb0", font=("Segoe UI Semibold", 10))
        self.chat.tag_configure("body", foreground=self.TEXT, font=("Segoe UI", 10), lmargin1=12, lmargin2=12, spacing1=4, spacing3=14)
        self.chat.tag_configure("meta", foreground=self.MUTED, font=("Segoe UI", 8), lmargin1=12, spacing3=14)

        footer = tk.Frame(main, bg=self.BG)
        footer.pack(fill="x", padx=20, pady=(8, 16))
        self.attachments_label = tk.Label(footer, text="", bg=self.BG, fg=self.MUTED, font=("Segoe UI", 8), anchor="w")
        self.attachments_label.pack(fill="x", pady=(0, 5))
        composer = tk.Frame(footer, bg=self.PANEL, highlightbackground=self.BORDER, highlightthickness=1)
        composer.pack(fill="x")
        self.input = tk.Text(
            composer, height=3, wrap="word", bg=self.PANEL, fg=self.TEXT,
            insertbackground=self.TEXT, relief="flat", borderwidth=0,
            font=("Segoe UI", 10), padx=12, pady=10, undo=True,
        )
        self.input.pack(side="left", fill="both", expand=True)
        self.input.bind("<Control-Return>", self._send_hotkey)
        actions = tk.Frame(composer, bg=self.PANEL)
        actions.pack(side="right", fill="y", padx=8, pady=8)
        ttk.Button(actions, text="Attach", style="Nexa.TButton", command=self.attach_file).pack(fill="x", pady=(0, 6))
        self.send_button = ttk.Button(actions, text="Send  ↑", style="Accent.TButton", command=self.send_message, state="disabled")
        self.send_button.pack(fill="x")
        tk.Label(
            footer,
            text="Your messages and files stay on this computer. No cloud API is used.",
            bg=self.BG, fg=self.MUTED, font=("Segoe UI", 8),
        ).pack(anchor="center", pady=(8, 0))

    def _append_message(self, name: str, text: str, role: str) -> None:
        self.chat.configure(state="normal")
        tag = "name_user" if role == "user" else "name_ai"
        self.chat.insert("end", f"{name}\n", tag)
        self.chat.insert("end", f"{text}\n\n", "body")
        self.chat.configure(state="disabled")
        self.chat.see("end")

    def _append_stream(self, text: str) -> None:
        self.chat.configure(state="normal")
        self.chat.insert("end", text, "body")
        self.chat.configure(state="disabled")
        self.chat.see("end")

    def _boot_engine(self) -> None:
        try:
            exe = self.runtime_dir / "llama-server.exe"
            if not exe.is_file():
                raise FileNotFoundError(f"Built-in inference runtime is missing: {exe}")
            if not self.model_path.is_file():
                raise FileNotFoundError(f"The bundled AI model is missing: {self.model_path}")
            threads = max(2, min(6, (os.cpu_count() or 4)))
            cmd = [
                str(exe), "-m", str(self.model_path),
                "--host", "127.0.0.1", "--port", str(LOCAL_MODEL_PORT),
                "-c", "4096", "-t", str(threads), "--parallel", "1",
                "--alias", MODEL_ID, "--no-webui", "--offline",
            ]
            self.llama_process = subprocess.Popen(
                cmd, cwd=str(self.runtime_dir), stdin=subprocess.DEVNULL,
                stdout=self.log_handle, stderr=subprocess.STDOUT,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            if not self._wait_for_url(f"http://127.0.0.1:{LOCAL_MODEL_PORT}/health", 360):
                raise RuntimeError("The built-in AI model did not become ready. See the runtime log for details.")

            from nexa_ai.config import settings
            import uvicorn
            from nexa_ai.api import app

            config = uvicorn.Config(app, host=settings.host, port=settings.port, log_level="error", access_log=False)
            self.api_server = uvicorn.Server(config)
            self.api_thread = threading.Thread(target=self.api_server.run, daemon=True, name="NexaLocalAPI")
            self.api_thread.start()
            if not self._wait_for_url(f"http://127.0.0.1:{API_PORT}/health", 30):
                raise RuntimeError("Nexa AI local API could not start. Port 8000 may already be in use.")
            self.events.put(("ready", None))
        except Exception as exc:
            self.events.put(("boot_error", str(exc)))

    @staticmethod
    def _wait_for_url(url: str, timeout_seconds: int) -> bool:
        deadline = time.monotonic() + timeout_seconds
        while time.monotonic() < deadline:
            try:
                with httpx.Client(timeout=2) as client:
                    response = client.get(url)
                    if response.is_success:
                        return True
            except Exception:
                pass
            time.sleep(0.5)
        return False

    def _poll_events(self) -> None:
        try:
            while True:
                kind, payload = self.events.get_nowait()
                if kind == "ready":
                    self.ready = True
                    self.status_var.set("● Offline model ready")
                    self.status_label.configure(fg="#73d6a4")
                    self.send_button.configure(state="normal")
                    self._append_message(
                        "Nexa AI",
                        "I'm ready. Your AI model is running locally on this PC. You can disconnect from the internet and continue chatting.",
                        "assistant",
                    )
                elif kind == "boot_error":
                    self.status_var.set("Offline engine failed to start")
                    self.status_label.configure(fg="#ff8d8d")
                    messagebox.showerror("Nexa AI could not start", f"{payload}\n\nDiagnostic log: {self.log_path}")
                elif kind == "stream":
                    self._append_stream(str(payload))
                elif kind == "done":
                    self.busy = False
                    self.send_button.configure(state="normal" if self.ready else "disabled")
                    self.status_var.set("● Offline model ready")
                    self.status_label.configure(fg="#73d6a4")
                    self.chat.configure(state="normal")
                    self.chat.insert("end", "\n\n", "body")
                    self.chat.configure(state="disabled")
                    self.chat.see("end")
                elif kind == "request_error":
                    self.busy = False
                    self.send_button.configure(state="normal" if self.ready else "disabled")
                    self.status_var.set("Request failed")
                    self.status_label.configure(fg="#ff8d8d")
                    self._append_message("Nexa AI", f"I couldn't complete that request.\n\n{payload}", "assistant")
                elif kind == "attached":
                    self.pending_files.append(payload)
                    self.uploading = False
                    self.send_button.configure(state="normal" if self.ready and not self.busy else "disabled")
                    self.status_var.set("● Offline model ready")
                    self.status_label.configure(fg="#73d6a4")
                    self._refresh_attachments()
                elif kind == "attach_error":
                    self.uploading = False
                    self.send_button.configure(state="normal" if self.ready and not self.busy else "disabled")
                    messagebox.showerror("Attachment error", str(payload))
        except queue.Empty:
            pass
        if self.root.winfo_exists():
            self.root.after(100, self._poll_events)

    def _refresh_attachments(self) -> None:
        names = [item.get("filename", "file") for item in self.pending_files]
        self.attachments_label.configure(text=("Attached: " + "  ·  ".join(names)) if names else "")

    def attach_file(self) -> None:
        if self.uploading or self.busy or not self.ready:
            return
        path = filedialog.askopenfilename(
            title="Attach a local document",
            filetypes=[
                ("Supported documents", "*.pdf *.txt *.md *.csv *.json *.xml *.py *.js *.html *.css *.log"),
                ("All files", "*.*"),
            ],
        )
        if not path:
            return
        self.uploading = True
        self.send_button.configure(state="disabled")
        self.status_var.set("Saving attachment locally…")
        self.status_label.configure(fg=self.ACCENT)
        threading.Thread(target=self._upload_file, args=(Path(path),), daemon=True).start()

    def _upload_file(self, path: Path) -> None:
        try:
            with path.open("rb") as file_handle, httpx.Client(timeout=300) as client:
                response = client.post(
                    f"http://127.0.0.1:{API_PORT}/v1/files",
                    files={"file": (path.name, file_handle)},
                )
            response.raise_for_status()
            self.events.put(("attached", response.json()))
        except Exception as exc:
            self.events.put(("attach_error", str(exc)))

    def _send_hotkey(self, _event=None):
        self.send_message()
        return "break"

    def send_message(self) -> None:
        if not self.ready or self.busy or self.uploading:
            return
        text = self.input.get("1.0", "end-1c").strip()
        if not text and not self.pending_files:
            return
        self.input.delete("1.0", "end")
        self.busy = True
        self.send_button.configure(state="disabled")
        self.status_var.set("Nexa AI is thinking locally…")
        self.status_label.configure(fg=self.ACCENT)
        attachments = list(self.pending_files)
        self.pending_files.clear()
        self._refresh_attachments()
        user_content: Any = [{"type": "text", "text": text}] if attachments else text
        if attachments:
            user_content.extend({"type": "input_file", "file_id": item["id"]} for item in attachments)
        self.messages.append({"role": "user", "content": user_content})
        visible_text = text or "Please analyze the attached document."
        if attachments:
            visible_text += "\n\n" + "\n".join(f"📎 {x.get('filename', 'file')}" for x in attachments)
        self._append_message("You", visible_text, "user")
        self._append_message("Nexa AI", "", "assistant")
        threading.Thread(target=self._stream_request, daemon=True, name="NexaResponse").start()

    def _stream_request(self) -> None:
        answer: list[str] = []
        try:
            payload = {
                "model": MODEL_ID, "messages": self.messages, "stream": True,
                "temperature": 0.7, "max_tokens": 1536,
            }
            with httpx.Client(timeout=httpx.Timeout(900, connect=10)) as client:
                with client.stream("POST", f"http://127.0.0.1:{API_PORT}/v1/chat/completions", json=payload) as response:
                    if response.is_error:
                        try:
                            body = response.json()
                            detail = body.get("error", {}).get("message", str(body))
                        except Exception:
                            detail = response.text[:800]
                        raise RuntimeError(detail)
                    for line in response.iter_lines():
                        if not line or not line.startswith("data:"):
                            continue
                        raw = line[5:].strip()
                        if raw == "[DONE]":
                            break
                        try:
                            item = json.loads(raw)
                        except json.JSONDecodeError:
                            continue
                        if "error" in item:
                            err = item["error"]
                            raise RuntimeError(err.get("message", str(err)) if isinstance(err, dict) else str(err))
                        choices = item.get("choices") or []
                        if choices:
                            delta = choices[0].get("delta", {})
                            piece = delta.get("content", "")
                            if isinstance(piece, list):
                                piece = "".join(str(p.get("text", "")) for p in piece if isinstance(p, dict))
                            if piece:
                                answer.append(str(piece))
                                self.events.put(("stream", str(piece)))
            self.messages.append({"role": "assistant", "content": "".join(answer)})
            self._save_chat()
            self.events.put(("done", None))
        except Exception as exc:
            if self.messages and self.messages[-1].get("role") == "user":
                self.messages.pop()
            self.events.put(("request_error", str(exc)))

    def _save_chat(self) -> None:
        try:
            folder = self.data_dir / "chats"
            folder.mkdir(parents=True, exist_ok=True)
            name = f"chat-{datetime.now():%Y%m%d-%H%M%S}.json"
            (folder / name).write_text(json.dumps(self.messages, ensure_ascii=False, indent=2), encoding="utf-8")
        except OSError:
            pass

    def new_conversation(self) -> None:
        if self.busy:
            return
        self.messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        self.chat.configure(state="normal")
        self.chat.delete("1.0", "end")
        self.chat.configure(state="disabled")
        self.pending_files.clear()
        self._refresh_attachments()
        self._append_message("Nexa AI", "New conversation started. What would you like to work on?", "assistant")

    def on_close(self) -> None:
        try:
            if self.api_server:
                self.api_server.should_exit = True
            if self.llama_process and self.llama_process.poll() is None:
                self.llama_process.terminate()
                try:
                    self.llama_process.wait(timeout=8)
                except subprocess.TimeoutExpired:
                    self.llama_process.kill()
            self.log_handle.close()
        except Exception:
            pass
        self.root.destroy()


def main() -> None:
    root = tk.Tk()
    try:
        NexaDesktop(root)
    except Exception as exc:
        messagebox.showerror(APP_NAME, f"Nexa AI could not initialize.\n\n{exc}")
        return
    root.mainloop()


if __name__ == "__main__":
    main()
