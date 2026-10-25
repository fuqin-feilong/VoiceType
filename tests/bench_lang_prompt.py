"""语言感知提示词方案对比：先检测语言，再用对应语言的标点提示词。"""
from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from voicetype.asr.whisper_engine import WhisperEngine  # noqa: E402
from voicetype.cuda_setup import add_cuda_dll_dirs  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
from probe_asr import read_wav  # noqa: E402

PROMPTS = {
    "zh": "以下是普通话的句子，请使用简体中文，并加上标点符号。",
    "en": "The following is an English sentence with proper punctuation.",
}


def run(model, audio, language, prompt, beam=5):
    t = time.perf_counter()
    segs, info = model.transcribe(
        audio.astype("float32"),
        language=language,
        task="transcribe",
        beam_size=beam,
        temperature=[0.0, 0.2],
        condition_on_previous_text=False,
        initial_prompt=prompt,
        without_timestamps=True,
        vad_filter=True,
        vad_parameters={"min_silence_duration_ms": 250, "speech_pad_ms": 100},
        no_speech_threshold=0.6,
        log_prob_threshold=-1.0,
        compression_ratio_threshold=2.4,
        hallucination_silence_threshold=2.0,
    )
    text = " ".join((s.text or "").strip() for s in segs).strip()
    return text, (time.perf_counter() - t) * 1000, info


def main() -> int:
    add_cuda_dll_dirs()
    root = Path(__file__).resolve().parents[1]
    eng = WhisperEngine("large-v3-turbo", root / "models", "auto", "auto")
    eng.load()
    model = eng._model

    wavs = {
        "zh_chat": read_wav(root / "tests" / "data" / "zh_chat.wav"),
        "zh_code": read_wav(root / "tests" / "data" / "zh_code.wav"),
        "mixed": read_wav(root / "tests" / "data" / "mixed.wav"),
        "en_code": read_wav(root / "tests" / "data" / "en_code.wav"),
    }
    lines = []
    for name, audio in wavs.items():
        t = time.perf_counter()
        lang, prob, _ = model.detect_language(audio.astype("float32"))
        det_ms = (time.perf_counter() - t) * 1000
        prompt = PROMPTS.get(lang)
        text, ms, info = run(model, audio, lang if prob >= 0.5 else None, prompt)
        line = (
            f"{name:9s} detect={lang}({prob:.2f}) {det_ms:.0f}ms  "
            f"asr={ms:.0f}ms total={det_ms+ms:.0f}ms\n           {text}"
        )
        lines.append(line)
        print(line)
    out = root / "tests" / "lang_bench.txt"
    out.write_text("\n".join(lines), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
