from __future__ import annotations

import ctypes
import os
from ctypes import wintypes


TARGET_NAME = "BanglaSubtitleStudio/OpenAIAPIKey"
CRED_TYPE_GENERIC = 1
CRED_PERSIST_LOCAL_MACHINE = 2
ERROR_NOT_FOUND = 1168


class CredentialStoreError(RuntimeError):
    pass


class _CREDENTIALW(ctypes.Structure):
    _fields_ = [
        ("Flags", wintypes.DWORD),
        ("Type", wintypes.DWORD),
        ("TargetName", wintypes.LPWSTR),
        ("Comment", wintypes.LPWSTR),
        ("LastWritten", wintypes.FILETIME),
        ("CredentialBlobSize", wintypes.DWORD),
        ("CredentialBlob", ctypes.POINTER(ctypes.c_ubyte)),
        ("Persist", wintypes.DWORD),
        ("AttributeCount", wintypes.DWORD),
        ("Attributes", ctypes.c_void_p),
        ("TargetAlias", wintypes.LPWSTR),
        ("UserName", wintypes.LPWSTR),
    ]


def _wincred() -> ctypes.WinDLL:
    if os.name != "nt":
        raise CredentialStoreError("Windows Credential Manager শুধু Windows-এ পাওয়া যায়।")
    return ctypes.WinDLL("advapi32", use_last_error=True)


def save_api_key(api_key: str) -> None:
    secret = api_key.strip()
    if not secret:
        raise CredentialStoreError("API key খালি রাখা যাবে না।")
    encoded = secret.encode("utf-8")
    blob = (ctypes.c_ubyte * len(encoded)).from_buffer_copy(encoded)
    credential = _CREDENTIALW()
    credential.Type = CRED_TYPE_GENERIC
    credential.TargetName = TARGET_NAME
    credential.Comment = "Bangla Subtitle Studio OpenAI API key"
    credential.CredentialBlobSize = len(encoded)
    credential.CredentialBlob = ctypes.cast(blob, ctypes.POINTER(ctypes.c_ubyte))
    credential.Persist = CRED_PERSIST_LOCAL_MACHINE
    credential.UserName = "OpenAI"

    api = _wincred()
    api.CredWriteW.argtypes = [ctypes.POINTER(_CREDENTIALW), wintypes.DWORD]
    api.CredWriteW.restype = wintypes.BOOL
    if not api.CredWriteW(ctypes.byref(credential), 0):
        error = ctypes.get_last_error()
        raise CredentialStoreError(f"Windows Credential Manager-এ key Save হয়নি (error {error})।")


def load_api_key() -> str:
    if os.name != "nt":
        return ""
    api = _wincred()
    pointer = ctypes.POINTER(_CREDENTIALW)()
    api.CredReadW.argtypes = [
        wintypes.LPCWSTR,
        wintypes.DWORD,
        wintypes.DWORD,
        ctypes.POINTER(ctypes.POINTER(_CREDENTIALW)),
    ]
    api.CredReadW.restype = wintypes.BOOL
    api.CredFree.argtypes = [ctypes.c_void_p]
    api.CredFree.restype = None
    if not api.CredReadW(TARGET_NAME, CRED_TYPE_GENERIC, 0, ctypes.byref(pointer)):
        error = ctypes.get_last_error()
        if error == ERROR_NOT_FOUND:
            return ""
        raise CredentialStoreError(f"Windows Credential Manager থেকে key পড়া যায়নি (error {error})।")
    try:
        credential = pointer.contents
        if not credential.CredentialBlob or not credential.CredentialBlobSize:
            return ""
        raw = ctypes.string_at(credential.CredentialBlob, credential.CredentialBlobSize)
        return raw.decode("utf-8")
    except (UnicodeDecodeError, ValueError) as exc:
        raise CredentialStoreError("Save করা API key পড়া যায়নি।") from exc
    finally:
        api.CredFree(pointer)


def delete_api_key() -> None:
    if os.name != "nt":
        return
    api = _wincred()
    api.CredDeleteW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD]
    api.CredDeleteW.restype = wintypes.BOOL
    if not api.CredDeleteW(TARGET_NAME, CRED_TYPE_GENERIC, 0):
        error = ctypes.get_last_error()
        if error != ERROR_NOT_FOUND:
            raise CredentialStoreError(f"Save করা API key মুছতে সমস্যা হয়েছে (error {error})।")

