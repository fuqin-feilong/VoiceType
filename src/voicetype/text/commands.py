"""语音指令：整句指令 + 代码模式下的符号口令。"""
from __future__ import annotations

UNDO = "__UNDO__"
CANCEL = "__CANCEL__"

# 整句只有这些词时，直接变成对应输出
WHOLE_UTTERANCE: dict[str, str] = {
    "换行": "\n",
    "回车": "\n",
    "新的一行": "\n",
    "另起一行": "\n",
    "逗号": "，",
    "句号": "。",
    "问号": "？",
    "感叹号": "！",
    "冒号": "：",
    "分号": "；",
    "左括号": "（",
    "右括号": "）",
    "括号": "（）",
    "左引号": "“",
    "右引号": "”",
    "双引号": "“”",
    "撤销": UNDO,
    "撤销上一句": UNDO,
    "撤销刚才的": UNDO,
    "删掉刚才的": UNDO,
    "取消": CANCEL,
}

# 代码模式下句内可替换的符号口令（长词优先）
CODE_INLINE: dict[str, str] = {
    "小驼峰": "",
    "大驼峰": "",
    "下划线": "_",
    "横杠": "-",
    "连字符": "-",
    "点号": ".",
    "斜杠": "/",
    "反斜杠": "\\",
    "左括号": "(",
    "右括号": ")",
    "左花括号": "{",
    "右花括号": "}",
    "左方括号": "[",
    "右方括号": "]",
    "等号": "=",
    "等于": "=",
    "加号": "+",
    "减号": "-",
    "星号": "*",
    "与": "&&",
    "或": "||",
    "箭头": "->",
    "双冒号": "::",
    "分号": ";",
    "逗号": ",",
    "句号": ".",
    "制表符": "\t",
    "tab": "\t",
}

_NORMALIZE_STRIP = " \t\r\n，。！？、；：,.!?;:"


def match_whole(text: str) -> str | None:
    key = text.strip().strip(_NORMALIZE_STRIP).replace(" ", "")
    return WHOLE_UTTERANCE.get(key)


def apply_inline_symbols(text: str) -> str:
    for k in sorted(CODE_INLINE, key=len, reverse=True):
        v = CODE_INLINE[k]
        if v:
            text = text.replace(k, v)
    return text
