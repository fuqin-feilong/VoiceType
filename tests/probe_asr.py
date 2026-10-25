"""离线验证 ASR：python tests/probe_asr.py --model tiny"""
from __future__ import annotations

import argparse
import sys
import time
import wave
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from voicetype.asr.whisper_engine import WhisperEngine  # noqa: E402
from voicetype.text.pipeline import process  # noqa: E402


def read_wav(path: Path) -> np.ndarray:
    with wave.open(str(path), "rb") as w:
        sr = w.getframerate()
        n = w.getnframes()
        ch = w.getnchannels()
        raw = w.readframes(n)
    audio = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
    if ch > 1:
        audio = audio.reshape(-1, ch).mean(axis=1)
    if sr != 16000:
        n_out = int(round(audio.size * 16000 / sr))
        x_old = np.linspace(0.0, 1.0, num=audio.size, endpoint=False)
        x_new = np.linspace(0.0, 1.0, num=n_out, endpoint=False)
        audio = np.interp(x_new, x_old, audio).astype(np.float32)
    return audio


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="tiny")
    ap.add_argument("--device", default="auto")
    ap.add_argument("--lang", default=None, help="zh / en / 不填=自动")
    ap.add_argument("--wav", nargs="*", default=None)
    ap.add_argument("--out", default=None, help="把结果写入 UTF-8 文件")
    args = ap.parse_args()

    lines: list[str] = []

    def log(msg: str = "") -> None:
        print(msg)
        lines.append(msg)

    models_dir = ROOT / "models"
    wavs = args.wav or sorted((ROOT / "tests" / "data").glob("*.wav"))
    if not wavs:
        print("没有测试音频，先运行 tests/make_samples.ps1")
        return 1

    eng = WhisperEngine(
        model_name=args.model,
        models_dir=models_dir,
        device=args.device,
    )
    t0 = time.perf_counter()
    eng.load()
    log(f"模型加载 {time.perf_counter()-t0:.1f}s device={eng.device_used} compute={eng.compute_used}")

    for w in wavs:
        w = Path(w)
        if not w.exists():
            log(f"跳过（不存在）: {w}")
            continue
        audio = read_wav(w)
        t = time.perf_counter()
        raw = eng.transcribe(audio, language=args.lang)
        dt = time.perf_counter() - t
        final = process(
            raw,
            code_mode=False,
            chinese_punctuation=True,
            remove_fillers=True,
            custom_dictionary={},
        )
        log(f"\n[{w.name}] {audio.size/16000:.2f}s 用时 {dt*1000:.0f}ms")
        log(f"  raw  : {raw}")
        log(f"  final: {final}")

    if args.out:
        Path(args.out).write_text("\n".join(lines), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
