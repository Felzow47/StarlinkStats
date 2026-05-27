"""Carte métrique — drag/resize fluide (mode Personnaliser)."""

from __future__ import annotations

from PyQt6.QtCore import QPoint, QPointF, QRectF, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QLinearGradient, QPainter, QPainterPath, QPen
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMenu,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

QWIDGETSIZE_MAX = 16777215

from starlink_widget.core.card_prefs import (
    SIZE_LARGE,
    SIZE_MEDIUM,
    SIZE_SMALL,
    CardPrefs,
    save_card_pref,
)
from starlink_widget.core.display_fields import graph_footer_label, supports_graph
from starlink_widget.ui.animations import animate_height
from starlink_widget.ui.sparkline import SparklineWidget
from starlink_widget.ui.styles import (
    INNER_RADIUS,
    TEXT_SECONDARY,
    TILE_BG,
    TILE_BORDER,
)

DRAG_THRESHOLD_PX = 6
SIZE_HEIGHTS = {SIZE_SMALL: 76, SIZE_MEDIUM: 112, SIZE_LARGE: 132}
SIZE_TITLE_FONT = {SIZE_SMALL: 9, SIZE_MEDIUM: 10, SIZE_LARGE: 11}
SIZE_VALUE_FONT = {SIZE_SMALL: 15, SIZE_MEDIUM: 22, SIZE_LARGE: 26}
SIZE_UNIT_FONT = {SIZE_SMALL: 10, SIZE_MEDIUM: 11, SIZE_LARGE: 12}
GRIP_HIT = 44
HEIGHT_GRID = 8
MIN_PREVIEW_H = 56
MAX_PREVIEW_H = 160


class ResizeGripOverlay(QWidget):
    """Poignée coin bas-droit — curseur resize au survol."""

    def __init__(self, tile: "MetricTile") -> None:
        super().__init__(tile)
        self._tile = tile
        self._hover = False
        self.setFixedSize(GRIP_HIT, GRIP_HIT)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setCursor(Qt.CursorShape.SizeFDiagCursor)
        self.setToolTip("Redimensionner la carte")
        self.hide()

    def _sync_visible(self) -> None:
        show = self._tile._customize_mode and not self._tile._floating
        self.setVisible(show)
        if show:
            self.raise_()

    def enterEvent(self, event) -> None:
        self._hover = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self._hover = False
        self.update()
        super().leaveEvent(event)

    def mousePressEvent(self, event) -> None:
        if event.button() != Qt.MouseButton.LeftButton:
            super().mousePressEvent(event)
            return
        self._tile._start_resize_drag(event.globalPosition().toPoint())
        event.accept()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        active = self._hover or self._tile._drag_mode == "resize"

        if active:
            glow = QLinearGradient(0, h, w, 0)
            glow.setColorAt(0.0, QColor(90, 160, 255, 0))
            glow.setColorAt(1.0, QColor(90, 160, 255, 42))
            painter.fillRect(self.rect(), glow)

        alpha = 210 if active else 115
        pen = QPen(QColor(255, 255, 255, alpha), 2.0 if active else 1.5)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)

        inset = 9
        gap = 5
        for i in range(3):
            d = inset + i * gap
            painter.drawLine(
                QPointF(w - d, h - inset),
                QPointF(w - inset, h - d),
            )


class MetricTile(QWidget):
    float_move = pyqtSignal(QPoint)
    float_end = pyqtSignal(QPoint)
    prefs_changed = pyqtSignal(str)
    layout_preview = pyqtSignal(str)

    def __init__(
        self,
        title: str,
        field_key: str,
        prefs: CardPrefs,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.field_key = field_key
        self._prefs = prefs.normalized()
        self._saved_prefs = self._prefs
        self._customize_mode = False
        self._press_global: QPoint | None = None
        self._press_offset = QPoint()
        self._drag_mode: str | None = None
        self._floating = False
        self._drop_target = False
        self._preview_height = self._base_height()
        self.setObjectName("metricTile")
        self.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )

        root = QVBoxLayout(self)
        root.setContentsMargins(14, 12, 14, 8)
        root.setSpacing(4)

        self._header = QWidget()
        header_row = QHBoxLayout(self._header)
        header_row.setContentsMargins(0, 0, 0, 0)
        header_row.setSpacing(6)
        self.title_label = QLabel(title)
        self.title_label.setObjectName("metricTitle")
        header_row.addWidget(self.title_label, stretch=1)
        self.footer_wide = QLabel("dernière minute")
        self.footer_wide.setObjectName("metricFooter")
        header_row.addWidget(
            self.footer_wide,
            alignment=Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignRight,
        )
        root.addWidget(self._header)

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
        root.addLayout(value_row)

        self.sparkline = SparklineWidget()
        self.sparkline.setVisible(
            self._prefs.graph and supports_graph(field_key)
        )
        root.addWidget(self.sparkline)

        self._grip = ResizeGripOverlay(self)
        self.clear_width_lock()
        self._apply_dims(self._prefs.size, self._prefs.col_span, animate=False)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        s = self._grip.width()
        self._grip.move(max(0, self.width() - s), max(0, self.height() - s))
        self._grip.raise_()

    def is_resizing(self) -> bool:
        return self._drag_mode == "resize"

    def _has_graph(self) -> bool:
        return self._prefs.graph and supports_graph(self.field_key)

    def _base_height(self, size: int | None = None) -> int:
        s = size if size is not None else self._saved_prefs.size
        h = SIZE_HEIGHTS.get(s, SIZE_MEDIUM)
        if self._saved_prefs.graph and supports_graph(self.field_key):
            h += 12
        return self._snap_height_to_grid(h)

    def _snap_height_to_grid(self, height: int) -> int:
        snapped = round(height / HEIGHT_GRID) * HEIGHT_GRID
        return max(MIN_PREVIEW_H, min(MAX_PREVIEW_H, snapped))

    def _height_for_size(self, size: int) -> int:
        h = SIZE_HEIGHTS.get(size, SIZE_MEDIUM)
        if self._saved_prefs.graph and supports_graph(self.field_key):
            h += 12
        return self._snap_height_to_grid(h)

    def set_customize_mode(self, enabled: bool) -> None:
        self._customize_mode = enabled
        if enabled:
            self.setToolTip(
                "Glisser pour échanger · coin bas-droit pour redimensionner"
            )
        else:
            self._cancel_drag()
            self.setToolTip("")
        self._grip._sync_visible()

    def set_floating(self, floating: bool) -> None:
        self._floating = floating
        self.setProperty("floating", floating)
        self._grip._sync_visible()
        self.update()

    def set_drop_target(self, active: bool) -> None:
        self._drop_target = active
        self.update()

    def clear_width_lock(self) -> None:
        self.setMinimumWidth(0)
        self.setMaximumWidth(QWIDGETSIZE_MAX)
        policy = self.sizePolicy()
        policy.setHorizontalPolicy(QSizePolicy.Policy.Expanding)
        policy.setVerticalPolicy(QSizePolicy.Policy.Fixed)
        policy.setHorizontalStretch(1)
        self.setSizePolicy(policy)

    def prefs(self) -> CardPrefs:
        return self._prefs

    def set_prefs(self, prefs: CardPrefs) -> None:
        self._prefs = prefs.normalized()
        self._saved_prefs = self._prefs
        self._preview_height = self._base_height()
        self._apply_dims(self._prefs.size, self._prefs.col_span, animate=False)

    def set_value(self, value: str, unit: str = "") -> None:
        self.value_label.setText(value)
        if unit:
            self.unit_label.setText(unit)
            self.unit_label.setVisible(True)
        else:
            self.unit_label.setText("")
            self.unit_label.setVisible(False)

    def set_sparkline_data(self, data: list[float]) -> None:
        if self._prefs.graph:
            self.sparkline.set_data(data)

    def _snap_size_from_height(self, height: int) -> int:
        h = self._snap_height_to_grid(height)
        best = SIZE_MEDIUM
        best_dist = 10_000
        for size, base_h in SIZE_HEIGHTS.items():
            target = self._height_for_size(size)
            dist = abs(h - target)
            if dist < best_dist:
                best_dist = dist
                best = size
        return best

    def _span_from_delta(self, dx: int) -> int:
        if dx > 40:
            return 2
        if dx < -30:
            return 1
        return self._saved_prefs.col_span

    def _preview_height_from_delta(self, dy: int) -> int:
        start = self._height_for_size(self._saved_prefs.size)
        return self._snap_height_to_grid(start + int(dy * 0.55))

    def _apply_typography(self) -> None:
        size = self._saved_prefs.size
        title_px = SIZE_TITLE_FONT.get(size, 10)
        value_px = SIZE_VALUE_FONT.get(size, 22)
        unit_px = SIZE_UNIT_FONT.get(size, 11)

        self.title_label.setStyleSheet(
            f"color: {TEXT_SECONDARY}; font-size: {title_px}px; font-weight: 500;"
        )
        self.value_label.setStyleSheet(
            f"font-size: {value_px}px; font-weight: 700; letter-spacing: -0.5px;"
        )
        self.unit_label.setStyleSheet(
            f"color: {TEXT_SECONDARY}; font-size: {unit_px}px; font-weight: 500;"
        )
        self.footer_wide.setStyleSheet(
            f"color: {TEXT_SECONDARY}; font-size: 9px; font-weight: 400;"
        )

    def _update_footer_placement(self) -> None:
        show_graph = self._has_graph()
        wide = self._prefs.col_span >= 2
        self.footer_wide.setText(graph_footer_label(self.field_key))
        self.footer_wide.setVisible(show_graph and wide)
        self.sparkline.setVisible(show_graph)

    def _apply_dims(
        self, size: int, col_span: int, *, animate: bool, height: int | None = None
    ) -> None:
        self._prefs = CardPrefs(size, self._prefs.graph, col_span).normalized()
        self.clear_width_lock()
        h = self._snap_height_to_grid(
            height if height is not None else self._base_height(size)
        )
        self._preview_height = h
        self._update_footer_placement()
        self._apply_typography()

        if animate and self.height() != h:
            animate_height(self, h, self.parentWidget())
        else:
            self.setMinimumHeight(h)
            self.setMaximumHeight(h)

    def _start_resize_drag(self, global_pos: QPoint) -> None:
        self._press_global = global_pos
        self._drag_mode = "resize"
        self.setCursor(Qt.CursorShape.SizeFDiagCursor)
        self.grabMouse()

    def _cancel_drag(self) -> None:
        if self._drag_mode:
            self.releaseMouse()
        self._drag_mode = None
        self._press_global = None
        self.set_drag_highlight(False)
        self.set_drop_target(False)
        self.unsetCursor()
        self._apply_dims(
            self._saved_prefs.size,
            self._saved_prefs.col_span,
            animate=True,
            height=self._base_height(),
        )

    def _save_graph(self, enabled: bool) -> None:
        if not supports_graph(self.field_key):
            return
        self._prefs = CardPrefs(
            self._saved_prefs.size, enabled, self._saved_prefs.col_span
        ).normalized()
        self._saved_prefs = self._prefs
        save_card_pref(self.field_key, self._prefs)
        self._apply_dims(self._prefs.size, self._prefs.col_span, animate=True)

    def contextMenuEvent(self, event) -> None:
        menu = QMenu(self)
        if supports_graph(self.field_key):
            label = (
                "Masquer le graphique"
                if self._prefs.graph
                else "Afficher le graphique"
            )
            menu.addAction(label, self._toggle_graph)
        menu.exec(event.globalPos())

    def _commit_dims(self, size: int, span: int) -> None:
        self._saved_prefs = CardPrefs(size, self._prefs.graph, span).normalized()
        self._apply_dims(size, span, animate=True)
        save_card_pref(self.field_key, self._prefs)
        self.prefs_changed.emit(self.field_key)

    def _toggle_graph(self) -> None:
        self._save_graph(not self._prefs.graph)

    def set_drag_highlight(self, active: bool) -> None:
        self.setProperty("dragHighlight", active)
        self.update()

    def mousePressEvent(self, event) -> None:
        if not self._customize_mode or event.button() != Qt.MouseButton.LeftButton:
            super().mousePressEvent(event)
            return
        g = event.globalPosition().toPoint()
        self._press_global = g
        self._drag_mode = "move"
        self._press_offset = self.mapToGlobal(QPoint(0, 0)) - g
        self.grabMouse()
        event.accept()

    def mouseMoveEvent(self, event) -> None:
        if not self._customize_mode or self._drag_mode is None:
            super().mouseMoveEvent(event)
            return
        g = event.globalPosition().toPoint()
        if self._press_global is None:
            return

        if self._drag_mode == "resize":
            delta = g - self._press_global
            h = self._preview_height_from_delta(delta.y())
            span = self._span_from_delta(delta.x())
            height_changed = h != self._preview_height
            span_changed = span != self._prefs.col_span
            if height_changed:
                self._preview_height = h
                self.setMinimumHeight(h)
                self.setMaximumHeight(h)
            if span_changed:
                size = self._snap_size_from_height(h)
                self._apply_dims(size, span, animate=False, height=h)
                self.layout_preview.emit(self.field_key)
            event.accept()
            return

        dist = (g - self._press_global).manhattanLength()
        if not self._floating and dist >= DRAG_THRESHOLD_PX:
            self.set_drag_highlight(True)
            self.setCursor(Qt.CursorShape.SizeAllCursor)
            self.set_floating(True)
            self.float_move.emit(g + self._press_offset)

        if self._floating:
            self.float_move.emit(g + self._press_offset)
        event.accept()

    def mouseReleaseEvent(self, event) -> None:
        if self._drag_mode is None or event.button() != Qt.MouseButton.LeftButton:
            super().mouseReleaseEvent(event)
            return
        g = event.globalPosition().toPoint()

        if self._drag_mode == "resize" and self._press_global is not None:
            delta = g - self._press_global
            h = self._preview_height_from_delta(delta.y())
            size = self._snap_size_from_height(h)
            span = self._span_from_delta(delta.x())
            final_h = self._height_for_size(size)
            changed = (
                size != self._saved_prefs.size
                or span != self._saved_prefs.col_span
            )
            self._saved_prefs = CardPrefs(size, self._prefs.graph, span).normalized()
            self._apply_dims(size, span, animate=True, height=final_h)
            if changed:
                save_card_pref(self.field_key, self._prefs)
                self.prefs_changed.emit(self.field_key)
        elif self._floating:
            self.float_end.emit(g)

        self.releaseMouse()
        self._drag_mode = None
        self._press_global = None
        self.set_floating(False)
        self.set_drag_highlight(False)
        self.unsetCursor()
        event.accept()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -1.0, -1.0)
        path = QPainterPath()
        path.addRoundedRect(rect, INNER_RADIUS, INNER_RADIUS)
        fill = QColor(*TILE_BG)
        if self._floating:
            fill.setAlpha(240)
        painter.fillPath(path, fill)

        if self._drop_target:
            border = QColor(90, 170, 255, 200)
            painter.setPen(QPen(border, 2.0))
        elif self.property("dragHighlight") or self._floating:
            border = QColor(120, 180, 255, 180)
            painter.setPen(QPen(border, 1.4))
        else:
            border = QColor(*TILE_BORDER)
            painter.setPen(QPen(border, 1.0))
        painter.drawPath(path)
        super().paintEvent(event)
