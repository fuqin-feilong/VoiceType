"""把 HUD 和设置界面渲染成 PNG，便于检查视觉效果。

python tests/probe_ui.py
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from PySide6.QtCore import QPoint
from PySide6.QtGui import QColor, QPixmap
from PySide6.QtWidgets import QApplication  # noqa: E402

from voicetype.config import Config  # noqa: E402
from voicetype.ui.hud import Hud  # noqa: E402
from voicetype.ui.settings import SettingsDialog  # noqa: E402

OUT = ROOT / "tests" / "ui"


def shot_on_gray(hud: Hud, path) -> None:
    """把半透明浮层合成到灰底上，方便看清浅色/深色两套配色。"""
    pm = QPixmap(hud.size())
    pm.fill(QColor("#8A8A8A"))
    hud.render(pm, QPoint(0, 0))
    pm.save(str(path))


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    app = QApplication(sys.argv)

    hud = Hud()
    hud.show_state("listening", badge="EN")
    hud.show()
    app.processEvents()
    hud.grab().save(str(OUT / "hud_listening.png"))

    hud.set_preview("帮我把这个文件发给他，顺便问一下明天的会几点开始。")
    app.processEvents()
    hud.grab().save(str(OUT / "hud_preview.png"))

    hud.set_preview(
        "这个 API 的 Response 需要加一个 Timeout 参数，然后把 auth middleware "
        "里的 token 校验挪到一个独立函数里，最后补上单元测试。"
    )
    app.processEvents()
    hud.grab().save(str(OUT / "hud_preview_long.png"))

    hud.show_state(
        "done",
        "已输入 22 字",
        preview="这个 API 的 Response 需要加一个 Timeout 参数。",
        autohide_ms=0,
    )
    app.processEvents()
    hud.grab().save(str(OUT / "hud_done.png"))

    for theme in ("dark", "light", "gray"):
        hud.apply_theme(theme)
        hud.show_state("listening", badge="")
        hud.set_preview("帮我把这个文件发给他，顺便问一下明天的会几点开始。")
        app.processEvents()
        shot_on_gray(hud, OUT / f"hud_theme_{theme}.png")

    hud.close()

    status = [
        ("版本", "0.1.0"),
        ("模型", "large-v3-turbo"),
        ("推理设备", "CUDA · int8_float16"),
        ("实时预览", "已开启"),
    ]
    dlg = SettingsDialog(Config(), status=status)
    dlg.show()
    app.processEvents()
    for i, name in enumerate(["general", "asr", "input", "dict", "about"]):
        dlg.nav.setCurrentRow(i)
        app.processEvents()
        dlg.grab().save(str(OUT / f"settings_{name}.png"))
    dlg.close()
    print("saved to", OUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
