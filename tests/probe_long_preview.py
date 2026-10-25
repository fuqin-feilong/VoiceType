"""长句实时预览诊断：模拟 20 秒连续说话，记录每次预览的语言/文本/耗时。"""
from __future__ import annotations

import sys
import time
import wave
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

from probe_asr import read_wav  # noqa: E402
from voicetype import paths  # noqa: E402
from voicetype.asr.whisper_engine import WhisperEngine  # noqa: E402
from voicetype.config import Config  # noqa: E402

OUT = ROOT / "tests"


def build_long() -> np.ndarray:
    parts = []
    for name in ("zh_chat.wav", "zh_code.wav", "mixed.wav", "zh_chat.wav"):
        parts.append(read_wav(ROOT / "tests" / "data" / name))
        parts.append(np.zeros(4800, dtype=np.float32))  # 0.3s 静音
    audio = np.concatenate(parts)
    return audio


def write_wav(audio: np.ndarray, path: Path) -> None:
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(16000)
        w.writeframes((np.clip(audio, -1, 1) * 32767).astype(np.int16).tobytes())


def main() -> int:
    audio = build_long()
    write_wav(audio, OUT / "data" / "long_zh.wav")
    print(f"长音频 {audio.size/16000:.1f}s")

    eng = WhisperEngine("large-v3-turbo", paths.models_dir(), "auto", "auto")
    eng.load()
    lines = [f"长音频 {audio.size/16000:.1f}s"]

    # 1) 直接测 preview_text：不传语言（模拟首次）
    print("\n== preview_text(language=None) 逐段增长 ==")
    for sec in (1.0, 2.0, 4.0, 8.0, 12.0):
        n = int(16000 * sec)
        t = time.perf_counter()
        text, lang = eng.preview_text(audio[:n], None)
        dt = (time.perf_counter() - t) * 1000
        line = f"  {sec:4.1f}s -> lang={lang} {dt:5.0f}ms  {text[-60:]}"
        print(line)
        lines.append(line)

    # 2) 模拟长会话：窗口滑动 + 缓存语言（复现线上逻辑）
    print("\n== 模拟 20s 会话（旧逻辑：缓存语言 + 12s 窗口）==")
    cached_lang = None
    committed = ""
    for i, sec in enumerate(np.arange(1.2, 20.1, 0.8)):
        n = int(16000 * sec)
        window = audio[max(0, n - 16000 * 12) : n]
        t = time.perf_counter()
        text, detected = eng.preview_text(window, cached_lang)
        dt = (time.perf_counter() - t) * 1000
        if cached_lang is None and detected:
            cached_lang = detected
        line = f"  t={sec:5.1f}s lang={cached_lang} {dt:5.0f}ms  {text[-50:]}"
        print(line)
        lines.append(line)

    (OUT / "long_preview.txt").write_text("\n".join(lines), encoding="utf-8")

    # 3) 最终识别
    t = time.perf_counter()
    final = eng.transcribe(audio, None)
    print(f"\n最终 {((time.perf_counter()-t)*1000):.0f}ms: {final}")
    with open(OUT / "long_preview.txt", "a", encoding="utf-8") as f:
        f.write(f"\n\n最终: {final}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
