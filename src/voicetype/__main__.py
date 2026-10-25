from __future__ import annotations

import ctypes
import logging
import sys

from . import paths
from .config import Config
from .logging_setup import setup_logging
from .single_instance import acquire

log = logging.getLogger(__name__)


def _set_dpi_awareness() -> None:
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)  # PER_MONITOR_AWARE_V2
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass


def main() -> int:
    _set_dpi_awareness()
    cfg = Config()
    setup_logging(str(cfg.get("advanced.log_level", "INFO")))
    log.info("VoiceType 启动 | data=%s | models=%s", paths.data_dir(), paths.models_dir())

    if not acquire():
        log.info("已有实例在运行，退出")
        return 0

    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication

    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    app = QApplication(sys.argv)
    app.setApplicationName("VoiceType")
    app.setQuitOnLastWindowClosed(False)

    from .app import VoiceTypeApp

    controller = VoiceTypeApp(cfg)
    controller.start()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
