"""Animations fluides pour cartes et grille."""

from __future__ import annotations

from PyQt6.QtCore import QEasingCurve, QPropertyAnimation, QRect
from PyQt6.QtWidgets import QWidget

DURATION_MOVE = 220
DURATION_RESIZE = 120
DURATION_OPACITY = 280


def animate_geometry(
    widget: QWidget,
    end: QRect,
    parent: QWidget | None = None,
    duration: int = DURATION_MOVE,
) -> QPropertyAnimation:
    anim = QPropertyAnimation(widget, b"geometry", parent or widget.parentWidget())
    anim.setDuration(duration)
    anim.setStartValue(widget.geometry())
    anim.setEndValue(end)
    anim.setEasingCurve(QEasingCurve.Type.OutCubic)
    anim.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)
    return anim


def animate_height(
    widget: QWidget,
    end_h: int,
    parent: QWidget | None = None,
    duration: int = DURATION_RESIZE,
) -> QPropertyAnimation:
    anim = QPropertyAnimation(widget, b"geometry", parent or widget.parentWidget())
    g = widget.geometry()
    end = QRect(g.x(), g.y(), g.width(), end_h)
    anim.setDuration(duration)
    anim.setStartValue(g)
    anim.setEndValue(end)
    anim.setEasingCurve(QEasingCurve.Type.OutCubic)
    anim.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)
    return anim


def animate_window_opacity(
    widget: QWidget,
    end: float,
    duration: int = DURATION_OPACITY,
) -> QPropertyAnimation:
    anim = QPropertyAnimation(widget, b"windowOpacity", widget)
    anim.setDuration(duration)
    anim.setStartValue(widget.windowOpacity())
    anim.setEndValue(end)
    anim.setEasingCurve(QEasingCurve.Type.InOutCubic)
    anim.start(QPropertyAnimation.DeletionPolicy.KeepWhenStopped)
    return anim
