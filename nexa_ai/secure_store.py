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


class DPAPISecretStore:
    """Store credentials encrypted for the current Windows user with Windows DPAPI."""

    def __init__(self, directory: str | Path) -> None:
        self.directory = Path(directory).expanduser()
        self.directory.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _crypt(data: bytes, *, protect: bool) -> bytes:
        if os.name != "nt":
            raise RuntimeError("Secure Gemini key storage is only supported on Windows.")
        if not data:
            raise ValueError("Secret cannot be empty.")

        crypt32 = ctypes.WinDLL("Crypt32.dll", use_last_error=True)
        kernel32 = ctypes.WinDLL("Kernel32.dll", use_last_error=True)
        input_buffer = ctypes.create_string_buffer(data)
        input_blob = _DataBlob(
            len(data),
            ctypes.cast(input_buffer, ctypes.POINTER(ctypes.c_ubyte)),
        )
        output_blob = _DataBlob()
        flags = 0x1  # CRYPTPROTECT_UI_FORBIDDEN

        if protect:
            function = crypt32.CryptProtectData
            function.argtypes = [
                ctypes.POINTER(_DataBlob), wintypes.LPCWSTR, ctypes.c_void_p,
                ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD,
                ctypes.POINTER(_DataBlob),
            ]
            function.restype = wintypes.BOOL
            ok = function(
                ctypes.byref(input_blob), "NexaAI Gemini API credential",
                None, None, None, flags, ctypes.byref(output_blob),
            )
        else:
            function = crypt32.CryptUnprotectData
            function.argtypes = [
                ctypes.POINTER(_DataBlob), ctypes.POINTER(wintypes.LPWSTR),
                ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p,
                wintypes.DWORD, ctypes.POINTER(_DataBlob),
            ]
            function.restype = wintypes.BOOL
            description = wintypes.LPWSTR()
            ok = function(
                ctypes.byref(input_blob), ctypes.byref(description),
                None, None, None, flags, ctypes.byref(output_blob),
            )
            if description:
                kernel32.LocalFree(ctypes.cast(description, ctypes.c_void_p))

        if not ok:
            error = ctypes.get_last_error()
            raise OSError(error, "Windows DPAPI could not protect or unprotect the credential.")

        try:
            return ctypes.string_at(output_blob.pbData, output_blob.cbData)
        finally:
            kernel32.LocalFree(ctypes.cast(output_blob.pbData, ctypes.c_void_p))

    def _path(self, name: str) -> Path:
        safe = "".join(char for char in str(name) if char.isalnum() or char in {"-", "_"})
        if not safe or safe != name:
            raise ValueError("Invalid credential name.")
        return self.directory / f"{safe}.dpapi"

    def set_secret(self, name: str, value: str) -> None:
        secret = str(value).strip()
        if not secret:
            raise ValueError("API key cannot be empty.")
        encrypted = self._crypt(secret.encode("utf-8"), protect=True)
        target = self._path(name)
        temporary = target.with_suffix(".tmp")
        temporary.write_bytes(encrypted)
        temporary.replace(target)

    def get_secret(self, name: str) -> str | None:
        path = self._path(name)
        if not path.is_file():
            return None
        encrypted = path.read_bytes()
        if not encrypted:
            return None
        return self._crypt(encrypted, protect=False).decode("utf-8")

    def has_secret(self, name: str) -> bool:
        path = self._path(name)
        return path.is_file() and path.stat().st_size > 0

    def delete_secret(self, name: str) -> None:
        self._path(name).unlink(missing_ok=True)
