"""长句实时预览验证：25 秒连续说话，检查不丢前半段、不出现英文乱码。"""
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

WAV = "long_zh.wav"
GROW_SECONDS = 25.0

results: list[str] = []
previews: list[tuple[float, str]] = []
state = {"phase": "focus", "stable": 0, "t0": 0.0, "done": None, "shot": False, "fg_lost": 0}


class Window(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("VoiceType long probe")
        self.resize(900, 360)
        lay = QVBoxLayout(self)
        self.edit = QTextEdit()
        lay.addWidget(self.edit)


def log(msg: str) -> None:
    results.append(msg)
    print(msg)


def cjk_ratio(text: str) -> float:
    if not text:
        return 0.0
    cjk = sum(1 for ch in text if "\u4e00" <= ch <= "\u9fff")
    return cjk / max(1, len(text.replace(" ", "")))


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

    ctrl.recorder.start = lambda: None  # type: ignore[method-assign]
    ctrl.recorder.stop = lambda: audio  # type: ignore[method-assign]
    ctrl.recorder.snapshot = lambda: audio[  # type: ignore[method-assign]
        : max(0, int(audio.size * min(1.0, (time.perf_counter() - state["t0"]) / GROW_SECONDS)))
    ]

    def on_preview(text: str, gen: int) -> None:
        previews.append((time.perf_counter() - state["t0"], text))

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
            if api.foreground_window() != int(w.winId()):
                state["fg_lost"] += 1
                if state["fg_lost"] == 1:
                    log(f"!! 焦点在 t={elapsed:.1f}s 被抢走: {api.window_class(api.foreground_window())}")
                api.set_foreground(int(w.winId()))
                w.edit.setFocus()
            if not state["shot"] and elapsed > 18:
                state["shot"] = True
                out = ROOT / "tests" / "ui"
                out.mkdir(parents=True, exist_ok=True)
                ctrl.hud.grab().save(str(out / "hud_long_live.png"))
                log(f"快照 t={elapsed:.1f}s: {previews[-1][1][-40:] if previews else '(空)'}")
            if elapsed >= GROW_SECONDS:
                log(f"松手，共收到 {len(previews)} 次预览")
                state["phase"] = "waiting"
                ctrl._on_release("right_ctrl", GROW_SECONDS)
            return

        if state["phase"] == "waiting" and state["done"] is not None:
            res = state["done"]
            got = w.edit.toPlainText()
            log(
                f"任务 ok={res.ok} error={res.error!r} message={res.message!r} "
                f"raw={len(res.raw)}字 final={len(res.final)}字"
            )
            log("\n预览序列:")
            for t, text in previews:
                log(f"  t={t:5.1f}s cjk={cjk_ratio(text):.2f} {text[-60:]}")
            log(f"\n最终: {got!r}")
            log(f"焦点丢失次数: {state['fg_lost']}")

            late = [(t, text) for t, text in previews if t > 5]
            bad = [(round(t, 1), text[:18]) for t, text in late if "帮我把这个文件" not in text]
            log(f"缺少开头的预览: {bad}")

            keeps_start = bool(late) and all("帮我把这个文件" in t[1] for t in late)
            no_english = bool(late) and all(cjk_ratio(t[1]) > 0.5 for t in late)
            final_ok = "文件发给他" in got and "Timeout" in got
            log(f"\n长句保留前半段: {'PASS' if keeps_start else 'FAIL'}")
            log(f"预览均为中文: {'PASS' if no_english else 'FAIL'}")
            log(f"最终结果完整: {'PASS' if final_ok else 'FAIL'}")
            log(f"预览次数: {len(previews)}")

            (ROOT / "tests" / "long_live_result.txt").write_text(
                "\n".join(results), encoding="utf-8"
            )
            state["phase"] = "end"
            QTimer.singleShot(200, ctrl.quit)
            return

    timer = QTimer()
    timer.timeout.connect(tick)
    timer.start(100)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
