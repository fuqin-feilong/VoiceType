"""HUD 定位单测：水平居中 / 光标下方 / 贴底翻转 / 单次会话内不移动。"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from PySide6.QtWidgets import QApplication  # noqa: E402

from voicetype.ui.hud import Hud  # noqa: E402
from voicetype.win32.caret import Anchor  # noqa: E402


class FakeTracker:
    def __init__(self, anchor: Anchor):
        self.a = anchor

    def anchor(self) -> Anchor:
        return self.a


def main() -> int:
    app = QApplication(sys.argv)
    geo = app.primaryScreen().availableGeometry()
    center_x = geo.center().x()
    print(f"屏幕可用区域: {geo.left()},{geo.top()} {geo.width()}x{geo.height()}")
    failures = 0

    def case(name: str, anchor: Anchor, expect: str) -> None:
        nonlocal failures
        hud = Hud(FakeTracker(anchor))
        hud.show_state("listening")  # 捕获锚点并定位
        app.processEvents()
        x, y, w, h = hud.x(), hud.y(), hud.width(), hud.height()
        centered = abs((x + w // 2) - center_x) <= 2
        if expect == "below":
            y_ok = abs(y - (anchor.bottom + 8)) <= 4
        else:  # above
            y_ok = abs(y - (anchor.top - h - 8)) <= 4
        ok = centered and y_ok
        print(
            f"{name:10s} -> pos=({x},{y}) size={w}x{h} "
            f"居中={centered} 垂直={y_ok}  {'PASS' if ok else 'FAIL'}"
        )
        if not ok:
            failures += 1
        hud.close()

    cy = geo.center().y()
    case("光标下方", Anchor(center_x, cy, cy + 20, "win32"), "below")
    case("贴底翻转", Anchor(center_x, geo.bottom() - 40, geo.bottom() - 20, "win32"), "above")
    case("窗口估算", Anchor(center_x, geo.bottom() - 180, geo.bottom() - 180, "window-bottom", True), "above")

    # 同一次会话内锚点变化不应移动（防乱动）
    tracker = FakeTracker(Anchor(center_x, cy, cy + 20, "win32"))
    hud = Hud(tracker)
    hud.show_state("listening")
    app.processEvents()
    first = (hud.x(), hud.y())
    tracker.a = Anchor(center_x + 400, cy + 400, cy + 420, "uia")
    hud.position()
    second = (hud.x(), hud.y())
    stable = first == second
    print(f"{'会话内锁定':10s} -> {first} -> {second}  {'PASS' if stable else 'FAIL'}")
    if not stable:
        failures += 1

    # 下一次说话重新定位
    hud.hide_now()
    tracker.a = Anchor(center_x, cy + 300, cy + 320, "win32")
    hud.show_state("listening")
    app.processEvents()
    third = (hud.x(), hud.y())
    refreshed = third[1] != first[1]
    print(f"{'下次重新定位':10s} -> {third}  {'PASS' if refreshed else 'FAIL'}")
    if not refreshed:
        failures += 1
    hud.close()

    print(f"\n结果: {'ALL PASS' if failures == 0 else f'{failures} FAIL'}")
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
