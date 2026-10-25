"""开机自启（HKCU Run）。"""
from __future__ import annotations

import logging
import sys
import winreg
from pathlib import Path

from . import paths

log = logging.getLogger(__name__)
RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
VALUE_NAME = "VoiceType"


def _command() -> str:
    if paths.is_frozen():
        return f'"{sys.executable}"'
    py = Path(sys.executable)
    pythonw = py.with_name("pythonw.exe")
    exe = pythonw if pythonw.exists() else py
    return f'"{exe}" -m voicetype'


def is_enabled() -> bool:
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
            value, _ = winreg.QueryValueEx(key, VALUE_NAME)
            return bool(value)
    except FileNotFoundError:
        return False
    except OSError:
        return False


def set_enabled(enabled: bool) -> None:
    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE
        ) as key:
            if enabled:
                winreg.SetValueEx(key, VALUE_NAME, 0, winreg.REG_SZ, _command())
                log.info("已设置开机自启: %s", _command())
            else:
                try:
                    winreg.DeleteValue(key, VALUE_NAME)
                    log.info("已取消开机自启")
                except FileNotFoundError:
                    pass
    except OSError:
        log.exception("设置开机自启失败")
