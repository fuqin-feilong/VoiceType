"""光标定位能力诊断：GUIThreadInfo vs UIA。"""
from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from voicetype.win32 import api  # noqa: E402


def main() -> int:
    hwnd = api.foreground_window()
    print("foreground:", api.window_class(hwnd), api.window_process_name(hwnd))
    print("gui_rect:", api.caret_screen_rect())
    print("cursor  :", api.cursor_pos())

    import uiautomation as auto

    for i in range(3):
        t = time.perf_counter()
        try:
            pos = auto.GetCaretPos()
        except Exception as e:
            pos = f"ERR {e}"
        print(f"uia[{i}]: {pos}  {(time.perf_counter()-t)*1000:.0f}ms")
        time.sleep(0.2)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
