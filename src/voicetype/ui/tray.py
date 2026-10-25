"""托盘菜单。

注意：QAction 必须保持 Python 引用，否则会被 GC，菜单项会凭空消失。
"""
from __future__ import annotations

from PySide6.QtCore import QPoint, Signal
from PySide6.QtGui import QAction, QCursor
from PySide6.QtWidgets import QMenu, QSystemTrayIcon

from .icons import make_icon
from .theme import build_menu_qss


class Tray(QSystemTrayIcon):
    settings_requested = Signal()
    undo_requested = Signal()
    quit_requested = Signal()
    code_mode_toggled = Signal(bool)
    logs_requested = Signal()

    def __init__(self, code_mode: bool = False, theme: str = "dark"):
        super().__init__(make_icon())
        self.setToolTip("VoiceType · 语音输入")

        self._actions: list[QAction] = []
        self._menu = QMenu()
        self._menu.setStyleSheet(build_menu_qss(theme))

        self._status = self._add("正在启动…")
        self._status.setEnabled(False)
        self._menu.addSeparator()

        self._code = self._add("代码模式", checkable=True)
        self._code.setChecked(code_mode)
        self._code.toggled.connect(self.code_mode_toggled.emit)

        self._add("撤销上次输入", callback=self.undo_requested.emit)
        self._menu.addSeparator()

        self._add("设置…", callback=self.settings_requested.emit)
        self._add("打开日志", callback=self.logs_requested.emit)
        self._menu.addSeparator()

        self._add("退出 VoiceType", callback=self.quit_requested.emit)

        self.setContextMenu(self._menu)
        self.activated.connect(self._on_activated)

    # ---------------------------------------------------------------- 构建
    def _add(self, text: str, callback=None, checkable: bool = False) -> QAction:
        action = QAction(text, self._menu)
        action.setCheckable(checkable)
        if callback is not None:
            action.triggered.connect(callback)
        self._menu.addAction(action)
        self._actions.append(action)  # 关键：防止 Python 回收导致菜单项消失
        return action

    def _on_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            # 左键也弹菜单，很多用户不会去右键
            self._menu.popup(QCursor.pos())
        elif reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self.settings_requested.emit()

    # ---------------------------------------------------------------- 外部接口
    def set_status(self, text: str) -> None:
        self._status.setText(text)
        self.setToolTip(f"VoiceType · {text}")

    def set_code_mode(self, value: bool) -> None:
        self._code.blockSignals(True)
        self._code.setChecked(value)
        self._code.blockSignals(False)

    def set_busy(self, busy: bool) -> None:
        self.setIcon(make_icon("#F0A030" if busy else "#4F8CFF"))

    def apply_theme(self, name: str) -> None:
        self._menu.setStyleSheet(build_menu_qss(name))

    def popup_at_cursor(self) -> None:
        self._menu.popup(QCursor.pos() + QPoint(0, 0))
