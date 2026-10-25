"""程序化生成托盘图标，避免额外资源文件。"""
from __future__ import annotations

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPen, QPixmap


def make_icon(color: str = "#4F8CFF", size: int = 64) -> QIcon:
    pm = QPixmap(size, size)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)

    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor(color))
    p.drawEllipse(QRectF(2, 2, size - 4, size - 4))

    # 麦克风头
    p.setBrush(QColor("white"))
    p.drawRoundedRect(
        QRectF(size * 0.37, size * 0.20, size * 0.26, size * 0.36),
        size * 0.13,
        size * 0.13,
    )

    # 支架弧线
    pen = QPen(QColor("white"))
    pen.setWidthF(size * 0.055)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    p.setPen(pen)
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawArc(
        QRectF(size * 0.27, size * 0.36, size * 0.46, size * 0.36),
        0,
        -180 * 16,
    )
    # 竖杆
    p.drawLine(
        int(size * 0.5), int(size * 0.70), int(size * 0.5), int(size * 0.80)
    )
    p.end()
    return QIcon(pm)
