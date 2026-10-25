"""逐字注入：用于终端、部分不认粘贴的编辑器。"""
from __future__ import annotations

import logging

from ..win32 import api

log = logging.getLogger(__name__)


def type_text(text: str) -> bool:
    try:
        api.wait_release(api.VK["right_ctrl"], 0.2)
        api.wait_release(api.VK["right_alt"], 0.2)
        api.type_text(text)
        return True
    except Exception:
        log.exception("逐字注入失败")
        return False


def undo_chars(count: int) -> None:
    api.send_backspaces(min(count, 2000))
