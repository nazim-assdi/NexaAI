from __future__ import annotations

import ctypes
import json
import os
import queue
import subprocess
import sys
import threading
import time
import wave
from pathlib import Path
from uuid import uuid4
from typing import Any

import httpx
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from tkinter.scrolledtext import ScrolledText

from nexa_ai.model_library import QWEN3_MODEL_KEY, QWEN3_MODEL_ID, QWEN3_MODEL_NAME, QWEN3_MODEL_FILENAME, model_is_installed, download_model, verify_model_file
from nexa_ai.plugin_manager import PluginManager
from nexa_ai.history_store import HistoryStore
from nexa_ai.engine_config import build_engine_command, engine_profiles
from nexa_ai.n8n_studio import build_n8n_messages, extract_n8n_json, workflow_json_text
from nexa_ai.server_config import build_uvicorn_config
from nexa_ai.ui_layout import calculate_window_geometry

APP_NAME = "Nexa AI"
APP_VERSION = "1.5.2"
MODEL_ID = QWEN3_MODEL_ID
LOCAL_MODEL_PORT = 11435
API_PORT = 8000
SYSTEM_PROMPT = (
    "You are Nexa AI, a practical offline software developer and automation engineer. "
    "Reply naturally in the user's language; when the user writes Bangla, use natural Bangla. "
    "Help with Python, JavaScript, HTML/CSS, Windows troubleshooting, GitHub projects and n8n workflow design. "
    "For coding tasks, provide complete runnable code, explain filenames and setup, and point out assumptions. "
    "For n8n tasks, design valid node connections and realistic parameters, use credential placeholders, and never invent secrets. "
    "Do not claim that code or workflows were executed or tested unless the app actually reports that. "
    "You run locally and do not have live internet access; be clear when up-to-date external details cannot be checked."
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
    model_path = app_data_dir() / "models" / QWEN3_MODEL_FILENAME
    data_dir = app_data_dir() / "Data"
    data_dir.mkdir(parents=True, exist_ok=True)

    os.environ["NEXA_PROVIDER"] = "local"
    os.environ["NEXA_LOCAL_BASE_URL"] = f"http://127.0.0.1:{LOCAL_MODEL_PORT}/v1"
    os.environ["NEXA_LOCAL_API_KEY"] = ""
    os.environ.pop("NEXA_MM_PROJ_PATH", None)
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
    BG = "#171a17"
    PANEL = "#202720"
    PANEL_2 = "#2b352c"
    TEXT = "#e5e8d8"
    MUTED = "#a7b19f"
    ACCENT = "#c4d6a1"
    BORDER = "#3a4939"

    THEMES = {
        "Eye Comfort Premium": {
            "BG": "#171a17", "PANEL": "#202720", "PANEL_2": "#2b352c",
            "TEXT": "#e5e8d8", "MUTED": "#a7b19f", "ACCENT": "#c4d6a1",
            "BORDER": "#3a4939", "USER": "#bfd0b1", "AI": "#a8d3b1",
            "SELECT": "#405641", "ACTIVE": "#394a3b", "BUTTON_TEXT": "#172018",
        },
        "OLED Midnight": {
            "BG": "#090b0d", "PANEL": "#121619", "PANEL_2": "#1c252a",
            "TEXT": "#e4edf0", "MUTED": "#93a3aa", "ACCENT": "#8ac8c2",
            "BORDER": "#28363b", "USER": "#a9c5eb", "AI": "#91d3b4",
            "SELECT": "#294c50", "ACTIVE": "#263b40", "BUTTON_TEXT": "#081413",
        },
        "Soft Paper": {
            "BG": "#e9e5d9", "PANEL": "#f2efe5", "PANEL_2": "#e0e5d8",
            "TEXT": "#29332d", "MUTED": "#657166", "ACCENT": "#718f72",
            "BORDER": "#c9d0c4", "USER": "#4c6687", "AI": "#477b59",
            "SELECT": "#c4d7c6", "ACTIVE": "#d2dfd1", "BUTTON_TEXT": "#ffffff",
        },
    }

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title(f"{APP_NAME} {APP_VERSION}")
        self.root.minsize(820, 560)
        self.root.geometry(calculate_window_geometry(self.root.winfo_screenwidth(), self.root.winfo_screenheight()))
        self.root.configure(bg=self.BG)
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        try:
            icon_base = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent
            icon_path = icon_base / "assets" / "nexa-ai.ico"
            if icon_path.is_file():
                self.root.iconbitmap(default=str(icon_path))
        except (tk.TclError, OSError):
            pass

        self.runtime_dir, self.model_path, self.data_dir = configure_environment()
        self.app_root = app_data_dir()
        self.plugin_manager = PluginManager(self.app_root)
        self.history_store = HistoryStore(self.data_dir)
        self.conversation_id = uuid4().hex
        self.conversation_title = "New conversation"
        self.preferences_path = self.app_root / "preferences.json"
        self.theme_name = self._load_theme_preference()
        self._set_palette(self.theme_name)
        self.root.configure(bg=self.BG)
        self.current_model_key = QWEN3_MODEL_KEY
        self.current_model_id = MODEL_ID
        self.current_model_name = QWEN3_MODEL_NAME
        self.active_model_path = self.model_path
        self.active_mmproj_path: Path | None = None
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
        self.recording = False
        self.recording_stream = None
        self.recording_chunks: list[Any] = []
        self.recording_lock = threading.Lock()
        self.voice_turn = False
        self.whisper_model = None
        self._build_ui()
        self._append_message(
            "Nexa AI",
            "Welcome to NexaAI Chat Workspace. Your messages go to the local Qwen3 4B assistant. Click the message box at the bottom, type anything, then press Enter or Send Message. Ask for coding help, debugging, Bengali/English chat or n8n workflow design.",
            "assistant",
        )
        self.status_var.set("Preparing Qwen3 4B · checking local model…")
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
            background=[("active", self.THEMES[self.theme_name]["ACTIVE"]), ("disabled", self.PANEL)],
            foreground=[("disabled", "#61708a")],
        )
        style.configure(
            "Accent.TButton", font=("Segoe UI Semibold", 10), padding=(16, 9),
            background=self.ACCENT, foreground=self.THEMES[self.theme_name]["BUTTON_TEXT"], borderwidth=0,
        )
        style.map("Accent.TButton", background=[("active", self.THEMES[self.theme_name]["ACTIVE"]), ("disabled", self.PANEL_2)])

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
        tk.Label(labels, text="DEVELOPED BY NTECH", bg=self.PANEL, fg=self.ACCENT, font=("Segoe UI Semibold", 7)).pack(anchor="w", pady=(3, 0))

        ttk.Button(
            sidebar, text="💬   Chat Workspace", style="Accent.TButton",
            command=self.show_chat_workspace,
        ).pack(fill="x", padx=14, pady=(0, 8))
        ttk.Button(
            sidebar, text="＋   New conversation", style="Nexa.TButton",
            command=self.new_conversation,
        ).pack(fill="x", padx=14, pady=(0, 8))
        ttk.Button(
            sidebar, text="◷   Chat History", style="Nexa.TButton",
            command=self.open_history,
        ).pack(fill="x", padx=14, pady=(0, 8))
        ttk.Button(
            sidebar, text="⚙   n8n Workflow Studio", style="Nexa.TButton",
            command=self.open_n8n_studio,
        ).pack(fill="x", padx=14, pady=(0, 10))
        ttk.Button(
            sidebar, text="▦   Plugin Manager", style="Nexa.TButton",
            command=self.open_plugin_manager,
        ).pack(fill="x", padx=14, pady=(4, 14))
        tk.Label(sidebar, text="WORKSPACE", bg=self.PANEL, fg=self.MUTED, font=("Segoe UI Semibold", 8)).pack(anchor="w", padx=20, pady=(4, 10))
        tk.Label(sidebar, text="Local assistant", bg=self.PANEL, fg=self.TEXT, font=("Segoe UI", 10)).pack(anchor="w", padx=20, pady=5)
        tk.Label(sidebar, text="Chat & writing", bg=self.PANEL, fg=self.MUTED, font=("Segoe UI", 9)).pack(anchor="w", padx=20, pady=3)
        tk.Label(sidebar, text="Documents & local tools", bg=self.PANEL, fg=self.MUTED, font=("Segoe UI", 9)).pack(anchor="w", padx=20, pady=3)
        tk.Frame(sidebar, bg=self.PANEL).pack(fill="both", expand=True)
        tk.Frame(sidebar, bg=self.BORDER, height=1).pack(fill="x", padx=16, pady=(0, 12))
        tk.Label(sidebar, text="ACTIVE MODEL", bg=self.PANEL, fg=self.MUTED, font=("Segoe UI Semibold", 8)).pack(anchor="w", padx=20)
        self.model_name_var = tk.StringVar(value=self.current_model_name)
        tk.Label(sidebar, textvariable=self.model_name_var, bg=self.PANEL, fg=self.TEXT, font=("Segoe UI Semibold", 10), wraplength=190, justify="left").pack(anchor="w", padx=20, pady=(5, 3))
        tk.Label(sidebar, text="Runs locally on this PC", bg=self.PANEL, fg="#8fbd92", font=("Segoe UI", 9)).pack(anchor="w", padx=20, pady=(0, 18))

        main = tk.Frame(shell, bg=self.BG)
        main.pack(side="left", fill="both", expand=True)
        top = tk.Frame(main, bg=self.PANEL, height=66)
        top.pack(fill="x")
        top.pack_propagate(False)
        tk.Label(top, text="Chat Workspace", bg=self.PANEL, fg=self.TEXT, font=("Segoe UI Semibold", 14)).pack(side="left", padx=22)
        tk.Label(top, text="QWEN3 4B  ·  NTECH", bg=self.PANEL_2, fg=self.ACCENT, font=("Segoe UI Semibold", 8), padx=10, pady=5).pack(side="left")
        self.status_var = tk.StringVar(value="Starting…")
        self.status_label = tk.Label(top, textvariable=self.status_var, bg=self.PANEL, fg=self.MUTED, font=("Segoe UI", 9))
        self.status_label.pack(side="right", padx=(10, 22))
        self.theme_var = tk.StringVar(value=self.theme_name)
        self.theme_selector = ttk.Combobox(
            top, textvariable=self.theme_var, values=list(self.THEMES.keys()),
            state="readonly", width=20, font=("Segoe UI", 9),
        )
        self.theme_selector.pack(side="right", padx=8)
        self.theme_selector.bind("<<ComboboxSelected>>", self._change_theme)
        self.ttk_style = style

        self.chat = ScrolledText(
            main, wrap="word", bg=self.BG, fg=self.TEXT, insertbackground=self.TEXT,
            selectbackground=self.THEMES[self.theme_name]["SELECT"], relief="flat", borderwidth=0,
            font=("Segoe UI", 10), padx=26, pady=22, spacing1=2, spacing3=8,
            state="disabled",
        )
        self.chat.pack(fill="both", expand=True)
        self.chat.tag_configure("name_user", foreground=self.THEMES[self.theme_name]["USER"], font=("Segoe UI Semibold", 10))
        self.chat.tag_configure("name_ai", foreground=self.THEMES[self.theme_name]["AI"], font=("Segoe UI Semibold", 10))
        self.chat.tag_configure("body", foreground=self.TEXT, font=("Segoe UI", 10), lmargin1=12, lmargin2=12, spacing1=4, spacing3=14)
        self.chat.tag_configure("meta", foreground=self.MUTED, font=("Segoe UI", 8), lmargin1=12, spacing3=14)

        footer = tk.Frame(main, bg=self.BG)
        footer.pack(fill="x", padx=20, pady=(8, 12))
        tk.Label(footer, text="MESSAGE NEXA AI", bg=self.BG, fg=self.MUTED, font=("Segoe UI Semibold", 8), anchor="w").pack(fill="x", pady=(0, 5))
        self.attachments_label = tk.Label(footer, text="", bg=self.BG, fg=self.MUTED, font=("Segoe UI", 8), anchor="w")
        self.attachments_label.pack(fill="x", pady=(0, 5))
        composer = tk.Frame(footer, bg=self.PANEL, highlightbackground=self.ACCENT, highlightthickness=1)
        composer.pack(fill="x")
        self.input = tk.Text(
            composer, height=3, wrap="word", bg=self.PANEL, fg=self.TEXT,
            insertbackground=self.TEXT, relief="flat", borderwidth=0,
            font=("Segoe UI", 10), padx=12, pady=10, undo=True,
        )
        self.input.pack(side="left", fill="both", expand=True)
        self.input_placeholder = "Type your message here…  (Enter to send · Shift+Enter for a new line)"
        self.input_placeholder_active = True
        self.input.insert("1.0", self.input_placeholder)
        self.input.configure(fg=self.MUTED)
        self.input.bind("<FocusIn>", self._clear_input_placeholder)
        self.input.bind("<FocusOut>", self._restore_input_placeholder)
        self.input.bind("<Return>", self._send_enter)
        self.input.bind("<Control-Return>", self._send_hotkey)
        actions = tk.Frame(composer, bg=self.PANEL)
        actions.pack(side="right", fill="y", padx=8, pady=8)
        self.voice_button = ttk.Button(actions, text="🎙 Voice chat", style="Nexa.TButton", command=self.toggle_voice_chat)
        self.voice_button.pack(fill="x", pady=(0, 6))
        ttk.Button(actions, text="Attach file", style="Nexa.TButton", command=self.attach_file).pack(fill="x", pady=(0, 6))
        self.send_button = ttk.Button(actions, text="Send Message  ↑", style="Accent.TButton", command=self.send_message, state="disabled")
        self.send_button.pack(fill="x")
        self.speak_replies_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(footer, text="Speak voice-chat replies", variable=self.speak_replies_var).pack(anchor="e", pady=(5, 0))
        tk.Label(
            footer,
            text="LOCAL & PRIVATE  ·  DEVELOPED BY NTECH",
            bg=self.BG, fg=self.MUTED, font=("Segoe UI", 8),
        ).pack(anchor="center", pady=(5, 0))

    def show_chat_workspace(self) -> None:
        """Bring the chat composer into view and focus it for typing."""
        try:
            self.root.deiconify()
            self.root.lift()
            self.chat.see("end")
            self.input.focus_set()
            if self.input_placeholder_active:
                self._clear_input_placeholder()
        except tk.TclError:
            pass

    def _clear_input_placeholder(self, _event=None) -> None:
        if self.input_placeholder_active:
            self.input.delete("1.0", "end")
            self.input.configure(fg=self.TEXT)
            self.input_placeholder_active = False

    def _restore_input_placeholder(self, _event=None) -> None:
        if not self.input_placeholder_active and not self.input.get("1.0", "end-1c").strip():
            self.input.insert("1.0", self.input_placeholder)
            self.input.configure(fg=self.MUTED)
            self.input_placeholder_active = True

    def _send_enter(self, event=None):
        # Shift+Enter keeps the normal Text widget newline behaviour.
        if event is not None and (event.state & 0x0001):
            return None
        self.send_message()
        return "break"

    def _load_theme_preference(self) -> str:
        try:
            prefs = json.loads(self.preferences_path.read_text(encoding="utf-8"))
            selected = str(prefs.get("theme", "Eye Comfort Premium"))
            return selected if selected in self.THEMES else "Eye Comfort Premium"
        except (OSError, ValueError, AttributeError):
            return "Eye Comfort Premium"

    def _set_palette(self, theme_name: str) -> None:
        palette = self.THEMES.get(theme_name, self.THEMES["Eye Comfort Premium"])
        for key in ("BG", "PANEL", "PANEL_2", "TEXT", "MUTED", "ACCENT", "BORDER"):
            setattr(self, key, palette[key])
        self.theme_name = theme_name

    def _change_theme(self, _event=None) -> None:
        selected = self.theme_var.get()
        if selected not in self.THEMES or selected == self.theme_name:
            return
        old_palette = dict(self.THEMES[self.theme_name])
        self._set_palette(selected)
        new_palette = self.THEMES[self.theme_name]
        colour_map = {
            old_palette["BG"]: self.BG,
            old_palette["PANEL"]: self.PANEL,
            old_palette["PANEL_2"]: self.PANEL_2,
            old_palette["TEXT"]: self.TEXT,
            old_palette["MUTED"]: self.MUTED,
            old_palette["ACCENT"]: self.ACCENT,
            old_palette["BORDER"]: self.BORDER,
            old_palette["USER"]: new_palette["USER"],
            old_palette["AI"]: new_palette["AI"],
            old_palette["SELECT"]: new_palette["SELECT"],
        }
        self._retheme_widget(self.root, colour_map)
        self.root.configure(bg=self.BG)
        self.ttk_style.configure("Nexa.TButton", background=self.PANEL_2, foreground=self.TEXT)
        self.ttk_style.map("Nexa.TButton", background=[("active", new_palette["ACTIVE"]), ("disabled", self.PANEL)])
        self.ttk_style.configure("Accent.TButton", background=self.ACCENT, foreground=new_palette["BUTTON_TEXT"])
        self.ttk_style.map("Accent.TButton", background=[("active", new_palette["ACTIVE"]), ("disabled", self.PANEL_2)])
        self.ttk_style.configure("TCombobox", fieldbackground=self.PANEL_2, background=self.PANEL_2, foreground=self.TEXT)
        self.chat.tag_configure("name_user", foreground=new_palette["USER"])
        self.chat.tag_configure("name_ai", foreground=new_palette["AI"])
        self.chat.tag_configure("body", foreground=self.TEXT)
        self.chat.tag_configure("meta", foreground=self.MUTED)
        self.chat.configure(selectbackground=new_palette["SELECT"])
        self.theme_name = selected
        self._save_preferences()

    def _retheme_widget(self, widget: tk.Misc, colour_map: dict[str, str]) -> None:
        for option in ("bg", "background", "fg", "foreground", "insertbackground", "highlightbackground", "selectbackground"):
            try:
                value = widget.cget(option)
                if value in colour_map:
                    widget.configure(**{option: colour_map[value]})
            except (tk.TclError, TypeError):
                pass
        for child in widget.winfo_children():
            self._retheme_widget(child, colour_map)

    def _save_preferences(self) -> None:
        try:
            payload = {"theme": self.theme_name}
            tmp = self.preferences_path.with_suffix(".tmp")
            tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
            tmp.replace(self.preferences_path)
        except OSError:
            pass

    def open_plugin_manager(self) -> None:
        window = tk.Toplevel(self.root)
        window.title("Nexa AI · Plugin Manager")
        window.geometry("820x690")
        window.configure(bg=self.BG)
        tk.Label(window, text="Plugin Manager", bg=self.BG, fg=self.TEXT, font=("Segoe UI Semibold", 18)).pack(anchor="w", padx=22, pady=(20, 4))
        tk.Label(window, text="Enable trusted extensions and manage optional local AI capabilities.", bg=self.BG, fg=self.MUTED, font=("Segoe UI", 9)).pack(anchor="w", padx=22, pady=(0, 10))
        body = tk.Frame(window, bg=self.BG)
        body.pack(fill="both", expand=True, padx=16, pady=4)
        for item in self.plugin_manager.list_plugins():
            row = tk.Frame(body, bg=self.PANEL, highlightbackground=self.BORDER, highlightthickness=1)
            row.pack(fill="x", padx=4, pady=5)
            line = tk.Frame(row, bg=self.PANEL)
            line.pack(fill="x", padx=12, pady=(9, 2))
            if item.get("kind") == "imported extension":
                variable = tk.BooleanVar(value=item["enabled"])
                check = ttk.Checkbutton(
                    line, text=item["name"], variable=variable,
                    command=lambda pid=item["id"], var=variable: self._toggle_plugin(pid, var.get()),
                )
                check.pack(side="left")
            else:
                tk.Label(line, text=item["name"], bg=self.PANEL, fg=self.TEXT, font=("Segoe UI Semibold", 10)).pack(side="left")
                tk.Label(line, text="Optional pack", bg=self.PANEL, fg=self.MUTED, font=("Segoe UI", 8)).pack(side="left", padx=10)
            tk.Label(line, text=item.get("status", ""), bg=self.PANEL, fg=self.MUTED, font=("Segoe UI", 8)).pack(side="right")
            tk.Label(row, text=item["description"], bg=self.PANEL, fg=self.TEXT, font=("Segoe UI", 9), wraplength=750, justify="left").pack(anchor="w", padx=14, pady=(2, 4))
            tk.Label(row, text=f"Requires: {item['requires']}", bg=self.PANEL, fg=self.MUTED, font=("Segoe UI", 8), wraplength=750, justify="left").pack(anchor="w", padx=14, pady=(0, 9))
        footer = tk.Frame(window, bg=self.BG)
        footer.pack(fill="x", padx=20, pady=(5, 18))
        ttk.Button(footer, text="Import plugin ZIP…", style="Nexa.TButton", command=self._import_plugin_zip).pack(side="left")
        ttk.Button(footer, text="Run plugin command…", style="Accent.TButton", command=self._run_plugin_command).pack(side="right")
        tk.Label(footer, text="Imported code runs only after you enable it. Import extensions you trust.", bg=self.BG, fg=self.MUTED, font=("Segoe UI", 8), wraplength=430).pack(side="left", padx=12)

    def _toggle_plugin(self, plugin_id: str, enabled: bool) -> None:
        self.plugin_manager.set_enabled(plugin_id, enabled)
        try:
            context = self.plugin_manager.load_enabled_imported_plugins(self.app_root)
            if enabled:
                messagebox.showinfo(
                    "Plugin enabled",
                    f"Plugin is enabled. Registered commands: {len(context.commands)}",
                )
        except Exception as exc:
            self.plugin_manager.set_enabled(plugin_id, False)
            messagebox.showerror("Plugin failed to load", str(exc))
            return

    def _run_plugin_command(self) -> None:
        commands = dict(self.plugin_manager.commands)
        if not commands:
            messagebox.showinfo("No plugin commands", "Import and enable a plugin that registers at least one command.")
            return
        window = tk.Toplevel(self.root)
        window.title("Run Plugin Command")
        window.geometry("480x360")
        window.configure(bg=self.BG)
        tk.Label(window, text="Available plugin commands", bg=self.BG, fg=self.TEXT, font=("Segoe UI Semibold", 14)).pack(anchor="w", padx=18, pady=(18, 8))
        for name, handler in sorted(commands.items()):
            row = tk.Frame(window, bg=self.PANEL)
            row.pack(fill="x", padx=14, pady=4)
            tk.Label(row, text=name, bg=self.PANEL, fg=self.TEXT, font=("Consolas", 9)).pack(side="left", padx=10, pady=8)
            ttk.Button(
                row, text="Run", style="Nexa.TButton",
                command=lambda n=name, h=handler: self._execute_plugin_command(n, h),
            ).pack(side="right", padx=8, pady=5)

    def _execute_plugin_command(self, name: str, handler) -> None:
        def worker() -> None:
            try:
                result = handler()
                message = str(result)[:6000]
                self.root.after(0, lambda: messagebox.showinfo(f"Plugin: {name}", message))
            except Exception as exc:
                error_text = str(exc)
                self.root.after(0, lambda e=error_text: messagebox.showerror(f"Plugin: {name}", e))

        threading.Thread(target=worker, daemon=True, name=f"PluginCommand-{name}").start()

    def _import_plugin_zip(self) -> None:
        selected = filedialog.askopenfilename(
            title="Import a Nexa plugin package",
            filetypes=[("Nexa plugin ZIP", "*.zip"), ("All files", "*.*")],
        )
        if not selected:
            return
        try:
            plugin_id = self.plugin_manager.import_plugin_zip(Path(selected))
            messagebox.showinfo("Plugin imported", f"Plugin '{plugin_id}' was imported and is disabled by default. Open Plugin Manager to enable it.")
        except Exception as exc:
            messagebox.showerror("Plugin import failed", str(exc))

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
            if not model_is_installed(QWEN3_MODEL_KEY, self.app_root, self.model_path):
                self.events.put(("model_download_status", "First setup: downloading Qwen3 4B Q4_K_M · about 2.5 GB · internet required"))
            else:
                self.events.put(("model_download_status", "Verifying installed Qwen3 model integrity…"))
            last_progress = 0.0

            def report_progress(_label: str, done: int, total: int) -> None:
                nonlocal last_progress
                now = time.monotonic()
                elapsed = max(now - last_progress, 0.001)
                previous_bytes = getattr(report_progress, "_last_bytes", 0)
                speed = max(0.0, (done - previous_bytes) / elapsed)
                if now - last_progress >= 0.4 or (total and done >= total):
                    report_progress._last_bytes = done
                    last_progress = now
                    self.events.put(("model_download_progress", (done, total, speed)))

            # download_model verifies the full SHA-256 even when a GGUF is already present.
            # A damaged local file is discarded and safely downloaded again.
            self.active_model_path, _ = download_model(
                QWEN3_MODEL_KEY, self.app_root, self.model_path, report_progress
            )
            if not self.active_model_path.is_file():
                raise FileNotFoundError(f"Qwen3 4B model file is missing: {self.active_model_path}")
            self.log_handle.write("Qwen3 GGUF header and SHA-256 verification passed.\n")
            if self._port_is_occupied(LOCAL_MODEL_PORT):
                raise RuntimeError(
                    f"Local AI port {LOCAL_MODEL_PORT} is already in use. "
                    "Close another NexaAI window or local llama-server, then restart."
                )
            runtime_probe = subprocess.run(
                [str(exe), "--version"], cwd=str(self.runtime_dir),
                capture_output=True, text=True, timeout=20,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            if runtime_probe.returncode != 0:
                raise RuntimeError(
                    "The bundled llama.cpp executable or one of its DLL dependencies failed to load. "
                    f"Exit code: {runtime_probe.returncode}. "
                    f"{(runtime_probe.stderr or runtime_probe.stdout).strip()[:1000]}"
                )
            self.log_handle.write(f"llama.cpp runtime: {(runtime_probe.stdout or runtime_probe.stderr).strip()}\n")
            available_ram = self._available_memory_gb()
            if available_ram is not None:
                self.log_handle.write(f"Available physical RAM before model load: {available_ram:.2f} GB\n")
                if available_ram < 3.5:
                    self.log_handle.write("WARNING: available RAM is low; Qwen3 4B may still exceed memory limits.\n")

            profiles = engine_profiles(os.cpu_count())
            if available_ram is not None and available_ram < 4.0:
                profiles = profiles[1:]
            if available_ram is not None and available_ram < 2.6:
                profiles = profiles[1:]
            server_ready = False
            failures: list[str] = []
            for attempt, profile in enumerate(profiles, start=1):
                cmd = build_engine_command(exe, self.active_model_path, LOCAL_MODEL_PORT, self.current_model_id, profile)
                self.log_handle.write(
                    f"\n=== llama-server attempt {attempt}: {profile['name']} "
                    f"(ctx={profile['context']}, batch={profile['batch']}, ubatch={profile['ubatch']}, threads={profile['threads']}) ===\n"
                )
                self.log_handle.write("Command: " + subprocess.list2cmdline(cmd) + "\n")
                self.log_handle.flush()
                self.llama_process = subprocess.Popen(
                    cmd, cwd=str(self.runtime_dir), stdin=subprocess.DEVNULL,
                    stdout=self.log_handle, stderr=subprocess.STDOUT,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                )
                if self._wait_for_model_server(420):
                    server_ready = True
                    self.log_handle.write(f"llama-server ready using {profile['name']} profile.\n")
                    break
                return_code = self.llama_process.poll() if self.llama_process else None
                failures.append(f"{profile['name']} profile: process exit code {return_code}")
                self.log_handle.write(f"{failures[-1]}\n")
                self.log_handle.flush()
                self._stop_llama_process()
                time.sleep(2)

            if not server_ready:
                log_tail = self._read_runtime_log_tail(35)
                ram_text = f"Available RAM before startup: {available_ram:.2f} GB" if available_ram is not None else "Available RAM: unavailable"
                raise RuntimeError(
                    "The local Qwen3 engine could not start after CPU/memory fallback profiles.\n"
                    + ram_text + "\n"
                    + "\n".join(failures)
                    + "\n\nRecent llama.cpp diagnostics:\n"
                    + (log_tail or "No llama.cpp output was recorded.")
                    + f"\n\nFull log: {self.log_path}"
                )

            if self.api_server is None:
                from nexa_ai.config import settings
                import uvicorn
                from nexa_ai.api import app

                config = build_uvicorn_config(app, host=settings.host, port=settings.port)
                self.api_server = uvicorn.Server(config)
                self.api_thread = threading.Thread(target=self.api_server.run, daemon=True, name="NexaLocalAPI")
                self.api_thread.start()
                if not self._wait_for_url(f"http://127.0.0.1:{API_PORT}/health", 30):
                    raise RuntimeError("Nexa AI local API could not start. Port 8000 may already be in use.")
            self.events.put(("ready", None))
        except Exception as exc:
            self.events.put(("boot_error", str(exc)))

    @staticmethod
    def _port_is_occupied(port: int) -> bool:
        import socket
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
            probe.settimeout(0.4)
            return probe.connect_ex(("127.0.0.1", port)) == 0

    @staticmethod
    def _available_memory_gb() -> float | None:
        class MEMORYSTATUSEX(ctypes.Structure):
            _fields_ = [
                ("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
            ]
        try:
            status = MEMORYSTATUSEX()
            status.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
            if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
                return status.ullAvailPhys / (1024 ** 3)
        except (AttributeError, OSError):
            pass
        return None

    def _read_runtime_log_tail(self, line_count: int = 30) -> str:
        try:
            self.log_handle.flush()
            lines = self.log_path.read_text(encoding="utf-8", errors="replace").splitlines()
            return "\n".join(lines[-line_count:])
        except OSError:
            return ""

    def _stop_llama_process(self) -> None:
        process = self.llama_process
        if not process or process.poll() is not None:
            return
        process.terminate()
        try:
            process.wait(timeout=8)
        except subprocess.TimeoutExpired:
            process.kill()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                pass

    def _wait_for_model_server(self, timeout_seconds: int) -> bool:
        deadline = time.monotonic() + timeout_seconds
        health_url = f"http://127.0.0.1:{LOCAL_MODEL_PORT}/health"
        while time.monotonic() < deadline:
            if self.llama_process and self.llama_process.poll() is not None:
                return False
            try:
                with httpx.Client(timeout=2) as client:
                    response = client.get(health_url)
                    if response.is_success:
                        return True
            except Exception:
                pass
            time.sleep(0.5)
        return False

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
                    self.root.after(80, self.show_chat_workspace)
                    self._append_message(
                        "Nexa AI",
                        "Qwen3 4B is ready and running locally. This is the only assistant model used for chat, coding, reasoning and n8n workflow design. You can now disconnect from the internet.",
                        "assistant",
                    )
                elif kind == "model_download_status":
                    self.status_var.set(str(payload))
                    self.status_label.configure(fg=self.ACCENT)
                elif kind == "model_download_progress":
                    done, total, speed = payload
                    rate = f"{speed / (1024 ** 2):.1f} MB/s" if speed > 0 else "connecting…"
                    if total:
                        percent = done * 100 / total
                        remaining = max(0, total - done)
                        eta = f" · ETA {remaining / speed:.0f}s" if speed > 0 else ""
                        self.status_var.set(
                            f"Downloading Qwen3 4B · {percent:.1f}% · {done / (1024 ** 3):.2f}/{total / (1024 ** 3):.2f} GB · {rate}{eta}"
                        )
                    else:
                        self.status_var.set(f"Downloading Qwen3 4B · {done / (1024 ** 2):.0f} MB · {rate}")
                    self.status_label.configure(fg=self.ACCENT)
                elif kind == "boot_error":
                    self.status_var.set("Offline engine failed to start")
                    self.status_label.configure(fg="#ff8d8d")
                    messagebox.showerror("Nexa AI could not start", str(payload))
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
                    if self.voice_turn:
                        self.voice_turn = False
                        if self.speak_replies_var.get() and self.messages and self.messages[-1].get("role") == "assistant":
                            self._speak_text(str(self.messages[-1].get("content", "")))
                elif kind == "request_error":
                    self.busy = False
                    self.send_button.configure(state="normal" if self.ready else "disabled")
                    self.status_var.set("Request failed")
                    self.status_label.configure(fg="#ff8d8d")
                    self.voice_turn = False
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
                elif kind == "voice_status":
                    self.status_var.set(str(payload))
                elif kind == "voice_transcribed":
                    self.voice_button.configure(state="normal", text="🎙 Voice chat")
                    self.status_var.set("Voice recognized · sending to local AI…")
                    self.input.delete("1.0", "end")
                    self.input_placeholder_active = False
                    self.input.configure(fg=self.TEXT)
                    self.input.insert("1.0", str(payload))
                    self.voice_turn = True
                    self.send_message()
                elif kind == "voice_error":
                    self.voice_button.configure(state="normal", text="🎙 Voice chat")
                    self.send_button.configure(state="normal" if self.ready and not self.busy else "disabled")
                    self.recording = False
                    self.voice_turn = False
                    self.status_var.set("Voice chat unavailable")
                    messagebox.showerror("Voice chat", str(payload))
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
                ("Supported files", "*.pdf *.txt *.md *.csv *.json *.xml *.py *.js *.html *.css *.log"),
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
        text = "" if self.input_placeholder_active else self.input.get("1.0", "end-1c").strip()
        if not text and not self.pending_files:
            return
        self.input.delete("1.0", "end")
        self.input_placeholder_active = False
        self.input.configure(fg=self.TEXT)
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
        if self.conversation_title == "New conversation":
            self.conversation_title = (text or "Attached files").replace("\n", " ").strip()[:90] or "Conversation"
        self._save_chat()
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
                "model": self.current_model_id, "messages": self.messages, "stream": True,
                "temperature": 0.6, "max_tokens": 3072,
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
            if not any(message.get("role") == "user" for message in self.messages):
                return
            self.history_store.save(
                self.conversation_id,
                self.conversation_title,
                self.messages,
                self.current_model_id,
            )
        except (OSError, ValueError, TypeError):
            pass

    @staticmethod
    def _history_message_text(content: Any) -> str:
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts = []
            for item in content:
                if not isinstance(item, dict):
                    continue
                if item.get("type") in {"text", "input_text"}:
                    parts.append(str(item.get("text", "")))
                elif item.get("type") in {"input_file", "file"}:
                    parts.append(f"[Attachment: {item.get('file_id', 'local file')}]")
            return "\n".join(parts)
        return str(content or "")

    def _render_conversation(self, messages: list[dict[str, Any]]) -> None:
        self.chat.configure(state="normal")
        self.chat.delete("1.0", "end")
        self.chat.configure(state="disabled")
        for message in messages:
            role = message.get("role")
            if role not in {"user", "assistant"}:
                continue
            label = "You" if role == "user" else "Nexa AI"
            self._append_message(label, self._history_message_text(message.get("content", "")), role)
        self.chat.see("end")

    def open_history(self) -> None:
        window = tk.Toplevel(self.root)
        window.title("Nexa AI · Chat History")
        window.geometry("700x560")
        window.configure(bg=self.BG)
        tk.Label(window, text="Conversation history", bg=self.BG, fg=self.TEXT, font=("Segoe UI Semibold", 17)).pack(anchor="w", padx=20, pady=(18, 4))
        tk.Label(window, text="Chats are saved locally on this computer.", bg=self.BG, fg=self.MUTED, font=("Segoe UI", 9)).pack(anchor="w", padx=20, pady=(0, 12))

        body = tk.Frame(window, bg=self.BG)
        body.pack(fill="both", expand=True, padx=16, pady=4)
        listing = tk.Listbox(
            body, bg=self.PANEL, fg=self.TEXT, selectbackground=self.THEMES[self.theme_name]["SELECT"],
            selectforeground=self.TEXT, relief="flat", borderwidth=0,
            font=("Segoe UI", 10), activestyle="none",
        )
        listing.pack(side="left", fill="both", expand=True)
        scroll = ttk.Scrollbar(body, orient="vertical", command=listing.yview)
        scroll.pack(side="right", fill="y")
        listing.configure(yscrollcommand=scroll.set)

        items = self.history_store.list_conversations()
        for item in items:
            stamp = item.get("updated_at", "").replace("T", " ")[:16]
            listing.insert("end", f"{item['title']}   ·   {stamp}   ·   {item['message_count']} messages")
        if not items:
            listing.insert("end", "No saved conversations yet.")
            listing.configure(state="disabled")

        def selected_item():
            selection = listing.curselection()
            if not selection or not items:
                return None
            return items[selection[0]]

        buttons = tk.Frame(window, bg=self.BG)
        buttons.pack(fill="x", padx=18, pady=(10, 18))

        def load_selected():
            item = selected_item()
            if not item:
                return
            try:
                data = self.history_store.load(item["id"])
                self.messages = data["messages"]
                self.conversation_id = data["id"]
                self.conversation_title = data.get("title", "Conversation")
                self._render_conversation(self.messages)
                self.pending_files.clear()
                self._refresh_attachments()
                window.destroy()
            except Exception as exc:
                messagebox.showerror("History could not be opened", str(exc), parent=window)

        def delete_selected():
            item = selected_item()
            if not item:
                return
            if not messagebox.askyesno("Delete conversation", f"Delete '{item['title']}' from local history?", parent=window):
                return
            try:
                self.history_store.delete(item["id"])
                listing.delete(listing.curselection()[0])
                items.remove(item)
                if not items:
                    listing.configure(state="normal")
                    listing.insert("end", "No saved conversations yet.")
                    listing.configure(state="disabled")
            except Exception as exc:
                messagebox.showerror("Delete failed", str(exc), parent=window)

        ttk.Button(buttons, text="Open conversation", style="Accent.TButton", command=load_selected).pack(side="left")
        ttk.Button(buttons, text="Delete", style="Nexa.TButton", command=delete_selected).pack(side="left", padx=8)
        ttk.Button(buttons, text="Close", style="Nexa.TButton", command=window.destroy).pack(side="right")
        listing.bind("<Double-Button-1>", lambda _event: load_selected())

    def new_conversation(self) -> None:
        if self.busy or self.uploading or self.recording:
            return
        self._save_chat()
        self.conversation_id = uuid4().hex
        self.conversation_title = "New conversation"
        self.messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        self.chat.configure(state="normal")
        self.chat.delete("1.0", "end")
        self.chat.configure(state="disabled")
        self.pending_files.clear()
        self._refresh_attachments()
        self._append_message("Nexa AI", "New conversation started. What would you like to work on?", "assistant")

    def toggle_voice_chat(self) -> None:
        if not self.ready or self.busy or self.uploading:
            return
        if self.recording:
            self._stop_voice_recording()
            return

        try:
            import sounddevice as sd
            import numpy as np  # noqa: F401
        except Exception as exc:
            messagebox.showerror("Voice chat unavailable", f"Microphone support could not load: {exc}")
            return

        self.recording_chunks = []
        self.recording = True
        self.voice_button.configure(text="■ Stop & send", state="normal")
        self.send_button.configure(state="disabled")
        self.status_var.set("● Listening · speak now")
        self.status_label.configure(fg="#d6b66d")

        def audio_callback(indata, frames, time_info, status):
            if status:
                self.log_handle.write(f"Microphone status: {status}\n")
            with self.recording_lock:
                if self.recording:
                    self.recording_chunks.append(indata.copy())

        try:
            self.recording_stream = sd.InputStream(
                samplerate=16000, channels=1, dtype="int16",
                blocksize=0, callback=audio_callback,
            )
            self.recording_stream.start()
        except Exception as exc:
            self.recording = False
            self.recording_stream = None
            self.voice_button.configure(text="🎙 Voice chat")
            self.send_button.configure(state="normal")
            messagebox.showerror("Microphone error", str(exc))

    def _stop_voice_recording(self) -> None:
        stream = self.recording_stream
        self.recording = False
        self.recording_stream = None
        try:
            if stream:
                stream.stop()
                stream.close()
            import numpy as np
            with self.recording_lock:
                chunks = list(self.recording_chunks)
                self.recording_chunks.clear()
            if not chunks:
                raise RuntimeError("No microphone audio was captured.")
            audio = np.concatenate(chunks, axis=0).astype("int16", copy=False)
            if len(audio) < 8000:
                raise RuntimeError("The recording was too short. Please speak for at least half a second.")
            voice_dir = self.app_root / "Voice" / "recordings"
            voice_dir.mkdir(parents=True, exist_ok=True)
            audio_path = voice_dir / f"voice-{uuid4().hex}.wav"
            with wave.open(str(audio_path), "wb") as wav:
                wav.setnchannels(1)
                wav.setsampwidth(2)
                wav.setframerate(16000)
                wav.writeframes(audio.tobytes())
        except Exception as exc:
            self.voice_button.configure(text="🎙 Voice chat")
            self.send_button.configure(state="normal" if self.ready else "disabled")
            self.status_var.set("Voice recording failed")
            messagebox.showerror("Voice chat", str(exc))
            return

        self.voice_button.configure(state="disabled", text="Transcribing…")
        self.status_var.set("Preparing offline speech recognition…")
        threading.Thread(target=self._transcribe_voice, args=(audio_path,), daemon=True, name="NexaWhisper").start()

    def _transcribe_voice(self, audio_path: Path) -> None:
        try:
            from faster_whisper import WhisperModel
            voice_dir = self.app_root / "Voice"
            model_dir = voice_dir / "whisper-base"
            model_dir.mkdir(parents=True, exist_ok=True)

            if self.whisper_model is None:
                self.events.put(("voice_status", "Loading Whisper base model · first use downloads about 150 MB"))
                previous_hf = os.environ.pop("HF_HUB_OFFLINE", None)
                previous_transformers = os.environ.pop("TRANSFORMERS_OFFLINE", None)
                try:
                    # Model download is performed only on first use; subsequent recognition is local.
                    self.whisper_model = WhisperModel(
                        "base", device="cpu", compute_type="int8", download_root=str(model_dir)
                    )
                finally:
                    if previous_hf is not None:
                        os.environ["HF_HUB_OFFLINE"] = previous_hf
                    if previous_transformers is not None:
                        os.environ["TRANSFORMERS_OFFLINE"] = previous_transformers

            self.events.put(("voice_status", "Transcribing locally…"))
            segments, info = self.whisper_model.transcribe(
                str(audio_path), beam_size=3, vad_filter=True, condition_on_previous_text=False
            )
            transcript = " ".join(segment.text.strip() for segment in segments).strip()
            if not transcript:
                raise RuntimeError("No speech was recognized. Try speaking more clearly or closer to the microphone.")
            self.events.put(("voice_transcribed", transcript))
        except Exception as exc:
            self.events.put(("voice_error", str(exc)))
        finally:
            try:
                audio_path.unlink(missing_ok=True)
            except OSError:
                pass

    def _speak_text(self, text: str) -> None:
        reply = str(text).strip()
        if not reply:
            return

        def worker() -> None:
            try:
                import pyttsx3
                engine = pyttsx3.init()
                engine.setProperty("rate", 175)
                # Prefer an installed Bengali voice when available; otherwise use the Windows default voice.
                if any("\u0980" <= char <= "\u09ff" for char in reply):
                    for voice in engine.getProperty("voices"):
                        voice_info = " ".join([str(getattr(voice, "id", "")), str(getattr(voice, "name", "")), str(getattr(voice, "languages", ""))]).lower()
                        if "bengali" in voice_info or "bangla" in voice_info or "bn" in voice_info:
                            engine.setProperty("voice", voice.id)
                            break
                engine.say(reply[:5000])
                engine.runAndWait()
                engine.stop()
            except Exception as exc:
                self.root.after(0, lambda e=str(exc): self.status_var.set(f"Speech output unavailable: {e[:100]}"))

        threading.Thread(target=worker, daemon=True, name="NexaSpeechOutput").start()

    def open_n8n_studio(self) -> None:
        window = tk.Toplevel(self.root)
        window.title("Nexa AI · n8n Workflow Studio")
        window.geometry("980x760")
        window.minsize(760, 600)
        window.configure(bg=self.BG)

        tk.Label(window, text="n8n Workflow Studio", bg=self.BG, fg=self.TEXT, font=("Segoe UI Semibold", 19)).pack(anchor="w", padx=20, pady=(18, 3))
        tk.Label(
            window,
            text="Describe an automation in Bangla or English. The active local model creates an n8n workflow JSON you can export and import into your own n8n instance.",
            bg=self.BG, fg=self.MUTED, font=("Segoe UI", 9), wraplength=900, justify="left",
        ).pack(anchor="w", padx=20, pady=(0, 12))

        tk.Label(window, text="What should the workflow do?", bg=self.BG, fg=self.TEXT, font=("Segoe UI Semibold", 10)).pack(anchor="w", padx=20)
        prompt_box = tk.Text(window, height=6, wrap="word", bg=self.PANEL, fg=self.TEXT, insertbackground=self.TEXT, relief="flat", font=("Segoe UI", 10), padx=12, pady=10)
        prompt_box.pack(fill="x", padx=20, pady=(5, 10))

        actions = tk.Frame(window, bg=self.BG)
        actions.pack(fill="x", padx=20, pady=(0, 8))
        status = tk.Label(actions, text=f"Local model: {self.current_model_name}", bg=self.BG, fg=self.MUTED, font=("Segoe UI", 8))
        status.pack(side="left")
        output = ScrolledText(window, wrap="word", bg=self.PANEL, fg=self.TEXT, insertbackground=self.TEXT, relief="flat", font=("Consolas", 9), padx=12, pady=10)
        output.pack(fill="both", expand=True, padx=20, pady=(0, 10))
        output.insert("1.0", "Your generated n8n workflow JSON will appear here.")
        output.configure(state="disabled")
        result_state: dict[str, Any] = {"workflow": None}

        def set_output(value: str) -> None:
            output.configure(state="normal")
            output.delete("1.0", "end")
            output.insert("1.0", value)
            output.configure(state="disabled")

        def generate() -> None:
            if not self.ready or self.busy:
                messagebox.showwarning("Local model busy", "Wait until Nexa AI is ready before generating a workflow.", parent=window)
                return
            requirement = prompt_box.get("1.0", "end-1c").strip()
            try:
                messages = build_n8n_messages(requirement)
            except Exception as exc:
                messagebox.showerror("Workflow description", str(exc), parent=window)
                return
            generate_button.configure(state="disabled", text="Generating…")
            export_button.configure(state="disabled")
            copy_button.configure(state="disabled")
            status.configure(text=f"Generating with {self.current_model_name} · offline…", fg=self.ACCENT)
            result_state["workflow"] = None

            def worker() -> None:
                try:
                    payload = {
                        "model": self.current_model_id,
                        "messages": messages,
                        "stream": False,
                        "temperature": 0.15,
                        "max_tokens": 4096,
                    }
                    with httpx.Client(timeout=httpx.Timeout(900, connect=10)) as client:
                        response = client.post(f"http://127.0.0.1:{API_PORT}/v1/chat/completions", json=payload)
                    response.raise_for_status()
                    data = response.json()
                    raw = data["choices"][0]["message"]["content"]
                    workflow = extract_n8n_json(raw)
                    rendered = workflow_json_text(workflow)
                    self.root.after(0, lambda: finish_success(workflow, rendered))
                except Exception as exc:
                    error_text = str(exc)
                    self.root.after(0, lambda e=error_text: finish_error(e))

            def finish_success(workflow: dict[str, Any], rendered: str) -> None:
                if not window.winfo_exists():
                    return
                result_state["workflow"] = workflow
                set_output(rendered)
                generate_button.configure(state="normal", text="Generate workflow")
                export_button.configure(state="normal")
                copy_button.configure(state="normal")
                status.configure(text="✓ JSON structure validated · not executed", fg="#8fbd92")

            def finish_error(error_text: str) -> None:
                if not window.winfo_exists():
                    return
                generate_button.configure(state="normal", text="Try again")
                status.configure(text="Workflow generation failed", fg="#dd8d85")
                messagebox.showerror("Could not create workflow", error_text, parent=window)

            threading.Thread(target=worker, daemon=True, name="NexaN8nStudio").start()

        def export_workflow() -> None:
            workflow = result_state.get("workflow")
            if not workflow:
                return
            path = filedialog.asksaveasfilename(
                parent=window, title="Export n8n workflow", defaultextension=".json",
                initialfile="nexa-n8n-workflow.json", filetypes=[("n8n workflow JSON", "*.json")],
            )
            if not path:
                return
            try:
                Path(path).write_text(workflow_json_text(workflow), encoding="utf-8")
                status.configure(text=f"Saved: {Path(path).name}", fg="#8fbd92")
            except OSError as exc:
                messagebox.showerror("Export failed", str(exc), parent=window)

        def copy_workflow() -> None:
            workflow = result_state.get("workflow")
            if not workflow:
                return
            window.clipboard_clear()
            window.clipboard_append(workflow_json_text(workflow))
            status.configure(text="Workflow JSON copied to clipboard", fg="#8fbd92")

        generate_button = ttk.Button(actions, text="Generate workflow", style="Accent.TButton", command=generate)
        generate_button.pack(side="right")
        export_button = ttk.Button(actions, text="Export JSON", style="Nexa.TButton", command=export_workflow, state="disabled")
        export_button.pack(side="right", padx=(0, 8))
        copy_button = ttk.Button(actions, text="Copy JSON", style="Nexa.TButton", command=copy_workflow, state="disabled")
        copy_button.pack(side="right", padx=(0, 8))

    def on_close(self) -> None:
        try:
            self._save_chat()
            if self.recording_stream:
                self.recording = False
                self.recording_stream.stop()
                self.recording_stream.close()
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
