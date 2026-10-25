"""麦克风采集：sounddevice(portaudio) -> 16k mono float32。

音频流常开（首次按下时打开），按下只清空缓冲区，避免开头 100ms 被吃掉。
"""
from __future__ import annotations

import logging
import threading
import time
from typing import Callable

import numpy as np
import sounddevice as sd

log = logging.getLogger(__name__)

TARGET_SR = 16000


class AudioError(RuntimeError):
    pass


def _wasapi_default_input() -> int | None:
    try:
        hostapis = sd.query_hostapis()
        for api in hostapis:
            if "WASAPI" in api.get("name", ""):
                dev = api.get("default_input_device", -1)
                if dev is not None and dev >= 0:
                    return int(dev)
    except Exception:
        pass
    return None


def default_input_device() -> int:
    dev = _wasapi_default_input()
    if dev is not None:
        return dev
    try:
        d = sd.default.device[0]
        if d is not None and d >= 0:
            return int(d)
    except Exception:
        pass
    raise AudioError("未找到可用的麦克风，请检查 Windows 隐私设置中的麦克风权限")


def list_input_devices() -> list[tuple[int, str]]:
    out: list[tuple[int, str]] = []
    try:
        for idx, d in enumerate(sd.query_devices()):
            if d.get("max_input_channels", 0) > 0:
                out.append((idx, str(d["name"])))
    except Exception:
        log.exception("枚举音频设备失败")
    return out


class Recorder:
    def __init__(self, device: int | None = None, samplerate: int = TARGET_SR):
        self.device = device
        self.samplerate = samplerate
        self._frames: list[np.ndarray] = []
        self._stream: sd.InputStream | None = None
        self._lock = threading.Lock()
        self._on_level: Callable[[float], None] | None = None
        self._actual_sr = samplerate
        self._last_level_emit = 0.0
        self._recording = False
        self._last_error = ""

    def set_level_callback(self, cb: Callable[[float], None] | None) -> None:
        self._on_level = cb

    @property
    def active(self) -> bool:
        return self._recording

    # ---------------------------------------------------------------- 打开/关闭
    def preopen(self) -> None:
        """启动时常开音频流，减少按下到出声的延迟。"""
        if self._stream is not None:
            return
        try:
            dev = self.device if self.device is not None else default_input_device()
            self._actual_sr = self.samplerate
            try:
                self._open(dev, self.samplerate)
            except Exception as e:
                log.warning("以 16k 打开麦克风失败(%s)，改用设备默认采样率", e)
                info = sd.query_devices(dev, "input")
                native = int(info.get("default_samplerate") or 48000)
                self._actual_sr = native
                self._open(dev, native)
            self._stream.start()  # type: ignore[union-attr]
            log.info("麦克风已打开: device=%s sr=%s", dev, self._actual_sr)
        except Exception as e:
            self._stream = None
            self._last_error = str(e)
            log.error("打开麦克风失败: %s", e)

    def _open(self, dev: int, sr: int) -> None:
        def _cb(indata, frames, time_info, status):  # noqa: ARG001
            if status:
                log.debug("音频状态: %s", status)
            if not self._recording:
                return
            mono = indata[:, 0].copy()
            with self._lock:
                self._frames.append(mono)
            cb = self._on_level
            if cb is not None:
                now = time.perf_counter()
                if now - self._last_level_emit > 0.04:
                    self._last_level_emit = now
                    try:
                        rms = float(
                            np.sqrt(np.mean((mono.astype(np.float32) / 32768.0) ** 2))
                        )
                        cb(min(1.0, rms * 12.0))
                    except Exception:
                        pass

        self._stream = sd.InputStream(
            device=dev,
            channels=1,
            samplerate=sr,
            dtype="int16",
            blocksize=512,
            callback=_cb,
        )

    # ---------------------------------------------------------------- 录音
    def start(self) -> None:
        if self._stream is None:
            self.preopen()
        if self._stream is None:
            raise AudioError(self._last_error or "麦克风不可用")
        with self._lock:
            self._frames = []
        self._recording = True

    def stop(self) -> np.ndarray:
        self._recording = False
        with self._lock:
            frames, self._frames = self._frames, []
        return self._join(frames)

    def snapshot(self) -> np.ndarray:
        """录音过程中取当前已录到的音频（不清空），用于实时预览。"""
        with self._lock:
            frames = list(self._frames)
        return self._join(frames)

    def _join(self, frames: list[np.ndarray]) -> np.ndarray:
        if not frames:
            return np.zeros(0, dtype=np.float32)
        audio = np.concatenate(frames).astype(np.float32) / 32768.0
        if self._actual_sr != TARGET_SR and audio.size:
            audio = _resample(audio, self._actual_sr, TARGET_SR)
        return np.clip(audio, -1.0, 1.0)

    def cancel(self) -> None:
        self._recording = False
        with self._lock:
            self._frames = []

    def close(self) -> None:
        stream = self._stream
        self._stream = None
        self._recording = False
        if stream is not None:
            try:
                stream.stop()
                stream.close()
            except Exception:
                log.exception("关闭音频流失败")


def _resample(audio: np.ndarray, src_sr: int, dst_sr: int) -> np.ndarray:
    if src_sr == dst_sr or audio.size == 0:
        return audio
    n_out = int(round(audio.size * dst_sr / src_sr))
    if n_out <= 0:
        return audio
    x_old = np.linspace(0.0, 1.0, num=audio.size, endpoint=False)
    x_new = np.linspace(0.0, 1.0, num=n_out, endpoint=False)
    return np.interp(x_new, x_old, audio).astype(np.float32)
