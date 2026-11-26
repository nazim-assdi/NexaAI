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
import webbrowser
from pathlib import Path
from uuid import uuid4
from typing import Any

import httpx
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from tkinter.scrolledtext import ScrolledText

from nexa_ai.ollama_runtime import OllamaRuntime, OllamaNotInstalled, OLLAMA_MODEL, OLLAMA_MODEL_NAME, OLLAMA_MODEL_SIZE
from nexa_ai.gemini_backend import stream_text as stream_gemini, test_api_key as test_gemini_api_key
from nexa_ai.secure_store import DPAPISecretStore
from nexa_ai.plugin_manager import PluginManager
from nexa_ai.history_store import HistoryStore
from nexa_ai.n8n_studio import build_n8n_messages, extract_n8n_json, workflow_json_text
from nexa_ai.server_config import build_uvicorn_config
from nexa_ai.ui_layout import calculate_window_geometry
from nexa_ai.chat_layout import CHAT_SUGGESTIONS, recent_chat_label, build_chat_context, response_token_limit, enqueue_followup, take_followup
from nexa_ai.voice_utils import resample_mono_int16

APP_NAME = "Nexa AI"
APP_VERSION = "2.1.1"
MODEL_ID = OLLAMA_MODEL
DEFAULT_AI_CHOICE = "Qwen2.5-Coder 3B · Offline"
AI_CHOICES = {
    DEFAULT_AI_CHOICE: ("local", OLLAMA_MODEL, OLLAMA_MODEL_NAME),
    "Gemini 3.8 Flash · Online": ("gemini", "gemini-3.8-flash", "Gemini 3.8 Flash"),
    "Gemini 3.5 Flash-Lite · Online": ("gemini", "gemini-3.5-flash-lite", "Gemini 3.5 Flash-Lite"),
}
LOCAL_MODEL_PORT = 11439
API_PORT = 8000
SYSTEM_PROMPT = (
    "You are Nexa AI, a practical offline software developer and automation engineer. "
    "Reply naturally in the user's language; when the user writes Bangla, use natural Bangla. "
    "Help with Python, JavaScript, HTML/CSS, Windows troubleshooting, GitHub projects and n8n workflow design. "
    "For coding tasks, provide complete runnable code, explain filenames and setup, and point out assumptions. "
    "For n8n tasks, design valid node connections and realistic parameters, use credential placeholders, and never invent secrets. "
    "Do not claim that code or workflows were executed or tested unless the app actually reports that. "
    "You do not have live browsing access unless a connected tool explicitly provides it; be clear when up-to-date external details cannot be checked."
)


def resource_path(relative: str) -> Path:
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    return base / relative


def app_data_dir() -> Path:
    base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    target = base / "NexaAI"
    target.mkdir(parents=True, exist_ok=True)
    return target


def configure_environment() -> Path:
    data_dir = app_data_dir() / "Data"
    data_dir.mkdir(parents=True, exist_ok=True)
    os.environ["NEXA_LOCAL_BASE_URL"] = "http://127.0.0.1:11439"
    os.environ["NEXA_LOCAL_API_KEY"] = ""
    os.environ.pop("NEXA_MM_PROJ_PATH", None)
    os.environ["NEXA_MODEL"] = OLLAMA_MODEL
    os.environ["NEXA_HOST"] = "127.0.0.1"
    os.environ["NEXA_PORT"] = str(API_PORT)
    os.environ["NEXA_BASE_URL"] = f"http://127.0.0.1:{API_PORT}/v1"
    os.environ["NEXA_DATA_DIR"] = str(data_dir)
    os.environ["NEXA_MAX_OUTPUT_TOKENS"] = "2048"
    os.environ["NEXA_REQUEST_TIMEOUT"] = "600"
    os.environ["TOKENIZERS_PARALLELISM"] = "false"
    return data_dir

class NexaDesktop:
    BG = "#0b111b"
    PANEL = "#111b2a"
    PANEL_2 = "#1b2b40"
    TEXT = "#eaf1ff"
    MUTED = "#9baac0"
    ACCENT = "#83a6ff"
    BORDER = "#2b3a50"

    THEMES = {
        "NTech Chat Dark": {
            "BG": "#0b111b", "PANEL": "#111b2a", "PANEL_2": "#1b2b40",
            "TEXT": "#eaf1ff", "MUTED": "#9baac0", "ACCENT": "#83a6ff",
            "BORDER": "#2b3a50", "USER": "#c7d9ff", "AI": "#eaf1ff",
            "SELECT": "#263d5b", "ACTIVE": "#263c59", "BUTTON_TEXT": "#0d1420",
        },
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

        self.data_dir = configure_environment()
        self.app_root = app_data_dir()
        self.secret_store = DPAPISecretStore(self.app_root / "secrets")
        self.plugin_manager = PluginManager(self.app_root)
        self.history_store = HistoryStore(self.data_dir)
        self.conversation_id = uuid4().hex
        self.conversation_title = "New conversation"
        self.preferences_path = self.app_root / "preferences.json"
        self.theme_name = self._load_theme_preference()
        self.response_profile = self._load_response_preference()
        self.ai_choice = self._load_ai_preference()
        self.pending_ai_choice: str | None = None
        self.active_request_provider = "local"
        self._voice_capture_rate = 16000
        self.recording_warnings = ""
        self.pending_send_queue: list[str] = []
        self._set_palette(self.theme_name)
        self.root.configure(bg=self.BG)
        self.current_model_key = self.ai_choice
        self.current_model_id = MODEL_ID
        self.current_model_name = OLLAMA_MODEL_NAME
        self._apply_ai_choice(self.ai_choice, save=False)
        self.ollama_runtime = OllamaRuntime()
        self.log_path = app_data_dir() / "nexa-runtime.log"
        self.log_handle = self.log_path.open("a", encoding="utf-8", buffering=1)
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

        self.status_var.set("Preparing Qwen2.5-Coder 3B · checking Ollama…")
        threading.Thread(target=self._boot_engine, daemon=True, name="NexaBoot").start()
        self.root.after(100, self._poll_events)

    def _build_ui(self) -> None:
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("Nexa.TButton", font=("Segoe UI", 9), padding=(10, 7), background=self.PANEL_2, foreground=self.TEXT, borderwidth=0)
        style.map("Nexa.TButton", background=[("active", self.THEMES[self.theme_name]["ACTIVE"]), ("disabled", self.PANEL)], foreground=[("disabled", self.MUTED)])
        style.configure("Accent.TButton", font=("Segoe UI Semibold", 9), padding=(12, 7), background=self.ACCENT, foreground=self.THEMES[self.theme_name]["BUTTON_TEXT"], borderwidth=0)
        style.map("Accent.TButton", background=[("active", self.THEMES[self.theme_name]["ACTIVE"]), ("disabled", self.PANEL_2)])

        self.current_assistant_widget = None
        self.current_assistant_row = None
        shell = tk.Frame(self.root, bg=self.BG)
        shell.pack(fill="both", expand=True)

        sidebar = tk.Frame(shell, bg=self.PANEL, width=270)
        sidebar.pack(side="left", fill="y")
        sidebar.pack_propagate(False)
        brand = tk.Frame(sidebar, bg=self.PANEL)
        brand.pack(fill="x", padx=17, pady=(18, 18))
        tk.Label(brand, text="N", bg=self.ACCENT, fg="#101820", font=("Segoe UI Semibold", 17), width=2, height=1).pack(side="left", padx=(0, 10))
        brand_copy = tk.Frame(brand, bg=self.PANEL)
        brand_copy.pack(side="left", fill="x", expand=True)
        tk.Label(brand_copy, text="Nexa AI", bg=self.PANEL, fg=self.TEXT, font=("Segoe UI Semibold", 14)).pack(anchor="w")
        tk.Label(brand_copy, text="PRIVATE · OFFLINE AI", bg=self.PANEL, fg=self.MUTED, font=("Segoe UI", 8)).pack(anchor="w", pady=(1, 0))

        self._sidebar_button(sidebar, "＋   New chat", self.new_conversation, accent=True).pack(fill="x", padx=11, pady=(0, 7))
        self._sidebar_button(sidebar, "⌕   Search conversations", self.open_history).pack(fill="x", padx=11, pady=(0, 7))
        self._sidebar_button(sidebar, "⚙   n8n Workflow Studio", self.open_n8n_studio).pack(fill="x", padx=11, pady=(0, 4))
        self._sidebar_button(sidebar, "▦   Plugin Manager", self.open_plugin_manager).pack(fill="x", padx=11, pady=(0, 4))

        tk.Label(sidebar, text="RECENT", bg=self.PANEL, fg=self.MUTED, font=("Segoe UI Semibold", 8)).pack(anchor="w", padx=18, pady=(2, 8))
        self.recent_chats_frame = tk.Frame(sidebar, bg=self.PANEL)
        self.recent_chats_frame.pack(fill="both", expand=True, padx=8)
        self._refresh_recent_conversations()

        bottom = tk.Frame(sidebar, bg=self.PANEL)
        bottom.pack(fill="x", side="bottom", padx=12, pady=13)
        tk.Frame(bottom, bg=self.BORDER, height=1).pack(fill="x", pady=(0, 12))
        model_card = tk.Frame(bottom, bg=self.PANEL_2, padx=10, pady=9)
        model_card.pack(fill="x")
        self.model_title_label = tk.Label(model_card, text=self.current_model_name, bg=self.PANEL_2, fg="#80cfa0", font=("Segoe UI Semibold", 9))
        self.model_title_label.pack(anchor="w")
        tk.Label(model_card, text="Choose an offline or online AI", bg=self.PANEL_2, fg=self.MUTED, font=("Segoe UI", 8)).pack(anchor="w", pady=(3, 0))
        self.ai_choice_var = tk.StringVar(value=self.ai_choice)
        self.ai_selector = ttk.Combobox(model_card, textvariable=self.ai_choice_var, values=list(AI_CHOICES.keys()), state="readonly", width=27, font=("Segoe UI Semibold", 8), style="Nexa.TCombobox", height=6)
        self.ai_selector.pack(fill="x", pady=(7, 6))
        self.ai_selector.bind("<<ComboboxSelected>>", self._change_ai_choice)
        self.gemini_connect_button = ttk.Button(model_card, text="Connect Gemini", style="Nexa.TButton", command=self.open_gemini_settings)
        self.gemini_connect_button.pack(fill="x")
        tk.Label(bottom, text="DEVELOPED BY NTECH", bg=self.PANEL, fg=self.MUTED, font=("Segoe UI", 8)).pack(anchor="w", pady=(9, 0))

        main = tk.Frame(shell, bg=self.BG)
        main.pack(side="left", fill="both", expand=True)
        top = tk.Frame(main, bg=self.BG, height=66)
        top.pack(fill="x")
        top.pack_propagate(False)
        tk.Label(top, text="Nexa AI", bg=self.BG, fg=self.TEXT, font=("Segoe UI Semibold", 13)).pack(side="left", padx=(24, 10))
        self.model_badge = tk.Label(top, text="QWEN2.5-CODER 3B · OFFLINE", bg=self.PANEL_2, fg=self.ACCENT, font=("Segoe UI Semibold", 8), padx=10, pady=6)
        self.model_badge.pack(side="left", padx=(0, 6))
        self.status_var = tk.StringVar(value="Starting local engine…")
        self.status_label = tk.Label(top, textvariable=self.status_var, bg=self.BG, fg=self.MUTED, font=("Segoe UI", 8))
        self.status_label.pack(side="right", padx=(8, 17))
        self.theme_var = tk.StringVar(value=self.theme_name)
        self.theme_selector = ttk.Combobox(top, textvariable=self.theme_var, values=list(self.THEMES.keys()), state="readonly", width=18, font=("Segoe UI Semibold", 9), style="Nexa.TCombobox", height=9)
        self.theme_selector.pack(side="right", padx=(5, 15), pady=8)
        self.theme_selector.bind("<<ComboboxSelected>>", self._change_theme)
        self.response_profile_var = tk.StringVar(value=self.response_profile)
        self.response_selector = ttk.Combobox(
            top, textvariable=self.response_profile_var,
            values=["Quick", "Balanced", "Detailed"],
            state="readonly", width=12, font=("Segoe UI Semibold", 9), style="Nexa.TCombobox", height=8,
        )
        self.response_selector.pack(side="right", padx=5, pady=8)
        self.response_selector.bind("<<ComboboxSelected>>", self._change_response_profile)
        self.ttk_style = style
        self._configure_premium_dropdowns()

        chat_stage = tk.Frame(main, bg=self.BG)
        chat_stage.pack(fill="both", expand=True)
        self.chat_canvas = tk.Canvas(chat_stage, bg=self.BG, highlightthickness=0, borderwidth=0, yscrollincrement=28)
        chat_scroll = ttk.Scrollbar(chat_stage, orient="vertical", command=self.chat_canvas.yview, style="Nexa.Vertical.TScrollbar")
        self.chat_canvas.configure(yscrollcommand=chat_scroll.set)
        chat_scroll.pack(side="right", fill="y")
        self.chat_canvas.pack(side="left", fill="both", expand=True)
        self.chat_feed = tk.Frame(self.chat_canvas, bg=self.BG)
        self.chat_window_id = self.chat_canvas.create_window((0, 0), window=self.chat_feed, anchor="nw")
        self.chat_feed.bind("<Configure>", self._on_chat_feed_configure)
        self.chat_canvas.bind("<Configure>", self._on_chat_canvas_configure)
        self.chat_canvas.bind("<MouseWheel>", self._on_chat_mousewheel)
        self.chat_feed.bind("<MouseWheel>", self._on_chat_mousewheel)
        self._show_empty_state()

        footer = tk.Frame(main, bg=self.BG)
        footer.pack(fill="x", padx=20, pady=(5, 7))
        self.attachments_label = tk.Label(footer, text="", bg=self.BG, fg=self.MUTED, font=("Segoe UI", 8), anchor="w")
        self.attachments_label.pack(fill="x", padx=30, pady=(0, 5))
        composer_outer = tk.Frame(footer, bg=self.BORDER, highlightbackground=self.BORDER, highlightthickness=1, padx=1, pady=1)
        composer_outer.pack(fill="x", padx=30)
        composer = tk.Frame(composer_outer, bg=self.PANEL_2)
        composer.pack(fill="x")
        self.input = tk.Text(composer, height=2, wrap="word", bg=self.PANEL_2, fg=self.TEXT, insertbackground=self.TEXT, relief="flat", borderwidth=0, font=("Segoe UI", 10), padx=14, pady=12, undo=True)
        self.input.pack(fill="x", padx=2, pady=(2, 0))
        self.input_placeholder = "Message Nexa AI…"
        self.input_placeholder_active = True
        self.input.insert("1.0", self.input_placeholder)
        self.input.configure(fg=self.MUTED)
        self.input.bind("<FocusIn>", self._clear_input_placeholder)
        self.input.bind("<FocusOut>", self._restore_input_placeholder)
        self.input.bind("<Return>", self._send_enter)
        self.input.bind("<Control-Return>", self._send_hotkey)

        composer_tools = tk.Frame(composer, bg=self.PANEL_2)
        composer_tools.pack(fill="x", padx=9, pady=(0, 8))
        left_tools = tk.Frame(composer_tools, bg=self.PANEL_2)
        left_tools.pack(side="left")
        self.attach_button = tk.Button(left_tools, text="＋  Attach", command=self.attach_file, bg=self.PANEL_2, fg=self.MUTED, activebackground=self.PANEL, activeforeground=self.TEXT, relief="flat", borderwidth=0, font=("Segoe UI", 8), padx=9, pady=5, cursor="hand2")
        self.attach_button.pack(side="left", padx=(0, 4))
        self.voice_button = tk.Button(left_tools, text="🎙 Voice", command=self.toggle_voice_chat, bg=self.PANEL_2, fg=self.MUTED, activebackground=self.PANEL, activeforeground=self.TEXT, relief="flat", borderwidth=0, font=("Segoe UI", 8), padx=9, pady=5, cursor="hand2")
        self.voice_button.pack(side="left")
        self.send_button = tk.Button(composer_tools, text="↑", command=self.send_message, bg=self.ACCENT, fg=self.THEMES[self.theme_name]["BUTTON_TEXT"], activebackground=self.THEMES[self.theme_name]["ACTIVE"], activeforeground=self.TEXT, relief="flat", borderwidth=0, font=("Segoe UI Semibold", 14), width=3, height=1, state="disabled", cursor="hand2")
        self.send_button.pack(side="right", padx=(6, 0))

        footer_note = tk.Frame(footer, bg=self.BG)
        footer_note.pack(fill="x", padx=32, pady=(6, 0))
        self.speak_replies_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(footer_note, text="Speak voice-chat replies", variable=self.speak_replies_var, style="Nexa.TCheckbutton").pack(side="left")
        tk.Label(footer_note, text="Your conversations stay on this PC · NTech", bg=self.BG, fg=self.MUTED, font=("Segoe UI", 8)).pack(side="right")

    def _sidebar_button(self, parent, label: str, command, accent: bool = False):
        return tk.Button(parent, text=label, command=command, anchor="w", bg=self.PANEL_2 if accent else self.PANEL, fg=self.THEMES[self.theme_name]["BUTTON_TEXT"] if accent else self.TEXT, activebackground=self.THEMES[self.theme_name]["ACTIVE"], activeforeground=self.TEXT, relief="flat", borderwidth=0, padx=13, pady=10, font=("Segoe UI Semibold" if accent else "Segoe UI", 9), cursor="hand2")

    def _refresh_recent_conversations(self) -> None:
        frame = getattr(self, "recent_chats_frame", None)
        if frame is None or not frame.winfo_exists():
            return
        for child in frame.winfo_children():
            child.destroy()
        try:
            items = self.history_store.list_conversations()[:12]
        except Exception:
            items = []
        if not items:
            tk.Label(frame, text="Your conversations\nwill appear here.", bg=self.PANEL, fg=self.MUTED, justify="left", font=("Segoe UI", 8)).pack(anchor="w", padx=10, pady=8)
            return
        for item in items:
            title = recent_chat_label(item.get("title", ""))
            tk.Button(frame, text=title, anchor="w", command=lambda cid=item["id"]: self._open_saved_conversation(cid), bg=self.PANEL, fg=self.TEXT, activebackground=self.PANEL_2, activeforeground=self.TEXT, relief="flat", borderwidth=0, padx=10, pady=8, font=("Segoe UI", 8), cursor="hand2").pack(fill="x", pady=1)

    def _open_saved_conversation(self, conversation_id: str) -> None:
        try:
            data = self.history_store.load(conversation_id)
            self.messages = data["messages"]
            self.conversation_id = data["id"]
            self.conversation_title = data.get("title", "Conversation")
            self._render_conversation(self.messages)
            self.pending_files.clear()
            self._refresh_attachments()
            self.show_chat_workspace()
            self._refresh_recent_conversations()
        except Exception as exc:
            messagebox.showerror("History could not be opened", str(exc))

    def _on_chat_feed_configure(self, _event=None) -> None:
        try:
            self.chat_canvas.configure(scrollregion=self.chat_canvas.bbox("all"))
        except tk.TclError:
            pass

    def _on_chat_canvas_configure(self, event) -> None:
        try:
            self.chat_canvas.itemconfigure(self.chat_window_id, width=event.width)
            height = max(event.height, self.chat_feed.winfo_reqheight())
            self.chat_canvas.itemconfigure(self.chat_window_id, height=height)
        except tk.TclError:
            pass

    def _on_chat_mousewheel(self, event):
        self.chat_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        return "break"

    def _scroll_chat_to_bottom(self) -> None:
        try:
            self.root.update_idletasks()
            self.chat_canvas.configure(scrollregion=self.chat_canvas.bbox("all"))
            self.chat_canvas.yview_moveto(1.0)
        except tk.TclError:
            pass

    def _clear_chat_feed(self) -> None:
        for child in self.chat_feed.winfo_children():
            child.destroy()
        self.current_assistant_widget = None
        self.current_assistant_row = None
        self.current_assistant_copy_button = None
        self.empty_state = None

    def _show_empty_state(self) -> None:
        self._clear_chat_feed()
        empty = tk.Frame(self.chat_feed, bg=self.BG)
        empty.pack(fill="both", expand=True)
        self.empty_state = empty
        center = tk.Frame(empty, bg=self.BG)
        center.place(relx=0.5, rely=0.48, anchor="center")
        tk.Label(center, text="N", bg=self.ACCENT, fg="#101820", font=("Segoe UI Semibold", 18), width=2, height=1).pack(pady=(0, 15))
        tk.Label(center, text="What can I help with?", bg=self.BG, fg=self.TEXT, font=("Segoe UI Semibold", 22)).pack(pady=(0, 7))
        tk.Label(center, text="Chat, code, debug and build automations — privately on your PC.", bg=self.BG, fg=self.MUTED, font=("Segoe UI", 9)).pack(pady=(0, 19))
        cards = tk.Frame(center, bg=self.BG)
        cards.pack()
        for index, (title, description, prompt) in enumerate(CHAT_SUGGESTIONS):
            card = tk.Frame(cards, bg=self.PANEL, highlightbackground=self.BORDER, highlightthickness=1)
            card.grid(row=index // 2, column=index % 2, padx=6, pady=6, sticky="nsew")
            tk.Button(card, text=f"{title}\n{description}", anchor="w", justify="left", command=lambda value=prompt: self._fill_prompt_suggestion(value), bg=self.PANEL, fg=self.TEXT, activebackground=self.PANEL_2, activeforeground=self.TEXT, relief="flat", borderwidth=0, padx=14, pady=14, width=28, wraplength=225, font=("Segoe UI", 9), cursor="hand2").pack(fill="both", expand=True)
        cards.grid_columnconfigure(0, weight=1)
        cards.grid_columnconfigure(1, weight=1)
        self.root.after_idle(self._on_chat_feed_configure)

    def _fill_prompt_suggestion(self, prompt: str) -> None:
        self.input.delete("1.0", "end")
        self.input_placeholder_active = False
        self.input.configure(fg=self.TEXT)
        self.input.insert("1.0", prompt)
        self.input.focus_set()

    def show_chat_workspace(self) -> None:
        try:
            self.root.deiconify()
            self.root.lift()
            self._scroll_chat_to_bottom()
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
        if event is not None and (event.state & 0x0001):
            return None
        self.send_message()
        return "break"

    def _configure_premium_dropdowns(self) -> None:
        style = self.ttk_style
        palette = self.THEMES[self.theme_name]
        style.configure(
            "Nexa.TCombobox", fieldbackground=self.PANEL_2, background=self.PANEL_2,
            foreground=self.TEXT, arrowcolor=self.ACCENT, bordercolor=self.BORDER,
            lightcolor=self.BORDER, darkcolor=self.BORDER, padding=(11, 8), relief="flat",
        )
        style.map(
            "Nexa.TCombobox",
            fieldbackground=[("readonly", self.PANEL_2), ("focus", self.PANEL_2), ("disabled", self.PANEL)],
            background=[("active", self.PANEL_2), ("readonly", self.PANEL_2)],
            foreground=[("readonly", self.TEXT), ("disabled", self.MUTED)],
            selectbackground=[("readonly", self.PANEL_2)],
            selectforeground=[("readonly", self.TEXT)],
        )
        style.configure("Nexa.Vertical.TScrollbar", background=self.PANEL_2, troughcolor=self.BG, bordercolor=self.BG, arrowcolor=self.MUTED, relief="flat")
        style.configure("Nexa.TCheckbutton", background=self.BG, foreground=self.TEXT, padding=(4, 4), font=("Segoe UI", 9))
        style.map("Nexa.TCheckbutton", background=[("active", self.BG)], foreground=[("disabled", self.MUTED)])
        self.root.option_add("*TCombobox*Listbox.background", self.PANEL_2)
        self.root.option_add("*TCombobox*Listbox.foreground", self.TEXT)
        self.root.option_add("*TCombobox*Listbox.selectBackground", palette["SELECT"])
        self.root.option_add("*TCombobox*Listbox.selectForeground", self.TEXT)
        self.root.option_add("*TCombobox*Listbox.font", ("Segoe UI", 9))

    def _load_theme_preference(self) -> str:
        try:
            prefs = json.loads(self.preferences_path.read_text(encoding="utf-8"))
            selected = str(prefs.get("theme", "NTech Chat Dark"))
            return selected if selected in self.THEMES else "NTech Chat Dark"
        except (OSError, ValueError, AttributeError):
            return "NTech Chat Dark"

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
        self._configure_premium_dropdowns()
        self.chat_canvas.configure(bg=self.BG)
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

    def _load_ai_preference(self) -> str:
        try:
            payload = json.loads(self.preferences_path.read_text(encoding="utf-8"))
            selected = str(payload.get("ai_choice", DEFAULT_AI_CHOICE))
        except (OSError, ValueError, AttributeError):
            selected = DEFAULT_AI_CHOICE
        if selected not in AI_CHOICES:
            return DEFAULT_AI_CHOICE
        if AI_CHOICES[selected][0] == "gemini" and not self.secret_store.has_secret("gemini_api_key"):
            return DEFAULT_AI_CHOICE
        return selected

    def _apply_ai_choice(self, selected: str, save: bool = True) -> None:
        if selected not in AI_CHOICES:
            selected = DEFAULT_AI_CHOICE
        provider, model_id, model_name = AI_CHOICES[selected]
        self.ai_choice, self.ai_provider = selected, provider
        self.current_model_key, self.current_model_id, self.current_model_name = selected, model_id, model_name
        if hasattr(self, "ai_choice_var"):
            self.ai_choice_var.set(selected)
        if hasattr(self, "model_title_label"):
            self.model_title_label.configure(text=model_name)
        if hasattr(self, "model_badge"):
            self.model_badge.configure(text=f"{model_name.upper()} · {'ONLINE' if provider == 'gemini' else 'OFFLINE'}")
        if hasattr(self, "gemini_connect_button"):
            self.gemini_connect_button.configure(text="Gemini Settings" if self.secret_store.has_secret("gemini_api_key") else "Connect Gemini")
        if save:
            self._save_preferences()

    def _change_ai_choice(self, _event=None) -> None:
        selected = self.ai_choice_var.get()
        if selected not in AI_CHOICES:
            self.ai_choice_var.set(self.ai_choice)
            return
        if AI_CHOICES[selected][0] == "gemini" and not self.secret_store.has_secret("gemini_api_key"):
            self.pending_ai_choice = selected
            self.ai_choice_var.set(self.ai_choice)
            self.open_gemini_settings()
            return
        self._apply_ai_choice(selected)
        self.status_var.set(f"Selected {self.current_model_name}")

    def open_gemini_settings(self) -> None:
        window = tk.Toplevel(self.root)
        window.title("Nexa AI · Connect Gemini")
        window.geometry("540x340")
        window.resizable(False, False)
        window.configure(bg=self.BG)
        tk.Label(window, text="Connect Google Gemini", bg=self.BG, fg=self.TEXT, font=("Segoe UI Semibold", 17)).pack(anchor="w", padx=22, pady=(20, 5))
        tk.Label(window, text="Offline Qwen2.5-Coder needs no key. Gemini requires your Google AI Studio API key. Free-tier quotas apply, and Google may use free-tier prompts to improve its products.", bg=self.BG, fg=self.MUTED, font=("Segoe UI", 9), wraplength=490, justify="left").pack(anchor="w", padx=22, pady=(0, 14))
        tk.Label(window, text="Gemini API key", bg=self.BG, fg=self.TEXT, font=("Segoe UI Semibold", 9)).pack(anchor="w", padx=22)
        key_var = tk.StringVar()
        key_entry = tk.Entry(window, textvariable=key_var, show="•", bg=self.PANEL_2, fg=self.TEXT, insertbackground=self.TEXT, relief="flat", font=("Segoe UI", 10))
        key_entry.pack(fill="x", padx=22, pady=(5, 8), ipady=8)
        try:
            existing = self.secret_store.get_secret("gemini_api_key")
        except Exception as exc:
            existing, stored_error = None, str(exc)
        else:
            stored_error = ""
        if existing:
            key_var.set(existing)
        status_var = tk.StringVar(value=stored_error or ("Key is encrypted with Windows DPAPI on this PC." if existing else "No Gemini key saved. Offline Qwen stays available."))
        tk.Label(window, textvariable=status_var, bg=self.BG, fg=self.MUTED, font=("Segoe UI", 8), wraplength=490, justify="left").pack(anchor="w", padx=22, pady=(0, 9))
        buttons = tk.Frame(window, bg=self.BG)
        buttons.pack(fill="x", padx=22, pady=(4, 16))

        def open_key_page() -> None:
            webbrowser.open("https://aistudio.google.com/api-keys")

        def connect() -> None:
            key = key_var.get().strip()
            if not key:
                status_var.set("Paste your Google AI Studio API key first.")
                return
            connect_button.configure(state="disabled", text="Checking…")
            status_var.set("Testing Gemini key…")

            def worker() -> None:
                try:
                    test_gemini_api_key(key)
                    self.secret_store.set_secret("gemini_api_key", key)
                    self.events.put(("gemini_connected", {"window": window}))
                except Exception as exc:
                    self.events.put(("gemini_connect_error", {"window": window, "button": connect_button, "message": str(exc)}))

            threading.Thread(target=worker, daemon=True, name="NexaGeminiConnect").start()

        def disconnect() -> None:
            try:
                self.secret_store.delete_secret("gemini_api_key")
                if self.ai_provider == "gemini":
                    self._apply_ai_choice(DEFAULT_AI_CHOICE)
                self.pending_ai_choice = None
                self.gemini_connect_button.configure(text="Connect Gemini")
                status_var.set("Gemini key removed. Offline Qwen remains available.")
                key_var.set("")
            except Exception as exc:
                status_var.set(str(exc))

        ttk.Button(buttons, text="Get API key", style="Nexa.TButton", command=open_key_page).pack(side="left")
        if existing:
            ttk.Button(buttons, text="Disconnect", style="Nexa.TButton", command=disconnect).pack(side="left", padx=6)
        connect_button = ttk.Button(buttons, text="Connect & Save", style="Accent.TButton", command=connect)
        connect_button.pack(side="right")
        ttk.Button(buttons, text="Close", style="Nexa.TButton", command=window.destroy).pack(side="right", padx=6)
        key_entry.focus_set()

    def _load_response_preference(self) -> str:
        try:
            payload = json.loads(self.preferences_path.read_text(encoding="utf-8"))
            profile = str(payload.get("response_profile", "Quick"))
            return profile if profile in {"Quick", "Balanced", "Detailed"} else "Quick"
        except (OSError, ValueError, AttributeError):
            return "Quick"

    def _change_response_profile(self, _event=None) -> None:
        selected = self.response_profile_var.get()
        self.response_profile = selected if selected in {"Quick", "Balanced", "Detailed"} else "Quick"
        self._save_preferences()
        self.status_var.set(f"Response length set to {self.response_profile.lower()}")

    def _save_preferences(self) -> None:
        try:
            payload = {
                "theme": self.theme_name,
                "response_profile": getattr(self, "response_profile", "Quick"),
                "ai_choice": getattr(self, "ai_choice", DEFAULT_AI_CHOICE),
            }
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

    def _make_message_text(self, parent, text: str, background: str, foreground: str, width: int, padx: int, pady: int):
        widget = tk.Text(parent, wrap="word", bg=background, fg=foreground, insertbackground=foreground, relief="flat", borderwidth=0, highlightthickness=0, font=("Segoe UI", 10), width=width, height=1, padx=padx, pady=pady, spacing1=3, spacing3=4, undo=False)
        if text:
            widget.insert("1.0", text)
        widget.configure(state="disabled")
        widget.pack(fill="x", expand=True)
        widget.update_idletasks()
        try:
            display_lines = widget.count("1.0", "end-1c", "displaylines")
            line_count = max(1, int(display_lines[0])) if display_lines else 1
        except (IndexError, TypeError, tk.TclError):
            line_count = max(1, text.count("\n") + 1)
        widget.configure(height=line_count)
        widget.bind("<MouseWheel>", self._on_chat_mousewheel)
        return widget

    def _append_message(self, name: str, text: str, role: str) -> None:
        if self.empty_state is not None and self.empty_state.winfo_exists():
            self.empty_state.destroy()
            self.empty_state = None
        row = tk.Frame(self.chat_feed, bg=self.BG)
        row.pack(fill="x", padx=22 if role == "assistant" else 18, pady=(15, 11))
        canvas_width = max(560, self.chat_canvas.winfo_width())
        text_width = max(44, min(90, int((canvas_width - 290) / 8)))
        if role == "user":
            bubble = tk.Frame(row, bg=self.PANEL_2, highlightbackground=self.BORDER, highlightthickness=1, padx=1, pady=1)
            bubble.pack(anchor="e", padx=(70, 0))
            self._make_message_text(bubble, text, self.PANEL_2, self.TEXT, min(72, text_width), 13, 9)
            self.current_assistant_widget = None
            self.current_assistant_row = None
        else:
            header = tk.Frame(row, bg=self.BG)
            header.pack(fill="x", pady=(0, 5))
            tk.Label(header, text="N", bg=self.ACCENT, fg="#101820", font=("Segoe UI Semibold", 9), width=2, height=1).pack(side="left", padx=(0, 9))
            tk.Label(header, text="Nexa AI", bg=self.BG, fg=self.TEXT, font=("Segoe UI Semibold", 9)).pack(side="left")
            body = tk.Frame(row, bg=self.BG)
            body.pack(fill="x", padx=(31, 0))
            message_widget = self._make_message_text(body, text, self.BG, self.TEXT, text_width, 1, 2)
            actions = tk.Frame(row, bg=self.BG)
            actions.pack(fill="x", padx=(31, 0), pady=(4, 0))
            copy_button = tk.Button(actions, text="⧉  Copy answer", command=lambda w=message_widget: self._copy_message_text(w), bg=self.BG, fg=self.MUTED, activebackground=self.PANEL_2, activeforeground=self.TEXT, relief="flat", borderwidth=0, font=("Segoe UI", 8), padx=8, pady=3, cursor="hand2", state="normal" if text else "disabled")
            copy_button.pack(side="left")
            if not text:
                self.current_assistant_widget = message_widget
                self.current_assistant_row = row
                self.current_assistant_copy_button = copy_button
            else:
                self._format_message_widget(message_widget)
                self.current_assistant_widget = None
                self.current_assistant_row = None
                self.current_assistant_copy_button = None
        self._scroll_chat_to_bottom()

    def _copy_message_text(self, widget) -> None:
        try:
            content = widget.get("1.0", "end-1c")
            self.root.clipboard_clear()
            self.root.clipboard_append(content)
            self.status_var.set("Answer copied to clipboard")
            self.status_label.configure(fg="#73d6a4")
        except tk.TclError as exc:
            messagebox.showerror("Copy answer", str(exc))

    def _format_message_widget(self, widget) -> None:
        try:
            widget.configure(state="normal")
            lines = widget.get("1.0", "end-1c").splitlines()
            in_code = False
            for number, line in enumerate(lines, start=1):
                start, end = f"{number}.0", f"{number}.end"
                if line.strip().startswith("```"):
                    in_code = not in_code
                    widget.tag_add("codeblock", start, end)
                elif in_code:
                    widget.tag_add("codeblock", start, end)
                elif line.lstrip().startswith("#"):
                    widget.tag_add("heading", start, end)
            widget.configure(state="disabled")
        except tk.TclError:
            try:
                widget.configure(state="disabled")
            except tk.TclError:
                pass

    def _finish_assistant_message(self) -> None:
        widget = self.current_assistant_widget
        button = self.current_assistant_copy_button
        if widget is not None and widget.winfo_exists():
            self._format_message_widget(widget)
        if button is not None:
            try:
                button.configure(state="normal")
            except tk.TclError:
                pass
        self.current_assistant_widget = None
        self.current_assistant_row = None
        self.current_assistant_copy_button = None

    def _append_stream(self, text: str) -> None:
        widget = self.current_assistant_widget
        if widget is None or not widget.winfo_exists():
            return
        try:
            widget.configure(state="normal")
            widget.insert("end", text)
            widget.update_idletasks()
            display_lines = widget.count("1.0", "end-1c", "displaylines")
            line_count = max(1, int(display_lines[0])) if display_lines else 1
            widget.configure(height=line_count, state="disabled")
            self._scroll_chat_to_bottom()
        except tk.TclError:
            self.current_assistant_widget = None

    def _remove_empty_assistant_row(self) -> None:
        widget = self.current_assistant_widget
        row = self.current_assistant_row
        if widget is not None and row is not None:
            try:
                if not widget.get("1.0", "end-1c").strip():
                    row.destroy()
            except tk.TclError:
                pass
        self.current_assistant_widget = None
        self.current_assistant_row = None
        self.current_assistant_copy_button = None


    def _boot_engine(self) -> None:
        try:
            self.events.put(("model_download_status", "Checking NexaAI offline engine…"))
            self.ollama_runtime.ensure_server(self.log_handle)
            self.log_handle.write("Ollama local API is ready.\n")

            def report_progress(status: str, completed: int, total: int, speed: float) -> None:
                self.events.put(("model_download_status", status))
                if total:
                    self.events.put(("model_download_progress", (completed, total, speed)))

            if OLLAMA_MODEL not in self.ollama_runtime.installed_models():
                self.events.put(("model_download_status", f"Installing missing Qwen2.5-Coder 3B · {OLLAMA_MODEL_SIZE}"))
            self.ollama_runtime.ensure_model(report_progress)
            self.log_handle.write(f"Local model ready: {OLLAMA_MODEL}\n")

            if self.api_server is None:
                from nexa_ai.config import settings
                import uvicorn
                from nexa_ai.api import app
                config = build_uvicorn_config(app, host=settings.host, port=settings.port)
                self.api_server = uvicorn.Server(config)
                self.api_thread = threading.Thread(target=self.api_server.run, daemon=True, name="NexaLocalAPI")
                self.api_thread.start()
                if not self._wait_for_url(f"http://127.0.0.1:{API_PORT}/health", 30):
                    raise RuntimeError("NexaAI local API could not start. Port 8000 may already be in use.")
            self.events.put(("ready", None))
        except OllamaNotInstalled as exc:
            self.events.put(("ollama_missing", str(exc)))
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
        stream_parts: list[str] = []

        def flush_stream() -> None:
            if stream_parts:
                self._append_stream("".join(stream_parts))
                stream_parts.clear()

        try:
            while True:
                kind, payload = self.events.get_nowait()
                if kind == "stream":
                    stream_parts.append(str(payload))
                    continue
                flush_stream()
                if kind == "ready":
                    self.ready = True
                    self.status_var.set("● Offline model ready")
                    self.status_label.configure(fg="#73d6a4")
                    self.send_button.configure(state="normal")
                    self.root.after(80, self.show_chat_workspace)
                elif kind == "history_updated":
                    self._refresh_recent_conversations()
                elif kind == "gemini_connected":
                    try:
                        payload["window"].destroy()
                    except (tk.TclError, KeyError, TypeError):
                        pass
                    choice = self.pending_ai_choice or "Gemini 3.8 Flash · Online"
                    if choice not in AI_CHOICES or AI_CHOICES[choice][0] != "gemini":
                        choice = "Gemini 3.8 Flash · Online"
                    self.pending_ai_choice = None
                    self._apply_ai_choice(choice)
                    self.status_var.set("Gemini connected · ready for online chat")
                    self.status_label.configure(fg="#73d6a4")
                elif kind == "gemini_connect_error":
                    try:
                        payload["button"].configure(state="normal", text="Connect & Save")
                        payload["window"].title("Nexa AI · Gemini connection failed")
                    except (tk.TclError, KeyError, TypeError):
                        pass
                    messagebox.showerror("Gemini connection failed", str(payload.get("message", "Could not connect to Gemini.")))
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
                        self.status_var.set(f"Downloading Qwen2.5-Coder 3B · {percent:.1f}% · {done / (1024 ** 3):.2f}/{total / (1024 ** 3):.2f} GB · {rate}{eta}")
                    else:
                        self.status_var.set(f"Downloading Qwen2.5-Coder 3B · {done / (1024 ** 2):.0f} MB · {rate}")
                    self.status_label.configure(fg=self.ACCENT)
                elif kind == "ollama_missing":
                    self.status_var.set("Bundled AI engine missing")
                    self.status_label.configure(fg="#ff8d8d")
                    messagebox.showerror(
                        "NexaAI engine missing",
                        "The built-in Ollama runtime could not be found. Repair or reinstall NexaAI to restore the offline AI engine.\n\n"
                        + str(payload),
                    )
                elif kind == "boot_error":
                    self.status_var.set("Offline engine failed to start")
                    self.status_label.configure(fg="#ff8d8d")
                    messagebox.showerror("Nexa AI could not start", str(payload))
                elif kind == "first_token":
                    self.status_var.set("Writing answer…")
                    self.status_label.configure(fg=self.ACCENT)
                elif kind == "done":
                    self.busy = False
                    self.send_button.configure(state="normal" if self.ready else "disabled", text="↑")
                    self.status_var.set("● Gemini online ready" if self.active_request_provider == "gemini" else "● Offline Qwen ready")
                    self.status_label.configure(fg="#73d6a4")
                    self.ai_selector.configure(state="readonly")
                    self._finish_assistant_message()
                    self._scroll_chat_to_bottom()
                    if self.pending_send_queue:
                        self.status_var.set("Sending queued follow-up · " + str(len(self.pending_send_queue)) + " left")
                        self.root.after(120, self._send_next_queued)
                    if self.voice_turn:
                        self.voice_turn = False
                        if self.speak_replies_var.get() and self.messages and self.messages[-1].get("role") == "assistant":
                            self._speak_text(str(self.messages[-1].get("content", "")))
                elif kind == "request_error":
                    self.busy = False
                    self.send_button.configure(state="normal" if self.ready else "disabled", text="↑")
                    self.status_var.set("Request failed")
                    self.status_label.configure(fg="#ff8d8d")
                    self.ai_selector.configure(state="readonly")
                    self.voice_turn = False
                    self._remove_empty_assistant_row()
                    self._append_message("Nexa AI", f"I couldn't complete that request.\n\n{payload}", "assistant")
                    if self.pending_send_queue:
                        self.root.after(300, self._send_next_queued)
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
                    if "Listening" in str(payload):
                        self.status_label.configure(fg="#d6b66d")
                    elif "Transcrib" in str(payload) or "Whisper" in str(payload):
                        self.status_label.configure(fg=self.ACCENT)
                elif kind == "voice_transcribed":
                    self.voice_button.configure(state="normal", text="🎙 Voice")
                    self.status_var.set("Voice recognized · sending to selected AI…")
                    self.input.delete("1.0", "end")
                    self.input_placeholder_active = False
                    self.input.configure(fg=self.TEXT)
                    self.input.insert("1.0", str(payload))
                    self.voice_turn = True
                    self.send_message()
                elif kind == "voice_error":
                    self.voice_button.configure(state="normal", text="🎙 Voice")
                    self.send_button.configure(state="normal" if self.ready and not self.busy else "disabled")
                    self.recording = False
                    self.voice_turn = False
                    self.status_var.set("Voice chat unavailable")
                    self.status_label.configure(fg="#ff8d8d")
                    messagebox.showerror("Voice chat", str(payload))
        except queue.Empty:
            flush_stream()
        if self.root.winfo_exists():
            self.root.after(80, self._poll_events)
    def _refresh_attachments(self) -> None:
        names = [item.get("filename", "file") for item in self.pending_files]
        self.attachments_label.configure(text=("Attached: " + "  ·  ".join(names)) if names else "")

    def attach_file(self) -> None:
        if self.uploading or self.busy or not self.ready:
            return
        path = filedialog.askopenfilename(
            title="Attach a local document",
            filetypes=[
                ("Supported files", "*.pdf *.png *.jpg *.jpeg *.webp *.heic *.heif *.txt *.md *.csv *.json *.xml *.py *.js *.html *.css *.log"),
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
        if not self.ready or self.uploading:
            return
        text = "" if self.input_placeholder_active else self.input.get("1.0", "end-1c").strip()
        if not text and not self.pending_files:
            return

        # Keep a follow-up instead of dropping it while the local model is responding.
        if self.busy:
            if self.pending_files:
                self.status_var.set("Wait until the current answer finishes before attaching another file.")
                return
            if not enqueue_followup(self.pending_send_queue, text, limit=4):
                self.status_var.set("Message queue is full · maximum 4 follow-ups")
                return
            self.input.delete("1.0", "end")
            self.input_placeholder_active = False
            self.input.configure(fg=self.TEXT)
            self.send_button.configure(text="Queue " + str(len(self.pending_send_queue)), state="normal")
            self.status_var.set(f"Follow-up queued · {len(self.pending_send_queue)} waiting")
            return

        provider, model_id = self.ai_provider, self.current_model_id
        if provider == "gemini" and not self.secret_store.has_secret("gemini_api_key"):
            self.pending_ai_choice = self.ai_choice
            self.open_gemini_settings()
            return
        self.input.delete("1.0", "end")
        self.input_placeholder_active = False
        self.input.configure(fg=self.TEXT)
        self.busy = True
        self.send_button.configure(state="normal", text="Queue")
        self.status_var.set(f"Preparing {self.current_model_name} response…")
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
        max_tokens = response_token_limit(self.response_profile_var.get())
        self.active_request_provider = provider
        self.ai_selector.configure(state="disabled")
        threading.Thread(target=self._stream_request, args=(max_tokens, provider, model_id), daemon=True, name="NexaResponse").start()

    def _send_next_queued(self) -> None:
        if not self.ready or self.busy or not self.pending_send_queue:
            return
        next_text = take_followup(self.pending_send_queue)
        if next_text is None:
            return
        self.input.delete("1.0", "end")
        self.input.insert("1.0", next_text)
        self.input_placeholder_active = False
        self.input.configure(fg=self.TEXT)
        self.send_message()

    def _stream_request(self, max_tokens: int = 768, provider: str = "local", model_id: str | None = None) -> None:
        answer: list[str] = []
        selected_model = model_id or self.current_model_id

        def emit_piece(piece: str) -> None:
            if not piece:
                return
            if not answer:
                self.events.put(("first_token", None))
            answer.append(piece)
            self.events.put(("stream", piece))

        try:
            messages = build_chat_context(self.messages, max_recent_messages=12)
            if provider == "gemini":
                api_key = self.secret_store.get_secret("gemini_api_key")
                if not api_key:
                    raise RuntimeError("Gemini is not connected. Switch to offline Qwen or connect Gemini.")
                for piece in stream_gemini(messages, api_key, selected_model, temperature=0.55, max_tokens=int(max_tokens)):
                    emit_piece(str(piece))
            else:
                payload = {
                    "model": selected_model,
                    "messages": messages,
                    "stream": True,
                    "temperature": 0.55,
                    "max_tokens": int(max_tokens),
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
                                    piece = "".join(str(part.get("text", "")) for part in piece if isinstance(part, dict))
                                emit_piece(str(piece) if piece else "")

            final_answer = "".join(answer).strip()
            if not final_answer:
                raise RuntimeError("The selected AI provider returned no visible answer. Check its status and try again.")
            self.messages.append({"role": "assistant", "content": final_answer})
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
            self.events.put(("history_updated", None))
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
        self._clear_chat_feed()
        rendered = False
        for message in messages:
            role = message.get("role")
            if role not in {"user", "assistant"}:
                continue
            label = "You" if role == "user" else "Nexa AI"
            self._append_message(label, self._history_message_text(message.get("content", "")), role)
            rendered = True
        if not rendered:
            self._show_empty_state()
        self._scroll_chat_to_bottom()

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
                self._open_saved_conversation(item["id"])
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
                self._refresh_recent_conversations()
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
        self._show_empty_state()
        self.pending_files.clear()
        self.pending_send_queue.clear()
        self.send_button.configure(text="↑", state="normal" if self.ready else "disabled")
        self._refresh_attachments()
        self.show_chat_workspace()

    def toggle_voice_chat(self) -> None:
        if not self.ready or self.busy or self.uploading:
            return
        if self.recording:
            self._stop_voice_recording()
            return

        try:
            import sounddevice as sd
            import numpy as np  # noqa: F401
            default_device = sd.default.device
            input_device = default_device[0] if isinstance(default_device, (tuple, list)) else default_device
            if input_device is None or int(input_device) < 0:
                input_device = None
            device_info = sd.query_devices(input_device, kind="input")
            if int(device_info.get("max_input_channels", 0)) < 1:
                raise RuntimeError("Windows has no microphone input device selected. Connect or enable a microphone in Sound settings.")
            native_rate = int(round(float(device_info.get("default_samplerate", 48000))))
            candidates = list(dict.fromkeys([native_rate, 48000, 44100, 32000, 24000, 16000]))
            capture_rate = None
            last_error = None
            for candidate in candidates:
                try:
                    sd.check_input_settings(device=input_device, channels=1, samplerate=candidate, dtype="int16")
                    capture_rate = candidate
                    break
                except Exception as exc:
                    last_error = exc
            if capture_rate is None:
                raise RuntimeError(f"The selected microphone does not support a usable sample rate. {last_error}")
        except Exception as exc:
            messagebox.showerror(
                "Voice chat unavailable",
                f"Could not open the Windows microphone. Check Settings → System → Sound → Input and microphone privacy permissions.\n\n{exc}",
            )
            return

        self.recording_chunks = []
        self.recording_warnings = ""
        self._voice_capture_rate = capture_rate
        self.recording = True
        self.voice_button.configure(text="■ Stop & send", state="normal")
        self.send_button.configure(state="disabled")
        self.status_var.set(f"● Listening · microphone {capture_rate} Hz · speak now")
        self.status_label.configure(fg="#d6b66d")

        def audio_callback(indata, frames, time_info, status):
            if status:
                with self.recording_lock:
                    self.recording_warnings = str(status)
            with self.recording_lock:
                if self.recording:
                    self.recording_chunks.append(indata.copy())

        try:
            self.recording_stream = sd.InputStream(
                device=input_device, samplerate=capture_rate, channels=1,
                dtype="int16", blocksize=0, callback=audio_callback,
            )
            self.recording_stream.start()
        except Exception as exc:
            self.recording = False
            self.recording_stream = None
            self.voice_button.configure(text="🎙 Voice", state="normal")
            self.send_button.configure(state="normal" if self.ready else "disabled")
            self.status_var.set("Microphone could not start")
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
                warning = getattr(self, "recording_warnings", "")
                self.recording_chunks.clear()
            if not chunks:
                raise RuntimeError("No audio was captured. Check that Windows selected the correct microphone and that microphone access is enabled.")
            native_audio = np.concatenate(chunks, axis=0).astype("int16", copy=False)
            audio = resample_mono_int16(native_audio, self._voice_capture_rate, 16000)
            if len(audio) < 8000:
                raise RuntimeError("The recording was too short. Speak for at least half a second, then press Stop & send.")
            if warning:
                self.log_handle.write(f"Microphone warning: {warning}\n")
            voice_dir = self.app_root / "Voice" / "recordings"
            voice_dir.mkdir(parents=True, exist_ok=True)
            audio_path = voice_dir / f"voice-{uuid4().hex}.wav"
            with wave.open(str(audio_path), "wb") as wav:
                wav.setnchannels(1)
                wav.setsampwidth(2)
                wav.setframerate(16000)
                wav.writeframes(audio.tobytes())
        except Exception as exc:
            self.voice_button.configure(text="🎙 Voice", state="normal")
            self.send_button.configure(state="normal" if self.ready else "disabled")
            self.status_var.set("Voice recording failed")
            self.status_label.configure(fg="#ff8d8d")
            messagebox.showerror("Voice chat", str(exc))
            return

        self.voice_button.configure(state="disabled", text="Loading voice…")
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
                        "base", device="cpu", compute_type="int8", download_root=str(model_dir),
                        cpu_threads=max(1, min(2, os.cpu_count() or 2)), num_workers=1,
                    )
                finally:
                    if previous_hf is not None:
                        os.environ["HF_HUB_OFFLINE"] = previous_hf
                    if previous_transformers is not None:
                        os.environ["TRANSFORMERS_OFFLINE"] = previous_transformers

            self.events.put(("voice_status", "Transcribing locally…"))
            segments, info = self.whisper_model.transcribe(
                str(audio_path), beam_size=1, vad_filter=True,
                condition_on_previous_text=False, without_timestamps=True,
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
            com_initialized = False
            try:
                import comtypes
                comtypes.CoInitialize()
                com_initialized = True
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
                try:
                    self.root.after(0, lambda e=str(exc): self.status_var.set(f"Speech output unavailable: {e[:100]}"))
                except tk.TclError:
                    pass
            finally:
                if com_initialized:
                    try:
                        comtypes.CoUninitialize()
                    except Exception:
                        pass

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
            text="Describe an automation in Bangla or English. The selected AI creates an n8n workflow JSON you can export and import into your own n8n instance.",
            bg=self.BG, fg=self.MUTED, font=("Segoe UI", 9), wraplength=900, justify="left",
        ).pack(anchor="w", padx=20, pady=(0, 12))

        tk.Label(window, text="What should the workflow do?", bg=self.BG, fg=self.TEXT, font=("Segoe UI Semibold", 10)).pack(anchor="w", padx=20)
        prompt_box = tk.Text(window, height=6, wrap="word", bg=self.PANEL, fg=self.TEXT, insertbackground=self.TEXT, relief="flat", font=("Segoe UI", 10), padx=12, pady=10)
        prompt_box.pack(fill="x", padx=20, pady=(5, 10))

        actions = tk.Frame(window, bg=self.BG)
        actions.pack(fill="x", padx=20, pady=(0, 8))
        status = tk.Label(actions, text=f"AI model: {self.current_model_name}", bg=self.BG, fg=self.MUTED, font=("Segoe UI", 8))
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
            model_provider, model_id, model_name = self.ai_provider, self.current_model_id, self.current_model_name
            if model_provider == "gemini" and not self.secret_store.has_secret("gemini_api_key"):
                self.pending_ai_choice = self.ai_choice
                self.open_gemini_settings()
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
            status.configure(text=f"Generating with {model_name} · {model_provider}…", fg=self.ACCENT)
            result_state["workflow"] = None

            def worker() -> None:
                try:
                    if model_provider == "gemini":
                        api_key = self.secret_store.get_secret("gemini_api_key")
                        if not api_key:
                            raise RuntimeError("Connect Gemini in the AI engine panel first.")
                        raw = "".join(stream_gemini(messages, api_key, model_id, temperature=0.15, max_tokens=4096))
                    else:
                        payload = {
                            "model": model_id,
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
            if self.ollama_runtime:
                self.ollama_runtime.stop()
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
