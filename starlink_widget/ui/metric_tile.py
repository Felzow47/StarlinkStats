"""Carte métrique — drag/resize fluide (mode Personnaliser)."""

from __future__ import annotations

from PyQt6.QtCore import QPoint, QPointF, QRect, QRectF, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QLinearGradient, QPainter, QPainterPath, QPen
from PyQt6.QtGui import QMouseEvent  # noqa: F401 – utilisé dans les signatures
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
MAX_PREVIEW_H = 160
GRAPH_HEIGHT_EXTRA = 12
# Sous cette hauteur : texte seul (graphique masqué), prefs.graph inchangé
GRAPH_VISIBLE_MIN_H = SIZE_HEIGHTS[SIZE_SMALL] + GRAPH_HEIGHT_EXTRA
MIN_HEIGHT_TEXT_ONLY = SIZE_HEIGHTS[SIZE_SMALL]
# Texte seul : plus petit que le preset S (graphique masqué)
MIN_HEIGHT_COMPACT = 56
# Cartes empilables dans une même colonne (texte seul, sans graphique)
COMPACT_GRID_MAX_H = MIN_HEIGHT_TEXT_ONLY


def _lerp_int(lo: int, hi: int, t: float) -> int:
    return int(round(lo + (hi - lo) * max(0.0, min(1.0, t))))


# Taille de la zone cliquable (en px) pour chaque poignée de bord
GRIP_THICKNESS = 8
GRIP_MIN_W = 100
GRIP_MIN_H = 56


class EdgeHandle(QWidget):
    """Poignée invisible sur un bord du tile — curseur + détection click."""

    EDGES = ("top", "bottom", "left", "right")
    CURSORS = {
        "top": Qt.CursorShape.SizeVerCursor,
        "bottom": Qt.CursorShape.SizeVerCursor,
        "left": Qt.CursorShape.SizeHorCursor,
        "right": Qt.CursorShape.SizeHorCursor,
    }

    def __init__(self, tile: "MetricTile", edge: str) -> None:
        super().__init__(tile)
        self._tile = tile
        self._edge = edge
        self._hover = False
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setCursor(self.CURSORS[edge])
        self.setMouseTracking(True)
        self.hide()

    def sync_geometry(self) -> None:
        """Place la poignée sur le bon bord du tile parent."""
        t = GRIP_THICKNESS
        w, h = self._tile.width(), self._tile.height()
        if self._edge == "top":
            self.setGeometry(t, 0, w - 2 * t, t)
        elif self._edge == "bottom":
            self.setGeometry(t, h - t, w - 2 * t, t)
        elif self._edge == "left":
            self.setGeometry(0, t, t, h - 2 * t)
        elif self._edge == "right":
            self.setGeometry(w - t, t, t, h - 2 * t)
        self.raise_()

    def sync_visible(self) -> None:
        show = self._tile._customize_mode and not self._tile._floating
        self.setVisible(show)
        if show:
            self.sync_geometry()

    def enterEvent(self, event) -> None:
        self._hover = True
        self._tile.update()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self._hover = False
        self._tile.update()
        super().leaveEvent(event)

    def mousePressEvent(self, event) -> None:
        if event.button() != Qt.MouseButton.LeftButton:
            super().mousePressEvent(event)
            return
        self._tile._start_resize_drag(event.globalPosition().toPoint(), self._edge)
        event.accept()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        active = self._tile._drag_mode == f"resize_{self._edge}"
        w, h = self.width(), self.height()

        # 3 niveaux : drag actif > survol > visible au repos
        if active:
            alpha = 220
        elif self._hover:
            alpha = 160
        else:
            alpha = 60  # toujours visible en mode personnaliser

        color = QColor(100, 180, 255, alpha)
        if self._edge in ("top", "bottom"):
            bar_h = 3 if (active or self._hover) else 2
            y_bar = (h - bar_h) // 2
            painter.fillRect(8, y_bar, w - 16, bar_h, color)
        else:
            bar_w = 3 if (active or self._hover) else 2
            x_bar = (w - bar_w) // 2
            painter.fillRect(x_bar, 8, bar_w, h - 16, color)


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
        self._graph_user_wants = self._prefs.graph
        self._customize_mode = False
        self._press_global: QPoint | None = None
        self._press_offset = QPoint()
        self._drag_mode: str | None = None  # "move" | "resize_top" | ...
        self._floating = False
        self._drop_target = False
        self._preview_height = self._base_height()
        # Dimensions au début du resize
        self._resize_start_geo: QRect = QRect()
        # Position au début du move (géré par MainWindow en mode flottant)
        self.setObjectName("metricTile")
        self.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )

        self._root_layout = QVBoxLayout(self)
        self._root_layout.setContentsMargins(14, 12, 14, 8)
        self._root_layout.setSpacing(4)

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
        self._root_layout.addWidget(self._header)

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
        self._root_layout.addLayout(value_row)

        self.sparkline = SparklineWidget()
        self.sparkline.setVisible(
            self._prefs.graph and supports_graph(field_key)
        )
        self._root_layout.addWidget(self.sparkline)

        # 4 poignées de redimensionnement
        self._handles = {e: EdgeHandle(self, e) for e in EdgeHandle.EDGES}

        self.clear_width_lock()
        self._apply_dims(self._prefs.size, self._prefs.col_span, animate=False)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        for h in self._handles.values():
            if h.isVisible():
                h.sync_geometry()

    def is_resizing(self) -> bool:
        return self._drag_mode is not None and self._drag_mode.startswith("resize_")

    def _show_graph_for_height(self, height: int) -> bool:
        """Graphique visible seulement si la hauteur le permet (sinon texte seul)."""
        return (
            self._graph_user_wants
            and supports_graph(self.field_key)
            and height >= GRAPH_VISIBLE_MIN_H
        )

    def _graph_pref_for_height(self, height: int) -> bool:
        """Valeur graph à persister selon la hauteur (compact = masqué)."""
        return self._show_graph_for_height(height)

    def _base_height(self, size: int | None = None) -> int:
        if self._saved_prefs.height_px > 0:
            return self._snap_height_to_grid(self._saved_prefs.height_px)
        s = size if size is not None else self._saved_prefs.size
        if supports_graph(self.field_key) and self._saved_prefs.graph:
            h = SIZE_HEIGHTS.get(s, SIZE_MEDIUM) + GRAPH_HEIGHT_EXTRA
            return self._snap_height_to_grid(h)
        if not supports_graph(self.field_key) or not self._saved_prefs.graph:
            return self._snap_height_to_grid(MIN_HEIGHT_COMPACT)
        h = SIZE_HEIGHTS.get(s, SIZE_MEDIUM)
        return self._snap_height_to_grid(h)

    def _min_allowed_height(self, height: int | None = None) -> int:
        """Plancher : compact sans graphique, sinon hauteur avec graphique."""
        h = self._preview_height if height is None else height
        if self._show_graph_for_height(h):
            return round(GRAPH_VISIBLE_MIN_H / HEIGHT_GRID) * HEIGHT_GRID
        return round(MIN_HEIGHT_COMPACT / HEIGHT_GRID) * HEIGHT_GRID

    def _snap_height_to_grid(self, height: int) -> int:
        snapped = round(height / HEIGHT_GRID) * HEIGHT_GRID
        return max(self._min_allowed_height(height), min(MAX_PREVIEW_H, snapped))

    def _height_for_size(self, size: int) -> int:
        h = SIZE_HEIGHTS.get(size, SIZE_MEDIUM)
        if self._saved_prefs.graph and supports_graph(self.field_key):
            h += GRAPH_HEIGHT_EXTRA
        return self._snap_height_to_grid(h)

    def _candidate_heights(self) -> list[tuple[int, int]]:
        """Hauteurs cibles (preset, px) pour le snap au relâchement."""
        out: list[tuple[int, int]] = []
        compact_h = round(MIN_HEIGHT_COMPACT / HEIGHT_GRID) * HEIGHT_GRID
        out.append((SIZE_SMALL, compact_h))
        for size, base in SIZE_HEIGHTS.items():
            out.append((size, round(base / HEIGHT_GRID) * HEIGHT_GRID))
            if self._graph_user_wants and supports_graph(self.field_key):
                with_graph = base + GRAPH_HEIGHT_EXTRA
                out.append(
                    (size, round(with_graph / HEIGHT_GRID) * HEIGHT_GRID)
                )
        return out

    def set_customize_mode(self, enabled: bool) -> None:
        self._customize_mode = enabled
        if enabled:
            self.setToolTip("Glisser pour déplacer · bords pour redimensionner")
        else:
            self._cancel_drag()
            self.setToolTip("")
        for h in self._handles.values():
            h.sync_visible()

    def set_floating(self, floating: bool) -> None:
        self._floating = floating
        self.setProperty("floating", floating)
        for h in self._handles.values():
            h.sync_visible()
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
        self._graph_user_wants = self._prefs.graph
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
        if self._show_graph_for_height(self.height()):
            self.sparkline.set_data(data)

    def _snap_size_from_height(self, height: int) -> int:
        h = self._snap_height_to_grid(height)
        best = SIZE_MEDIUM
        best_dist = 10_000
        for size, target in self._candidate_heights():
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

    def _content_min_height(self) -> int:
        """Hauteur minimale pour afficher titre + valeur sans coupure."""
        self._root_layout.activate()
        return self._root_layout.sizeHint().height()

    def _is_compact_height(self, height: int) -> bool:
        return height <= COMPACT_GRID_MAX_H and not self._show_graph_for_height(height)

    def _grid_height_from_prefs(self) -> int:
        if self._saved_prefs.height_px > 0:
            return self._snap_height_to_grid(self._saved_prefs.height_px)
        if self._preview_height > 0:
            return self._snap_height_to_grid(self._preview_height)
        return self._base_height()

    def layout_height(self) -> int:
        """Hauteur de référence pour la grille."""
        h = self._grid_height_from_prefs()
        if self._is_compact_height(h):
            return h
        return max(h, self._content_min_height())

    def prepare_for_grid_layout(self) -> int:
        """Sync typo + hauteur (conserve le compact choisi par l'utilisateur)."""
        h = self._grid_height_from_prefs()
        self._preview_height = h
        self._update_footer_placement()
        self._apply_compact_layout(h)
        self._apply_typography(h)
        if not self._is_compact_height(h):
            need = self._content_min_height()
            if need > h:
                h = self._snap_height_to_grid(need)
                self._preview_height = h
                self._apply_compact_layout(h)
                self._apply_typography(h)
        return h

    def apply_grid_geometry(self, geo: QRect) -> None:
        """Positionne la carte et applique la typo pour cette taille."""
        h = geo.height()
        self._preview_height = h
        self.setFixedSize(geo.width(), h)
        self.move(geo.topLeft())
        self._update_footer_placement()
        self._apply_compact_layout(h)
        self._apply_typography(h)
        if self._is_compact_height(h):
            return
        need = self._content_min_height()
        if need > h:
            h = self._snap_height_to_grid(need)
            self._preview_height = h
            self.setFixedHeight(h)
            self._apply_typography(h)

    def is_grid_compact(self) -> bool:
        """Carte assez petite pour s'empiler avec une autre dans la même colonne."""
        if self._prefs.col_span >= 2:
            return False
        h = self.layout_height()
        return h <= COMPACT_GRID_MAX_H and not self._show_graph_for_height(h)

    def _typography_height_range(self) -> tuple[int, int]:
        """Bornes hauteur pour l'interpolation des polices (carte avec graphique)."""
        h_min = MIN_HEIGHT_TEXT_ONLY
        h_max = SIZE_HEIGHTS[SIZE_LARGE]
        if self._graph_user_wants and supports_graph(self.field_key):
            h_max += GRAPH_HEIGHT_EXTRA
        return h_min, max(h_min + 1, h_max)

    def _typography_scale(self, height: int) -> float:
        h_min, h_max = self._typography_height_range()
        return (height - h_min) / (h_max - h_min)

    def _apply_typography(self, height: int | None = None) -> None:
        h = self._preview_height if height is None else height
        if not self._show_graph_for_height(h):
            # Texte seul : polices lisibles, légère variation selon la hauteur
            t_c = (h - MIN_HEIGHT_COMPACT) / max(
                1, MIN_HEIGHT_TEXT_ONLY - MIN_HEIGHT_COMPACT
            )
            title_px = _lerp_int(
                SIZE_TITLE_FONT[SIZE_SMALL], SIZE_TITLE_FONT[SIZE_MEDIUM], t_c
            )
            value_px = _lerp_int(
                SIZE_VALUE_FONT[SIZE_SMALL], SIZE_VALUE_FONT[SIZE_MEDIUM], t_c
            )
            unit_px = _lerp_int(
                SIZE_UNIT_FONT[SIZE_SMALL], SIZE_UNIT_FONT[SIZE_MEDIUM], t_c
            )
            footer_px = 8
        else:
            t = self._typography_scale(h)
            title_px = _lerp_int(
                SIZE_TITLE_FONT[SIZE_SMALL], SIZE_TITLE_FONT[SIZE_LARGE], t
            )
            value_px = _lerp_int(
                SIZE_VALUE_FONT[SIZE_SMALL], SIZE_VALUE_FONT[SIZE_LARGE], t
            )
            unit_px = _lerp_int(
                SIZE_UNIT_FONT[SIZE_SMALL], SIZE_UNIT_FONT[SIZE_LARGE], t
            )
            footer_px = _lerp_int(8, 9, t)

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
            f"color: {TEXT_SECONDARY}; font-size: {footer_px}px; font-weight: 400;"
        )
        if self._is_compact_height(h):
            self.title_label.setMinimumHeight(0)
            self.value_label.setMinimumHeight(0)
        elif h >= MIN_HEIGHT_TEXT_ONLY:
            self.title_label.setMinimumHeight(title_px + 4)
            self.value_label.setMinimumHeight(value_px + 6)
        else:
            self.title_label.setMinimumHeight(0)
            self.value_label.setMinimumHeight(0)

    def _update_footer_placement(self) -> None:
        show_graph = self._show_graph_for_height(self._preview_height)
        wide = self._prefs.col_span >= 2
        self.footer_wide.setText(graph_footer_label(self.field_key))
        self.footer_wide.setVisible(show_graph and wide)
        self.sparkline.setVisible(show_graph)
        if show_graph:
            self.sparkline.setMaximumHeight(QWIDGETSIZE_MAX)
        else:
            self.sparkline.setMaximumHeight(0)

    def _apply_compact_layout(self, height: int) -> None:
        """Marges réduites en mode texte seul très compact."""
        compact = not self._show_graph_for_height(height)
        if compact and height < MIN_HEIGHT_TEXT_ONLY:
            self._root_layout.setContentsMargins(10, 6, 10, 4)
            self._root_layout.setSpacing(2)
        else:
            self._root_layout.setContentsMargins(14, 12, 14, 8)
            self._root_layout.setSpacing(4)

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
        self._apply_compact_layout(h)
        self._apply_typography(h)

        if animate and self.height() != h:
            animate_height(self, h, self.parentWidget())
        else:
            self.setMinimumHeight(h)
            self.setMaximumHeight(h)

    def _start_resize_drag(self, global_pos: QPoint, edge: str) -> None:
        """Démarre un resize sur le bord donné ; mémorise la géométrie initiale."""
        self._press_global = global_pos
        self._drag_mode = f"resize_{edge}"
        self._resize_start_geo = self.geometry()
        self.grabMouse()

    def _cancel_drag(self) -> None:
        if self._drag_mode:
            self.releaseMouse()
        self._drag_mode = None
        self._press_global = None
        self.set_drag_highlight(False)
        self.set_drop_target(False)
        self.unsetCursor()
        if self.is_resizing():
            # Restaure les dimensions d'avant resize
            geo = self._resize_start_geo
            if geo.isValid():
                self.setFixedSize(geo.width(), geo.height())
                self.move(geo.topLeft())

    def _save_graph(self, enabled: bool) -> None:
        if not supports_graph(self.field_key):
            return
        self._graph_user_wants = enabled
        h = max(self._preview_height, GRAPH_VISIBLE_MIN_H) if enabled else self._preview_height
        self._prefs = CardPrefs(
            self._saved_prefs.size,
            enabled,
            self._saved_prefs.col_span,
            height_px=self._saved_prefs.height_px,
        ).normalized()
        self._saved_prefs = self._prefs
        save_card_pref(self.field_key, self._prefs)
        self._apply_dims(self._prefs.size, self._prefs.col_span, animate=True, height=h)

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
        self._saved_prefs = CardPrefs(
            size, self._prefs.graph, span, height_px=self._preview_height
        ).normalized()
        self._apply_dims(size, span, animate=True)
        save_card_pref(self.field_key, self._prefs)
        self.prefs_changed.emit(self.field_key)

    def _toggle_graph(self) -> None:
        self._save_graph(not self._prefs.graph)

    def set_drag_highlight(self, active: bool) -> None:
        self.setProperty("dragHighlight", active)
        self.update()

    # ------------------------------------------------------------------
    # Resize helpers
    # ------------------------------------------------------------------

    def _edge_at(self, local_pos) -> str | None:
        """Retourne le nom du bord ('top','bottom','left','right') si on est dans la zone de poignée, sinon None."""
        if not self._customize_mode:
            return None
        t = GRIP_THICKNESS * 2  # zone de détection un peu plus large côté centre
        x, y = local_pos.x(), local_pos.y()
        w, h = self.width(), self.height()
        if y <= t:
            return "top"
        if y >= h - t:
            return "bottom"
        if x <= t:
            return "left"
        if x >= w - t:
            return "right"
        return None

    def _update_cursor(self, local_pos) -> None:
        """Met à jour le curseur selon la zone survolée (mode personnaliser seulement)."""
        if not self._customize_mode:
            self.unsetCursor()
            return
        edge = self._edge_at(local_pos)
        if edge in ("top", "bottom"):
            self.setCursor(Qt.CursorShape.SizeVerCursor)
        elif edge in ("left", "right"):
            self.setCursor(Qt.CursorShape.SizeHorCursor)
        else:
            self.unsetCursor()

    def _perform_resize(self, delta: QPoint, edge: str) -> None:
        """Applique le resize en live sur le bon bord, sans bouger la position opposée."""
        geo = self._resize_start_geo
        parent = self.parentWidget()

        if edge == "bottom":
            new_h = max(GRIP_MIN_H, geo.height() + delta.y())
            new_h = round(new_h / HEIGHT_GRID) * HEIGHT_GRID
        elif edge == "top":
            new_h = max(GRIP_MIN_H, geo.height() - delta.y())
            new_h = round(new_h / HEIGHT_GRID) * HEIGHT_GRID
            new_y = geo.bottom() + 1 - new_h
            self.move(self.x(), max(0, new_y))
        elif edge == "right":
            max_w = (parent.width() - geo.x()) if parent else 9999
            new_w = max(GRIP_MIN_W, min(max_w, geo.width() + delta.x()))
            new_w = round(new_w / 4) * 4
            self.setFixedWidth(new_w)
            for h in self._handles.values():
                h.sync_geometry()
            return
        elif edge == "left":
            new_w = max(GRIP_MIN_W, geo.width() - delta.x())
            new_w = round(new_w / 4) * 4
            new_x = geo.right() + 1 - new_w
            if parent:
                new_x = max(0, new_x)
                new_w = geo.right() + 1 - new_x
            self.setFixedWidth(new_w)
            self.move(new_x, self.y())
            for h in self._handles.values():
                h.sync_geometry()
            return
        else:
            return

        # Hauteur
        if edge in ("top", "bottom"):
            self._preview_height = new_h
            self._update_footer_placement()
            self._apply_compact_layout(new_h)
            self._apply_typography(new_h)
            self.setFixedHeight(new_h)
            for h in self._handles.values():
                h.sync_geometry()

    def _finish_resize(self) -> None:
        """Persiste les nouvelles dimensions après un resize."""
        final_w = self.width()
        final_h = self.height()
        graph_save = self._graph_pref_for_height(final_h)
        size = self._snap_size_from_height(final_h)
        parent = self.parentWidget()
        total_w = parent.width() if parent else final_w * 2
        span = 2 if final_w >= total_w * 0.75 else 1
        self._saved_prefs = CardPrefs(
            size, graph_save, span,
            height_px=final_h, grid_col=self._saved_prefs.grid_col,
            width_px=final_w,
        ).normalized()
        self._prefs = self._saved_prefs
        self._preview_height = final_h
        save_card_pref(self.field_key, self._prefs)
        self.prefs_changed.emit(self.field_key)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if not self._customize_mode or event.button() != Qt.MouseButton.LeftButton:
            super().mousePressEvent(event)
            return
        g = event.globalPosition().toPoint()
        edge = self._edge_at(event.pos())
        if edge:
            self._start_resize_drag(g, edge)
        else:
            self._drag_mode = "move"
            self._press_global = g
            self._press_offset = self.mapToGlobal(QPoint(0, 0)) - g
            self.grabMouse()
        event.accept()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if not self._customize_mode or self._drag_mode is None:
            self._update_cursor(event.pos())
            super().mouseMoveEvent(event)
            return
        g = event.globalPosition().toPoint()
        if self._press_global is None:
            return
        delta = g - self._press_global
        if self._drag_mode.startswith("resize"):
            self._perform_resize(delta, self._drag_mode.split("_")[1])
        elif self._drag_mode == "move":
            dist = (g - self._press_global).manhattanLength()
            if not self._floating and dist >= DRAG_THRESHOLD_PX:
                self.set_drag_highlight(True)
                self.setCursor(Qt.CursorShape.SizeAllCursor)
                self.set_floating(True)
                self.float_move.emit(g + self._press_offset)
            if self._floating:
                self.float_move.emit(g + self._press_offset)
        event.accept()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if self._drag_mode is None:
            super().mouseReleaseEvent(event)
            return
        g = event.globalPosition().toPoint()
        if self._drag_mode.startswith("resize"):
            self._finish_resize()
        elif self._drag_mode == "move" and self._floating:
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
