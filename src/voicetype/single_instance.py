"""单实例互斥。"""
from __future__ import annotations

import ctypes

ERROR_ALREADY_EXISTS = 183

_handle = None


def acquire(name: str = "VoiceType.SingleInstance") -> bool:
    global _handle
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateMutexW.restype = ctypes.c_void_p
    _handle = kernel32.CreateMutexW(None, False, name)
    if not _handle:
        return True
    return ctypes.get_last_error() != ERROR_ALREADY_EXISTS
