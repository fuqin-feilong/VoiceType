"""标点/延迟参数对比实验。"""
from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from voicetype.asr.whisper_engine import WhisperEngine  # noqa: E402
from voicetype.cuda_setup import add_cuda_dll_dirs  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
from probe_asr import read_wav  # noqa: E402

PROMPT = "以下是普通话的句子，请使用简体中文并加上标点符号。"


def run(model, audio, *, vad=True, beam=5, prompt=None):
    t = time.perf_counter()
    segs, _ = model.transcribe(
        audio.astype("float32"),
        language=None,
        task="transcribe",
        beam_size=beam,
        temperature=[0.0, 0.2],
        condition_on_previous_text=False,
        initial_prompt=prompt,
        without_timestamps=True,
        vad_filter=vad,
        vad_parameters={"min_silence_duration_ms": 250, "speech_pad_ms": 100} if vad else None,
        no_speech_threshold=0.6,
        log_prob_threshold=-1.0,
        compression_ratio_threshold=2.4,
        hallucination_silence_threshold=2.0,
    )
    text = " ".join((s.text or "").strip() for s in segs).strip()
    return text, (time.perf_counter() - t) * 1000


def main() -> int:
    add_cuda_dll_dirs()
    root = Path(__file__).resolve().parents[1]
    eng = WhisperEngine("large-v3-turbo", root / "models", "auto", "auto")
    eng.load()
    model = eng._model

    zh = read_wav(root / "tests" / "data" / "zh_chat.wav")
    en = read_wav(root / "tests" / "data" / "en_code.wav")

    configs = [
        ("baseline", dict()),
        ("prompt_zh", dict(prompt=PROMPT)),
        ("no_vad", dict(vad=False)),
        ("beam1", dict(beam=1)),
        ("beam1+prompt", dict(beam=1, prompt=PROMPT)),
    ]
    lines = []
    for name, kw in configs:
        for label, audio in (("zh", zh), ("en", en)):
            text, dt = run(model, audio, **kw)
            line = f"{name:14s} {label} {dt:5.0f}ms  {text}"
            lines.append(line)
            print(line)
    out = root / "tests" / "punct_bench.txt"
    out.write_text("\n".join(lines), encoding="utf-8")
    print("written", out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
