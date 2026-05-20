"""Tuile métrique style carte Starlink."""

from __future__ import annotations

from PyQt6.QtCore import Qt, QRectF
from PyQt6.QtGui import QColor, QPainter, QPainterPath, QPen
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

from starlink_widget.ui.styles import INNER_RADIUS, TILE_BG, TILE_BORDER


class MetricTile(QWidget):
    def __init__(self, title: str, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("metricTile")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(4)

        self.title_label = QLabel(title)
        self.title_label.setObjectName("metricTitle")
        layout.addWidget(self.title_label)

        value_row = QHBoxLayout()
        value_row.setSpacing(4)
        self.value_label = QLabel("—")
        self.value_label.setObjectName("metricValue")
        value_row.addWidget(self.value_label)
        self.unit_label = QLabel("")
        self.unit_label.setObjectName("metricUnit")
        self.unit_label.setVisible(False)
        value_row.addWidget(
            self.unit_label, alignment=Qt.AlignmentFlag.AlignBottom
        )
        value_row.addStretch()
        layout.addLayout(value_row)

    def set_value(self, value: str, unit: str = "") -> None:
        self.value_label.setText(value)
        if unit:
            self.unit_label.setText(unit)
            self.unit_label.setVisible(True)
        else:
            self.unit_label.setText("")
            self.unit_label.setVisible(False)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -1.0, -1.0)
        path = QPainterPath()
        path.addRoundedRect(rect, INNER_RADIUS, INNER_RADIUS)
        painter.fillPath(path, QColor(*TILE_BG))
        painter.setPen(QPen(QColor(*TILE_BORDER), 1.0))
        painter.drawPath(path)
        super().paintEvent(event)
