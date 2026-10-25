"""模型下载：ModelScope（国内快）→ HF 官方 → hf-mirror。"""
from __future__ import annotations

import json
import logging
import os
import shutil
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Callable

log = logging.getLogger(__name__)

HF_MIRRORS = ["https://huggingface.co", "https://hf-mirror.com"]

MODELSCOPE_REPOS = {
    "large-v3-turbo": "pengzhendong/faster-whisper-large-v3-turbo",
    "large-v3": "pengzhendong/faster-whisper-large-v3",
    "distil-large-v3": "pengzhendong/faster-whisper-distil-large-v3",
    "medium": "pengzhendong/faster-whisper-medium",
    "small": "pengzhendong/faster-whisper-small",
    "base": "pengzhendong/faster-whisper-base",
    "tiny": "pengzhendong/faster-whisper-tiny",
}

_SKIP_FILES = {"README.md", ".gitattributes", "configuration.json"}
_REQUIRED = "model.bin"


def ensure_model(
    model_name: str,
    models_dir: Path,
    on_progress: Callable[[str], None] | None = None,
) -> Path:
    """确保 models/<model_name>/model.bin 存在，返回模型目录。"""
    target = models_dir / model_name
    if (target / _REQUIRED).exists():
        return target
    if (models_dir / _REQUIRED).exists():  # 兼容扁平目录布局
        return models_dir

    target.mkdir(parents=True, exist_ok=True)

    if model_name in MODELSCOPE_REPOS:
        try:
            _download_modelscope(model_name, target, on_progress)
            if (target / _REQUIRED).exists():
                return target
        except Exception as e:
            log.warning("ModelScope 下载失败: %s", e)

    from faster_whisper.utils import download_model

    last_err: Exception | None = None
    for endpoint in HF_MIRRORS:
        os.environ["HF_ENDPOINT"] = endpoint
        try:
            if on_progress:
                on_progress(f"正在从 {endpoint.split('//')[1]} 下载模型…")
            log.info("下载模型 %s from %s", model_name, endpoint)
            download_model(model_name, output_dir=str(target))
            if (target / _REQUIRED).exists():
                return target
        except Exception as e:
            last_err = e
            log.warning("从 %s 下载失败: %s", endpoint, e)
    raise RuntimeError(f"模型下载失败: {last_err}")


# ---------------------------------------------------------------- ModelScope
def _download_modelscope(
    model_name: str,
    target: Path,
    on_progress: Callable[[str], None] | None,
) -> None:
    repo = MODELSCOPE_REPOS[model_name]
    api = (
        f"https://modelscope.cn/api/v1/models/{repo}/repo/files"
        "?Revision=master&Root="
    )
    with urllib.request.urlopen(api, timeout=30) as r:
        data = json.load(r)
    files = [
        f["Name"]
        for f in data["Data"]["Files"]
        if f.get("Type") == "blob" and f["Name"] not in _SKIP_FILES
    ]
    if _REQUIRED not in files:
        raise RuntimeError("ModelScope 仓库缺少 model.bin")

    for name in files:
        dest = target / name
        if dest.exists() and dest.stat().st_size > 0:
            continue
        url = (
            f"https://modelscope.cn/api/v1/models/{repo}/repo"
            f"?Revision=master&FilePath={urllib.parse.quote(name)}"
        )
        if on_progress:
            on_progress(f"正在从 ModelScope 下载 {name}…")
        log.info("下载 %s -> %s", url, dest)
        _download_file(url, dest, on_progress)


def _download_file(
    url: str,
    dest: Path,
    on_progress: Callable[[str], None] | None,
    retries: int = 5,
) -> None:
    part = dest.with_suffix(dest.suffix + ".part")
    for attempt in range(1, retries + 1):
        try:
            offset = part.stat().st_size if part.exists() else 0
            req = urllib.request.Request(url)
            if offset:
                req.add_header("Range", f"bytes={offset}-")
            with urllib.request.urlopen(req, timeout=60) as resp:
                total = int(resp.headers.get("Content-Length") or 0) + offset
                mode = "ab" if offset and resp.status == 206 else "wb"
                if mode == "wb":
                    offset = 0
                last = 0.0
                with open(part, mode) as f:
                    while True:
                        chunk = resp.read(1024 * 256)
                        if not chunk:
                            break
                        f.write(chunk)
                        offset += len(chunk)
                        now = time.time()
                        if on_progress and now - last > 0.8:
                            last = now
                            pct = f"{offset/total*100:.0f}%" if total else ""
                            on_progress(
                                f"下载 {dest.name}  {offset/1048576:.0f}"
                                f"{'/' + format(total/1048576, '.0f') if total else ''} MB {pct}"
                            )
            part.replace(dest)
            return
        except Exception as e:
            log.warning("下载 %s 失败(第 %d 次): %s", dest.name, attempt, e)
            if attempt == retries:
                raise
            time.sleep(min(2 * attempt, 8))


def cleanup_partials(models_dir: Path) -> None:
    for p in models_dir.rglob("*.part"):
        try:
            p.unlink()
        except OSError:
            pass
    # 清理下载中断留下的空目录
    for p in models_dir.iterdir():
        if p.is_dir() and not any(p.iterdir()):
            shutil.rmtree(p, ignore_errors=True)
