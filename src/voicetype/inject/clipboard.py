"""剪贴板粘贴注入：最快、最稳，适合普通应用与中文长文本。"""
from __future__ import annotations

import logging
import threading
import time
from typing import Any

import win32clipboard as cb
import win32con

from ..win32 import api

log = logging.getLogger(__name__)

FORMAT_HTML = cb.RegisterClipboardFormat("HTML Format")
FORMAT_RTF = cb.RegisterClipboardFormat("Rich Text Format")

# 这些格式无法安全地往返（延迟渲染/句柄类），跳过
_SKIP_FORMATS = {
    win32con.CF_OWNERDISPLAY,
    win32con.CF_BITMAP,
    win32con.CF_DSPBITMAP,
    win32con.CF_METAFILEPICT,
    win32con.CF_DSPMETAFILEPICT,
    win32con.CF_DSPTEXT,
    win32con.CF_PALETTE,
}


def _open(retries: int = 8, delay: float = 0.02) -> bool:
    for _ in range(retries):
        try:
            cb.OpenClipboard()
            return True
        except Exception:
            time.sleep(delay)
    return False


def snapshot() -> dict[int, Any] | None:
    if not _open():
        log.warning("剪贴板被占用，无法备份")
        return None
    data: dict[int, Any] = {}
    try:
        fmt = 0
        while True:
            fmt = cb.EnumClipboardFormats(fmt)
            if not fmt:
                break
            if fmt in _SKIP_FORMATS:
                continue
            try:
                data[fmt] = cb.GetClipboardData(fmt)
            except Exception:
                continue
    finally:
        try:
            cb.CloseClipboard()
        except Exception:
            pass
    return data


def restore(data: dict[int, Any] | None) -> None:
    if data is None:
        return
    if not _open():
        return
    try:
        cb.EmptyClipboard()
        for fmt, value in data.items():
            try:
                cb.SetClipboardData(fmt, value)
            except Exception as e:
                log.debug("恢复剪贴板格式 %s 失败: %s", fmt, e)
    finally:
        try:
            cb.CloseClipboard()
        except Exception:
            pass


def set_text(text: str) -> bool:
    if not _open():
        return False
    try:
        cb.EmptyClipboard()
        cb.SetClipboardData(win32con.CF_UNICODETEXT, text)
        return True
    finally:
        try:
            cb.CloseClipboard()
        except Exception:
            pass


def get_text() -> str | None:
    if not _open():
        return None
    try:
        if cb.IsClipboardFormatAvailable(win32con.CF_UNICODETEXT):
            return cb.GetClipboardData(win32con.CF_UNICODETEXT)
        return None
    except Exception:
        return None
    finally:
        try:
            cb.CloseClipboard()
        except Exception:
            pass


def paste_text(text: str, restore_delay: float = 0.35, do_restore: bool = True) -> bool:
    """把 text 放进剪贴板并发送 Ctrl+V。"""
    backup = snapshot() if do_restore else None
    if not set_text(text):
        log.error("写入剪贴板失败")
        return False
    # 等热键修饰键松开，避免 Ctrl 叠加
    api.wait_release(api.VK["right_ctrl"], 0.2)
    api.wait_release(api.VK["right_alt"], 0.2)
    api.send_ctrl_v()
    if do_restore:
        threading.Timer(
            max(0.05, restore_delay), _restore_if_unchanged, args=(backup, text)
        ).start()
    return True


def _restore_if_unchanged(backup: dict[int, Any] | None, sent: str) -> None:
    try:
        if get_text() != sent:
            log.debug("剪贴板已被用户修改，跳过恢复")
            return
        restore(backup)
    except Exception:
        log.exception("恢复剪贴板异常")
