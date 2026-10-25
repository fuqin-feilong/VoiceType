"""HUD 浮层：置顶、不抢焦点、鼠标穿透，支持实时转写文字预览。"""
from __future__ import annotations

import ctypes
from collections import deque

from PySide6.QtCore import QPoint, QRect, QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPainter, QPen
from PySide6.QtWidgets import QApplication, QWidget

from ..win32 import api
from ..win32.caret import CaretTracker
from .theme import hud_palette

GWL_EXSTYLE = -20
WS_EX_NOACTIVATE = 0x08000000
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_TRANSPARENT = 0x00000020

TEXTS = {
    "listening": "聆听中",
    "working": "识别中",
    "loading": "模型加载中",
    "idle": "",
}

PAD = 16
HEADER_H = 50
W_SMALL = 272
W_WIDE = 460
MAX_LINES = 4
MAX_CHARS = 160


class Hud(QWidget):
    def __init__(self, tracker: CaretTracker | None = None, theme: str = "dark"):
        super().__init__(None)
        self._tracker = tracker or CaretTracker()
        self._pal = hud_palette(theme)
        self.setWindowFlags(
            Qt.WindowType.Tool
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setFixedSize(W_WIDE, HEADER_H)

        self._state = "idle"
        self._text = ""
        self._preview = ""
        self._badge = ""
        self._phase = 0
        self._levels: deque[float] = deque([0.0] * 18, maxlen=18)
        self._anchor = None  # 每次说话开始时锁定一次，过程中不再移动

        self._hide_timer = QTimer(self)
        self._hide_timer.setSingleShot(True)
        self._hide_timer.timeout.connect(self._auto_hide)
        self._repaint_timer = QTimer(self)
        self._repaint_timer.setInterval(33)
        self._repaint_timer.timeout.connect(self._tick)

        # 必须在窗口第一次显示之前就带上 NOACTIVATE，否则首次 show() 会抢焦点
        self.winId()
        self._apply_no_activate()

    # ---------------------------------------------------------------- 生命周期
    def _apply_no_activate(self) -> None:
        try:
            hwnd = int(self.winId())
            user32 = ctypes.WinDLL("user32", use_last_error=True)
            style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
            style |= WS_EX_NOACTIVATE | WS_EX_TOOLWINDOW | WS_EX_TRANSPARENT
            user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style)
        except Exception:
            pass

    def showEvent(self, event):  # noqa: N802
        self._apply_no_activate()
        super().showEvent(event)

    # ---------------------------------------------------------------- 外部接口
    def show_state(
        self,
        state: str,
        text: str = "",
        badge: str = "",
        preview: str | None = None,
        autohide_ms: int = 0,
    ) -> None:
        self._state = state
        self._badge = badge
        if text:
            self._text = text
        elif state in TEXTS:
            self._text = TEXTS[state]
        if preview is not None:
            self._preview = preview
        if state == "listening":
            self._levels = deque([0.0] * 18, maxlen=18)
        # 每次说话开始时锁定一次锚点；后续识别中/完成都沿用，
        # 避免过程中反复重算导致浮层跳动
        if state == "listening" or self._anchor is None:
            self._anchor = self._tracker.anchor()
        self._relayout()
        self.position()
        self._hide_timer.stop()
        if not self.isVisible():
            self.show()
        self.raise_()
        self._repaint_timer.start()
        self.update()
        if autohide_ms > 0:
            self._hide_timer.start(autohide_ms)

    def _auto_hide(self) -> None:
        self.hide()

    def set_preview(self, text: str) -> None:
        if text == self._preview:
            return
        self._preview = text
        self._relayout()
        self.update()

    def apply_theme(self, name: str) -> None:
        self._pal = hud_palette(name)
        self.update()

    def push_level(self, level: float) -> None:
        if self._state != "listening":
            return
        self._levels.append(max(0.0, min(1.0, level)))

    def hide_now(self) -> None:
        self._hide_timer.stop()
        self._repaint_timer.stop()
        self._anchor = None
        self.hide()

    # ---------------------------------------------------------------- 布局
    def _tail(self) -> str:
        text = (self._preview or "").strip()
        if len(text) > MAX_CHARS:
            text = "…" + text[-MAX_CHARS:]
        return text

    def _preview_font(self) -> QFont:
        f = QFont("Microsoft YaHei UI")
        f.setPixelSize(13)
        return f

    def _relayout(self) -> None:
        tail = self._tail()
        # 宽度固定：避免有/无预览文本时横向跳动
        w = W_WIDE
        if not tail:
            h = HEADER_H
        else:
            fm = QFontMetrics(self._preview_font())
            rect = fm.boundingRect(
                QRect(0, 0, w - 2 * PAD, 4000),
                int(Qt.TextFlag.TextWordWrap),
                tail,
            )
            line_h = fm.lineSpacing()
            lines = max(1, min(MAX_LINES, -(-rect.height() // line_h)))
            h = HEADER_H + lines * line_h + 10
        if (w, h) != (self.width(), self.height()):
            self.setFixedSize(w, h)
            if self.isVisible():
                self.position()

    def position(self) -> None:
        """水平居中；垂直方向贴在锚点下方，放不下就翻到上方。"""
        a = self._anchor
        if a is None:
            return
        w, h = self.width(), self.height()
        screen = QApplication.screenAt(QPoint(a.x, a.bottom)) or QApplication.primaryScreen()
        geo = screen.availableGeometry()

        x = geo.center().x() - w // 2      # 屏幕水平居中
        y = a.bottom + 8                   # 默认在光标下方
        if a.prefer_above or y + h > geo.bottom() - 8:
            y = a.top - h - 8
        if y < geo.top() + 8:
            y = a.bottom + 8

        x = max(geo.left() + 8, min(x, geo.right() - w - 8))
        y = max(geo.top() + 8, min(y, geo.bottom() - h - 8))
        if abs(x - self.x()) > 2 or abs(y - self.y()) > 2:
            self.move(x, y)

    # ---------------------------------------------------------------- 绘制
    def _tick(self) -> None:
        self._phase = (self._phase + 1) % 60
        if self._state == "listening":
            self._levels.append(self._levels[-1] * 0.55)
        self.update()

    def paintEvent(self, event):  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()

        # 背景
        pal = self._pal
        p.setPen(QPen(QColor(*pal["border"]), 1))
        p.setBrush(QColor(*pal["bg"]))
        p.drawRoundedRect(QRectF(0.5, 0.5, w - 1, h - 1), 14, 14)

        color = QColor(pal["states"].get(self._state, pal["states"]["idle"]))

        # 状态点
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(color)
        p.drawEllipse(QRectF(PAD, HEADER_H / 2 - 4, 8, 8))

        # 状态文字
        p.setPen(QColor(pal["text"]))
        f = QFont("Microsoft YaHei UI")
        f.setPixelSize(13)
        p.setFont(f)
        p.drawText(
            QRectF(PAD + 16, 0, w - 150, HEADER_H),
            int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft),
            self._text,
        )

        # 右侧：聆听时画电平条，识别中画跳动点
        right = float(w - PAD)
        if self._badge:
            p.setPen(QColor(pal["muted"]))
            f2 = QFont("Consolas")
            f2.setPixelSize(10)
            f2.setBold(True)
            p.setFont(f2)
            p.drawText(
                QRectF(right - 22, 0, 22, HEADER_H),
                int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight),
                self._badge,
            )
            right -= 30

        if self._state == "listening":
            bar_w, gap = 3, 3
            n = 8
            levels = list(self._levels)[-n:]
            base_x = right - n * (bar_w + gap)
            for i, lv in enumerate(levels):
                hh = 4 + lv * 22
                p.setBrush(QColor(color.red(), color.green(), color.blue(), 225))
                p.drawRoundedRect(
                    QRectF(base_x + i * (bar_w + gap), HEADER_H / 2 - hh / 2, bar_w, hh),
                    1.5,
                    1.5,
                )
        elif self._state in ("working", "loading"):
            for i in range(3):
                lit = (self._phase // 6) % 3 == i
                p.setBrush(
                    QColor(color.red(), color.green(), color.blue(), 235 if lit else 70)
                )
                p.drawEllipse(QRectF(right - 26 + i * 9, HEADER_H / 2 - 2.5, 5, 5))

        # 实时文字
        tail = self._tail()
        if tail:
            pf = self._preview_font()
            fm = QFontMetrics(pf)
            line_h = fm.lineSpacing()
            area = QRect(
                PAD,
                HEADER_H - 4,
                w - 2 * PAD,
                min(h - HEADER_H + 4 - 8, MAX_LINES * line_h),
            )
            p.setFont(pf)
            p.setPen(
                QColor(pal["preview_done"])
                if self._state == "done"
                else QColor(pal["preview"])
            )
            p.setClipRect(area)
            p.drawText(
                area,
                int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignBottom)
                | int(Qt.TextFlag.TextWordWrap),
                tail,
            )
            p.setClipping(False)

        p.end()
