"""端到端验证：音频 -> 识别 -> 文本处理 -> 注入 -> 结果校验。

不经过麦克风，直接喂 wav；同时验证 HUD 浮层不会抢走焦点。
python tests/probe_e2e.py
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

from PySide6.QtCore import Qt, QTimer  # noqa: E402
from PySide6.QtWidgets import QApplication, QTextEdit, QVBoxLayout, QWidget  # noqa: E402

from probe_asr import read_wav  # noqa: E402
from voicetype import paths  # noqa: E402
from voicetype.app import VoiceTypeApp  # noqa: E402
from voicetype.asr.whisper_engine import WhisperEngine  # noqa: E402
from voicetype.config import Config  # noqa: E402
from voicetype.win32 import api  # noqa: E402

CASES = [
    ("right_ctrl", "zh_chat.wav"),
    ("right_alt", "en_code.wav"),
    ("right_ctrl", "mixed.wav"),
]
EXPECT = {
    "zh_chat.wav": ("帮我把这个文件发给他", "明天的会几点开始"),
    "en_code.wav": ("Refactor the auth middleware", "unit tests"),
    "mixed.wav": ("API", "timeout"),
}

results: list[str] = []
state = {"i": 0, "stable": 0, "done": None, "waiting": False}


class Window(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("VoiceType e2e probe")
        self.resize(820, 320)
        lay = QVBoxLayout(self)
        self.edit = QTextEdit()
        lay.addWidget(self.edit)


def log(msg: str) -> None:
    results.append(msg)
    print(msg)


def main() -> int:
    app = QApplication(sys.argv)
    w = Window()
    w.show()
    w.raise_()
    w.activateWindow()

    cfg = Config()
    ctrl = VoiceTypeApp(cfg)
    ctrl.engine = WhisperEngine(
        str(cfg.get("asr.model")),
        paths.models_dir(),
        str(cfg.get("asr.device", "auto")),
        "auto",
    )
    t0 = time.perf_counter()
    ctrl.engine.load()
    ctrl.engine_ready = True
    log(f"引擎就绪 {time.perf_counter()-t0:.1f}s device={ctrl.engine.device_used}")

    ctrl.sig_job_done.connect(lambda r: state.update(done=r))

    def tick() -> None:
        if state["i"] >= len(CASES):
            (ROOT / "tests" / "e2e_result.txt").write_text(
                "\n".join(results), encoding="utf-8"
            )
            ctrl.quit()
            return

        if state["waiting"]:
            if state["done"] is None:
                return
            name = CASES[state["i"]][1]
            got = w.edit.toPlainText()
            musts = EXPECT[name]
            low = got.lower()
            ok = all(m.lower() in low for m in musts)
            fg = api.foreground_window()
            log(
                f"{name:15s} {'PASS' if ok else 'FAIL'}  fg_ok={fg == int(w.winId())}  {got!r}"
            )
            if not ok:
                log(f"  缺少关键词: {[m for m in musts if m.lower() not in low]}")
            w.edit.clear()
            state["i"] += 1
            state["done"] = None
            state["waiting"] = False
            state["stable"] = 0
            return

        if api.foreground_window() != int(w.winId()):
            api.set_foreground(int(w.winId()))
            w.edit.setFocus()
            state["stable"] = 0
            return
        state["stable"] += 1
        if state["stable"] < 4:
            return

        name, wav = CASES[state["i"]]
        audio = read_wav(ROOT / "tests" / "data" / wav)
        log(f"提交 {wav} ({audio.size/16000:.1f}s) key={name}")
        ctrl._submit(audio, name)
        state["waiting"] = True
        state["stable"] = 0

    timer = QTimer()
    timer.timeout.connect(tick)
    timer.start(150)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
