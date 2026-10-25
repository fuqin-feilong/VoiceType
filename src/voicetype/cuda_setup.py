"""把 pip 安装的 CUDA/cuDNN DLL 目录加进搜索路径。

CTranslate2 在 Windows 上需要 cublas64_12.dll / cudnn64_9.dll，
pip 包 nvidia-cublas-cu12 / nvidia-cudnn-cu12 会提供，但目录不在 PATH 里。
"""
from __future__ import annotations

import logging
import os
from pathlib import Path

log = logging.getLogger(__name__)

_PACKAGES = ("cublas", "cudnn", "cuda_nvrtc")
_ready = False


def cuda_dll_dirs() -> list[Path]:
    dirs: list[Path] = []

    # 打包版：exe 同级（或 _internal）下的 cuda/ 目录
    try:
        from .paths import cuda_dir

        packed = cuda_dir()
        if packed is not None:
            dirs.append(packed)
    except Exception:
        pass

    # 开发版：pip 安装的 nvidia 包
    try:
        import nvidia  # namespace package

        base = Path(list(nvidia.__path__)[0])
        for sub in _PACKAGES:
            for leaf in ("bin", "lib"):
                p = base / sub / leaf
                if p.is_dir():
                    dirs.append(p)
    except Exception:
        pass

    return dirs


def add_cuda_dll_dirs() -> None:
    global _ready
    if _ready:
        return
    _ready = True

    dirs = cuda_dll_dirs()
    if not dirs:
        return

    for p in dirs:
        try:
            os.add_dll_directory(str(p))
        except Exception:
            pass
    # 双保险：有些库用 LoadLibraryW 只认 PATH
    os.environ["PATH"] = ";".join(str(p) for p in dirs) + ";" + os.environ.get("PATH", "")
    log.debug("已注册 CUDA DLL 目录: %s", [str(d) for d in dirs])
