"""光标锚点追踪。

优先级：
1. Win32 GetGUIThreadInfo —— 标准输入框最准，几乎零开销
2. UIA TextPattern / 焦点控件矩形 —— 浏览器、Electron（VS Code）等
3. 前景窗口输入区估算 —— 微信这类自绘 Qt 窗口（拿不到控件）

UIA 查询放在后台线程，慢/卡死都不影响 UI。
"""
from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass

from . import api

log = logging.getLogger(__name__)

UIA_TextPatternId = 10014


@dataclass
class Anchor:
    x: int
    top: int
    bottom: int
    source: str
    prefer_above: bool = False


class CaretTracker:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._win32: tuple[int, int, int, int, int, float] | None = None  # l,t,r,b,hwnd,ts
        self._uia: tuple[int, int, int, int, int, float] | None = None
        self._uia_unsupported: int = 0
        self._last_uia_try = 0.0
        self._cursor = (-1, -1)
        self._cursor_moved_at = 0.0
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()

    # ---------------------------------------------------------------- 生命周期
    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, name="caret", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    # ---------------------------------------------------------------- 查询
    def anchor(self) -> Anchor:
        hwnd = api.foreground_window()
        now = time.perf_counter()
        with self._lock:
            win32 = self._win32
            uia = self._uia

        if win32 and win32[4] == hwnd and now - win32[5] < 1.5:
            left, top, right, bottom = win32[:4]
            return Anchor((left + right) // 2, top, bottom, "win32")

        if uia and uia[4] == hwnd and now - uia[5] < 2.0:
            left, top, right, bottom = uia[:4]
            x = (left + right) // 2
            return Anchor(x, top, bottom, "uia")

        return self._window_fallback(hwnd)

    def _window_fallback(self, hwnd: int) -> Anchor:
        rect = api.window_rect(hwnd)
        mx, my = api.cursor_pos()
        if not rect:
            return Anchor(mx, my, my + 20, "cursor", prefer_above=True)

        left, top, right, bottom = rect
        width, height = right - left, bottom - top

        # 鼠标刚动过、且停在窗口内部 —— 多半是在点输入框，用鼠标位置
        recently_moved = time.perf_counter() - self._cursor_moved_at < 3.0
        margin = 80
        if (
            recently_moved
            and left + margin < mx < right - margin
            and top + margin < my < bottom - margin
            and height > 300
        ):
            return Anchor(mx, my, my + 20, "cursor")

        if api.is_maximized(hwnd) or height > 700:
            # 大型窗口：输入框通常在底部，锚到窗口底部偏上一点，浮层放在它上面
            x = left + int(width * 0.55)
            y = bottom - 180
            return Anchor(x, y, y, "window-bottom", prefer_above=True)

        return Anchor((left + right) // 2, bottom - 24, bottom - 24, "window", prefer_above=True)

    # ---------------------------------------------------------------- 后台线程
    def _loop(self) -> None:
        self._co_init()
        while not self._stop.is_set():
            try:
                self._poll_once()
            except Exception:
                log.debug("光标轮询异常", exc_info=True)
            time.sleep(0.2)
        self._co_uninit()

    def _poll_once(self) -> None:
        hwnd = api.foreground_window()
        if not hwnd:
            return
        now = time.perf_counter()
        pos = api.cursor_pos()
        if pos != self._cursor:
            self._cursor = pos
            self._cursor_moved_at = now
        rect = api.caret_screen_rect()
        if rect and rect[2] > rect[0] and rect[3] > rect[1]:
            with self._lock:
                self._win32 = (*rect, hwnd, now)
            return
        if hwnd == self._uia_unsupported:
            return
        if now - self._last_uia_try < 0.8:
            return
        self._last_uia_try = now
        result = _uia_query(hwnd)
        if result == "unsupported":
            with self._lock:
                self._uia_unsupported = hwnd
            log.debug("UIA 不支持该窗口: %s", api.window_class(hwnd))
            return
        if result is None:
            return
        with self._lock:
            self._uia = (*result, hwnd, now)

    @staticmethod
    def _co_init() -> None:
        try:
            import comtypes

            comtypes.CoInitialize()
        except Exception:
            pass

    @staticmethod
    def _co_uninit() -> None:
        try:
            import comtypes

            comtypes.CoUninitialize()
        except Exception:
            pass


# ---------------------------------------------------------------- UIA
_uia = None
_uia_mod = None


def _uia_query(hwnd: int) -> tuple[int, int, int, int] | str | None:
    """返回焦点控件/选区的屏幕矩形；"unsupported" 表示该窗口只暴露窗口级元素。"""
    global _uia, _uia_mod
    try:
        import comtypes.client

        if _uia is None:
            try:
                # 打包版直接使用随包附带、构建时生成的类型库
                from comtypes.gen import UIAutomationClient as mod
            except Exception:
                comtypes.client.GetModule("UIAutomationCore.dll")
                from comtypes.gen import UIAutomationClient as mod

            _uia_mod = mod
            _uia = comtypes.client.CreateObject(
                mod.CUIAutomation, interface=mod.IUIAutomation
            )
        assert _uia_mod is not None
        el = _uia.GetFocusedElement()
        if el is None:
            return None

        # 1) 文本选区（最精确）
        try:
            pat = el.GetCurrentPattern(UIA_TextPatternId)
            tp = pat.QueryInterface(_uia_mod.IUIAutomationTextPattern)
            sel = tp.GetSelection()
            if sel and sel.Length > 0:
                rng = sel.GetElement(0)
                rects = rng.GetBoundingRectangles()
                if rects and len(rects) >= 4:
                    left, top, w, h = rects[0], rects[1], rects[2], rects[3]
                    if w >= 0 and h > 0:
                        return (int(left), int(top), int(left + w), int(top + h))
        except Exception:
            pass

        # 2) 焦点控件矩形：只有"小控件"才可信（控件本身就是输入框时）
        try:
            r = el.CurrentBoundingRectangle
            left, top, right, bottom = r.left, r.top, r.right, r.bottom
            if right - left <= 0 or bottom - top <= 0:
                return "unsupported"
            wrect = api.window_rect(hwnd)
            if wrect:
                ww, wh = wrect[2] - wrect[0], wrect[3] - wrect[1]
                # 和窗口一样大 => 只是窗口级元素，没有参考价值
                if (right - left) > ww * 0.9 and (bottom - top) > wh * 0.6:
                    return "unsupported"
            return (int(left), int(top), int(right), int(bottom))
        except Exception:
            return None
    except Exception:
        return None
