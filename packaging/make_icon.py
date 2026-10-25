"""生成多尺寸 .ico（打包用）。"""
from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "windows")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from PIL import Image  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from voicetype.ui.icons import make_icon  # noqa: E402


def main() -> int:
    out = ROOT / "src" / "voicetype" / "assets"
    out.mkdir(parents=True, exist_ok=True)
    app = QApplication(sys.argv)
    icon = make_icon()
    big = out / "voicetype_256.png"
    icon.pixmap(256, 256).save(str(big))

    img = Image.open(big).convert("RGBA")
    ico = out / "voicetype.ico"
    img.save(
        ico,
        format="ICO",
        sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)],
    )
    print("saved", ico, ico.stat().st_size, "bytes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
