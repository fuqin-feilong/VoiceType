"""配置读写：%LOCALAPPDATA%\\VoiceType\\config.json"""
from __future__ import annotations

import copy
import json
import logging
from pathlib import Path
from typing import Any

from . import paths

log = logging.getLogger(__name__)

DEFAULTS: dict[str, Any] = {
    "hotkeys": {
        # 按住说话：右 Ctrl（中英自动）/ 右 Alt（强制英文）/ 鼠标侧键
        "ptt_auto": "right_ctrl",
        "ptt_en": "f8",
        "ptt_extra": "",
    },
    "asr": {
        "model": "large-v3-turbo",
        "device": "auto",          # auto | cuda | cpu
        "compute_type": "auto",    # auto | int8_float16 | int8 | float16 | float32
        "language": "auto",        # auto | zh | en
        "beam_size": 5,
        "initial_prompt": "",
        "hotwords": "",
        "vad_filter": True,
        "auto_prompt": True,
    },
    "text": {
        "code_mode": False,
        "chinese_punctuation": True,
        "simplified_chinese": True,
        "remove_fillers": True,
        "trailing_space": False,
        "dictionary": {},
    },
    "inject": {
        "method": "auto",          # auto | paste | type
        "restore_clipboard": True,
        "restore_delay_ms": 350,
        "app_rules": {},
    },
    "ui": {
        "hud": True,
        "theme": "dark",
        "live_preview": True,
        "sounds": True,
        "start_with_windows": False,
    },
    "audio": {
        "device": None,
        "samplerate": 16000,
    },
    "advanced": {
        "min_hold_ms": 250,
        "max_utterance_sec": 20,
        "log_level": "INFO",
    },
}


def _deep_merge(base: dict, override: dict) -> dict:
    out = copy.deepcopy(base)
    for k, v in override.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


class Config:
    def __init__(self, path: Path | None = None):
        self.path = Path(path) if path else paths.config_file()
        self.data: dict[str, Any] = copy.deepcopy(DEFAULTS)
        self.load()

    # ---------- 基础读写 ----------
    def load(self) -> None:
        if not self.path.exists():
            self.save()
            return
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                self.data = _deep_merge(DEFAULTS, raw)
        except Exception as e:  # 配置损坏不应阻止启动
            log.warning("配置文件读取失败，使用默认值: %s", e)

    def save(self) -> None:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_suffix(".json.tmp")
            tmp.write_text(
                json.dumps(self.data, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            tmp.replace(self.path)
        except Exception as e:
            log.error("配置保存失败: %s", e)

    # ---------- 点路径访问 ----------
    def get(self, dotted: str, default: Any = None) -> Any:
        cur: Any = self.data
        for part in dotted.split("."):
            if not isinstance(cur, dict) or part not in cur:
                return default
            cur = cur[part]
        return cur

    def set(self, dotted: str, value: Any, save: bool = True) -> None:
        parts = dotted.split(".")
        cur = self.data
        for part in parts[:-1]:
            cur = cur.setdefault(part, {})
        cur[parts[-1]] = value
        if save:
            self.save()
