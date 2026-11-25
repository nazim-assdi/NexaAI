from __future__ import annotations

import ctypes
import os
from ctypes import wintypes


class _FILETIME(ctypes.Structure):
    _fields_ = [("dwLowDateTime", wintypes.DWORD), ("dwHighDateTime", wintypes.DWORD)]


class _CREDENTIALW(ctypes.Structure):
    _fields_ = [
        ("Flags", wintypes.DWORD), ("Type", wintypes.DWORD),
        ("TargetName", wintypes.LPWSTR), ("Comment", wintypes.LPWSTR),
        ("LastWritten", _FILETIME), ("CredentialBlobSize", wintypes.DWORD),
        ("CredentialBlob", ctypes.POINTER(ctypes.c_ubyte)),
        ("Persist", wintypes.DWORD), ("AttributeCount", wintypes.DWORD),
        ("Attributes", ctypes.c_void_p), ("TargetAlias", wintypes.LPWSTR),
        ("UserName", wintypes.LPWSTR),
    ]


_CRED_TYPE_GENERIC = 1
_CRED_PERSIST_LOCAL_MACHINE = 2
_ERROR_NOT_FOUND = 1168
_ALLOWED_NAMES = {
    "gemini", "groq", "openrouter", "zai", "mistral", "nvidia",
    "cohere", "cloudflare_token", "cloudflare_account_id", "kilo",
}


def _target(name: str) -> str:
    key = str(name).strip().lower()
    if key not in _ALLOWED_NAMES:
        raise ValueError("Unknown FreeLM credential name.")
    return f"NexaAI/FreeLM/{key}"


def _api():
    if os.name != "nt":
        raise RuntimeError("NexaAI cloud credentials require Windows Credential Manager.")
    advapi32 = ctypes.WinDLL("Advapi32.dll", use_last_error=True)
    advapi32.CredWriteW.argtypes = [ctypes.POINTER(_CREDENTIALW), wintypes.DWORD]
    advapi32.CredWriteW.restype = wintypes.BOOL
    advapi32.CredReadW.argtypes = [
        wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
        ctypes.POINTER(ctypes.POINTER(_CREDENTIALW)),
    ]
    advapi32.CredReadW.restype = wintypes.BOOL
    advapi32.CredDeleteW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD]
    advapi32.CredDeleteW.restype = wintypes.BOOL
    advapi32.CredFree.argtypes = [ctypes.c_void_p]
    advapi32.CredFree.restype = None
    return advapi32


def save_secret(name: str, value: str) -> None:
    secret = str(value)
    if not secret:
        raise ValueError("A credential cannot be empty.")
    raw = secret.encode("utf-16-le")
    buffer = ctypes.create_string_buffer(raw, len(raw))
    credential = _CREDENTIALW()
    credential.Type = _CRED_TYPE_GENERIC
    credential.TargetName = _target(name)
    credential.CredentialBlobSize = len(raw)
    credential.CredentialBlob = ctypes.cast(buffer, ctypes.POINTER(ctypes.c_ubyte))
    credential.Persist = _CRED_PERSIST_LOCAL_MACHINE
    credential.UserName = "NexaAI"
    if not _api().CredWriteW(ctypes.byref(credential), 0):
        raise OSError(ctypes.get_last_error(), "Windows Credential Manager could not save this API key.")


def get_secret(name: str) -> str:
    target = _target(name)
    api = _api()
    pointer = ctypes.POINTER(_CREDENTIALW)()
    if not api.CredReadW(target, _CRED_TYPE_GENERIC, 0, ctypes.byref(pointer)):
        error = ctypes.get_last_error()
        if error == _ERROR_NOT_FOUND:
            return ""
        raise OSError(error, "Windows Credential Manager could not read this API key.")
    try:
        credential = pointer.contents
        if not credential.CredentialBlob or not credential.CredentialBlobSize:
            return ""
        raw = ctypes.string_at(credential.CredentialBlob, credential.CredentialBlobSize)
        return raw.decode("utf-16-le")
    finally:
        api.CredFree(pointer)


def delete_secret(name: str) -> None:
    if not _api().CredDeleteW(_target(name), _CRED_TYPE_GENERIC, 0):
        error = ctypes.get_last_error()
        if error != _ERROR_NOT_FOUND:
            raise OSError(error, "Windows Credential Manager could not remove this API key.")


def has_secret(name: str) -> bool:
    return bool(get_secret(name))
