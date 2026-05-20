"""Main always-on-top widget window."""

from __future__ import annotations

from PyQt6.QtCore import QPoint, QSettings, Qt, QTimer
from PyQt6.QtGui import QAction, QColor, QIcon, QMouseEvent, QPixmap, QPainter
from PyQt6.QtWidgets import (
    QApplication,
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
from starlink_widget.ui.styles import style_for_state
from starlink_widget.workers.poll_worker import PollWorker

SETTINGS_ORG = "StarlinkWidget"
SETTINGS_APP = "Widget"


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
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
        self.resize(320, 180)

        self._build_ui()
        self._restore_geometry()
        self._setup_tray()
        self._setup_flash_timer()
        self._start_worker()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(6)

        self.status_label = QLabel("Initialisation…")
        self.status_label.setObjectName("statusLabel")
        layout.addWidget(self.status_label)

        self.alert_label = QLabel("")
        self.alert_label.setObjectName("alertLabel")
        self.alert_label.setWordWrap(True)
        layout.addWidget(self.alert_label)

        self.align_label = QLabel("")
        self.align_label.setObjectName("detailLabel")
        layout.addWidget(self.align_label)

        self.throughput_label = QLabel("")
        self.throughput_label.setObjectName("detailLabel")
        layout.addWidget(self.throughput_label)

        self.version_label = QLabel("")
        self.version_label.setObjectName("detailLabel")
        layout.addWidget(self.version_label)

        row = QHBoxLayout()
        self.indicator = QLabel("●")
        self.indicator.setStyleSheet("font-size: 28px; background: transparent;")
        row.addWidget(self.indicator)
        row.addStretch()
        layout.addLayout(row)

        self._apply_style(HealthState.GREEN)

    def _setup_flash_timer(self) -> None:
        self._flash_timer = QTimer(self)
        self._flash_timer.setInterval(500)
        self._flash_timer.timeout.connect(self._toggle_flash)

    def _toggle_flash(self) -> None:
        if self._current_state == HealthState.RED and self.isVisible():
            self._flash_on = not self._flash_on
            self._apply_style(HealthState.RED, flashing=self._flash_on)

    def _make_tray_icon(self) -> QIcon:
        size = 64
        pix = QPixmap(size, size)
        pix.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pix)
        painter.setBrush(QColor("#3dcc3d"))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(8, 8, size - 16, size - 16)
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

        self.status_label.setText(status_text)
        self._apply_style(health)

        if health == HealthState.RED:
            if not self._flash_timer.isActive():
                self._flash_timer.start()
        else:
            self._flash_timer.stop()
            self._flash_on = False

        alerts = snapshot.critical_alerts
        self.alert_label.setText(
            "⚠ " + " · ".join(alerts) if alerts else ""
        )

        if snapshot.azimuth_delta_deg is not None:
            delta = snapshot.azimuth_delta_deg
            warn = " ⚠" if abs(delta) > 5 else ""
            self.align_label.setText(f"Alignement Az Δ {delta:+.1f}°{warn}")
        else:
            self.align_label.setText("")

        if snapshot.dish_reachable:
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
            self.throughput_label.setText(f"↓ {dl} Mbps   ↑ {ul} Mbps")
        else:
            self.throughput_label.setText("")

        ver = snapshot.software_version or ""
        self.version_label.setText(ver if snapshot.dish_reachable else "")

        colors = {
            HealthState.GREEN: "#3dcc3d",
            HealthState.ORANGE: "#ff9933",
            HealthState.RED: "#ff3333",
        }
        self.indicator.setStyleSheet(
            f"font-size: 28px; color: {colors.get(health, '#888')}; background: transparent;"
        )

    def _apply_style(self, state: HealthState, flashing: bool = False) -> None:
        self.setStyleSheet(style_for_state(state, flashing=flashing))

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
