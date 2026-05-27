"""Grille 2 colonnes — empilement des cartes compactes, positionnement absolu."""

from __future__ import annotations

from PyQt6.QtCore import QRect
from PyQt6.QtWidgets import QGridLayout, QWidget

from starlink_widget.core.card_prefs import CardPrefs, col_span, save_card_pref

GRID_COLS = 2
COMPACT_STACK_GAP = 6
MAX_COMPACT_STACK = 2
# Hauteur max d'une colonne pour empiler deux cartes compactes
COMPACT_COLUMN_BUDGET = 112


def _is_compact_widget(widget: QWidget) -> bool:
    if hasattr(widget, "is_grid_compact"):
        return bool(widget.is_grid_compact())
    return max(widget.height(), 1) <= 76


def _layout_slots(
    tiles: list[tuple[str, QWidget, CardPrefs]],
) -> list[tuple[str, QWidget, CardPrefs, int, int, int, int]]:
    """Calcule row, col, span et décalage vertical (empilement compact)."""
    row = 0
    col = 0
    col_y = [0, 0]
    col_stack_count = [0, 0]
    slots: list[tuple[str, QWidget, CardPrefs, int, int, int, int]] = []

    for key, widget, prefs in tiles:
        span = min(col_span(prefs), GRID_COLS - col) if col < GRID_COLS else 1
        if span < 1 or col + span > GRID_COLS:
            row += 1
            col = 0
            col_y = [0, 0]
            col_stack_count = [0, 0]
            span = min(col_span(prefs), GRID_COLS)

        compact = _is_compact_widget(widget) and span == 1

        if span >= 2:
            y = max(col_y[0], col_y[1])
            slots.append((key, widget, prefs, row, 0, span, y))
            row += 1
            col = 0
            col_y = [0, 0]
            col_stack_count = [0, 0]
            continue

        c = col
        y = col_y[c]

        if (
            compact
            and col_stack_count[c] > 0
            and col_stack_count[c] < MAX_COMPACT_STACK
            and y + max(widget.height(), 1) <= COMPACT_COLUMN_BUDGET
        ):
            pass
        elif col_stack_count[c] > 0:
            col += 1
            if col >= GRID_COLS:
                row += 1
                col = 0
                col_y = [0, 0]
                col_stack_count = [0, 0]
            c = col
            y = col_y[c]

        h = max(widget.height(), 1)
        slots.append((key, widget, prefs, row, c, span, y))
        col_y[c] = y + h + (COMPACT_STACK_GAP if compact else 0)
        if compact:
            col_stack_count[c] += 1
        else:
            col_stack_count[c] = MAX_COMPACT_STACK

        if compact and col_stack_count[c] < MAX_COMPACT_STACK:
            continue

        col += 1
        if col >= GRID_COLS:
            row += 1
            col = 0
            col_y = [0, 0]
            col_stack_count = [0, 0]

    return slots


def _stack_side_by_side_compacts(
    slots: list[tuple[str, QWidget, CardPrefs, int, int, int, int]],
) -> None:
    """Deux cartes compactes sur une même ligne → empilées dans la colonne de gauche."""
    by_row: dict[int, list[int]] = {}
    for i, (_k, w, _p, row, col, span, y) in enumerate(slots):
        if span == 1 and y == 0 and _is_compact_widget(w):
            by_row.setdefault(row, []).append(i)

    for indices in by_row.values():
        if len(indices) != 2:
            continue
        i, j = indices
        if slots[i][4] == slots[j][4]:
            continue
        _k1, w1, p1, row, c1, s1, y1 = slots[i]
        _k2, w2, p2, _r2, c2, s2, y2 = slots[j]
        h1, h2 = max(w1.height(), 1), max(w2.height(), 1)
        if h1 + h2 + COMPACT_STACK_GAP > COMPACT_COLUMN_BUDGET:
            continue
        left, right = (i, j) if c1 < c2 else (j, i)
        _lk, lw, _lp, _lr, lc, _ls, ly = slots[left]
        rk, rw, rp, _rr, _rc, rs, _ry = slots[right]
        h_left = max(lw.height(), 1)
        slots[right] = (
            rk,
            rw,
            rp,
            row,
            lc,
            rs,
            ly + h_left + COMPACT_STACK_GAP,
        )


def preview_normalize_spans(
    tiles: list[tuple[str, QWidget, CardPrefs]],
) -> list[tuple[str, QWidget, CardPrefs]]:
    """Comme normalize_metric_spans, sans persistance (aperçu drag)."""
    out: list[tuple[str, QWidget, CardPrefs]] = []
    for key, widget, prefs, _row, _col, eff_span, _y in _layout_slots(tiles):
        if eff_span < col_span(prefs):
            prefs = CardPrefs(prefs.size, prefs.graph, eff_span).normalized()
        out.append((key, widget, prefs))
    return out


def compute_grid_geometries(
    container_width: int,
    spacing: int,
    tiles: list[tuple[str, QWidget, CardPrefs]],
) -> dict[str, QRect]:
    """Positions absolues des cartes pour un ordre donné."""
    tiles = preview_normalize_spans(tiles)
    slots = _layout_slots(tiles)
    _stack_side_by_side_compacts(slots)
    col_w = max(1, (container_width - spacing) // GRID_COLS)

    row_heights: dict[int, int] = {}
    for _key, widget, _prefs, row, _col, _span, y_in_row in slots:
        bottom = y_in_row + max(widget.height(), 1)
        row_heights[row] = max(row_heights.get(row, 0), bottom)

    row_y: dict[int, int] = {}
    y = 0
    for row in sorted(row_heights):
        row_y[row] = y
        y += row_heights[row] + spacing

    geos: dict[str, QRect] = {}
    for key, widget, _prefs, row, col, span, y_in_row in slots:
        w = col_w * span + spacing * max(0, span - 1)
        x = col * (col_w + spacing)
        h = max(widget.height(), 1)
        geos[key] = QRect(x, row_y[row] + y_in_row, max(w, 1), h)
    return geos


def grid_content_height(geos: dict[str, QRect], spacing: int) -> int:
    if not geos:
        return 0
    return max(r.y() + r.height() for r in geos.values()) + spacing


def normalize_metric_spans(
    tiles: list[tuple[str, QWidget, CardPrefs]],
) -> list[tuple[str, QWidget, CardPrefs]]:
    """Réduit col_span si la grille ne peut pas l'honorer (ex. 1×2 → 1×1)."""
    changed = False
    for key, widget, prefs, _row, _col, eff_span, _y in _layout_slots(tiles):
        if eff_span >= col_span(prefs):
            continue
        prefs = CardPrefs(prefs.size, prefs.graph, eff_span).normalized()
        save_card_pref(key, prefs)
        if hasattr(widget, "set_prefs"):
            widget.set_prefs(prefs)
        changed = True
    if not changed:
        return tiles
    return [(key, widget, widget.prefs()) for key, widget, _ in tiles]


def apply_metric_geometries(
    wrap: QWidget,
    tiles: list[tuple[str, QWidget, CardPrefs]],
    *,
    spacing: int,
) -> int:
    """Place les cartes en coordonnées absolues ; retourne la hauteur du bloc."""
    tiles = normalize_metric_spans(tiles)
    width = max(wrap.width(), 1)
    geos = compute_grid_geometries(width, spacing, tiles)
    for key, widget, _prefs in tiles:
        if key not in geos:
            continue
        if hasattr(widget, "clear_width_lock"):
            widget.clear_width_lock()
        widget.setParent(wrap)
        widget.setGeometry(geos[key])
        widget.show()
    return grid_content_height(geos, spacing)


def place_metric_tiles(
    layout: QGridLayout,
    tiles: list[tuple[str, QWidget, CardPrefs]],
) -> None:
    """Compat : vide la grille Qt et applique le positionnement absolu."""
    wrap = layout.parentWidget()
    if wrap is None:
        return
    while layout.count():
        layout.takeAt(0)
    height = apply_metric_geometries(wrap, tiles, spacing=layout.spacing())
    wrap.setMinimumHeight(max(height - layout.spacing(), 0))
