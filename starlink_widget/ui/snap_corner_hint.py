"""Indicateur animé dans un coin d'écran (aperçu snap en mode Personnaliser)."""

from __future__ import annotations

import math
from dataclasses import dataclass

from PyQt6.QtCore import QPoint, QPointF, QRectF, QSize, Qt, QTimer
from PyQt6.QtGui import QColor, QLinearGradient, QPainter, QPainterPath, QPen
from PyQt6.QtWidgets import QWidget

from starlink_widget.ui.styles import CARD_BORDER, CORNER_RADIUS

GRIP_INSET = 9
GRIP_GAP = 5
GRIP_BLUE = (90, 160, 255)


@dataclass(frozen=True)
class SnapCandidate:
    widget_pos: QPoint
    corner: str


class SnapCornerHint(QWidget):
    def __init__(self) -> None:
        super().__init__(None)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self._corner = "tl"
        self._phase = 0.0
        self._timer = QTimer(self)
        self._timer.setInterval(16)
        self._timer.timeout.connect(self._tick)

    def show_corner(self, corner: str, global_pos: QPoint, size: QSize) -> None:
        self._corner = corner
        self.setFixedSize(size)
        self.move(global_pos)
        if not self.isVisible():
            self.show()
        if not self._timer.isActive():
            self._timer.start()

    def hide_hint(self) -> None:
        self._timer.stop()
        self.hide()

    def _tick(self) -> None:
        self._phase = (self._phase + 0.07) % (2 * math.pi)
        self.update()

    def _glow_gradient(self, w: int, h: int) -> QLinearGradient:
        if self._corner == "tl":
            grad = QLinearGradient(w, h, 0, 0)
        elif self._corner == "tr":
            grad = QLinearGradient(0, h, w, 0)
        elif self._corner == "bl":
            grad = QLinearGradient(w, 0, 0, h)
        else:
            grad = QLinearGradient(0, 0, w, h)
        return grad

    def _draw_grip_lines(self, painter: QPainter, w: int, h: int, alpha: int) -> None:
        pen = QPen(QColor(255, 255, 255, alpha), 2.0)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        inset = GRIP_INSET
        gap = GRIP_GAP
        if self._corner == "tl":
            for i in range(3):
                d = inset + i * gap
                painter.drawLine(QPointF(d, inset), QPointF(inset, d))
        elif self._corner == "tr":
            for i in range(3):
                d = inset + i * gap
                painter.drawLine(QPointF(w - d, inset), QPointF(w - inset, d))
        elif self._corner == "bl":
            for i in range(3):
                d = inset + i * gap
                painter.drawLine(QPointF(d, h - inset), QPointF(inset, h - d))
        else:
            for i in range(3):
                d = inset + i * gap
                painter.drawLine(
                    QPointF(w - d, h - inset),
                    QPointF(w - inset, h - d),
                )

    def paintEvent(self, _event) -> None:
        pulse = 0.55 + 0.45 * math.sin(self._phase)
        w, h = self.width(), self.height()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        rect = QRectF(0.5, 0.5, w - 1.0, h - 1.0)
        path = QPainterPath()
        path.addRoundedRect(rect, CORNER_RADIUS, CORNER_RADIUS)

        glow = self._glow_gradient(w, h)
        glow.setColorAt(0.0, QColor(*GRIP_BLUE, 0))
        glow.setColorAt(1.0, QColor(*GRIP_BLUE, int(32 + 38 * pulse)))
        painter.fillPath(path, glow)

        border = QColor(*CARD_BORDER)
        border.setAlpha(int(90 + 70 * pulse))
        painter.setPen(QPen(border, 1.0))
        painter.drawPath(path)

        line_alpha = int(115 + 95 * pulse)
        self._draw_grip_lines(painter, w, h, line_alpha)
