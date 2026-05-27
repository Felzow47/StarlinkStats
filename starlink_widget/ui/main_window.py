"""Main always-on-top widget window."""

from __future__ import annotations

from collections import defaultdict, deque
from typing import Deque, Dict, List, Optional, Set

from PyQt6.QtCore import QPoint, QEasingCurve, QRect, QRectF, QPropertyAnimation, QSettings, QSize, Qt, QTimer
from PyQt6.QtGui import (
    QAction,
    QCursor,
    QColor,
    QFontMetrics,
    QIcon,
    QMouseEvent,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
)
from PyQt6.QtWidgets import (
    QApplication,
    QGridLayout,
    QLabel,
    QMenu,
    QSystemTrayIcon,
    QVBoxLayout,
    QWidget,
)

from starlink_widget.core import autostart
from starlink_widget.core.config import AppConfig
from starlink_widget.debug_log import debug_exception, debug_log
from starlink_widget.core.card_prefs import CardPrefs, get_card_pref
from starlink_widget.core.display_fields import (
    FIELD_BY_KEY,
    HEADER_KEYS,
    format_field,
    numeric_sample,
    supports_graph,
)
from starlink_widget.core.models import StatusSnapshot
from starlink_widget.core.state import HealthState, evaluate_health
from starlink_widget.core.widget_prefs import (
    load_ordered_metric_keys,
    load_visible_fields,
)

from starlink_widget.ui.animations import DURATION_OPACITY
from starlink_widget.ui.grid_drag import (
    DropTarget,
    apply_drop_target,
    compute_drop_targets,
    pick_drop_target,
    target_identity,
)
from starlink_widget.ui.grid_layout import metrics_area_width, place_metric_tiles
from starlink_widget.ui.layout_drag_preview import LayoutDragPreview
from starlink_widget.ui.metric_tile import MetricTile
from starlink_widget.ui.settings_dialog import SettingsDialog
from starlink_widget.ui.snap_corner_hint import SnapCandidate, SnapCornerHint
from starlink_widget.ui.styles import (
    CARD_BG,
    CARD_BG_FLASH,
    CARD_BORDER,
    CORNER_RADIUS,
    OK_GREEN,
    WIDGET_WIDTH,
    format_status_title,
    label_styles,
    status_color,
)
from starlink_widget.workers.poll_worker import PollWorker

SETTINGS_ORG = "StarlinkWidget"
SETTINGS_APP = "Widget"
HISTORY_LEN = 60
HOVER_SHOW_DELAY_MS = 800
CORNER_SNAP_RADIUS = 100
CORNER_INSET = 24


class StatusDot(QWidget):
    SIZE = 10

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._color = QColor(OK_GREEN)
        self.setFixedSize(self.SIZE, self.SIZE)

    def set_color(self, hex_color: str) -> None:
        self._color = QColor(hex_color)
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(self._color)
        s = self.SIZE
        painter.drawEllipse(0, 0, s, s)


class StatusTitleRow(QWidget):
    """Ligne statut : point coloré aligné optiquement sur le titre."""

    GAP = 8

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.status_dot = StatusDot(self)
        self.status_title = QLabel("Initialisation", self)
        self.status_title.setObjectName("statusTitle")
        self.status_title.setAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        )

    def sizeHint(self) -> QSize:
        fm = QFontMetrics(self.status_title.font())
        h = max(StatusDot.SIZE, fm.height())
        return QSize(200, h)

    def minimumSizeHint(self) -> QSize:
        return self.sizeHint()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._layout_row()

    def _layout_row(self) -> None:
        row_h = self.height()
        title_x = StatusDot.SIZE + self.GAP
        dot_y = (row_h - StatusDot.SIZE) // 2
        self.status_dot.setGeometry(0, dot_y, StatusDot.SIZE, StatusDot.SIZE)
        self.status_title.setGeometry(
            title_x,
            0,
            max(0, self.width() - title_x),
            row_h,
        )


class MainWindow(QWidget):
    def __init__(self, config: AppConfig) -> None:
        super().__init__()
        self.config = config
        self._drag_pos: QPoint | None = None
        self._flash_on = False
        self._current_state = HealthState.GREEN
        self._last_status_text = "Initialisation"
        self._worker: PollWorker | None = None
        self._last_snapshot: Optional[StatusSnapshot] = None
        self._visible_fields: Set[str] = load_visible_fields()
        self._metric_tiles: Dict[str, MetricTile] = {}
        self._history: Dict[str, Deque[float]] = defaultdict(
            lambda: deque(maxlen=HISTORY_LEN)
        )
        self._settings_dialog: SettingsDialog | None = None
        self._float_tile: MetricTile | None = None
        self._float_target_pos = QPoint()
        self._float_pointer_global = QPoint()
        self._float_smooth_timer = QTimer(self)
        self._float_smooth_timer.setInterval(16)
        self._float_smooth_timer.timeout.connect(self._tick_float_smooth)
        self._cursor_over = False
        self._opacity_anim: QPropertyAnimation | None = None
        self._hover_timer = QTimer(self)
        self._hover_timer.setInterval(50)
        self._hover_timer.timeout.connect(self._poll_hover_passive)
        self._show_delay_timer = QTimer(self)
        self._show_delay_timer.setSingleShot(True)
        self._show_delay_timer.timeout.connect(self._fade_in_passive)
        self._snap_hint = SnapCornerHint()
        self._float_placeholder: QWidget | None = None
        self._layout_preview: LayoutDragPreview | None = None
        self._pending_drop_target_key: str | None = None
        self._highlighted_drop_target_key: str | None = None
        self._drop_targets: list[DropTarget] = []
        self._active_drop_target: DropTarget | None = None
        self._preview_target_key: tuple | None = None

        self.setObjectName("StarlinkWidget")
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setFixedWidth(WIDGET_WIDTH)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.DefaultContextMenu)

        self._build_ui()
        self._rebuild_metrics_grid()
        self._restore_geometry()
        self._setup_tray()
        self._setup_flash_timer()
        self._start_worker()
        self._fit_to_content()
        self._hover_timer.start()
        self._apply_interaction_mode()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        QTimer.singleShot(0, self._layout_metrics_when_ready)

    def _layout_metrics_when_ready(self) -> None:
        if self._float_tile is not None:
            return
        self._relayout_grid_positions(animated=False)

    def _build_ui(self) -> None:
        self._root_layout = QVBoxLayout(self)
        self._root_layout.setContentsMargins(14, 14, 14, 12)
        self._root_layout.setSpacing(10)

        self._header_wrap = QWidget()
        header = QVBoxLayout(self._header_wrap)
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(2)

        title_row = StatusTitleRow()
        self._title_row = title_row
        self.status_dot = title_row.status_dot
        self.status_title = title_row.status_title
        header.addWidget(title_row)

        self.status_subtitle = QLabel("")
        self.status_subtitle.setObjectName("statusSubtitle")
        self.status_subtitle.setContentsMargins(18, 0, 0, 0)
        self.status_subtitle.setVisible(False)
        header.addWidget(self.status_subtitle)
        self._root_layout.addWidget(self._header_wrap)

        self.alert_label = QLabel("")
        self.alert_label.setObjectName("alertLabel")
        self.alert_label.setWordWrap(True)
        self.alert_label.setVisible(False)
        self._root_layout.addWidget(self.alert_label)

        self._metrics_wrap = QWidget()
        self._metrics_layout = QGridLayout(self._metrics_wrap)
        self._metrics_layout.setSpacing(8)
        self._metrics_layout.setColumnStretch(0, 1)
        self._metrics_layout.setColumnStretch(1, 1)
        self._layout_preview = LayoutDragPreview(self._metrics_wrap)
        self._metrics_wrap.setVisible(False)
        self._root_layout.addWidget(self._metrics_wrap)

        self.setStyleSheet(label_styles())
        self._title_row.updateGeometry()
        self._title_row._layout_row()
        self._apply_paint_state(HealthState.GREEN)

    def _create_metric_tile(self, key: str) -> MetricTile:
        field = FIELD_BY_KEY[key]
        prefs = get_card_pref(key)
        tile = MetricTile(field.label, key, prefs, parent=self._metrics_wrap)
        tile.hide()
        tile.float_move.connect(self._on_tile_float_move)
        tile.float_end.connect(self._on_tile_float_end)
        tile.prefs_changed.connect(self._on_tile_prefs_changed)
        tile.layout_preview.connect(self._on_tile_layout_preview)
        # #region agent log
        debug_log(
            "main_window:_create_metric_tile",
            "tile created",
            {
                "key": key,
                "parent": tile.parent().objectName() if tile.parent() else None,
                "is_window": tile.isWindow(),
            },
            hypothesis_id="L",
            run_id="orphan-window",
        )
        # #endregion
        return tile

    def _remove_metric_tile(self, key: str) -> None:
        tile = self._metric_tiles.pop(key, None)
        if tile is None:
            return
        if tile.parent() is self._metrics_wrap:
            self._metrics_layout.removeWidget(tile)
        tile.hide()
        tile.setParent(None)
        tile.deleteLater()

    def _rebuild_metrics_grid(self) -> None:
        for key in list(self._metric_tiles.keys()):
            self._remove_metric_tile(key)

        for key in load_ordered_metric_keys():
            tile = self._create_metric_tile(key)
            self._metric_tiles[key] = tile
            
        for tile in self._metric_tiles.values():
            tile.show()
        
        self._relayout_grid_positions(animated=False)
        self._sync_customize_mode()

        if self._last_snapshot is not None:
            self._apply_snapshot(self._last_snapshot)

    def _on_tile_layout_preview(self, _key: str) -> None:
        self._relayout_grid_positions(animated=False)

    def _clear_drop_highlights(self) -> None:
        for tile in self._metric_tiles.values():
            tile.set_drop_target(False)
        self._highlighted_drop_target_key = None

    def _clear_drag_preview(self) -> None:
        if self._layout_preview is not None:
            self._layout_preview.clear_preview()

    def _metric_placement(
        self, order: List[str]
    ) -> List[tuple[str, MetricTile, CardPrefs]]:
        return [
            (key, self._metric_tiles[key], self._metric_tiles[key].prefs())
            for key in order
            if key in self._metric_tiles
        ]

    def _prepare_placement_for_layout(
        self, placement: List[tuple[str, MetricTile, CardPrefs]],
    ) -> List[tuple[str, MetricTile, CardPrefs]]:
        for _key, tile, _prefs in placement:
            if tile is self._float_tile:
                continue
            if hasattr(tile, "prepare_for_grid_layout"):
                tile.prepare_for_grid_layout()
        return placement

    def _refresh_drop_targets(self) -> None:
        if self._float_tile is None:
            self._drop_targets = []
            return
        placement = self._metric_placement(
            [k for k in load_ordered_metric_keys() if k in self._metric_tiles]
        )
        spacing = self._metrics_layout.spacing()
        width = metrics_area_width(self._metrics_wrap)
        drag_key = self._float_tile.field_key
        self._drop_targets = compute_drop_targets(
            width, spacing, placement, drag_key=drag_key
        )
        # #region agent log
        debug_log(
            "main_window:_refresh_drop_targets",
            "drop targets",
            {
                "drag_key": drag_key,
                "width": width,
                "n_targets": len(self._drop_targets),
            },
            hypothesis_id="E",
        )
        # #endregion

    def _float_pointer_local(self) -> QPoint:
        if self._float_tile is None:
            return QPoint()
        ft = self._float_tile
        return ft.pos() + QPoint(ft.width() // 2, ft.height() // 2)

    def _pick_drop_target(
        self, local_point: QPoint, *, refresh: bool = False
    ) -> DropTarget | None:
        if refresh or not self._drop_targets:
            self._refresh_drop_targets()
        if not self._drop_targets or self._float_tile is None:
            return None
        width = metrics_area_width(self._metrics_wrap)
        spacing = self._metrics_layout.spacing()
        return pick_drop_target(
            self._drop_targets,
            local_point,
            container_width=width,
            spacing=spacing,
            drag_compact=self._float_tile.is_grid_compact(),
            previous=self._active_drop_target,
        )

    def _apply_drop(self, drag_key: str, target: DropTarget) -> bool:
        order_before = [
            k for k in load_ordered_metric_keys() if k in self._metric_tiles
        ]
        prefs_before = get_card_pref(drag_key)
        drag_tile = self._metric_tiles.get(drag_key)
        anchor_tile = self._metric_tiles.get(target.anchor_key)
        drag_compact = (
            drag_tile.is_grid_compact() if drag_tile is not None else False
        )
        anchor_compact = (
            anchor_tile.is_grid_compact() if anchor_tile is not None else False
        )
        apply_drop_target(
            drag_key,
            target,
            drag_compact=drag_compact,
            anchor_compact=anchor_compact,
        )
        if drag_tile is not None:
            drag_tile.set_prefs(get_card_pref(drag_key))
        if target.action == "swap" and anchor_tile is not None:
            anchor_tile.set_prefs(get_card_pref(target.anchor_key))
        order_after = [
            k for k in load_ordered_metric_keys() if k in self._metric_tiles
        ]
        prefs_after = get_card_pref(drag_key)
        changed = (
            order_before != order_after
            or prefs_before.grid_col != prefs_after.grid_col
        )
        # #region agent log
        debug_log(
            "main_window:_apply_drop",
            "drop applied",
            {
                "drag_key": drag_key,
                "action": target.action,
                "anchor": target.anchor_key,
                "col": target.grid_col,
                "stack": target.stack,
                "rect": [
                    target.rect.x(),
                    target.rect.y(),
                    target.rect.width(),
                    target.rect.height(),
                ],
                "col_before": prefs_before.grid_col,
                "col_after": prefs_after.grid_col,
                "changed": changed,
            },
            hypothesis_id="K",
            run_id="grid-drag-v2",
        )
        # #endregion
        return changed

    def _show_drop_preview(self, target: DropTarget) -> None:
        if self._float_tile is None or self._layout_preview is None:
            return
        drag_key = self._float_tile.field_key
        active = target.rect
        self._layout_preview.set_compact_zones([active], active=active)
        self._layout_preview.set_preview({}, active)
        self._float_tile.raise_()
        # #region agent log
        debug_log(
            "main_window:_show_drop_preview",
            "drop preview",
            {
                "drag_key": drag_key,
                "compact": self._float_tile.is_grid_compact(),
                "static_moved": False,
                "n_zones": 1,
                "action": target.action,
                "anchor": target.anchor_key,
                "col": target.grid_col,
            },
            hypothesis_id="L",
        )
        # #endregion

    def _remove_float_placeholder(self) -> None:
        try:
            ph = self._float_placeholder
            self._float_placeholder = None
            if ph is None:
                return
            if self._metrics_layout.indexOf(ph) >= 0:
                self._metrics_layout.removeWidget(ph)
            ph.hide()
            ph.setParent(None)
            ph.deleteLater()
        except Exception as exc:
            debug_exception("main_window:_remove_float_placeholder", exc, hypothesis_id="D")
            raise

    def _detach_float_tile(self, tile: MetricTile) -> None:
        self._pending_drop_target_key = None
        self._highlighted_drop_target_key = None
        self._active_drop_target = None
        try:
            idx = self._metrics_layout.indexOf(tile)
            # #region agent log
            debug_log(
                "main_window:_detach_float_tile",
                "detach start",
                {
                    "field_key": tile.field_key,
                    "layout_idx": idx,
                    "tile_size": [tile.width(), tile.height()],
                },
                hypothesis_id="A",
            )
            # #endregion
            geo = tile.geometry()
            if tile.parent() is self._metrics_wrap and geo.width() > 0:
                self._remove_float_placeholder()
                self._float_placeholder = QWidget(self._metrics_wrap)
                self._float_placeholder.setGeometry(geo)
            elif idx >= 0:
                self._metrics_layout.removeWidget(tile)
            tile.setParent(self._metrics_wrap)
            tile.raise_()
            tile.set_floating(True)
            spacing = self._metrics_layout.spacing()
            col_w = max(
                1, (metrics_area_width(self._metrics_wrap) - spacing) // 2
            )
            tile.setFixedWidth(col_w)
            self._clear_drag_preview()
            self._preview_target_key = None
            self._refresh_drop_targets()
            # #region agent log
            debug_log(
                "main_window:_detach_float_tile",
                "detach ok",
                {"field_key": tile.field_key},
                hypothesis_id="A",
            )
            # #endregion
        except Exception as exc:
            debug_exception("main_window:_detach_float_tile", exc, hypothesis_id="A")
            raise

    def _relayout_grid_positions(self, *, animated: bool = False) -> None:
        """Réorganise la grille 2 colonnes avec alignement strict."""
        has_orphans = any(
            tile.parent() is not self._metrics_wrap
            for tile in self._metric_tiles.values()
        )
        if self._float_tile is not None and not has_orphans:
            return
        starts: Dict[str, object] = {}
        if animated:
            for key, tile in self._metric_tiles.items():
                if tile.parent() is not self._metrics_wrap:
                    continue
                starts[key] = tile.geometry()

        self._remove_float_placeholder()

        metric_keys = load_ordered_metric_keys()
        placement: List[tuple[str, MetricTile, CardPrefs]] = []
        for key in metric_keys:
            if key not in self._metric_tiles:
                continue
            tile = self._metric_tiles[key]
            placement.append((key, tile, get_card_pref(key)))
        place_metric_tiles(self._metrics_layout, placement)

        if animated and starts:
            from starlink_widget.ui.animations import animate_geometry

            for key, tile in self._metric_tiles.items():
                if key not in starts:
                    continue
                end = tile.geometry()
                start = starts[key]
                if start.topLeft() != end.topLeft():
                    tile.setGeometry(start)
                    animate_geometry(tile, end, self._metrics_wrap)

        self._fit_to_content()

    def _reload_preferences(self) -> None:
        self._visible_fields = load_visible_fields()
        existing = set(self._metric_tiles.keys())
        wanted = set(load_ordered_metric_keys())
        removed = existing - wanted
        added = wanted - existing

        for key in removed:
            self._remove_metric_tile(key)

        for key in added:
            tile = self._create_metric_tile(key)
            self._metric_tiles[key] = tile

        if removed or added:
            self._relayout_grid_positions(animated=False)
            for key, tile in self._metric_tiles.items():
                if tile.parent() is self._metrics_wrap:
                    tile.show()
                else:
                    # #region agent log
                    debug_log(
                        "main_window:_reload_preferences",
                        "orphan tile skipped show",
                        {
                            "key": key,
                            "parent": (
                                tile.parent().objectName()
                                if tile.parent()
                                else None
                            ),
                            "is_window": tile.isWindow(),
                        },
                        hypothesis_id="L",
                        run_id="orphan-window",
                    )
                    # #endregion
            if self._last_snapshot is not None:
                self._apply_snapshot(self._last_snapshot)
            self._sync_customize_mode()
            self._fit_to_content()
            return

        if wanted:
            for key in wanted:
                tile = self._metric_tiles.get(key)
                if tile is not None:
                    tile.set_prefs(get_card_pref(key))
            self._relayout_grid_positions(animated=True)
            if self._last_snapshot is not None:
                self._apply_snapshot(self._last_snapshot)
            self._fit_to_content()

    def _is_customize_mode(self) -> bool:
        return (
            self._settings_dialog is not None
            and self._settings_dialog.isVisible()
        )

    def _stop_opacity_anim(self) -> None:
        anim = self._opacity_anim
        if anim is None:
            return
        self._opacity_anim = None
        anim.stop()

    def _on_opacity_anim_finished(self) -> None:
        self._opacity_anim = None

    def _animate_passive_opacity(self, target: float) -> None:
        if abs(self.windowOpacity() - target) < 0.01:
            self.setWindowOpacity(target)
            return
        self._stop_opacity_anim()
        anim = QPropertyAnimation(self, b"windowOpacity", self)
        anim.setDuration(DURATION_OPACITY)
        anim.setStartValue(self.windowOpacity())
        anim.setEndValue(target)
        anim.setEasingCurve(QEasingCurve.Type.InOutCubic)
        anim.finished.connect(self._on_opacity_anim_finished)
        anim.start()
        self._opacity_anim = anim

    def _fade_out_passive(self) -> None:
        self._show_delay_timer.stop()
        self._animate_passive_opacity(0.0)

    def _schedule_fade_in_passive(self) -> None:
        self._show_delay_timer.stop()
        if not self._cursor_over:
            self._stop_opacity_anim()
            self._show_delay_timer.start(HOVER_SHOW_DELAY_MS)

    def _fade_in_passive(self) -> None:
        if self._cursor_over or self._is_customize_mode():
            return
        self._animate_passive_opacity(1.0)

    def _apply_interaction_mode(self) -> None:
        """Mode normal (perso ouverte) vs passif (click-through + fade au survol)."""
        if self._is_customize_mode():
            self._show_delay_timer.stop()
            self._stop_opacity_anim()
            self.setWindowOpacity(1.0)
            self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
            self._cursor_over = False
            return
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        over = self.frameGeometry().contains(QCursor.pos())
        self._cursor_over = over
        self._show_delay_timer.stop()
        self._stop_opacity_anim()
        if over:
            self.setWindowOpacity(0.0)
        else:
            self.setWindowOpacity(1.0)

    def _poll_hover_passive(self) -> None:
        if not self.isVisible() or self._is_customize_mode():
            return
        over = self.frameGeometry().contains(QCursor.pos())
        if over == self._cursor_over:
            return
        self._cursor_over = over
        if over:
            self._fade_out_passive()
        else:
            self._schedule_fade_in_passive()

    def _sync_customize_mode(self) -> None:
        on = self._is_customize_mode()
        if not on and self._float_tile is not None:
            self._cancel_float_drag()
        if not on:
            self._hide_snap_hint()
        for tile in self._metric_tiles.values():
            tile.set_customize_mode(on)
        self._apply_interaction_mode()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -1.0, -1.0)
        path = QPainterPath()
        path.addRoundedRect(rect, CORNER_RADIUS, CORNER_RADIUS)
        fill = (
            QColor(*CARD_BG_FLASH)
            if self._flash_on and self._current_state == HealthState.RED
            else QColor(*CARD_BG)
        )
        painter.fillPath(path, fill)
        painter.setPen(QPen(QColor(*CARD_BORDER), 1.0))
        painter.drawPath(path)

    def _apply_paint_state(self, state: HealthState, flashing: bool = False) -> None:
        self._current_state = state
        self._flash_on = flashing
        self.status_dot.set_color(status_color(state, flashing))
        self.update()

    def _fit_to_content(self) -> None:
        if self._root_layout is not None:
            self._root_layout.activate()
            hint = self._root_layout.sizeHint()
            self.setFixedSize(WIDGET_WIDTH, max(hint.height(), 72))

    def _set_status(self, raw_text: str, subtitle: str = "") -> None:
        self.status_title.setText(format_status_title(raw_text))
        self._title_row.updateGeometry()
        self._title_row._layout_row()
        if subtitle:
            self.status_subtitle.setText(subtitle)
            self.status_subtitle.setVisible(True)
        else:
            self.status_subtitle.setText("")
            self.status_subtitle.setVisible(False)

    def contextMenuEvent(self, event) -> None:
        if not self._is_customize_mode():
            event.ignore()
            return
        menu = QMenu(self)
        hide_action = menu.addAction("Masquer")
        hide_action.triggered.connect(self.hide)
        quit_action = menu.addAction("Quitter le widget")
        quit_action.triggered.connect(self._quit_app)
        menu.exec(event.globalPos())

    def _on_tile_float_move(self, global_top_left: QPoint) -> None:
        try:
            if not self._is_customize_mode():
                return
            tile = self.sender()
            if not isinstance(tile, MetricTile):
                return
            if self._float_tile is None:
                self._float_tile = tile
                self._detach_float_tile(tile)
            ft = self._float_tile
            self._float_target_pos = self._metrics_wrap.mapFromGlobal(global_top_left)
            pointer_local = self._metrics_wrap.mapFromGlobal(
                global_top_left + QPoint(ft.width() // 2, ft.height() // 2)
            )
            candidate = self._pick_drop_target(pointer_local)
            self._active_drop_target = candidate
            # #region agent log
            debug_log(
                "main_window:_on_tile_float_move",
                "float move",
                {
                    "drag_key": ft.field_key,
                    "compact": ft.is_grid_compact(),
                    "pointer": [pointer_local.x(), pointer_local.y()],
                    "cursor": [self._float_target_pos.x(), self._float_target_pos.y()],
                    "slot_action": candidate.action if candidate else None,
                    "slot_anchor": candidate.anchor_key if candidate else None,
                    "slot_col": candidate.grid_col if candidate else None,
                    "slot_rect": (
                        [
                            candidate.rect.x(),
                            candidate.rect.y(),
                            candidate.rect.width(),
                            candidate.rect.height(),
                        ]
                        if candidate
                        else None
                    ),
                },
                hypothesis_id="H",
            )
            # #endregion
            if (
                abs(ft.pos().x() - self._float_target_pos.x()) > 1
                or abs(ft.pos().y() - self._float_target_pos.y()) > 1
            ):
                ft.move(self._float_target_pos)
            self._float_pointer_global = self._metrics_wrap.mapToGlobal(
                pointer_local
            )
            if not self._float_smooth_timer.isActive():
                self._float_smooth_timer.start()
        except Exception as exc:
            debug_exception(
                "main_window:_on_tile_float_move",
                exc,
                hypothesis_id="E",
                extra={"global": [global_top_left.x(), global_top_left.y()]},
            )
            raise

    def _tick_float_smooth(self) -> None:
        try:
            if self._float_tile is None:
                self._float_smooth_timer.stop()
                return
            cur = self._float_tile.pos()
            tgt = self._float_target_pos
            if (
                abs(cur.x() - tgt.x()) > 1
                or abs(cur.y() - tgt.y()) > 1
            ):
                nx = cur.x() + int((tgt.x() - cur.x()) * 0.55)
                ny = cur.y() + int((tgt.y() - cur.y()) * 0.55)
                if abs(nx - tgt.x()) <= 1 and abs(ny - tgt.y()) <= 1:
                    self._float_tile.move(tgt)
                else:
                    self._float_tile.move(nx, ny)
            ft = self._float_tile
            center_local = ft.pos() + QPoint(ft.width() // 2, ft.height() // 2)
            self._float_pointer_global = self._metrics_wrap.mapToGlobal(center_local)
            self._update_drag_target_preview()
        except Exception as exc:
            debug_exception("main_window:_tick_float_smooth", exc, hypothesis_id="B")
            raise

    def _update_drag_target_preview(self) -> None:
        if self._float_tile is None or self._layout_preview is None:
            return
        target = self._active_drop_target
        if target is None:
            target = self._pick_drop_target(self._float_pointer_local())
        if target is None:
            self._clear_drop_highlights()
            self._clear_drag_preview()
            self._pending_drop_target_key = None
            self._preview_target_key = None
            return
        self._active_drop_target = target
        self._clear_drop_highlights()
        self._highlighted_drop_target_key = None
        self._pending_drop_target_key = target.anchor_key
        target_key = target_identity(target)
        if target_key == self._preview_target_key:
            return
        self._preview_target_key = target_key
        self._show_drop_preview(target)

    def _on_tile_float_end(self, global_pos: QPoint) -> None:
        drag_key: str | None = None
        try:
            # #region agent log
            debug_log(
                "main_window:_on_tile_float_end",
                "float end start",
                {"global": [global_pos.x(), global_pos.y()]},
                hypothesis_id="C",
            )
            # #endregion
            self._float_smooth_timer.stop()
            self._clear_drag_preview()
            if self._float_tile is None:
                return
            drag_key = self._float_tile.field_key
            self._clear_drop_highlights()
            target = self._active_drop_target
            if target is None:
                local = self._metrics_wrap.mapFromGlobal(global_pos)
                target = self._pick_drop_target(local)
            did_swap = False
            if target is not None:
                did_swap = self._apply_drop(drag_key, target)
            # #region agent log
            debug_log(
                "main_window:_on_tile_float_end",
                "drop resolved",
                {
                    "drag_key": drag_key,
                    "action": target.action if target else None,
                    "anchor": target.anchor_key if target else None,
                    "col": target.grid_col if target else None,
                    "did_swap": did_swap,
                },
                hypothesis_id="A",
                run_id="grid-drag-v2",
            )
            # #endregion
        except Exception as exc:
            debug_exception("main_window:_on_tile_float_end", exc, hypothesis_id="C")
            raise
        finally:
            self._pending_drop_target_key = None
            self._highlighted_drop_target_key = None
            self._active_drop_target = None
            self._preview_target_key = None
            self._drop_targets = []
            if self._float_tile is not None:
                floating = self._float_tile
                floating.clear_width_lock()
                floating.set_floating(False)
                self._float_tile = None
            self._remove_float_placeholder()
            self._relayout_grid_positions(animated=True)
            # #region agent log
            if drag_key is not None:
                debug_log(
                    "main_window:_on_tile_float_end",
                    "float end ok",
                    {"drag_key": drag_key},
                    hypothesis_id="C",
                )
            # #endregion
            if self._settings_dialog is not None:
                self._settings_dialog.refresh_list()

    def _cancel_float_drag(self) -> None:
        self._float_smooth_timer.stop()
        self._clear_drop_highlights()
        self._clear_drag_preview()
        self._pending_drop_target_key = None
        self._highlighted_drop_target_key = None
        self._active_drop_target = None
        self._drop_targets = []
        if self._float_tile is None:
            return
        floating = self._float_tile
        floating.clear_width_lock()
        floating.set_floating(False)
        self._float_tile = None
        self._remove_float_placeholder()
        self._relayout_grid_positions(animated=False)

    def _on_tile_prefs_changed(self, key: str) -> None:
        tile = self._metric_tiles.get(key)
        animated = tile is None or not tile.is_resizing()
        self._relayout_grid_positions(animated=animated)

    def _push_history(self, snapshot: StatusSnapshot) -> None:
        for key in self._metric_tiles:
            if not supports_graph(key):
                continue
            sample = numeric_sample(snapshot, key)
            hist = self._history[key]
            if sample is not None:
                hist.append(sample)
            elif key == "pop_ping_latency" and hist:
                # Ping parfois absent (perte) : prolonger la courbe pour le graphique
                hist.append(hist[-1])
            elif key == "pop_ping_drop_rate":
                # Perte nulle ou absente : garder la courbe à 0 %
                hist.append(0.0)

    def _open_settings(self) -> None:
        if self._settings_dialog is None:
            self._settings_dialog = SettingsDialog(self)
            self._settings_dialog.setWindowFlags(
                Qt.WindowType.Window
                | Qt.WindowType.WindowStaysOnTopHint
                | Qt.WindowType.CustomizeWindowHint
                | Qt.WindowType.WindowTitleHint
                | Qt.WindowType.WindowCloseButtonHint
            )
            self._settings_dialog.preferences_changed.connect(
                self._reload_preferences
            )
            self._settings_dialog.finished.connect(self._sync_customize_mode)
        if self._settings_dialog.isVisible():
            self._settings_dialog.raise_()
            self._settings_dialog.activateWindow()
        else:
            self._settings_dialog.show()
        self._sync_customize_mode()

    def _quit_app(self) -> None:
        self._save_geometry()
        if self._worker:
            self._worker.stop()
            self._worker.wait(3000)
        self.tray.hide()
        QApplication.instance().quit()

    def _setup_flash_timer(self) -> None:
        self._flash_timer = QTimer(self)
        self._flash_timer.setInterval(500)
        self._flash_timer.timeout.connect(self._toggle_flash)

    def _toggle_flash(self) -> None:
        if self._current_state == HealthState.RED and self.isVisible():
            flashing = not self._flash_on
            self._apply_paint_state(HealthState.RED, flashing=flashing)
            self._update_tray(
                HealthState.RED, self._last_status_text, flashing=flashing
            )

    def _make_tray_icon(self, hex_color: str = OK_GREEN) -> QIcon:
        size = 64
        pix = QPixmap(size, size)
        pix.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pix)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setBrush(QColor(hex_color))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(10, 10, size - 20, size - 20)
        painter.end()
        return QIcon(pix)

    def _update_tray(
        self,
        state: HealthState,
        status_text: str,
        *,
        flashing: bool = False,
    ) -> None:
        if not hasattr(self, "tray"):
            return
        self.tray.setIcon(
            self._make_tray_icon(status_color(state, flashing))
        )
        title = format_status_title(status_text)
        self.tray.setToolTip(f"Starlink — {title}")

    def _setup_tray(self) -> None:
        self.tray = QSystemTrayIcon(self)
        self.tray.setIcon(self._make_tray_icon())
        self.tray.setToolTip("Starlink Widget")
        menu = QMenu()
        show_action = QAction("Afficher", self)
        show_action.triggered.connect(self.show)
        menu.addAction(show_action)
        hide_action = QAction("Masquer", self)
        hide_action.triggered.connect(self.hide)
        menu.addAction(hide_action)
        menu.addSeparator()
        customize = QAction("Personnaliser…", self)
        customize.triggered.connect(self._open_settings)
        menu.addAction(customize)
        menu.addSeparator()
        self.autostart_action = QAction("Démarrer avec Windows", self)
        self.autostart_action.setCheckable(True)
        self.autostart_action.setChecked(autostart.is_enabled())
        self.autostart_action.triggered.connect(self._toggle_autostart)
        menu.addAction(self.autostart_action)
        menu.addSeparator()
        quit_action = QAction("Quitter le widget", self)
        quit_action.triggered.connect(self._quit_app)
        menu.addAction(quit_action)
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(self._tray_activated)
        self.tray.show()

    def _tray_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            if self.isVisible():
                self.hide()
            else:
                self.show()

    def _toggle_autostart(self, checked: bool) -> None:
        if checked:
            ok = autostart.enable()
        else:
            ok = autostart.disable()
        if not ok:
            self.autostart_action.setChecked(autostart.is_enabled())

    def _start_worker(self) -> None:
        self._worker = PollWorker(self.config, self)
        self._worker.snapshot_ready.connect(self._on_snapshot)
        self._worker.visibility_changed.connect(self._on_visibility)
        self._worker.start()

    def _on_visibility(self, visible: bool) -> None:
        if visible:
            self.show()
            if self._last_snapshot is not None:
                self._update_tray(
                    self._current_state,
                    self._last_status_text,
                    flashing=self._flash_on,
                )
            else:
                self._update_tray(HealthState.GREEN, "Initialisation")
        else:
            self._flash_timer.stop()
            self.hide()
            self._update_tray(HealthState.HIDDEN, "Hors réseau Starlink")

    def _on_snapshot(self, snapshot: StatusSnapshot) -> None:
        if not snapshot.on_starlink_lan:
            return
        self._last_snapshot = snapshot
        self._apply_snapshot(snapshot)

    def _apply_snapshot(self, snapshot: StatusSnapshot) -> None:
        health, status_text = evaluate_health(snapshot)
        self._current_state = health
        self._last_status_text = status_text

        show_header = "connection_status" in self._visible_fields
        self._header_wrap.setVisible(show_header)
        if show_header:
            subtitle = ""
            if status_text.startswith("EN LIGNE — "):
                subtitle = status_text.split(" — ", 1)[1]
            self._set_status(status_text, subtitle)

        if health == HealthState.RED:
            if not self._flash_timer.isActive():
                self._flash_timer.start()
            self._apply_paint_state(health, flashing=self._flash_on)
        else:
            self._flash_timer.stop()
            self._apply_paint_state(health, flashing=False)

        self._update_tray(
            health,
            status_text,
            flashing=health == HealthState.RED and self._flash_on,
        )

        show_alerts = "alerts_summary" in self._visible_fields
        alerts = snapshot.critical_alerts
        if show_alerts and alerts:
            self.alert_label.setText(" · ".join(alerts))
            self.alert_label.setVisible(True)
        else:
            self.alert_label.setText("")
            self.alert_label.setVisible(False)

        has_tiles = bool(self._metric_tiles)
        show_metrics = has_tiles and snapshot.dish_reachable
        self._metrics_wrap.setVisible(show_metrics)

        if show_metrics:
            self._push_history(snapshot)
            for key, tile in self._metric_tiles.items():
                formatted = format_field(snapshot, key)
                if formatted is None:
                    tile.set_value("—", "")
                else:
                    value, unit = formatted
                    if key == "azimuth_delta" and snapshot.azimuth_delta_deg is not None:
                        if abs(snapshot.azimuth_delta_deg) > 5:
                            value += " ⚠"
                    tile.set_value(value, unit)
                hist = list(self._history.get(key, []))
                if tile.prefs().graph and hist:
                    tile.set_sparkline_data(hist)
                if tile.parent() is self._metrics_wrap:
                    tile.setVisible(True)
                elif tile.isWindow():
                    tile.hide()
        elif has_tiles:
            for tile in self._metric_tiles.values():
                if tile.parent() is self._metrics_wrap:
                    tile.setVisible(False)
                elif tile.isWindow():
                    tile.hide()

        self._fit_to_content()

    def _restore_geometry(self) -> None:
        settings = QSettings(SETTINGS_ORG, SETTINGS_APP)
        if settings.contains("geometry"):
            self.restoreGeometry(settings.value("geometry"))
        else:
            screen = QApplication.primaryScreen()
            if screen:
                geo = screen.availableGeometry()
                self.move(geo.right() - self.width() - 40, geo.top() + 40)

    def _save_geometry(self) -> None:
        settings = QSettings(SETTINGS_ORG, SETTINGS_APP)
        settings.setValue("geometry", self.saveGeometry())

    def _corner_snap_pos(self, proposed: QPoint) -> QPoint:
        candidate = self._find_snap_candidate(proposed)
        return candidate.widget_pos if candidate else proposed

    def _find_snap_candidate(self, proposed: QPoint) -> SnapCandidate | None:
        """Coin d'accrochage le plus proche, tous écrans confondus."""
        w = self.width()
        h = self.height()
        snap_d2 = CORNER_SNAP_RADIUS * CORNER_SNAP_RADIUS
        best: SnapCandidate | None = None
        best_d2 = snap_d2 + 1

        for screen in QApplication.screens():
            area = screen.availableGeometry().adjusted(
                CORNER_INSET, CORNER_INSET, -CORNER_INSET, -CORNER_INSET
            )
            if area.width() < w or area.height() < h:
                continue
            x0 = area.x()
            y0 = area.y()
            x1 = area.x() + area.width() - w
            y1 = area.y() + area.height() - h
            options = (
                ("tl", QPoint(x0, y0)),
                ("tr", QPoint(x1, y0)),
                ("bl", QPoint(x0, y1)),
                ("br", QPoint(x1, y1)),
            )
            for corner, widget_pos in options:
                dx = proposed.x() - widget_pos.x()
                dy = proposed.y() - widget_pos.y()
                d2 = dx * dx + dy * dy
                if d2 <= snap_d2 and d2 < best_d2:
                    best_d2 = d2
                    best = SnapCandidate(widget_pos, corner)
        return best

    def _update_snap_hint(self, proposed: QPoint) -> None:
        candidate = self._find_snap_candidate(proposed)
        if candidate:
            self._snap_hint.show_corner(
                candidate.corner,
                candidate.widget_pos,
                QSize(self.width(), self.height()),
            )
        else:
            self._hide_snap_hint()

    def _hide_snap_hint(self) -> None:
        self._snap_hint.hide_hint()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if not self._is_customize_mode():
            event.ignore()
            return
        if event.button() == Qt.MouseButton.LeftButton:
            child = self.childAt(event.position().toPoint())
            if isinstance(child, MetricTile) or self._is_under_metric_tile(child):
                super().mousePressEvent(event)
                return
            self._drag_pos = (
                event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            )
            event.accept()

    @staticmethod
    def _is_under_metric_tile(widget: QWidget | None) -> bool:
        while widget is not None:
            if isinstance(widget, MetricTile):
                return True
            widget = widget.parentWidget()
        return False

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if not self._is_customize_mode():
            event.ignore()
            return
        if self._drag_pos is not None and event.buttons() & Qt.MouseButton.LeftButton:
            proposed = event.globalPosition().toPoint() - self._drag_pos
            self.move(proposed)
            self._update_snap_hint(proposed)
            event.accept()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if not self._is_customize_mode():
            event.ignore()
            return
        if self._drag_pos is not None:
            self.move(self._corner_snap_pos(self.frameGeometry().topLeft()))
        self._drag_pos = None
        self._hide_snap_hint()
        self._save_geometry()

    def closeEvent(self, event) -> None:
        self._quit_app()
        event.accept()
