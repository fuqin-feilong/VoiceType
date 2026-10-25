"""全局热键监听：轮询 GetAsyncKeyState，不使用键盘钩子。

优点：不注入任何进程、不注册 WH_KEYBOARD_LL，杀软/反作弊友好；
缺点：10ms 轮询有极轻微延迟（可忽略），且需要按键本身可被 GetAsyncKeyState 观测。
"""
from __future__ import annotations

import logging
import threading
import time
from typing import Callable

from .win32 import api

log = logging.getLogger(__name__)


class HotkeyListener:
    def __init__(
        self,
        bindings: dict[str, int],
        on_press: Callable[[str], None],
        on_release: Callable[[str, float], None],
        on_cancel: Callable[[], None] | None = None,
        poll_ms: int = 10,
    ):
        self._bindings = dict(bindings)
        self._on_press = on_press
        self._on_release = on_release
        self._on_cancel = on_cancel
        self._poll = max(poll_ms, 5) / 1000.0
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._active: str | None = None
        self._started_at = 0.0
        self._cancel_sent = False

    def start(self) -> None:
        self._thread = threading.Thread(
            target=self._run, name="hotkey", daemon=True
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=1.0)

    @property
    def active(self) -> bool:
        return self._active is not None

    def _run(self) -> None:
        log.info("热键监听已启动: %s", self._bindings)
        while not self._stop.is_set():
            try:
                self._tick()
            except Exception:
                log.exception("热键轮询异常")
                time.sleep(0.5)
            time.sleep(self._poll)

    def _tick(self) -> None:
        if self._active is None:
            for name, vk in self._bindings.items():
                if api.is_key_down(vk):
                    self._active = name
                    self._started_at = time.perf_counter()
                    self._cancel_sent = False
                    log.debug("按下热键 %s", name)
                    self._safe(self._on_press, name)
                    return
            return

        # 录音中：支持 Esc 取消
        if not self._cancel_sent and api.is_key_down(api.VK["escape"]):
            self._cancel_sent = True
            if self._on_cancel:
                self._safe(self._on_cancel)

        vk = self._bindings.get(self._active)
        if vk is None or not api.is_key_down(vk):
            name = self._active
            duration = time.perf_counter() - self._started_at
            self._active = None
            log.debug("松开热键 %s (%.0fms)", name, duration * 1000)
            self._safe(self._on_release, name, duration)

    @staticmethod
    def _safe(fn, *args) -> None:
        try:
            fn(*args)
        except Exception:
            log.exception("热键回调异常")


def resolve_binding(name: str) -> int | None:
    return api.VK.get(name)
