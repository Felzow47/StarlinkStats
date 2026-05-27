"""Grille 2 colonnes — empilement par colonne (pas de lignes synchronisées)."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path

from PyQt6.QtCore import QPoint, QRect
from PyQt6.QtWidgets import QGridLayout, QWidget

from starlink_widget.core.card_prefs import (
    SIZE_SMALL,
    CardPrefs,
    col_span,
    save_card_pref,
)
from starlink_widget.core.widget_prefs import load_stack_under
from starlink_widget.ui.styles import WIDGET_WIDTH

GRID_COLS = 2
COMPACT_STACK_GAP = 6
MAX_COMPACT_STACK = 4
COMPACT_COLUMN_BUDGET = 260
COMPACT_GRID_MAX_H = 76
MIN_HEIGHT_COMPACT = 56
METRICS_H_MARGIN = 28

_LOG_PATH = Path(__file__).resolve().parent.parent.parent / "debug-ff12e1.log"
_SESSION = "ff12e1"


@dataclass(frozen=True)
class CompactDropZone:
    """Zone où déposer une carte compacte (insertion après anchor_key)."""

    rect: QRect
    anchor_key: str


@dataclass(frozen=True)
class GridSnapSlot:
    """Emplacement grille : insertion ou remplacement (échange) d'une carte."""

    rect: QRect
    insert_after_key: str | None
    grid_col: int
    insert_index: int
    replace_key: str | None = None
    insert_before_key: str | None = None


def _column_width(container_width: int, spacing: int) -> int:
    return max(1, (container_width - spacing) // GRID_COLS)


def _is_full_width_geo(geo: QRect, container_width: int, spacing: int) -> bool:
    return geo.width() > _column_width(container_width, spacing) + spacing // 2


def _is_wide_snap_slot(
    slot: GridSnapSlot, container_width: int, spacing: int
) -> bool:
    return _is_full_width_geo(slot.rect, container_width, spacing)


def grid_column_at_x(x: int, container_width: int, spacing: int) -> int:
    """Colonne 0/1 selon la position horizontale du curseur."""
    col_w = _column_width(container_width, spacing)
    boundary = col_w + spacing // 2
    return 0 if x < boundary else 1


def geo_grid_column(geo: QRect, container_width: int, spacing: int) -> int:
    return grid_column_at_x(geo.x() + max(1, geo.width()) // 2, container_width, spacing)


def metrics_area_width(wrap: QWidget | None = None) -> int:
    """Largeur utile de la grille (fixe, indépendante d'un conteneur élargi)."""
    _ = wrap
    return max(1, WIDGET_WIDTH - METRICS_H_MARGIN)


def _tile_layout_height(widget: QWidget) -> int:
    if hasattr(widget, "layout_height"):
        return max(1, int(widget.layout_height()))
    return max(widget.height(), 1)


def _is_compact_widget(widget: QWidget) -> bool:
    if hasattr(widget, "is_grid_compact"):
        return bool(widget.is_grid_compact())
    return _tile_layout_height(widget) <= 76


def _resolve_columns(
    tiles: list[tuple[str, QWidget, CardPrefs]],
    stack_under: dict[str, str] | None,
) -> dict[str, int]:
    """Colonne 0/1 par carte — colonne fixe conservée au déplacement."""
    stack_map = dict(stack_under or {})
    assign: dict[str, int] = {}

    for key, _widget, prefs in tiles:
        if prefs.grid_col in (0, 1):
            assign[key] = prefs.grid_col

    for key, _widget, _prefs in tiles:
        if key in assign:
            continue
        anchor = stack_map.get(key)
        if anchor is not None and anchor in assign:
            assign[key] = assign[anchor]

    col = 0
    col_stack = [0, 0]
    for key, widget, prefs in tiles:
        if key in assign:
            continue
        span = min(col_span(prefs), GRID_COLS)
        h = _tile_layout_height(widget)
        compact = _is_compact_widget(widget) and span == 1

        if span >= 2:
            assign[key] = 0
            col = 0
            col_stack = [0, 0]
            continue

        if col >= GRID_COLS:
            col = 0
            col_stack = [0, 0]

        c = col
        if compact and col_stack[c] > 0 and col_stack[c] < MAX_COMPACT_STACK:
            used = col_stack[c] * (MIN_HEIGHT_COMPACT + COMPACT_STACK_GAP)
            if used + h > COMPACT_COLUMN_BUDGET:
                col += 1
                if col >= GRID_COLS:
                    col = 0
                    col_stack = [0, 0]
                c = col
        elif col_stack[c] > 0:
            col += 1
            if col >= GRID_COLS:
                col = 0
                col_stack = [0, 0]
            c = col

        assign[key] = c
        if compact:
            col_stack[c] += 1
            if col_stack[c] >= MAX_COMPACT_STACK:
                col = (c + 1) % GRID_COLS
                col_stack[col] = 0
            continue

        col_stack[c] = MAX_COMPACT_STACK
        col += 1
        if col >= GRID_COLS:
            col = 0
            col_stack = [0, 0]

    return assign


def _compute_placements(
    tiles: list[tuple[str, QWidget, CardPrefs]],
    *,
    stack_under: dict[str, str] | None = None,
) -> list[tuple[str, QWidget, CardPrefs, int, int]]:
    """Empile verticalement dans chaque colonne selon l'ordre global."""
    col_assign = _resolve_columns(tiles, stack_under)
    col_bottom = [0, 0]
    placements: list[tuple[str, QWidget, CardPrefs, int, int]] = []

    for key, widget, prefs in tiles:
        span = min(col_span(prefs), GRID_COLS)
        h = _tile_layout_height(widget)
        compact = _is_compact_widget(widget) and span == 1

        if span >= 2:
            y = max(col_bottom[0], col_bottom[1])
            placements.append((key, widget, prefs, -1, 2))
            bottom = y + h
            col_bottom[0] = bottom
            col_bottom[1] = bottom
            continue

        c = col_assign[key]
        y = col_bottom[c]
        placements.append((key, widget, prefs, c, 1))
        gap = COMPACT_STACK_GAP if compact else 0
        col_bottom[c] = y + h + gap

    return placements


def _layout_slots(
    tiles: list[tuple[str, QWidget, CardPrefs]],
) -> list[tuple[str, QWidget, CardPrefs, int, int, int, int]]:
    """Slots pour normalisation span (row/col factices, y = offset colonne)."""
    col_bottom = [0, 0]
    slots: list[tuple[str, QWidget, CardPrefs, int, int, int, int]] = []
    for key, widget, prefs, col, span in _compute_placements(tiles):
        if span >= 2:
            y = max(col_bottom[0], col_bottom[1])
            slots.append((key, widget, prefs, 0, 0, span, y))
            h = _tile_layout_height(widget)
            bottom = y + h
            col_bottom[0] = bottom
            col_bottom[1] = bottom
            continue
        y = col_bottom[col]
        slots.append((key, widget, prefs, 0, col, span, y))
        h = _tile_layout_height(widget)
        gap = COMPACT_STACK_GAP if _is_compact_widget(widget) else 0
        col_bottom[col] = y + h + gap
    return slots


def preview_normalize_spans(
    tiles: list[tuple[str, QWidget, CardPrefs]],
) -> list[tuple[str, QWidget, CardPrefs]]:
    """Comme normalize_metric_spans, sans persistance (aperçu drag)."""
    out: list[tuple[str, Widget, CardPrefs]] = []
    for key, widget, prefs, _row, _col, eff_span, _y in _layout_slots(tiles):
        if col_span(prefs) >= 2:
            out.append((key, widget, prefs))
            continue
        if eff_span < col_span(prefs):
            prefs = CardPrefs(
                prefs.size,
                prefs.graph,
                eff_span,
                prefs.height_px,
                prefs.grid_col,
            ).normalized()
        out.append((key, widget, prefs))
    return out


def compute_grid_geometries(
    container_width: int,
    spacing: int,
    tiles: list[tuple[str, QWidget, CardPrefs]],
    *,
    stack_under: dict[str, str] | None = None,
) -> dict[str, QRect]:
    """Positions absolues — chaque colonne a sa propre hauteur cumulée."""
    if stack_under is None:
        stack_under = load_stack_under()
    tiles = preview_normalize_spans(tiles)
    placements = _compute_placements(tiles, stack_under=stack_under)
    col_w = max(1, (container_width - spacing) // GRID_COLS)
    col_bottom = [0, 0]
    stack_anchor = [0, 0]
    geos: dict[str, QRect] = {}
    log_placements: list[dict] = []

    for key, widget, prefs, col, span in placements:
        h = _tile_layout_height(widget)
        compact = _is_compact_widget(widget)

        if span >= 2:
            y = max(col_bottom[0], col_bottom[1])
            w = col_w * GRID_COLS + spacing
            geos[key] = QRect(0, y, max(w, 1), h)
            bottom = y + h + spacing
            col_bottom[0] = bottom
            col_bottom[1] = bottom
            stack_anchor = [0, 0]
            log_placements.append(
                {"key": key, "col": "full", "y": y, "h": h, "col_bottom": list(col_bottom)}
            )
            continue

        c = col
        y = col_bottom[c]
        x = c * (col_w + spacing)
        geos[key] = QRect(x, y, col_w, h)
        gap = COMPACT_STACK_GAP if compact else spacing
        if compact and stack_anchor[c] == 0 and col_bottom[c] == y:
            stack_anchor[c] = y
        col_bottom[c] = y + h + gap
        log_placements.append(
            {
                "key": key,
                "col": c,
                "y": y,
                "h": h,
                "col_bottom": list(col_bottom),
            }
        )

    # #region agent log
    try:
        payload = {
            "sessionId": _SESSION,
            "runId": "column-layout",
            "hypothesisId": "F",
            "location": "grid_layout:compute_grid_geometries",
            "message": "column placements",
            "data": {"placements": log_placements},
            "timestamp": int(time.time() * 1000),
        }
        with _LOG_PATH.open("a", encoding="utf-8") as f:
            f.write(json.dumps(payload, ensure_ascii=False) + "\n")
    except Exception:
        pass
    # #endregion

    return geos


def _preview_order_insert_after(
    keys: list[str], drag_key: str, anchor_key: str
) -> list[str]:
    if (
        anchor_key not in keys
        or drag_key not in keys
        or drag_key == anchor_key
    ):
        return list(keys)
    preview = list(keys)
    preview.remove(drag_key)
    new_idx = preview.index(anchor_key) + 1
    if keys.index(drag_key) == new_idx:
        return list(keys)
    preview.insert(new_idx, drag_key)
    return preview


def compute_compact_drop_zones(
    container_width: int,
    spacing: int,
    tiles: list[tuple[str, QWidget, CardPrefs]],
    *,
    drag_key: str,
) -> list[CompactDropZone]:
    """Emplacements = position réelle de la carte après insert_after(anchor)."""
    if not tiles or not drag_key:
        return []

    keys = [key for key, _w, _p in tiles]
    by_key = {key: (widget, prefs) for key, widget, prefs in tiles}
    zones: list[CompactDropZone] = []
    seen: set[tuple[int, int, int, int]] = set()

    for anchor_key in keys:
        if anchor_key == drag_key:
            continue
        preview_keys = _preview_order_insert_after(keys, drag_key, anchor_key)
        if preview_keys == keys:
            continue
        preview_tiles = [
            (k, by_key[k][0], by_key[k][1]) for k in preview_keys
        ]
        preview_stack = dict(load_stack_under())
        preview_stack[drag_key] = anchor_key
        geos = compute_grid_geometries(
            container_width,
            spacing,
            preview_tiles,
            stack_under=preview_stack,
        )
        drag_geo = geos.get(drag_key)
        if drag_geo is None or drag_geo.width() < 2 or drag_geo.height() < 2:
            continue
        sig = (drag_geo.x(), drag_geo.y(), drag_geo.width(), drag_geo.height())
        if sig in seen:
            continue
        seen.add(sig)
        zones.append(CompactDropZone(QRect(drag_geo), anchor_key))

    return zones


def compute_grid_snap_slots(
    container_width: int,
    spacing: int,
    tiles: list[tuple[str, QWidget, CardPrefs]],
    *,
    drag_key: str,
) -> list[GridSnapSlot]:
    """Emplacements valides : échange sur chaque carte + insertions dans l'ordre."""
    if not tiles or not drag_key:
        return []

    keys = [key for key, _w, _p in tiles]
    if drag_key not in keys:
        return []
    by_key = {key: (widget, prefs) for key, widget, prefs in tiles}
    base = [key for key in keys if key != drag_key]
    slots: list[GridSnapSlot] = []
    seen: set[tuple[int, int, int, int]] = set()

    static_tiles = [(k, by_key[k][0], by_key[k][1]) for k in base]
    static_geos = compute_grid_geometries(
        container_width, spacing, static_tiles
    )
    drag_widget, drag_prefs = by_key[drag_key]
    drag_compact = _is_compact_widget(drag_widget)
    if drag_compact:
        for occupant_key, geo in static_geos.items():
            if _is_compact_widget(by_key[occupant_key][0]):
                continue
            sig = (geo.x(), geo.y(), geo.width(), geo.height())
            if sig in seen:
                continue
            seen.add(sig)
            col = geo_grid_column(geo, container_width, spacing)
            slots.append(
                GridSnapSlot(
                    QRect(geo),
                    None,
                    col,
                    -1,
                    replace_key=occupant_key,
                )
            )
    else:
        for occupant_key, geo in static_geos.items():
            sig = (geo.x(), geo.y(), geo.width(), geo.height())
            if sig in seen:
                continue
            seen.add(sig)
            col = geo_grid_column(geo, container_width, spacing)
            slots.append(
                GridSnapSlot(
                    QRect(geo),
                    None,
                    col,
                    -1,
                    replace_key=occupant_key,
                )
            )

    def _append_slot(
        drag_geo: QRect,
        *,
        grid_col: int,
        insert_index: int,
        insert_after: str | None,
        insert_before: str | None = None,
        replace: str | None = None,
    ) -> None:
        sig = (drag_geo.x(), drag_geo.y(), drag_geo.width(), drag_geo.height())
        if sig in seen:
            return
        seen.add(sig)
        slots.append(
            GridSnapSlot(
                QRect(drag_geo),
                insert_after,
                grid_col,
                insert_index,
                replace_key=replace,
                insert_before_key=insert_before,
            )
        )

    def _preview_tiles_for(
        ordered: list[str], forced_col: int
    ) -> list[tuple[str, QWidget, CardPrefs]]:
        forced = CardPrefs(
            drag_prefs.size,
            drag_prefs.graph,
            drag_prefs.col_span,
            drag_prefs.height_px,
            forced_col,
        ).normalized()
        return [
            (k, by_key[k][0], forced if k == drag_key else by_key[k][1])
            for k in ordered
        ]

    for target_col in (0, 1):
        col_keys = sorted(
            (
                k
                for k in base
                if k in static_geos
                and geo_grid_column(static_geos[k], container_width, spacing)
                == target_col
            ),
            key=lambda k: static_geos[k].y(),
        )
        for insert_idx in range(len(col_keys) + 1):
            preview_stack = {
                k: v for k, v in load_stack_under().items() if k != drag_key
            }
            insert_after: str | None = None
            insert_before: str | None = None
            if insert_idx == 0:
                if col_keys:
                    first_key = col_keys[0]
                    ordered = list(base)
                    ordered.insert(ordered.index(first_key), drag_key)
                    insert_before = first_key
                else:
                    ordered = list(base) + [drag_key]
            else:
                anchor = col_keys[insert_idx - 1]
                ordered = list(base)
                ordered.insert(ordered.index(anchor) + 1, drag_key)
                preview_stack[drag_key] = anchor
                insert_after = anchor
            geos = compute_grid_geometries(
                container_width,
                spacing,
                _preview_tiles_for(ordered, target_col),
                stack_under=preview_stack,
            )
            drag_geo = geos.get(drag_key)
            if drag_geo is None or drag_geo.width() < 2 or drag_geo.height() < 2:
                continue
            if (
                geo_grid_column(drag_geo, container_width, spacing) != target_col
            ):
                continue
            slot_index = -1 if insert_idx == 0 and not col_keys else insert_idx
            _append_slot(
                drag_geo,
                grid_col=target_col,
                insert_index=slot_index,
                insert_after=insert_after,
                insert_before=insert_before,
            )

    if drag_compact:
        for anchor_key in base:
            occupant = by_key[anchor_key][0]
            if _is_compact_widget(occupant):
                continue
            anchor_geo = static_geos.get(anchor_key)
            if anchor_geo is None:
                continue
            anchor_prefs = by_key[anchor_key][1]
            if _is_full_width_geo(anchor_geo, container_width, spacing):
                target_cols = (0, 1)
            elif anchor_prefs.grid_col in (0, 1):
                target_cols = (anchor_prefs.grid_col,)
            else:
                target_cols = (geo_grid_column(anchor_geo, container_width, spacing),)
            for forced_col in target_cols:
                ordered = list(base)
                ordered.insert(ordered.index(anchor_key), drag_key)
                geos = compute_grid_geometries(
                    container_width,
                    spacing,
                    _preview_tiles_for(ordered, forced_col),
                )
                drag_geo = geos.get(drag_key)
                if drag_geo is None or drag_geo.width() < 2 or drag_geo.height() < 2:
                    continue
                if (
                    geo_grid_column(drag_geo, container_width, spacing)
                    != forced_col
                ):
                    continue
                _append_slot(
                    drag_geo,
                    grid_col=forced_col,
                    insert_index=-1,
                    insert_after=None,
                    insert_before=anchor_key,
                )

    # #region agent log
    try:
        payload = {
            "sessionId": _SESSION,
            "runId": "grid-snap",
            "hypothesisId": "I",
            "location": "grid_layout:compute_grid_snap_slots",
            "message": "snap slots",
            "data": {
                "width": container_width,
                "n_slots": len(slots),
                "drag_compact": drag_compact,
                "slots": [
                    {
                        "after": s.insert_after_key,
                        "replace": s.replace_key,
                        "col": s.grid_col,
                        "rect": [
                            s.rect.x(),
                            s.rect.y(),
                            s.rect.width(),
                            s.rect.height(),
                        ],
                    }
                    for s in slots[:12]
                ],
            },
            "timestamp": int(time.time() * 1000),
        }
        with _LOG_PATH.open("a", encoding="utf-8") as f:
            f.write(json.dumps(payload, ensure_ascii=False) + "\n")
    except Exception:
        pass
    # #endregion

    return slots


def nearest_grid_snap_slot(
    slots: list[GridSnapSlot],
    point: QPoint,
    *,
    container_width: int,
    spacing: int,
    compact: bool = False,
) -> GridSnapSlot | None:
    """Slot le plus proche dans la colonne visée par le curseur."""
    if not slots:
        return None
    target_col = grid_column_at_x(point.x(), container_width, spacing)
    col_w = _column_width(container_width, spacing)
    col_slots = [s for s in slots if s.grid_col == target_col]
    pool = col_slots or slots
    if compact:
        pool = [
            s
            for s in slots
            if not s.replace_key or _is_wide_snap_slot(s, container_width, spacing)
        ]
        over_wide = [
            s
            for s in pool
            if _is_wide_snap_slot(s, container_width, spacing)
            and s.rect.adjusted(-8, -8, 8, 8).contains(point)
        ]
        if over_wide:
            pool = over_wide + [
                s
                for s in pool
                if not s.replace_key and s.grid_col == target_col
            ]
        else:
            pool = [s for s in pool if s.grid_col == target_col] or pool

    hit_pad = 4
    inside = [
        s
        for s in pool
        if s.rect.adjusted(-hit_pad, -hit_pad, hit_pad, hit_pad).contains(point)
    ]
    search = inside or pool

    best: GridSnapSlot | None = None
    best_d2: int | None = None
    for slot in search:
        center = slot.rect.center()
        if compact and not slot.replace_key:
            d2 = (center.y() - point.y()) ** 2
        elif compact and _is_wide_snap_slot(slot, container_width, spacing):
            d2 = (center.x() - point.x()) ** 2 + (center.y() - point.y()) ** 2
        else:
            d2 = (center.x() - point.x()) ** 2 + (center.y() - point.y()) ** 2
        if best_d2 is None or d2 < best_d2:
            best_d2 = d2
            best = slot

    # #region agent log
    try:
        payload = {
            "sessionId": _SESSION,
            "runId": "post-fix",
            "hypothesisId": "J",
            "location": "grid_layout:nearest_grid_snap_slot",
            "message": "nearest slot",
            "data": {
                "point": [point.x(), point.y()],
                "target_col": target_col,
                "n_col_slots": len(col_slots),
                "picked_col": best.grid_col if best else None,
                "picked_rect": (
                    [
                        best.rect.x(),
                        best.rect.y(),
                        best.rect.width(),
                        best.rect.height(),
                    ]
                    if best
                    else None
                ),
                "picked_after": best.insert_after_key if best else None,
                "picked_before": best.insert_before_key if best else None,
                "picked_replace": best.replace_key if best else None,
                "compact": compact,
            },
            "timestamp": int(time.time() * 1000),
        }
        with _LOG_PATH.open("a", encoding="utf-8") as f:
            f.write(json.dumps(payload, ensure_ascii=False) + "\n")
    except Exception:
        pass
    # #endregion

    return best


def grid_content_height(geos: dict[str, QRect], spacing: int) -> int:
    if not geos:
        return 0
    return max(r.y() + r.height() for r in geos.values()) + spacing


def _prefs_are_compact(prefs: CardPrefs) -> bool:
    if prefs.height_px > 0:
        return prefs.height_px <= COMPACT_GRID_MAX_H
    return not prefs.graph


def normalize_metric_spans(
    tiles: list[tuple[str, QWidget, CardPrefs]],
) -> list[tuple[str, Widget, CardPrefs]]:
    """Réduit col_span si la grille ne peut pas l'honorer (ex. 1×2 → 1×1)."""
    changed = False
    for key, widget, prefs, _row, _col, eff_span, _y in _layout_slots(tiles):
        new_span = col_span(prefs)
        if _prefs_are_compact(prefs) and new_span >= 2:
            new_span = 1
        if new_span >= 2:
            continue
        if eff_span < new_span:
            new_span = eff_span
        if new_span >= col_span(prefs):
            continue
        prefs = CardPrefs(
            prefs.size,
            prefs.graph,
            new_span,
            prefs.height_px,
            prefs.grid_col,
        ).normalized()
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
    width = metrics_area_width(wrap)
    geos: dict[str, QRect] = {}
    for _pass in range(2):
        for _key, widget, _prefs in tiles:
            if hasattr(widget, "prepare_for_grid_layout"):
                widget.prepare_for_grid_layout()
        geos = compute_grid_geometries(width, spacing, tiles)
        startup_tiles: list[dict] = []
        for key, widget, prefs in tiles:
            if key not in geos:
                continue
            geo = geos[key]
            if widget.parent() is not wrap:
                widget.setParent(wrap)
            if hasattr(widget, "apply_grid_geometry"):
                widget.apply_grid_geometry(geo)
            else:
                widget.setFixedSize(geo.width(), geo.height())
                widget.move(geo.topLeft())
            widget.show()
            startup_tiles.append(
                {
                    "key": key,
                    "prefs_h_px": prefs.height_px,
                    "layout_h": (
                        widget.layout_height()
                        if hasattr(widget, "layout_height")
                        else geo.height()
                    ),
                    "geo": [
                        geo.x(),
                        geo.y(),
                        geo.width(),
                        geo.height(),
                    ],
                    "widget": [widget.width(), widget.height()],
                }
            )
        # #region agent log
        try:
            overlaps = detect_geometry_overlaps(geos)
            payload = {
                "sessionId": _SESSION,
                "runId": "startup",
                "hypothesisId": "G",
                "location": "grid_layout:apply_metric_geometries",
                "message": "startup tile sizes",
                "data": {
                    "pass": _pass,
                    "width": width,
                    "tiles": startup_tiles,
                    "overlaps": overlaps,
                },
                "timestamp": int(time.time() * 1000),
            }
            with _LOG_PATH.open("a", encoding="utf-8") as f:
                f.write(json.dumps(payload, ensure_ascii=False) + "\n")
        except Exception:
            pass
        # #endregion
        if not any(
            hasattr(w, "layout_height")
            and w.layout_height() > geos[k].height()
            and not (
                hasattr(w, "_is_compact_height")
                and w._is_compact_height(geos[k].height())
            )
            for k, w, _ in tiles
            if k in geos
        ):
            break
    return grid_content_height(geos, spacing)


def detect_geometry_overlaps(geos: dict[str, QRect]) -> list[dict]:
    """Détecte les rectangles qui se chevauchent (debug layout)."""
    keys = list(geos.keys())
    overlaps: list[dict] = []
    for i, ka in enumerate(keys):
        ra = geos[ka]
        for kb in keys[i + 1 :]:
            rb = geos[kb]
            inter = ra.intersected(rb)
            if inter.width() > 1 and inter.height() > 1:
                overlaps.append(
                    {
                        "a": ka,
                        "b": kb,
                        "inter": [
                            inter.x(),
                            inter.y(),
                            inter.width(),
                            inter.height(),
                        ],
                    }
                )
    return overlaps


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
