"""用 Windows SAPI 生成中英测试音频：python tests/make_samples.py"""
from __future__ import annotations

import sys
from pathlib import Path

import win32com.client

DATA = Path(__file__).resolve().parent / "data"

SAMPLES = [
    ("zh_chat.wav", "帮我把这个文件发给他，顺便问一下明天的会几点开始。"),
    ("zh_code.wav", "把那个异步函数改成小驼峰命名，然后加一个参数校验。"),
    ("en_code.wav", "Refactor the auth middleware and add unit tests."),
    ("mixed.wav", "这个 API 的 response 需要加一个 timeout 参数。"),
]


def main() -> int:
    DATA.mkdir(parents=True, exist_ok=True)
    voice = win32com.client.Dispatch("SAPI.SpVoice")
    tokens = voice.GetVoices()

    voices = []
    for i in range(tokens.Count):
        tok = tokens.Item(i)
        desc = tok.GetDescription()
        voices.append((i, desc))
        print(f"[{i}] {desc}")

    zh_idx = next((i for i, d in voices if "Chinese" in d or "中文" in d), None)
    en_idx = next((i for i, d in voices if "English" in d or "Zira" in d), None)

    stream = win32com.client.Dispatch("SAPI.SpFileStream")
    for name, text in SAMPLES:
        idx = en_idx if name.startswith("en_") else zh_idx
        if idx is None:
            print(f"跳过 {name}：缺少语音包")
            continue
        voice.Voice = tokens.Item(idx)
        path = DATA / name
        stream.Open(str(path), 3)  # 3 = SSFMCreateForWrite
        voice.AudioOutputStream = stream
        voice.Speak(text)
        stream.Close()
        print(f"生成 {path.name}  ({voices[idx][1]})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
