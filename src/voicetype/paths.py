"""应用路径解析。

- 开发态：配置在 %LOCALAPPDATA%，模型在仓库 models/
- 安装版：配置/日志/模型都在 %LOCALAPPDATA%\\VoiceType
- 免安装版：exe 旁边有 portable.txt 时，配置/模型都放 exe 同级目录
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

APP_NAME = "VoiceType"


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def exe_dir() -> Path:
    return Path(sys.executable).resolve().parent


def is_portable() -> bool:
    return is_frozen() and (exe_dir() / "portable.txt").exists()


def project_root() -> Path:
    if is_frozen():
        return exe_dir()
    return Path(__file__).resolve().parents[2]


def _base_data_dir() -> Path:
    env = os.environ.get("VOICETYPE_DATA_DIR")
    if env:
        return Path(env)
    if is_portable():
        return exe_dir() / "data"
    return Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / APP_NAME


def data_dir() -> Path:
    p = _base_data_dir()
    p.mkdir(parents=True, exist_ok=True)
    return p


def models_dir() -> Path:
    env = os.environ.get("VOICETYPE_MODELS_DIR")
    if env:
        p = Path(env)
    elif is_portable():
        # 免安装版：exe 旁边有 models/ 就完全绿色；否则复用用户目录里的模型缓存
        local = exe_dir() / "models"
        if local.is_dir():
            p = local
        else:
            p = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / APP_NAME / "models"
    elif is_frozen():
        p = data_dir() / "models"
    else:
        p = project_root() / "models"
    p.mkdir(parents=True, exist_ok=True)
    return p


def cuda_dir() -> Path | None:
    """打包版把裁剪后的 CUDA DLL 放在 exe 同级的 cuda/ 目录。"""
    roots = []
    if is_frozen():
        roots.append(exe_dir())
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        roots.append(Path(meipass))
    for root in roots:
        p = root / "cuda"
        if p.is_dir():
            return p
    return None


def logs_dir() -> Path:
    p = data_dir() / "logs"
    p.mkdir(parents=True, exist_ok=True)
    return p


def config_file() -> Path:
    return data_dir() / "config.json"
