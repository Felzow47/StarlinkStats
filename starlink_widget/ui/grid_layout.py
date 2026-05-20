"""Grille 2 colonnes — largeur selon col_span de chaque carte."""

from __future__ import annotations

from PyQt6.QtWidgets import QGridLayout, QWidget

from starlink_widget.core.card_prefs import CardPrefs, col_span


def place_metric_tiles(
    layout: QGridLayout,
    tiles: list[tuple[str, QWidget, CardPrefs]],
) -> None:
    row, col = 0, 0
    cols = 2
    for _key, widget, prefs in tiles:
        span = min(col_span(prefs), cols - col) if col < cols else 1
        if span < 1 or col + span > cols:
            row += 1
            col = 0
            span = min(col_span(prefs), cols)
        layout.addWidget(widget, row, col, 1, span)
        if hasattr(widget, "clear_width_lock"):
            widget.clear_width_lock()
        col += span
        if col >= cols:
            row += 1
            col = 0
