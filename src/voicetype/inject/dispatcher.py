"""注入方式调度：按目标窗口决定粘贴还是逐字。"""
from __future__ import annotations

import logging
from dataclasses import dataclass

from ..config import Config
from ..win32 import api
from . import clipboard, sendinput

log = logging.getLogger(__name__)

# 这些窗口 Ctrl+V 不生效或行为异常，强制逐字
TERMINAL_CLASSES = {
    "consolewindowclass",              # cmd / powershell (conhost)
    "cascadia_hosting_window_class",   # Windows Terminal
    "mintty",
    "putty",
    "windowsterminal",
}
TERMINAL_EXES = {"windowsterminal.exe", "cmd.exe", "powershell.exe", "pwsh.exe", "mintty.exe", "putty.exe"}


@dataclass
class InjectResult:
    ok: bool
    method: str
    text: str


def choose_method(cfg: Config, hwnd: int) -> str:
    global_method = (cfg.get("inject.method", "auto") or "auto").lower()
    if global_method in ("paste", "type"):
        return global_method

    cls = api.window_class(hwnd).lower()
    exe = api.window_process_name(hwnd)

    rules = cfg.get("inject.app_rules", {}) or {}
    for key, method in rules.items():
        k = str(key).lower()
        if k and (k == cls or k == exe) and method in ("paste", "type"):
            return method

    if cls in TERMINAL_CLASSES or exe in TERMINAL_EXES:
        return "type"
    return "paste"


def inject_text(text: str, cfg: Config) -> InjectResult:
    if not text:
        return InjectResult(False, "none", text)
    hwnd = api.foreground_window()
    method = choose_method(cfg, hwnd)
    log.info("注入 %d 字 via %s -> %s(%s)", len(text), method, api.window_class(hwnd), api.window_process_name(hwnd))

    if method == "type":
        ok = sendinput.type_text(text)
    else:
        ok = clipboard.paste_text(
            text,
            restore_delay=int(cfg.get("inject.restore_delay_ms", 350)) / 1000.0,
            do_restore=bool(cfg.get("inject.restore_clipboard", True)),
        )
    return InjectResult(ok, method, text)


def undo_last(count: int) -> None:
    sendinput.undo_chars(count)
