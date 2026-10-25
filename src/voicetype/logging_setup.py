from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler

from . import paths


def setup_logging(level: str = "INFO") -> None:
    root = logging.getLogger()
    root.setLevel(getattr(logging, level.upper(), logging.INFO))

    fmt = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s", "%H:%M:%S"
    )

    fh = RotatingFileHandler(
        paths.logs_dir() / "voicetype.log",
        maxBytes=2 * 1024 * 1024,
        backupCount=3,
        encoding="utf-8",
    )
    fh.setFormatter(fmt)
    root.addHandler(fh)

    # 开发态（有控制台）同时输出到 stdout，避免中文乱码
    if sys.stderr is not None:
        try:
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
        sh = logging.StreamHandler(sys.stderr)
        sh.setFormatter(fmt)
        root.addHandler(sh)
