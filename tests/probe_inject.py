"""端到端注入验证：把文字打进一个 Qt 文本框，再读回来比对。

python tests/probe_inject.py
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from PySide6.QtCore import Qt, QTimer  # noqa: E402
from PySide6.QtWidgets import QApplication, QTextEdit, QVBoxLayout, QWidget  # noqa: E402

from voicetype import inject  # noqa: E402
from voicetype.config import Config  # noqa: E402
from voicetype.win32 import api  # noqa: E402

TEXT_CN = "帮我把这个文件发给他，顺便问一下明天的会几点开始。"
TEXT_EN = "Refactor the auth middleware and add unit tests."
TEXT_MIX = "这个 API 的 response 需要加一个 timeout 参数。"

results: list[str] = []


def log(msg: str) -> None:
    results.append(msg)


class Window(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("VoiceType inject probe")
        self.resize(760, 320)
        lay = QVBoxLayout(self)
        self.edit = QTextEdit()
        self.edit.setPlaceholderText("这里应该出现注入的文字")
        lay.addWidget(self.edit)

    def inject(self, text: str, method: str) -> bool:
        cfg = Config()
        cfg.set("inject.method", method, save=False)
        cfg.set("inject.restore_clipboard", True, save=False)
        self.edit.setFocus(Qt.FocusReason.OtherFocusReason)
        focused = api.foreground_window() == int(self.winId())
        log(f"  [focused={focused}]")
        if not focused:
            return False
        inject.inject_text(text, cfg)
        return True


def main() -> int:
    app = QApplication(sys.argv)
    w = Window()
    w.show()
    w.raise_()
    w.activateWindow()

    steps = [
        ("paste zh", TEXT_CN, "paste"),
        ("paste en", TEXT_EN, "paste"),
        ("type mixed", TEXT_MIX, "type"),
        ("type zh", TEXT_CN, "type"),
    ]
    state = {"i": 0, "waiting": False, "sent_at": 0.0, "sent_text": "", "stable": 0}

    def check() -> None:
        got = w.edit.toPlainText()
        name, text, _ = steps[state["i"]]
        ok = got == text
        log(f"{name}: {'PASS' if ok else 'FAIL'}")
        if not ok:
            log(f"  expected={text!r}")
            log(f"  got     ={got!r}")
        w.edit.clear()
        state["i"] += 1
        state["waiting"] = False

    def tick() -> None:
        if state["i"] >= len(steps):
            out = ROOT / "tests" / "inject_result.txt"
            out.write_text("\n".join(results), encoding="utf-8")
            print("\n".join(results))
            app.quit()
            return

        if state["waiting"]:
            if time.perf_counter() - state["sent_at"] > 0.9:
                check()
            return

        # 先把窗口真正切到前台，并稳定 300ms 再注入（等 Qt 处理完 focus-in）
        if api.foreground_window() != int(w.winId()):
            api.set_foreground(int(w.winId()))
            w.edit.setFocus()
            state["stable"] = 0
            return
        state["stable"] += 1
        if state["stable"] < 4:
            return

        name, text, method = steps[state["i"]]
        if w.inject(text, method):
            state["waiting"] = True
            state["sent_at"] = time.perf_counter()
            state["stable"] = 0

    timer = QTimer()
    timer.timeout.connect(tick)
    timer.start(100)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
