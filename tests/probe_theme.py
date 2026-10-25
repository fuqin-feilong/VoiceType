"""主题切换测试 + 三套主题截图。"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from PySide6.QtWidgets import QApplication  # noqa: E402

from voicetype.config import Config  # noqa: E402
from voicetype.ui.settings import SettingsDialog  # noqa: E402

OUT = ROOT / "tests" / "ui"


def main() -> int:
    app = QApplication(sys.argv)
    OUT.mkdir(parents=True, exist_ok=True)
    tmp = Path(tempfile.mkdtemp()) / "config.json"
    cfg = Config(tmp)

    failures = 0

    def check(name: str, cond: bool) -> None:
        nonlocal failures
        print(f"{name}: {'PASS' if cond else 'FAIL'}")
        if not cond:
            failures += 1

    dlg = SettingsDialog(cfg, status=[("版本", "0.3.0"), ("模型", "large-v3-turbo")])
    dlg.show()
    app.processEvents()

    for theme in ("dark", "light", "gray"):
        dlg.theme_picker._buttons[theme].click()
        app.processEvents()
        check(f"切到 {theme}", dlg._theme == theme)
        dlg.grab().save(str(OUT / f"theme_{theme}.png"))
        dlg.nav.setCurrentRow(2)  # 输入页
        app.processEvents()
        dlg.grab().save(str(OUT / f"theme_{theme}_input.png"))
        dlg.nav.setCurrentRow(0)
        app.processEvents()

    # 保存后持久化
    dlg.theme_picker._buttons["gray"].click()
    dlg.accept()
    saved = Config(tmp)
    check("保存为灰色", saved.get("ui.theme") == "gray")

    # 取消时还原
    dlg2 = SettingsDialog(saved)
    dlg2.show()
    app.processEvents()
    dlg2.theme_picker._buttons["light"].click()
    app.processEvents()
    check("预览已切浅色", dlg2._theme == "light")
    dlg2.reject()
    check("取消后还原灰色", dlg2._theme == "gray")

    print(f"\n结果: {'ALL PASS' if failures == 0 else f'{failures} FAIL'}")
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
