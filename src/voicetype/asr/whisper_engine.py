"""faster-whisper 本地识别引擎（GPU 优先，自动降级 CPU）。"""
from __future__ import annotations

import logging
import time
from pathlib import Path

import numpy as np

from .base import AsrEngine

log = logging.getLogger(__name__)

_HALLUCINATION_HINTS = (
    "字幕由",
    "字幕提供",
    "谢谢观看",
    "明镜与点点",
    "请不吝点赞",
    "订阅",
    "打赏",
    "amara.org",
    "thanks for watching",
    "subscribe",
)

# 只用于实时预览：短句里出现这些基本是静音/噪声幻觉
_PREVIEW_NOISE = (
    "thank you",
    "thank you for watching",
    "thanks",
    "please subscribe",
    "subscribe",
    "ご視聴",
    "ありがとうございました",
    "おやすみなさい",
    "안녕하세요",
    "구독",
    "продолжение следует",
    "субтитры",
    "sottotitoli",
    "untertitel",
)

# 语言相关提示词：主要作用是诱导模型输出标点、简体中文
DEFAULT_PROMPTS = {
    "zh": "以下是普通话的句子，请使用简体中文，并加上标点符号。",
    "en": "The following is an English sentence with proper punctuation.",
}

# 代码模式专用：把术语喂给模型，显著减少同音错字（异步/一步、小驼峰/小驮峰）
CODE_PROMPTS = {
    "zh": "以下是程序员口述的编码需求，常见术语：函数、变量、参数校验、异步、回调、接口、字段、数组、命名。",
    "en": "The following is a programmer dictating code changes, mentioning functions, variables, parameters, async, callbacks, APIs and tests.",
}

MIN_LANG_PROB = 0.5


def resolve_model_ref(model_name: str, models_dir: Path) -> str:
    """优先用本地已下载目录，否则返回模型名让 HF 自己拉。"""
    candidates = [
        models_dir / model_name,
        models_dir,
    ]
    for c in candidates:
        if (c / "model.bin").exists():
            return str(c)
    return model_name


def _drop_hallucination(text: str) -> str:
    low = text.lower()
    for hint in _HALLUCINATION_HINTS:
        if hint in low and len(text) <= len(hint) + 24:
            log.info("丢弃疑似幻觉输出: %r", text)
            return ""
    return text


def _drop_preview_noise(text: str) -> str:
    """预览专用：丢掉静音/噪声上常见的短外文幻觉。"""
    low = text.lower().strip(" .,!，。！?？:：;；'\"“”‘’")
    if not low:
        return ""
    for hint in _PREVIEW_NOISE:
        if low == hint or (hint in low and len(low) <= len(hint) + 10):
            log.debug("丢弃预览噪声: %r", text)
            return ""
    return text


class WhisperEngine(AsrEngine):
    name = "faster-whisper"

    def __init__(
        self,
        model_name: str = "large-v3-turbo",
        models_dir: Path | None = None,
        device: str = "auto",
        compute_type: str = "auto",
        beam_size: int = 5,
        vad_filter: bool = True,
        auto_prompt: bool = True,
    ):
        self.model_name = model_name
        self.models_dir = models_dir
        self.device_pref = device
        self.compute_type = compute_type
        self.beam_size = beam_size
        self.vad_filter = vad_filter
        self.auto_prompt = auto_prompt
        self.code_mode = False
        self._model = None
        self.device_used = ""
        self.compute_used = ""

    # ---------------------------------------------------------------- 加载
    def load(self) -> None:
        if self._model is not None:
            return
        from ..cuda_setup import add_cuda_dll_dirs

        add_cuda_dll_dirs()
        from faster_whisper import WhisperModel

        ref = (
            resolve_model_ref(self.model_name, self.models_dir)
            if self.models_dir
            else self.model_name
        )
        devices = (
            ["cuda", "cpu"] if self.device_pref == "auto" else [self.device_pref]
        )
        last_err: Exception | None = None
        for dev in devices:
            ct = self._compute_for(dev)
            t0 = time.perf_counter()
            try:
                log.info("加载模型 %s device=%s compute=%s", ref, dev, ct)
                self._model = WhisperModel(
                    ref,
                    device=dev,
                    compute_type=ct,
                    cpu_threads=8,
                    num_workers=1,
                )
                self.device_used = dev
                self.compute_used = ct
                log.info(
                    "模型加载完成 %.1fs (device=%s, compute=%s)",
                    time.perf_counter() - t0,
                    dev,
                    ct,
                )
                self._warmup()
                return
            except Exception as e:
                last_err = e
                log.warning("以 %s 加载失败: %s", dev, e)
        raise RuntimeError(f"模型加载失败: {last_err}")

    def _compute_for(self, dev: str) -> str:
        if self.compute_type != "auto":
            return self.compute_type
        return "int8_float16" if dev == "cuda" else "int8"

    def _warmup(self) -> None:
        """用 1 秒静音预热 encoder，避免第一句话多等 300~600ms。"""
        if self._model is None:
            return
        try:
            silence = np.zeros(16000, dtype=np.float32)
            t0 = time.perf_counter()
            self._model.detect_language(silence)
            log.info("预热完成 %.0fms", (time.perf_counter() - t0) * 1000)
        except Exception as e:
            log.debug("预热失败: %s", e)

    def detect_language(self, audio: np.ndarray) -> tuple[str | None, float]:
        if self._model is None:
            return None, 0.0
        try:
            lang, prob, _ = self._model.detect_language(audio.astype(np.float32))
            return lang, float(prob)
        except Exception as e:
            log.debug("语言检测失败: %s", e)
            return None, 0.0

    def detect_zh_en(self, audio: np.ndarray) -> str:
        """只在中文/英文里二选一，彻底避免日韩俄等语言冒出来。"""
        if self._model is None:
            return "zh"
        try:
            _, _, probs = self._model.detect_language(audio.astype(np.float32))
            scores = dict(probs) if not isinstance(probs, dict) else probs
            zh = float(scores.get("zh", 0.0))
            en = float(scores.get("en", 0.0))
            return "en" if en > zh else "zh"
        except Exception as e:
            log.debug("zh/en 语言判定失败: %s", e)
            return "zh"

    @property
    def loaded(self) -> bool:
        return self._model is not None

    # ---------------------------------------------------------------- 识别
    def transcribe(
        self,
        audio: np.ndarray,
        language: str | None = None,
        initial_prompt: str | None = None,
        hotwords: str | None = None,
    ) -> str:
        self.load()
        assert self._model is not None
        if audio.size < 1600:  # < 0.1s
            return ""

        # 只在中文/英文里选，避免出现日韩等其他语言
        if language is None:
            language = self.detect_zh_en(audio)
            log.debug("语言判定: %s", language)

        prompt = initial_prompt
        if not prompt:
            table = CODE_PROMPTS if self.code_mode else DEFAULT_PROMPTS
            prompt = table.get(language or "", DEFAULT_PROMPTS["zh"])

        t0 = time.perf_counter()
        segments, info = self._model.transcribe(
            audio.astype(np.float32),
            language=language,
            task="transcribe",
            beam_size=self.beam_size,
            temperature=[0.0, 0.2],
            condition_on_previous_text=False,
            initial_prompt=prompt,
            hotwords=hotwords or None,
            without_timestamps=True,
            vad_filter=self.vad_filter,
            vad_parameters={"min_silence_duration_ms": 250, "speech_pad_ms": 100}
            if self.vad_filter
            else None,
            no_speech_threshold=0.6,
            log_prob_threshold=-1.0,
            compression_ratio_threshold=2.4,
            hallucination_silence_threshold=2.0,
        )
        parts: list[str] = []
        for seg in segments:
            text = (seg.text or "").strip()
            if not text:
                continue
            if seg.no_speech_prob and seg.no_speech_prob > 0.85:
                log.debug("跳过疑似静音段: %.2f %r", seg.no_speech_prob, text)
                continue
            parts.append(text)
        text = " ".join(parts).strip()
        text = _drop_hallucination(text)
        log.info(
            "识别 %.0fms -> %r (lang=%s p=%.2f)",
            (time.perf_counter() - t0) * 1000,
            text,
            getattr(info, "language", "?"),
            getattr(info, "language_probability", 0.0) or 0.0,
        )
        return text

    # ---------------------------------------------------------------- 实时预览
    def preview_text(
        self,
        audio: np.ndarray,
        language: str | None = None,
        initial_prompt: str | None = None,
    ) -> tuple[str, str | None]:
        """偏重准确率的快速转写（beam=5 + 标点/代码提示词），用于边说边显示。

        语言只会在 zh / en 之间选择。
        """
        self.load()
        assert self._model is not None
        if audio.size < 4800:  # < 0.3s
            return "", language
        try:
            if language is None:
                language = self.detect_zh_en(audio)
            if initial_prompt:
                prompt = initial_prompt
            else:
                table = CODE_PROMPTS if self.code_mode else DEFAULT_PROMPTS
                prompt = table.get(language or "", DEFAULT_PROMPTS["zh"])
            t0 = time.perf_counter()
            segments, info = self._model.transcribe(
                audio.astype(np.float32),
                language=language,
                task="transcribe",
                beam_size=5,
                temperature=0.0,
                condition_on_previous_text=False,
                initial_prompt=prompt,
                without_timestamps=True,
                vad_filter=False,
                # 预览不做静音过滤：外层已经用 RMS 挡过静音了
                no_speech_threshold=0.95,
                log_prob_threshold=None,
                compression_ratio_threshold=2.4,
                suppress_blank=True,
            )
            text = " ".join((s.text or "").strip() for s in segments if s.text).strip()
            text = _drop_preview_noise(_drop_hallucination(text))
            log.debug(
                "预览 %.0fms lang=%s len=%d",
                (time.perf_counter() - t0) * 1000,
                language,
                len(text),
            )
            return text, getattr(info, "language", language)
        except Exception:
            log.exception("预览识别失败")
            return "", language

