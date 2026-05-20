"""Main always-on-top widget window."""

from __future__ import annotations

from PyQt6.QtCore import QPoint, QRectF, QSettings, Qt, QTimer
from PyQt6.QtGui import (
    QAction,
    QColor,
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
    QHBoxLayout,
    QLabel,
    QMenu,
    QSystemTrayIcon,
    QVBoxLayout,
    QWidget,
)

from starlink_widget.core import autostart
from starlink_widget.core.config import AppConfig
from starlink_widget.core.models import StatusSnapshot
from starlink_widget.core.state import HealthState, evaluate_health
from starlink_widget.ui.metric_tile import MetricTile
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


class StatusDot(QWidget):
    """Pastille de statut (style app)."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._color = QColor(OK_GREEN)
        self.setFixedSize(10, 10)

    def set_color(self, hex_color: str) -> None:
        self._color = QColor(hex_color)
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(self._color)
        painter.drawEllipse(0, 0, 10, 10)


class MainWindow(QWidget):
    def __init__(self, config: AppConfig) -> None:
        super().__init__()
        self.config = config
        self._drag_pos: QPoint | None = None
        self._flash_on = False
        self._current_state = HealthState.GREEN
        self._worker: PollWorker | None = None

        self.setObjectName("StarlinkWidget")
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setFixedWidth(WIDGET_WIDTH)

        self._build_ui()
        self._restore_geometry()
        self._setup_tray()
        self._setup_flash_timer()
        self._start_worker()
        self._fit_to_content()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 12)
        layout.setSpacing(10)

        header = QHBoxLayout()
        header.setSpacing(8)
        self.status_dot = StatusDot()
        header.addWidget(self.status_dot, alignment=Qt.AlignmentFlag.AlignTop)
        header_text = QVBoxLayout()
        header_text.setSpacing(1)
        self.status_title = QLabel("Initialisation")
        self.status_title.setObjectName("statusTitle")
        header_text.addWidget(self.status_title)
        self.status_subtitle = QLabel("")
        self.status_subtitle.setObjectName("statusSubtitle")
        self.status_subtitle.setVisible(False)
        header_text.addWidget(self.status_subtitle)
        header.addLayout(header_text, stretch=1)
        layout.addLayout(header)

        self.alert_label = QLabel("")
        self.alert_label.setObjectName("alertLabel")
        self.alert_label.setWordWrap(True)
        self.alert_label.setVisible(False)
        layout.addWidget(self.alert_label)

        metrics = QGridLayout()
        metrics.setSpacing(8)
        metrics.setColumnStretch(0, 1)
        metrics.setColumnStretch(1, 1)
        self.dl_tile = MetricTile("Descendant")
        self.ul_tile = MetricTile("Montant")
        metrics.addWidget(self.dl_tile, 0, 0)
        metrics.addWidget(self.ul_tile, 0, 1)
        self.align_tile = MetricTile("Alignement")
        metrics.addWidget(self.align_tile, 1, 0, 1, 2)
        self._metrics_wrap = QWidget()
        self._metrics_wrap.setLayout(metrics)
        self._metrics_wrap.setVisible(False)
        layout.addWidget(self._metrics_wrap)

        self.version_label = QLabel("")
        self.version_label.setObjectName("versionLabel")
        self.version_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.version_label.setVisible(False)
        layout.addWidget(self.version_label)

        self.setStyleSheet(label_styles())
        self._apply_paint_state(HealthState.GREEN)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -1.0, -1.0)
        path = QPainterPath()
        path.addRoundedRect(rect, CORNER_RADIUS, CORNER_RADIUS)

        if self._flash_on and self._current_state == HealthState.RED:
            fill = QColor(*CARD_BG_FLASH)
        else:
            fill = QColor(*CARD_BG)
        painter.fillPath(path, fill)
        painter.setPen(QPen(QColor(*CARD_BORDER), 1.0))
        painter.drawPath(path)

    def _apply_paint_state(self, state: HealthState, flashing: bool = False) -> None:
        self._current_state = state
        self._flash_on = flashing
        self.status_dot.set_color(status_color(state, flashing))
        self.update()

    def _fit_to_content(self) -> None:
        if self.layout() is not None:
            self.layout().activate()
            hint = self.layout().sizeHint()
            self.setFixedSize(WIDGET_WIDTH, max(hint.height(), 80))

    def _set_status(self, health: HealthState, raw_text: str, subtitle: str = "") -> None:
        self.status_title.setText(format_status_title(raw_text))
        if subtitle:
            self.status_subtitle.setText(subtitle)
            self.status_subtitle.setVisible(True)
        else:
            self.status_subtitle.setText("")
            self.status_subtitle.setVisible(False)

    def _setup_flash_timer(self) -> None:
        self._flash_timer = QTimer(self)
        self._flash_timer.setInterval(500)
        self._flash_timer.timeout.connect(self._toggle_flash)

    def _toggle_flash(self) -> None:
        if self._current_state == HealthState.RED and self.isVisible():
            self._apply_paint_state(HealthState.RED, flashing=not self._flash_on)

    def _make_tray_icon(self) -> QIcon:
        size = 64
        pix = QPixmap(size, size)
        pix.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pix)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setBrush(QColor(OK_GREEN))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(10, 10, size - 20, size - 20)
        painter.end()
        return QIcon(pix)

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
        self.autostart_action = QAction("Démarrer avec Windows", self)
        self.autostart_action.setCheckable(True)
        self.autostart_action.setChecked(autostart.is_enabled())
        self.autostart_action.triggered.connect(self._toggle_autostart)
        menu.addAction(self.autostart_action)
        menu.addSeparator()
        quit_action = QAction("Quitter", self)
        quit_action.triggered.connect(QApplication.instance().quit)
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
            self.tray.setToolTip("Starlink Widget")
        else:
            self._flash_timer.stop()
            self.hide()
            self.tray.setToolTip("Hors réseau Starlink — widget masqué")

    def _on_snapshot(self, snapshot: StatusSnapshot) -> None:
        if not snapshot.on_starlink_lan:
            return

        health, status_text = evaluate_health(snapshot)
        self._current_state = health

        subtitle = ""
        if status_text.startswith("EN LIGNE — "):
            subtitle = status_text.split(" — ", 1)[1]
        self._set_status(health, status_text, subtitle)

        if health == HealthState.RED:
            if not self._flash_timer.isActive():
                self._flash_timer.start()
            self._apply_paint_state(health, flashing=self._flash_on)
        else:
            self._flash_timer.stop()
            self._apply_paint_state(health, flashing=False)

        alerts = snapshot.critical_alerts
        if alerts:
            self.alert_label.setText(" · ".join(alerts))
            self.alert_label.setVisible(True)
        else:
            self.alert_label.setText("")
            self.alert_label.setVisible(False)

        show_metrics = snapshot.dish_reachable
        self._metrics_wrap.setVisible(show_metrics)

        if snapshot.azimuth_delta_deg is not None:
            delta = snapshot.azimuth_delta_deg
            suffix = " ⚠" if abs(delta) > 5 else ""
            self.align_tile.set_value(f"{delta:+.1f}°{suffix}", "écart azimut")
            self.align_tile.setVisible(True)
        else:
            self.align_tile.setVisible(False)

        if show_metrics:
            dl = (
                f"{snapshot.downlink_mbps:.1f}"
                if snapshot.downlink_mbps is not None
                else "—"
            )
            ul = (
                f"{snapshot.uplink_mbps:.1f}"
                if snapshot.uplink_mbps is not None
                else "—"
            )
            self.dl_tile.set_value(dl, "Mbps")
            self.ul_tile.set_value(ul, "Mbps")
            self.dl_tile.setVisible(True)
            self.ul_tile.setVisible(True)
        else:
            self.dl_tile.setVisible(False)
            self.ul_tile.setVisible(False)

        ver = snapshot.software_version or ""
        self.version_label.setText(ver)
        self.version_label.setVisible(bool(ver))

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

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = (
                event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            )
            event.accept()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._drag_pos is not None and event.buttons() & Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        self._drag_pos = None
        self._save_geometry()

    def closeEvent(self, event) -> None:
        self._save_geometry()
        if self._worker:
            self._worker.stop()
            self._worker.wait(3000)
        self.tray.hide()
        super().closeEvent(event)
