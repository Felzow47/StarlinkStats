"""Boot/onboarding screen displayed on manual launches."""

from __future__ import annotations

from PyQt6.QtCore import QPoint, QRectF, Qt, QTimer
from PyQt6.QtGui import QColor, QIcon, QPainter
from PyQt6.QtWidgets import (
    QApplication,
    QDialog,
    QFrame,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from starlink_widget.core.paths import app_icon_path
from starlink_widget.ui.styles import (
    CARD_BG,
    CARD_BORDER,
    OK_GREEN,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
)


class FlatLoadingBar(QWidget):
    """Animated flat bar with permanently rounded ends."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setFixedHeight(8)
        self._phase = 0
        self._timer = QTimer(self)
        self._timer.setInterval(22)
        self._timer.timeout.connect(self._tick)
        self._timer.start()

    def _tick(self) -> None:
        self._phase = (self._phase + 1) % 200
        self.update()

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.rect().adjusted(0, 0, -1, -1)
        if rect.width() <= 0 or rect.height() <= 0:
            return

        track_rect = QRectF(rect)
        radius = track_rect.height() / 2
        track_color = QColor(255, 255, 255, 28)
        fill_color = QColor(OK_GREEN)

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(track_color)
        painter.drawRoundedRect(track_rect, radius, radius)

        # Ping-pong horizontal movement; chunk always inside track
        # so both visible ends stay rounded.
        progress = self._phase / 100.0
        if progress > 1.0:
            progress = 2.0 - progress
        chunk_width = max(int(track_rect.width() * 0.45), int(radius * 2 + 6))
        chunk_width = min(chunk_width, int(track_rect.width()))
        travel = max(0, int(track_rect.width()) - chunk_width)
        chunk_x = int(track_rect.x() + progress * travel)
        chunk_rect = QRectF(
            float(chunk_x),
            track_rect.y(),
            float(chunk_width),
            track_rect.height(),
        )

        painter.setBrush(fill_color)
        painter.drawRoundedRect(chunk_rect, radius, radius)


class BootScreen(QDialog):
    """Mandatory onboarding message shown before normal tray usage."""

    AUTO_CLOSE_MS = 30_000

    def __init__(self, parent=None) -> None:
        super().__init__(
            parent,
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool,
        )
        self.setObjectName("BootScreen")
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setModal(True)
        self.setFixedSize(600, 350)
        icon_path = app_icon_path()
        if icon_path is not None:
            self.setWindowIcon(QIcon(str(icon_path)))
        self._can_close = False
        self._status_tick = 0

        self._build_ui()
        self._status_timer = QTimer(self)
        self._status_timer.setInterval(350)
        self._status_timer.timeout.connect(self._animate_status)
        self._status_timer.start()
        self._auto_close_timer = QTimer(self)
        self._auto_close_timer.setSingleShot(True)
        self._auto_close_timer.timeout.connect(self._auto_close)

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        card = QFrame(self)
        card.setObjectName("BootCard")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(22, 18, 22, 18)
        card_layout.setSpacing(12)

        title = QLabel("Initialisation de Starlink Widget")
        title.setObjectName("bootTitle")
        card_layout.addWidget(title)

        self._status_label = QLabel("Demarrage du widget")
        self._status_label.setObjectName("bootStatus")
        card_layout.addWidget(self._status_label)

        card_layout.addWidget(FlatLoadingBar(card))

        help_text = QLabel(
            "Le systray (zone de notification) se trouve en bas a droite, pres de l'horloge Windows.\n\n"
            "- Double-clic sur l'icone : afficher / masquer le widget.\n"
            "- Clic droit sur l'icone : Personnaliser, demarrage automatique, quitter.\n"
            "- Si vous changez de reseau, le widget peut se masquer mais reste actif dans le systray.",
        )
        help_text.setObjectName("bootHelp")
        help_text.setWordWrap(True)
        card_layout.addWidget(help_text)

        self._ok_button = QPushButton("OK", card)
        self._ok_button.setObjectName("bootOkButton")
        self._ok_button.clicked.connect(self._confirm_and_close)
        card_layout.addWidget(self._ok_button, alignment=Qt.AlignmentFlag.AlignRight)

        root.addWidget(card)

        bg = f"rgba({CARD_BG[0]}, {CARD_BG[1]}, {CARD_BG[2]}, 255)"
        border = f"rgba({CARD_BORDER[0]}, {CARD_BORDER[1]}, {CARD_BORDER[2]}, {CARD_BORDER[3]})"
        self.setStyleSheet(
            f"""
            #BootScreen {{
                background: transparent;
            }}
            #BootCard {{
                background: {bg};
                border: 1px solid {border};
                border-radius: 16px;
            }}
            #bootTitle {{
                color: {TEXT_PRIMARY};
                font-size: 20px;
                font-weight: 700;
            }}
            #bootStatus {{
                color: {OK_GREEN};
                font-size: 13px;
                font-weight: 600;
            }}
            #bootHelp {{
                color: {TEXT_PRIMARY};
                font-size: 12px;
                line-height: 1.4;
            }}
            #bootOkButton {{
                min-width: 96px;
                min-height: 34px;
                border-radius: 10px;
                border: 1px solid rgba(52, 199, 89, 145);
                background: rgba(52, 199, 89, 45);
                color: {TEXT_PRIMARY};
                font-size: 13px;
                font-weight: 600;
                padding: 0 12px;
            }}
            #bootOkButton:hover {{
                background: rgba(52, 199, 89, 70);
            }}
            #bootOkButton:pressed {{
                background: rgba(52, 199, 89, 95);
            }}
            """
        )

    def run_and_wait_confirmation(self) -> None:
        self._center_on_primary_screen()
        self._auto_close_timer.start(self.AUTO_CLOSE_MS)
        self.exec()

    def reject(self) -> None:
        # Fermer via Alt+F4/Echap est bloqué sauf validation/fermeture auto.
        if self._can_close:
            super().reject()

    def _animate_status(self) -> None:
        dots = "." * (self._status_tick % 4)
        self._status_label.setText(f"Demarrage du widget{dots}")
        self._status_tick += 1

    def _confirm_and_close(self) -> None:
        self._auto_close_timer.stop()
        self._status_timer.stop()
        self._can_close = True
        self.accept()

    def _auto_close(self) -> None:
        self._confirm_and_close()

    def _center_on_primary_screen(self) -> None:
        screen = QApplication.primaryScreen()
        if screen is None:
            return
        area = screen.availableGeometry()
        x = area.x() + (area.width() - self.width()) // 2
        y = area.y() + (area.height() - self.height()) // 2
        self.move(QPoint(x, y))

