"""Mini graphique sparkline - courbe lissée style Starlink."""

from __future__ import annotations

from typing import List, Sequence

from PyQt6.QtCore import QPointF, Qt
from PyQt6.QtGui import QColor, QPainter, QPainterPath, QPen
from PyQt6.QtWidgets import QSizePolicy, QWidget

SPARKLINE_COLOR = QColor(255, 255, 255, 200)
SPARKLINE_HEIGHT = 36
EDGE_PAD = 0.08


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
        self.update()

    def _chart_range(self, vals: List[float]) -> tuple[float, float, bool]:
        lo = min(vals)
        hi = max(vals)
        if hi - lo < 1e-9:
            return lo, lo + 1.0, True
        pad = (hi - lo) * 0.15
        return lo - pad, hi + pad, False

    def _norm_y(
        self, v: float, lo: float, hi: float, h: float, margin: float, *, flat: bool
    ) -> float:
        if flat:
            return margin + h * 0.5
        span = max(hi - lo, 1e-9)
        norm = (v - lo) / span
        norm = EDGE_PAD + norm * (1.0 - 2.0 * EDGE_PAD)
        return margin + h * (1.0 - norm)

    def paintEvent(self, event) -> None:
        if len(self._data) < 1:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        margin = 4
        w = max(1, self.width() - margin * 2)
        h = max(1, self.height() - margin * 2)

        vals = _smooth(self._data) if len(self._data) >= 3 else list(self._data)
        lo, hi, flat = self._chart_range(vals)

        n = len(vals)
        points: List[QPointF] = []
        for i, v in enumerate(vals):
            x = margin + (i / max(n - 1, 1)) * w
            y = self._norm_y(v, lo, hi, h, margin, flat=flat)
            points.append(QPointF(x, y))

        stroke = max(1.4, min(2.4, self.height() / 18.0))
        pen = QPen(SPARKLINE_COLOR, stroke, Qt.PenStyle.SolidLine)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)

        if len(points) == 1:
            y = points[0].y()
            painter.drawLine(int(margin), int(y), int(margin + w), int(y))
            return

        path = QPainterPath()
        path.moveTo(points[0])
        for i in range(1, len(points)):
            prev = points[i - 1]
            curr = points[i]
            cx = (prev.x() + curr.x()) / 2.0
            path.cubicTo(cx, prev.y(), cx, curr.y(), curr.x(), curr.y())
        painter.drawPath(path)
