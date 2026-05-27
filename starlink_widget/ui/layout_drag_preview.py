"""Aperçu semi-transparent du layout pendant le drag (sans modifier la grille)."""

from __future__ import annotations

from PyQt6.QtCore import QRect, QRectF, Qt
from PyQt6.QtGui import QColor, QPainter, QPainterPath, QPen
from PyQt6.QtWidgets import QWidget


class LayoutDragPreview(QWidget):
    def __init__(self, container: QWidget) -> None:
        super().__init__(container)
        self._container = container
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.hide()
        self._slot_geos: dict[str, QRect] = {}
        self._drag_geo: QRect | None = None
        self._zone_geos: list[QRect] = []
        self._active_zone: QRect | None = None

    def set_compact_zones(
        self,
        zone_geos: list[QRect],
        *,
        active: QRect | None = None,
    ) -> None:
        self._zone_geos = list(zone_geos)
        self._active_zone = QRect(active) if active is not None else None
        if self._zone_geos:
            if self._container is not None and self._container.width() > 0:
                self.setGeometry(self._container.rect())
            self.show()
            self.raise_()
        self.update()

    def set_preview(
        self,
        slot_geos: dict[str, QRect],
        drag_geo: QRect | None = None,
    ) -> None:
        self._slot_geos = dict(slot_geos)
        self._drag_geo = QRect(drag_geo) if drag_geo is not None else None
        if self._slot_geos or self._drag_geo is not None or self._zone_geos:
            if self._container is not None and self._container.width() > 0:
                self.setGeometry(self._container.rect())
            self.show()
            self.raise_()
        elif not self._zone_geos:
            self.hide()
        self.update()

    def clear_preview(self) -> None:
        self._slot_geos = {}
        self._drag_geo = None
        self._zone_geos = []
        self._active_zone = None
        self.hide()

    def paintEvent(self, _event) -> None:
        if not self._slot_geos and self._drag_geo is None and not self._zone_geos:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        for geo in self._zone_geos:
            active = (
                self._active_zone is not None
                and geo.x() == self._active_zone.x()
                and geo.y() == self._active_zone.y()
                and geo.width() == self._active_zone.width()
                and geo.height() == self._active_zone.height()
            )
            self._draw_zone(painter, geo, active=active)

        for geo in self._slot_geos.values():
            self._draw_slot(painter, geo, drag=False)

        if self._drag_geo is not None:
            self._draw_slot(painter, self._drag_geo, drag=True)

    def _draw_slot(self, painter: QPainter, geo: QRect, *, drag: bool) -> None:
        if geo.width() < 2 or geo.height() < 2:
            return
        rect = QRectF(geo).adjusted(0.5, 0.5, -1.0, -1.0)
        if rect.width() < 1 or rect.height() < 1:
            return
        path = QPainterPath()
        path.addRoundedRect(rect, 12, 12)
        fill = QColor(90, 160, 255, 52 if drag else 28)
        painter.fillPath(path, fill)
        border = QColor(90, 170, 255, 200 if drag else 110)
        painter.setPen(QPen(border, 2.0 if drag else 1.2))
        painter.drawPath(path)

    def _draw_zone(self, painter: QPainter, geo: QRect, *, active: bool) -> None:
        if geo.width() < 2 or geo.height() < 2:
            return
        rect = QRectF(geo).adjusted(0.5, 0.5, -1.0, -1.0)
        path = QPainterPath()
        path.addRoundedRect(rect, 10, 10)
        fill = QColor(120, 200, 255, 70 if active else 22)
        painter.fillPath(path, fill)
        border = QColor(120, 200, 255, 220 if active else 90)
        pen = QPen(border, 2.0 if active else 1.0)
        pen.setStyle(Qt.PenStyle.DashLine)
        painter.setPen(pen)
        painter.drawPath(path)
