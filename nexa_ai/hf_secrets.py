from __future__ import annotations

import ctypes
import os
from ctypes import wintypes
from pathlib import Path


class _DataBlob(ctypes.Structure):
    _fields_ = [
        ("cbData", wintypes.DWORD),
        ("pbData", ctypes.POINTER(ctypes.c_ubyte)),
    ]


def _secret_path() -> Path:
    root = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    return root / "NexaAI" / "secrets" / "huggingface_token.dpapi"


def _dpapi(data: bytes, *, decrypt: bool) -> bytes:
    if os.name != "nt":
        raise RuntimeError("Hugging Face tokens can only be securely stored by this Windows build.")
    crypt32 = ctypes.WinDLL("crypt32.dll", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32.dll", use_last_error=True)
    buffer = ctypes.create_string_buffer(data)
    source = _DataBlob(len(data), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_ubyte)))
    target = _DataBlob()
    flags = 0x1  # CRYPTPROTECT_UI_FORBIDDEN

    if decrypt:
        description = wintypes.LPWSTR()
        function = crypt32.CryptUnprotectData
        function.argtypes = [
            ctypes.POINTER(_DataBlob), ctypes.POINTER(wintypes.LPWSTR),
            ctypes.POINTER(_DataBlob), ctypes.c_void_p, ctypes.c_void_p,
            wintypes.DWORD, ctypes.POINTER(_DataBlob),
        ]
        function.restype = wintypes.BOOL
        ok = function(ctypes.byref(source), ctypes.byref(description), None, None, None, flags, ctypes.byref(target))
    else:
        function = crypt32.CryptProtectData
        function.argtypes = [
            ctypes.POINTER(_DataBlob), wintypes.LPCWSTR, ctypes.POINTER(_DataBlob),
            ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(_DataBlob),
        ]
        function.restype = wintypes.BOOL
        ok = function(ctypes.byref(source), "NexaAI Hugging Face token", None, None, None, flags, ctypes.byref(target))

    if not ok:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        return ctypes.string_at(target.pbData, target.cbData)
    finally:
        kernel32.LocalFree.argtypes = [ctypes.c_void_p]
        kernel32.LocalFree.restype = ctypes.c_void_p
        kernel32.LocalFree(target.pbData)


def save_hf_token(token: str) -> None:
    value = str(token or "").strip()
    if not value:
        raise ValueError("Enter a Hugging Face access token.")
    encrypted = _dpapi(value.encode("utf-8"), decrypt=False)
    target = _secret_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(".tmp")
    temporary.write_bytes(encrypted)
    temporary.replace(target)


def load_hf_token() -> str | None:
    target = _secret_path()
    if not target.is_file():
        return None
    encrypted = target.read_bytes()
    if not encrypted:
        return None
    return _dpapi(encrypted, decrypt=True).decode("utf-8").strip() or None


def clear_hf_token() -> None:
    _secret_path().unlink(missing_ok=True)


def has_hf_token() -> bool:
    try:
        return bool(load_hf_token())
    except (OSError, RuntimeError, ValueError):
        return False
