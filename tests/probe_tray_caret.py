"""托盘菜单项 + 光标锚点诊断。"""
from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from PySide6.QtWidgets import QApplication  # noqa: E402

from voicetype.ui.tray import Tray  # noqa: E402
from voicetype.win32 import api  # noqa: E402
from voicetype.win32.caret import CaretTracker  # noqa: E402


def main() -> int:
    app = QApplication(sys.argv)
    tray = Tray()
    print("菜单项:", [a.text() for a in tray.contextMenu().actions() if a.text()])

    hwnd = api.foreground_window()
    print(
        "前台窗口:",
        api.window_class(hwnd),
        api.window_process_name(hwnd),
        "maximized=",
        api.is_maximized(hwnd),
        "rect=",
        api.window_rect(hwnd),
    )
    print("Win32 caret:", api.caret_screen_rect())
    print("mouse      :", api.cursor_pos())

    tracker = CaretTracker()
    tracker.start()
    for i in range(6):
        time.sleep(0.4)
        a = tracker.anchor()
        print(f"anchor[{i}]: x={a.x} top={a.top} bottom={a.bottom} src={a.source} above={a.prefer_above}")
    tracker.stop()
    tray.hide()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
