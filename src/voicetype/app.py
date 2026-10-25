"""应用主控：热键 → 录音 → 识别 → 文本处理 → 注入。"""
from __future__ import annotations

import logging
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PySide6.QtCore import QObject, QTimer, Signal
from PySide6.QtWidgets import QApplication, QDialog

from . import __version__, autostart, inject, paths
from .asr.downloader import ensure_model
from .asr.whisper_engine import WhisperEngine
from .audio import Recorder
from .config import Config
from .hotkey import HotkeyListener, resolve_binding
from .text import commands
from .text.pipeline import process
from .ui.hud import Hud
from .ui.settings import SettingsDialog
from .ui.tray import Tray
from .win32 import api
from .win32.caret import CaretTracker

log = logging.getLogger(__name__)


@dataclass
class JobResult:
    ok: bool = False
    raw: str = ""
    final: str = ""
    message: str = ""
    error: str = ""
    hwnd: int = 0
    elapsed: float = 0.0


class VoiceTypeApp(QObject):
    sig_press = Signal(str)
    sig_release = Signal(str, float)
    sig_cancel = Signal()
    sig_level = Signal(float)
    sig_status = Signal(str)
    sig_preload_done = Signal(bool, str)
    sig_job_done = Signal(object)
    sig_preview = Signal(str, int)

    def __init__(self, cfg: Config):
        super().__init__()
        self.cfg = cfg

        self.engine: WhisperEngine | None = None
        self.engine_ready = False
        self._loading = False
        self._busy = False
        self._recording = False
        self._active_key = ""
        self._press_t0 = 0.0
        self._cancelled = False
        self._last_insert: tuple[str, int, float] | None = None

        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="asr")

        self.caret_tracker = CaretTracker()
        self.hud = Hud(
            self.caret_tracker, theme=str(cfg.get("ui.theme", "dark"))
        )
        self.tray = Tray(
            code_mode=bool(cfg.get("text.code_mode", False)),
            theme=str(cfg.get("ui.theme", "dark")),
        )
        self.recorder = Recorder(
            device=cfg.get("audio.device"),
            samplerate=int(cfg.get("audio.samplerate", 16000)),
        )
        self.recorder.set_level_callback(self.sig_level.emit)
        self._hotkeys: HotkeyListener | None = None

        self._max_timer = QTimer(self)
        self._max_timer.setSingleShot(True)
        self._max_timer.timeout.connect(self._force_finish)

        # 实时预览
        self._preview_timer = QTimer(self)
        self._preview_timer.setInterval(800)
        self._preview_timer.timeout.connect(self._preview_tick)
        self._preview_gen = 0
        self._preview_inflight = False
        self._preview_lang: str | None = None
        self._preview_samples = 0
        self._preview_text = ""
        self._preview_shrinks = 0

        # 线程 → 主线程
        self.sig_press.connect(self._on_press)
        self.sig_release.connect(self._on_release)
        self.sig_cancel.connect(self._on_cancel)
        self.sig_level.connect(self._on_level)
        self.sig_status.connect(self._on_status)
        self.sig_preload_done.connect(self._on_preload_done)
        self.sig_job_done.connect(self._on_job_done)
        self.sig_preview.connect(self._on_preview)

        # 托盘
        self.tray.settings_requested.connect(self.open_settings)
        self.tray.quit_requested.connect(self.quit)
        self.tray.undo_requested.connect(self._undo_from_tray)
        self.tray.logs_requested.connect(self._open_logs)
        self.tray.code_mode_toggled.connect(self._on_code_mode_toggled)

    # ---------------------------------------------------------------- 启动
    def start(self) -> None:
        autostart.set_enabled(bool(self.cfg.get("ui.start_with_windows", False)))
        self.tray.show()
        self.tray.set_status("模型加载中…")
        self._start_hotkeys()
        self.caret_tracker.start()
        self.recorder.preopen()
        self._preload()

    def _start_hotkeys(self) -> None:
        if self._hotkeys:
            self._hotkeys.stop()
        bindings: dict[str, int] = {}
        for key in ("ptt_auto", "ptt_en", "ptt_extra"):
            name = self.cfg.get(f"hotkeys.{key}")
            if not name or name in bindings:
                continue
            vk = resolve_binding(str(name))
            if vk is None:
                log.warning("未知按键: %s", name)
                continue
            bindings[str(name)] = vk
        if not bindings:
            log.error("没有可用的热键绑定")
            return
        self._hotkeys = HotkeyListener(
            bindings,
            on_press=self.sig_press.emit,
            on_release=self.sig_release.emit,
            on_cancel=self.sig_cancel.emit,
        )
        self._hotkeys.start()

    def _preload(self) -> None:
        if self._loading:
            return
        self._loading = True
        self.engine_ready = False
        model_name = str(self.cfg.get("asr.model", "large-v3-turbo"))
        self.engine = WhisperEngine(
            model_name=model_name,
            models_dir=paths.models_dir(),
            device=str(self.cfg.get("asr.device", "auto")),
            compute_type=str(self.cfg.get("asr.compute_type", "auto")),
            beam_size=int(self.cfg.get("asr.beam_size", 5)),
            vad_filter=bool(self.cfg.get("asr.vad_filter", True)),
            auto_prompt=bool(self.cfg.get("asr.auto_prompt", True)),
        )
        self.engine.code_mode = bool(self.cfg.get("text.code_mode", False))

        def work() -> None:
            try:
                models_dir = paths.models_dir()
                ref_dir = models_dir / model_name
                if not (ref_dir / "model.bin").exists() and not (
                    models_dir / "model.bin"
                ).exists():
                    self.sig_status.emit(f"首次使用，正在下载 {model_name}…")
                    ensure_model(
                        model_name,
                        models_dir,
                        on_progress=self.sig_status.emit,
                    )
                self.engine.load()  # type: ignore[union-attr]
                self.sig_preload_done.emit(True, "")
            except Exception as e:
                log.exception("模型加载失败")
                self.sig_preload_done.emit(False, str(e))

        self._executor.submit(work)

    # ---------------------------------------------------------------- 热键
    def _on_press(self, name: str) -> None:
        if not self.engine_ready:
            self._hud_show("loading", "模型还在加载…", autohide_ms=1200)
            return
        if self._recording or self._busy:
            if self._busy:
                self._hud_show("working", "还在识别上一句…", autohide_ms=900)
            return
        self._active_key = name
        self._press_t0 = time.perf_counter()
        self._cancelled = False
        try:
            self.recorder.start()
        except Exception as e:
            log.error("麦克风启动失败: %s", e)
            self._hud_show("error", "麦克风打不开", autohide_ms=2500)
            return
        self._recording = True
        badge = "EN" if name == self.cfg.get("hotkeys.ptt_en") else ""
        self._preview_gen += 1
        self._preview_samples = 0
        self._preview_inflight = False
        self._preview_text = ""
        self._preview_shrinks = 0
        if name == self.cfg.get("hotkeys.ptt_en"):
            self._preview_lang = "en"
        else:
            configured = self.cfg.get("asr.language", "auto")
            self._preview_lang = None if configured in (None, "", "auto") else str(configured)
        self._hud_show("listening", badge=badge, preview="")
        self.tray.set_status("录音中…")
        self._beep("start")
        self._max_timer.start(int(self.cfg.get("advanced.max_utterance_sec", 20)) * 1000)
        if self.cfg.get("ui.live_preview", True):
            self._preview_timer.start()

    def _on_release(self, name: str, duration: float) -> None:
        if not self._recording or name != self._active_key:
            return
        self._max_timer.stop()
        self._preview_timer.stop()
        self._preview_gen += 1
        self._preview_inflight = False
        audio = self.recorder.stop()
        self._recording = False

        if self._cancelled:
            self.hud.hide_now()
            self.tray.set_status("就绪")
            return

        if duration * 1000 < int(self.cfg.get("advanced.min_hold_ms", 250)):
            self.hud.hide_now()
            return

        if audio.size < 2400:  # < 0.15s
            self._hud_show("error", "太短了，再说一次", autohide_ms=1200)
            return

        self._submit(audio, name)

    def _force_finish(self) -> None:
        if not self._recording:
            return
        self._preview_timer.stop()
        self._preview_gen += 1
        self._preview_inflight = False
        audio = self.recorder.stop()
        self._recording = False
        if audio.size >= 2400:
            self._submit(audio, self._active_key)

    def _on_cancel(self) -> None:
        if not self._recording:
            return
        self._cancelled = True
        self._max_timer.stop()
        self._preview_timer.stop()
        self._preview_gen += 1
        self._preview_inflight = False
        self.recorder.cancel()
        self._recording = False
        self.hud.hide_now()
        self.tray.set_status("已取消")

    # ---------------------------------------------------------------- 实时预览
    PREVIEW_MAX_SECONDS = 50.0

    def _preview_tick(self) -> None:
        if not self._recording or self._preview_inflight:
            return
        audio = self.recorder.snapshot()
        if audio.size < 9600:  # < 0.6s
            return
        if audio.size - self._preview_samples < 6400:  # 没有 0.4s 新音频
            return
        # 静音时不跑预览，避免 Whisper 在静音上编造内容
        tail = audio[-16000:]
        if float(np.sqrt(np.mean(tail.astype(np.float32) ** 2))) < 0.004:
            return
        self._preview_samples = audio.size

        limit = int(self.PREVIEW_MAX_SECONDS * 16000)
        window = audio[-limit:] if audio.size > limit else audio
        truncated = audio.size > limit

        self._preview_inflight = True
        gen = self._preview_gen
        self._executor.submit(
            self._preview_job, window, truncated, self._preview_lang, gen
        )

    def _preview_job(
        self, audio: np.ndarray, truncated: bool, lang: str | None, gen: int
    ) -> None:
        engine = self.engine
        try:
            if gen != self._preview_gen or engine is None:
                return
            # 整段解码：不会丢前半句，语言检测也更稳；不缓存检测结果
            prompt = (self.cfg.get("asr.initial_prompt") or "").strip() or None
            text, _ = engine.preview_text(audio, lang, prompt)
            if gen != self._preview_gen:
                return
            if truncated and text:
                text = "…" + text
            self.sig_preview.emit(text, gen)
        except Exception:
            log.exception("预览任务异常")
        finally:
            self._preview_inflight = False

    def _on_preview(self, text: str, gen: int) -> None:
        if gen != self._preview_gen or not self._recording:
            return
        if not text.strip():
            return
        text = self._process_text(text)
        prev = self._preview_text
        # 音频只会变长，转写不应突然变短；明显变短说明这次解码丢了开头
        if prev and len(text) < len(prev) * 0.85:
            self._preview_shrinks += 1
            if self._preview_shrinks < 3:
                return
        self._preview_shrinks = 0
        self._preview_text = text
        if self.cfg.get("ui.hud", True):
            self.hud.set_preview(text)

    def _process_text(self, raw: str) -> str:
        return process(
            raw,
            code_mode=bool(self.cfg.get("text.code_mode", False)),
            chinese_punctuation=bool(self.cfg.get("text.chinese_punctuation", True)),
            remove_fillers=bool(self.cfg.get("text.remove_fillers", True)),
            custom_dictionary=self.cfg.get("text.dictionary", {}) or {},
            trailing_space=False,
            simplified_chinese=bool(self.cfg.get("text.simplified_chinese", True)),
        )

    # ---------------------------------------------------------------- 识别
    def _submit(self, audio, key: str) -> None:
        self._busy = True
        self.tray.set_busy(True)
        self._hud_show("working", preview=self._preview_text or None)
        self.tray.set_status("识别中…")

        if key == self.cfg.get("hotkeys.ptt_en"):
            lang: str | None = "en"
        else:
            configured = self.cfg.get("asr.language", "auto")
            lang = None if configured in (None, "", "auto") else str(configured)

        prompt = (self.cfg.get("asr.initial_prompt") or "").strip() or None
        hotwords = (self.cfg.get("asr.hotwords") or "").strip() or None
        self._executor.submit(self._job, audio, lang, prompt, hotwords)

    def _job(self, audio, lang: str | None, prompt: str | None, hotwords: str | None) -> None:
        t0 = time.perf_counter()
        try:
            assert self.engine is not None
            raw = self.engine.transcribe(
                audio, language=lang, initial_prompt=prompt, hotwords=hotwords
            )
        except Exception as e:
            log.exception("识别失败")
            self.sig_job_done.emit(JobResult(ok=False, error=f"识别失败: {e}"))
            return

        if not raw.strip():
            self.sig_job_done.emit(JobResult(ok=False, message="没听清"))
            return

        cmd = commands.match_whole(raw)
        if cmd == commands.CANCEL:
            self.sig_job_done.emit(JobResult(ok=False, message="已取消"))
            return
        if cmd == commands.UNDO:
            ok, msg = self._undo_last()
            self.sig_job_done.emit(JobResult(ok=False, message=msg))
            return

        if cmd is not None:
            text = cmd
        else:
            text = self._process_text(raw)

        if not text.strip():
            self.sig_job_done.emit(JobResult(ok=False, raw=raw, message="没听清"))
            return

        hwnd = api.foreground_window()
        res = inject.inject_text(text, self.cfg)
        self.sig_job_done.emit(
            JobResult(
                ok=res.ok,
                raw=raw,
                final=text,
                hwnd=hwnd,
                elapsed=time.perf_counter() - t0,
                error="" if res.ok else "注入失败",
            )
        )

    def _on_job_done(self, res: JobResult) -> None:
        self._busy = False
        self.tray.set_busy(False)
        self.tray.set_status("就绪")

        if res.ok:
            self._last_insert = (res.final, res.hwnd, time.time())
            n = len(res.final)
            if res.final == "\n":
                label = "已换行"
            elif res.final in "，。？！：；、.,?!:;":
                label = f"已输入 {res.final}"
            else:
                label = f"已输入 {n} 字"
            self._hud_show(
                "done", label, preview=res.final, autohide_ms=1600
            )
            self._beep("done")
            log.info(
                "完成 %.0fms | raw=%r | final=%r", res.elapsed * 1000, res.raw, res.final
            )
        elif res.error:
            log.error("任务失败: %s", res.error)
            self._hud_show("error", "输入失败", preview=self._preview_text or None, autohide_ms=2200)
            self._beep("error")
        else:
            self._hud_show("error", res.message or "没听清", autohide_ms=1400)

    # ---------------------------------------------------------------- 撤销
    def _undo_last(self) -> tuple[bool, str]:
        if not self._last_insert:
            return False, "没有可撤销的输入"
        text, hwnd, ts = self._last_insert
        if time.time() - ts > 120:
            return False, "太久以前，已放弃撤销"
        if api.foreground_window() != hwnd:
            return False, "焦点窗口已切换，无法撤销"
        units = len(text.encode("utf-16-le")) // 2
        inject.undo_last(units)
        self._last_insert = None
        return True, f"已撤销 {len(text)} 字"

    def _undo_from_tray(self) -> None:
        ok, msg = self._undo_last()
        self._hud_show("done" if ok else "error", msg, autohide_ms=1400)
        if ok:
            self._beep("done")

    # ---------------------------------------------------------------- UI 事件
    def _on_level(self, level: float) -> None:
        self.hud.push_level(level)

    def _hud_show(
        self,
        state: str,
        text: str = "",
        badge: str = "",
        preview: str | None = None,
        autohide_ms: int = 0,
    ) -> None:
        if not self.cfg.get("ui.hud", True):
            return
        self.hud.show_state(
            state, text=text, badge=badge, preview=preview, autohide_ms=autohide_ms
        )

    def _on_status(self, msg: str) -> None:
        self.tray.set_status(msg)

    def _on_preload_done(self, ok: bool, err: str) -> None:
        self._loading = False
        if ok and self.engine is not None:
            self.engine_ready = True
            dev = self.engine.device_used.upper()
            model = self.cfg.get("asr.model")
            self.tray.set_status(f"就绪 · {model} · {dev}")
            log.info("引擎就绪: %s %s", model, dev)
        else:
            self.engine_ready = False
            self.tray.set_status("模型加载失败")
            self._hud_show("error", "模型加载失败", autohide_ms=4000)
            log.error("引擎不可用: %s", err)

    def _on_code_mode_toggled(self, value: bool) -> None:
        self.cfg.set("text.code_mode", bool(value))
        if self.engine is not None:
            self.engine.code_mode = bool(value)
        self._hud_show("done", "代码模式已开启" if value else "代码模式已关闭", autohide_ms=1000)

    def open_settings(self) -> None:
        before = (
            self.cfg.get("asr.model"),
            self.cfg.get("asr.device"),
            self.cfg.get("audio.device"),
            self.cfg.get("hotkeys.ptt_auto"),
            self.cfg.get("hotkeys.ptt_en"),
            self.cfg.get("hotkeys.ptt_extra"),
        )
        dlg = SettingsDialog(self.cfg, status=self._status_rows())
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return

        after = (
            self.cfg.get("asr.model"),
            self.cfg.get("asr.device"),
            self.cfg.get("audio.device"),
            self.cfg.get("hotkeys.ptt_auto"),
            self.cfg.get("hotkeys.ptt_en"),
            self.cfg.get("hotkeys.ptt_extra"),
        )
        autostart.set_enabled(bool(self.cfg.get("ui.start_with_windows", False)))
        self.tray.set_code_mode(bool(self.cfg.get("text.code_mode", False)))
        self.tray.apply_theme(str(self.cfg.get("ui.theme", "dark")))
        self.hud.apply_theme(str(self.cfg.get("ui.theme", "dark")))
        if self.engine is not None:
            self.engine.code_mode = bool(self.cfg.get("text.code_mode", False))

        if after[3:] != before[3:]:
            self._start_hotkeys()

        if after[2] != before[2]:
            self.recorder.close()
            self.recorder = Recorder(
                device=self.cfg.get("audio.device"),
                samplerate=int(self.cfg.get("audio.samplerate", 16000)),
            )
            self.recorder.set_level_callback(self.sig_level.emit)
            self.recorder.preopen()

        if after[:2] != before[:2]:
            self._preload()
            self._hud_show("loading", "正在切换模型…", autohide_ms=2000)
        else:
            self._hud_show("done", "设置已保存", autohide_ms=1000)

        if not self.cfg.get("ui.hud", True):
            self.hud.hide_now()

    def _open_logs(self) -> None:
        import os

        os.startfile(str(paths.logs_dir()))  # noqa: S606

    def _status_rows(self) -> list[tuple[str, str]]:
        rows: list[tuple[str, str]] = [("版本", __version__)]
        rows.append(("模型", str(self.cfg.get("asr.model", "large-v3-turbo"))))
        if self.engine is not None and self.engine.loaded:
            rows.append(
                (
                    "推理设备",
                    f"{self.engine.device_used.upper()} · {self.engine.compute_used}",
                )
            )
        else:
            rows.append(("推理设备", "未加载"))
        rows.append(("实时预览", "已开启" if self.cfg.get("ui.live_preview", True) else "已关闭"))
        return rows

    def _beep(self, kind: str) -> None:
        if not self.cfg.get("ui.sounds", True):
            return
        table = {"start": (880, 45), "done": (1240, 55), "error": (320, 130)}
        freq, dur = table.get(kind, (880, 45))

        def run() -> None:
            try:
                import winsound

                winsound.Beep(freq, dur)
            except Exception:
                pass

        threading.Thread(target=run, daemon=True).start()

    # ---------------------------------------------------------------- 退出
    def quit(self) -> None:
        log.info("退出")
        try:
            if self._hotkeys:
                self._hotkeys.stop()
            self.caret_tracker.stop()
            self.recorder.close()
            self._executor.shutdown(wait=False, cancel_futures=True)
        finally:
            self.hud.close()
            self.tray.hide()
            app = QApplication.instance()
            if app is not None:
                app.quit()
            # 兜底：1.5 秒内还没退干净就强制结束，避免托盘"退出"点不动
            threading.Timer(1.5, lambda: os._exit(0)).start()
