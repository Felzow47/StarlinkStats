"""Mini graphique sparkline — courbe lissée style Starlink."""

from __future__ import annotations

from typing import List, Sequence

from PyQt6.QtCore import QPointF, Qt
from PyQt6.QtGui import QColor, QPainter, QPainterPath, QPen
from PyQt6.QtWidgets import QSizePolicy, QWidget

SPARKLINE_COLOR = QColor(255, 255, 255, 180)
SPARKLINE_HEIGHT = 36


def _smooth(values: List[float], passes: int = 2) -> List[float]:
    if len(values) < 3:
        return values
    out = list(values)
    for _ in range(passes):
        nxt: List[float] = []
        for i in range(len(out)):
            prev_v = out[i - 1] if i > 0 else out[i]
            next_v = out[i + 1] if i < len(out) - 1 else out[i]
            nxt.append((prev_v + out[i] * 2 + next_v) / 4.0)
        out = nxt
    return out


class SparklineWidget(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._data: List[float] = []
        self.setMinimumHeight(SPARKLINE_HEIGHT)
        self.setMaximumHeight(SPARKLINE_HEIGHT)
        self.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )

    def set_data(self, data: Sequence[float]) -> None:
        self._data = list(data)
        self.setVisible(len(self._data) >= 2)
        self.update()

    def paintEvent(self, event) -> None:
        if len(self._data) < 2:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        margin = 6
        w = self.width() - margin * 2
        h = self.height() - margin * 2

        vals = _smooth(self._data)
        lo = min(vals)
        hi = max(vals)
        span = hi - lo
        if span < 1e-9:
            span = 1.0

        n = len(vals)
        points: List[QPointF] = []
        for i, v in enumerate(vals):
            x = margin + (i / (n - 1)) * w
            norm = (v - lo) / span
            y = margin + h * (1.0 - norm)
            points.append(QPointF(x, y))

        path = QPainterPath()
        path.moveTo(points[0])
        for i in range(1, len(points)):
            prev = points[i - 1]
            curr = points[i]
            cx = (prev.x() + curr.x()) / 2.0
            path.cubicTo(cx, prev.y(), cx, curr.y(), curr.x(), curr.y())

        pen = QPen(SPARKLINE_COLOR, 1.8, Qt.PenStyle.SolidLine)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        painter.drawPath(path)
