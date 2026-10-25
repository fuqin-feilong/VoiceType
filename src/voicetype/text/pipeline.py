"""文本后处理管线：清洗 → 标点 → 词典 → 代码模式。"""
from __future__ import annotations

import re

from . import dictionary
from .commands import apply_inline_symbols

_CJK = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]")
_SPACE_BETWEEN_CJK = re.compile(r"(?<=[\u4e00-\u9fff])[ \t]+(?=[\u4e00-\u9fff])")

_CN_PUNCT = {
    ",": "，",
    ".": "。",
    "?": "？",
    "!": "！",
    ":": "：",
    ";": "；",
    "(": "（",
    ")": "）",
}

_HALF_PUNCT = {v: k for k, v in _CN_PUNCT.items()}

_FILLER = re.compile(
    r"(?:嗯+|呃+|额+|唔+|emmm+|umm+|um+|uh+|er+)[，,、.。]?[ \t]*",
    re.I,
)

_MULTI_SPACE = re.compile(r"[ \t]{2,}")

_OPENCC = None


def _to_simplified(text: str) -> str:
    global _OPENCC
    if not _has_cjk(text):
        return text
    try:
        if _OPENCC is None:
            from opencc import OpenCC

            _OPENCC = OpenCC("t2s")
        return _OPENCC.convert(text)
    except Exception:
        return text


def to_simplified(text: str) -> str:
    """对外暴露的繁转简（预览用）。"""
    return _to_simplified(text)


def _has_cjk(s: str) -> bool:
    return bool(_CJK.search(s))


def _to_chinese_punct(text: str) -> str:
    if not _has_cjk(text):
        return text
    out: list[str] = []
    n = len(text)
    for i, ch in enumerate(text):
        rep = _CN_PUNCT.get(ch)
        if not rep:
            out.append(ch)
            continue
        prev = text[i - 1] if i > 0 else ""
        nxt = text[i + 1] if i + 1 < n else ""
        # 小数、版本号、时间等数字间的点不动
        if ch == "." and prev.isdigit() and nxt.isdigit():
            out.append(ch)
            continue
        if _has_cjk(prev) or _has_cjk(nxt):
            out.append(rep)
        else:
            out.append(ch)
    return "".join(out)


def _to_half_punct(text: str) -> str:
    for cn, ascii_ch in _HALF_PUNCT.items():
        text = text.replace(cn, ascii_ch)
    return text


def process(
    raw: str,
    *,
    code_mode: bool = False,
    chinese_punctuation: bool = True,
    remove_fillers: bool = True,
    custom_dictionary: dict[str, str] | None = None,
    trailing_space: bool = False,
    tech_terms: bool = True,
    simplified_chinese: bool = True,
) -> str:
    text = (raw or "").strip()
    if not text:
        return ""

    if remove_fillers:
        text = _FILLER.sub("", text).strip()

    # Whisper 有时输出繁体，统一转简体
    if simplified_chinese:
        text = _to_simplified(text)

    # 中文之间的多余空格（Whisper 有时会加）
    text = _SPACE_BETWEEN_CJK.sub("", text)

    if code_mode:
        text = _to_half_punct(text)
        text = text.rstrip("。.\n ")
    elif chinese_punctuation:
        text = _to_chinese_punct(text)

    text = apply_inline_symbols(text) if code_mode else text

    if custom_dictionary:
        text = dictionary.apply_custom(text, custom_dictionary)
    if tech_terms:
        text = dictionary.apply_tech_terms(text)

    text = _MULTI_SPACE.sub(" ", text).strip()

    if trailing_space and text and not text.endswith(("\n", " ")):
        text += " "
    return text
