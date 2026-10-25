"""PyInstaller 入口脚本。"""
from __future__ import annotations

import sys
from multiprocessing import freeze_support

if __name__ == "__main__":
    freeze_support()
    from voicetype.__main__ import main

    sys.exit(main())
