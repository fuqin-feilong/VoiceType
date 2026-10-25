"""实时预览端到端验证：模拟"边说边录"的音频缓冲，检查预览文本与最终注入。

python tests/probe_live.py
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

WAV = "zh_chat.wav"
GROW_SECONDS = 3.6

results: list[str] = []
previews: list[str] = []
state = {"phase": "focus", "stable": 0, "t0": 0.0, "done": None, "shot": False}


class Window(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("VoiceType live probe")
        self.resize(900, 360)
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
    cfg.set("ui.live_preview", True, save=False)
    ctrl = VoiceTypeApp(cfg)
    ctrl.engine = WhisperEngine(
        str(cfg.get("asr.model")), paths.models_dir(), str(cfg.get("asr.device", "auto")), "auto"
    )
    t0 = time.perf_counter()
    ctrl.engine.load()
    ctrl.engine_ready = True
    log(f"引擎就绪 {time.perf_counter()-t0:.1f}s {ctrl.engine.device_used}")

    audio = read_wav(ROOT / "tests" / "data" / WAV)
    log(f"音频 {audio.size/16000:.1f}s")

    # 用增长的时间模拟录音缓冲
    ctrl.recorder.start = lambda: None  # type: ignore[method-assign]
    ctrl.recorder.stop = lambda: audio  # type: ignore[method-assign]
    ctrl.recorder.snapshot = lambda: audio[  # type: ignore[method-assign]
        : max(0, int(audio.size * min(1.0, (time.perf_counter() - state["t0"]) / GROW_SECONDS)))
    ]

    def on_preview(text: str, gen: int) -> None:
        previews.append(text)

    ctrl.sig_preview.connect(on_preview)
    ctrl.sig_job_done.connect(lambda r: state.update(done=r))

    def tick() -> None:
        if state["phase"] == "focus":
            if api.foreground_window() != int(w.winId()):
                api.set_foreground(int(w.winId()))
                w.edit.setFocus()
                state["stable"] = 0
                return
            state["stable"] += 1
            if state["stable"] < 4:
                return
            log("开始「说话」")
            state["t0"] = time.perf_counter()
            state["phase"] = "speaking"
            ctrl._on_press("right_ctrl")
            return

        if state["phase"] == "speaking":
            elapsed = time.perf_counter() - state["t0"]
            if not state["shot"] and elapsed > 2.0:
                state["shot"] = True
                out = ROOT / "tests" / "ui"
                out.mkdir(parents=True, exist_ok=True)
                ctrl.hud.grab().save(str(out / "hud_live.png"))
                log(f"预览快照 t={elapsed:.1f}s: {previews[-1] if previews else '(空)'}")
            if elapsed >= GROW_SECONDS:
                log(f"松手，共收到 {len(previews)} 次预览")
                state["phase"] = "waiting"
                ctrl._on_release("right_ctrl", GROW_SECONDS)
            return

        if state["phase"] == "waiting" and state["done"] is not None:
            res = state["done"]
            got = w.edit.toPlainText()
            log(f"预览序列: {previews}")
            log(f"最终: {got!r}")
            ok = "文件发给他" in got and "明天的会几点开始" in got
            log(f"结果: {'PASS' if ok else 'FAIL'}")
            log(f"预览次数: {len(previews)}（期望 >= 2）")
            state["phase"] = "end"
            (ROOT / "tests" / "live_result.txt").write_text("\n".join(results), encoding="utf-8")
            QTimer.singleShot(200, ctrl.quit)
            return

    timer = QTimer()
    timer.timeout.connect(tick)
    timer.start(100)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
