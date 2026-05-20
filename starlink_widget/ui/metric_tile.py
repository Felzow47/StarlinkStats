"""Carte métrique — drag/resize en direct (mode Personnaliser)."""

from __future__ import annotations

from PyQt6.QtCore import QPoint, QRectF, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QPainter, QPainterPath, QPen
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMenu,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from starlink_widget.core.card_prefs import (
    SIZE_LARGE,
    SIZE_MEDIUM,
    SIZE_SMALL,
    CardPrefs,
    save_card_pref,
)
from starlink_widget.core.display_fields import supports_graph
from starlink_widget.ui.sparkline import SparklineWidget
from starlink_widget.ui.styles import (
    INNER_RADIUS,
    TEXT_SECONDARY,
    TILE_BG,
    TILE_BORDER,
)

DRAG_THRESHOLD_PX = 6
SIZE_HEIGHTS = {SIZE_SMALL: 76, SIZE_MEDIUM: 112, SIZE_LARGE: 132}
SIZE_VALUE_FONT = {SIZE_SMALL: 15, SIZE_MEDIUM: 22, SIZE_LARGE: 26}
GRIP_HIT = 22


class MetricTile(QWidget):
    """Signaux drag : déplacement flottant géré par MainWindow."""

    float_move = pyqtSignal(QPoint)  # position globale souris
    float_end = pyqtSignal(QPoint)
    prefs_changed = pyqtSignal(str)

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
        self._drag_mode: str | None = None  # "move" | "resize" | None
        self._floating = False
        self.setObjectName("metricTile")
        self.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )

        root = QVBoxLayout(self)
        root.setContentsMargins(14, 12, 14, 8)
        root.setSpacing(4)

        self.title_label = QLabel(title)
        self.title_label.setObjectName("metricTitle")
        root.addWidget(self.title_label)

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

        self.footer_label = QLabel("dernière minute")
        self.footer_label.setStyleSheet(
            f"color: {TEXT_SECONDARY}; font-size: 9px;"
        )
        self.footer_label.setVisible(self.sparkline.isVisible())
        root.addWidget(self.footer_label)

        self._apply_dims(self._prefs.size, self._prefs.col_span, preview=False)

    def set_customize_mode(self, enabled: bool) -> None:
        self._customize_mode = enabled
        if enabled:
            self.setToolTip(
                "Glisser pour déplacer · coin bas-droit pour redimensionner"
            )
        else:
            self._cancel_drag()
            self.setToolTip("")

    def set_floating(self, floating: bool) -> None:
        self._floating = floating
        self.setProperty("floating", floating)
        self.update()

    def prefs(self) -> CardPrefs:
        return self._prefs

    def set_prefs(self, prefs: CardPrefs) -> None:
        self._prefs = prefs.normalized()
        self._saved_prefs = self._prefs
        self._apply_dims(self._prefs.size, self._prefs.col_span, preview=False)

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

    def _dims_from_delta(self, dx: int, dy: int) -> tuple[int, int]:
        size = self._saved_prefs.size
        span = self._saved_prefs.col_span
        if dy > 36:
            size = SIZE_LARGE
        elif dy > 14:
            size = max(size, SIZE_MEDIUM)
        elif dy < -14:
            size = SIZE_SMALL
        if dx > 36:
            span = 2
        elif dx < -14:
            span = 1
        return size, span

    def _apply_dims(self, size: int, col_span: int, preview: bool) -> None:
        self._prefs = CardPrefs(size, self._prefs.graph, col_span).normalized()
        h = SIZE_HEIGHTS.get(size, SIZE_MEDIUM)
        if self._prefs.graph and supports_graph(self.field_key):
            h += 12
        self.setMinimumHeight(h)
        self.setMaximumHeight(h)
        font_px = SIZE_VALUE_FONT.get(size, 22)
        self.value_label.setStyleSheet(
            f"font-size: {font_px}px; font-weight: 700; letter-spacing: -0.5px;"
        )
        show_graph = self._prefs.graph and supports_graph(self.field_key)
        self.sparkline.setVisible(show_graph)
        self.footer_label.setVisible(show_graph)
        if not preview:
            self._saved_prefs = self._prefs

    def _hit_resize_grip(self, local: QPoint) -> bool:
        if not self._customize_mode:
            return False
        r = self.rect()
        grip = QRectF(
            r.width() - GRIP_HIT,
            r.height() - GRIP_HIT,
            GRIP_HIT,
            GRIP_HIT,
        )
        return grip.contains(local.x(), local.y())

    def _cancel_drag(self) -> None:
        if self._drag_mode:
            self.releaseMouse()
        self._drag_mode = None
        self._press_global = None
        self.set_drag_highlight(False)
        self.unsetCursor()
        self._apply_dims(
            self._saved_prefs.size,
            self._saved_prefs.col_span,
            preview=False,
        )

    def _save_graph(self, enabled: bool) -> None:
        if not supports_graph(self.field_key):
            return
        self._prefs = CardPrefs(
            self._saved_prefs.size, enabled, self._saved_prefs.col_span
        ).normalized()
        self._saved_prefs = self._prefs
        save_card_pref(self.field_key, self._prefs)
        self._apply_dims(self._prefs.size, self._prefs.col_span, preview=False)

    def contextMenuEvent(self, event) -> None:
        menu = QMenu(self)
        if supports_graph(self.field_key):
            label = (
                "Masquer le graphique"
                if self._prefs.graph
                else "Afficher le graphique"
            )
            menu.addAction(label, self._toggle_graph)
            menu.addSeparator()
        if self._customize_mode:
            menu.addAction(
                "Petite carte",
                lambda: self._commit_dims(SIZE_SMALL, self._saved_prefs.col_span),
            )
            menu.addAction(
                "Carte moyenne",
                lambda: self._commit_dims(SIZE_MEDIUM, self._saved_prefs.col_span),
            )
            menu.addAction(
                "Grande hauteur",
                lambda: self._commit_dims(SIZE_LARGE, self._saved_prefs.col_span),
            )
            menu.addSeparator()
            menu.addAction(
                "Demi-largeur",
                lambda: self._commit_dims(self._saved_prefs.size, 1),
            )
            menu.addAction(
                "Pleine largeur",
                lambda: self._commit_dims(self._saved_prefs.size, 2),
            )
        menu.exec(event.globalPos())

    def _commit_dims(self, size: int, span: int) -> None:
        self._apply_dims(size, span, preview=False)
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
        local = event.position().toPoint()
        g = event.globalPosition().toPoint()
        self._press_global = g
        if self._hit_resize_grip(local):
            self._drag_mode = "resize"
            self.setCursor(Qt.CursorShape.SizeFDiagCursor)
        else:
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
            size, span = self._dims_from_delta(delta.x(), delta.y())
            self._apply_dims(size, span, preview=True)
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

        if self._drag_mode == "resize":
            if self._press_global is not None:
                delta = g - self._press_global
                size, span = self._dims_from_delta(delta.x(), delta.y())
                changed = (
                    size != self._saved_prefs.size
                    or span != self._saved_prefs.col_span
                )
                self._apply_dims(size, span, preview=False)
                if changed:
                    save_card_pref(self.field_key, self._prefs)
                    self.prefs_changed.emit(self.field_key)
        elif self._floating:
            self.float_end.emit(g)
        elif self._drag_mode == "move":
            pass

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
            fill.setAlpha(235)
        painter.fillPath(path, fill)
        border = QColor(*TILE_BORDER)
        if self.property("dragHighlight") or self._floating:
            border = QColor(120, 180, 255, 180)
        painter.setPen(QPen(border, 1.2 if self._floating else 1.0))
        painter.drawPath(path)

        if self._customize_mode and not self._floating:
            grip = QRectF(
                rect.right() - GRIP_HIT,
                rect.bottom() - GRIP_HIT,
                GRIP_HIT - 2,
                GRIP_HIT - 2,
            )
            painter.setPen(QPen(QColor(255, 255, 255, 70), 1.2))
            for i in range(3):
                for j in range(3 - i):
                    painter.drawPoint(
                        int(grip.left() + 4 + i * 4),
                        int(grip.top() + 4 + j * 4),
                    )
        super().paintEvent(event)
