"""Système de drag & drop grille — simple et prévisible."""

from __future__ import annotations

from dataclasses import dataclass

from PyQt6.QtCore import QPoint, QRect
from PyQt6.QtWidgets import QWidget

from starlink_widget.core.card_prefs import CardPrefs, col_span
from starlink_widget.core.widget_prefs import (
    clear_stack_under,
    insert_field_after,
    insert_field_before,
    load_stack_under,
    set_card_grid_col,
    set_stack_under,
    swap_field_order,
)
from starlink_widget.ui.grid_layout import (
    GRID_COLS,
    _column_width,
    _is_compact_widget,
    compute_grid_geometries,
    geo_grid_column,
    grid_column_at_x,
    preview_normalize_spans,
)



@dataclass(frozen=True)
class DropTarget:
    """Une seule action de drop avec sa zone visuelle."""

    rect: QRect
    action: str  # insert_before | insert_after | swap
    anchor_key: str
    grid_col: int  # colonne cible pour la carte dragguée
    stack: bool = False
    drag_col: int = -1  # colonne d'origine (où va l'ancre lors d'un swap)


def _preview_insert_before(keys: list[str], drag_key: str, anchor_key: str) -> list[str]:
    if anchor_key not in keys or drag_key not in keys:
        return list(keys)
    preview = [k for k in keys if k != drag_key]
    preview.insert(preview.index(anchor_key), drag_key)
    return preview


def _preview_insert_after(keys: list[str], drag_key: str, anchor_key: str) -> list[str]:
    if anchor_key not in keys or drag_key not in keys:
        return list(keys)
    preview = [k for k in keys if k != drag_key]
    preview.insert(preview.index(anchor_key) + 1, drag_key)
    return preview


def _preview_swap(keys: list[str], drag_key: str, anchor_key: str) -> list[str]:
    if anchor_key not in keys or drag_key not in keys:
        return list(keys)
    preview = list(keys)
    i, j = preview.index(drag_key), preview.index(anchor_key)
    preview[i], preview[j] = preview[j], preview[i]
    return preview


def _tiles_for_order(
    order: list[str],
    by_key: dict[str, tuple[QWidget, CardPrefs]],
    drag_key: str,
    forced_col: int | None,
) -> list[tuple[str, QWidget, CardPrefs]]:
    out: list[tuple[str, QWidget, CardPrefs]] = []
    for key in order:
        widget, prefs = by_key[key]
        if key == drag_key and forced_col is not None:
            prefs = CardPrefs(
                prefs.size,
                prefs.graph,
                prefs.col_span,
                prefs.height_px,
                forced_col,
            ).normalized()
        out.append((key, widget, prefs))
    return out


def _drag_geometry(
    *,
    width: int,
    spacing: int,
    order: list[str],
    by_key: dict[str, tuple[QWidget, CardPrefs]],
    drag_key: str,
    forced_col: int | None,
    stack_anchor: str | None,
) -> QRect | None:
    stack = dict(load_stack_under())
    if stack_anchor:
        stack[drag_key] = stack_anchor
    tiles = preview_normalize_spans(
        _tiles_for_order(order, by_key, drag_key, forced_col)
    )
    geos = compute_grid_geometries(width, spacing, tiles, stack_under=stack)
    geo = geos.get(drag_key)
    if geo is None or geo.width() < 2 or geo.height() < 2:
        return None
    return geo


def _anchor_col(
    anchor_key: str,
    prefs: CardPrefs,
    static_geos: dict[str, QRect],
    width: int,
    spacing: int,
) -> int:
    if prefs.grid_col in (0, 1):
        return prefs.grid_col
    geo = static_geos.get(anchor_key)
    if geo is None:
        return 0
    return geo_grid_column(geo, width, spacing)


def compute_drop_targets(
    container_width: int,
    spacing: int,
    tiles: list[tuple[str, QWidget, CardPrefs]],
    *,
    drag_key: str,
) -> list[DropTarget]:
    """Calcule toutes les destinations valides pour une carte dragguée."""
    if not tiles or drag_key not in {k for k, _w, _p in tiles}:
        return []

    keys = [k for k, _w, _p in tiles]
    by_key = {k: (w, p) for k, w, p in tiles}
    drag_widget, drag_prefs = by_key[drag_key]
    drag_compact = _is_compact_widget(drag_widget)
    base = [k for k in keys if k != drag_key]

    static_tiles = [(k, by_key[k][0], by_key[k][1]) for k in base]
    static_geos = compute_grid_geometries(container_width, spacing, static_tiles)
    full_geos = compute_grid_geometries(container_width, spacing, tiles)
    drag_geo = full_geos.get(drag_key)
    drag_col = -1
    if drag_geo is not None:
        drag_col = geo_grid_column(drag_geo, container_width, spacing)
    if drag_prefs.grid_col in (0, 1):
        drag_col = drag_prefs.grid_col

    col_w = _column_width(container_width, spacing)
    targets: list[DropTarget] = []
    seen: set[tuple] = set()

    def _add(
        geo: QRect,
        action: str,
        anchor_key: str,
        grid_col: int,
        *,
        stack: bool = False,
        swap_drag_col: int = -1,
    ) -> None:
        expected_x = grid_col * (col_w + spacing)
        if abs(geo.x() - expected_x) > 4:
            return
        if geo.width() > col_w + spacing // 2 and not (
            action == "swap" and geo.width() > col_w * 2
        ):
            return
        sig = (
            geo.x(),
            geo.y(),
            geo.width(),
            geo.height(),
            action,
            anchor_key,
            grid_col,
            stack,
            swap_drag_col,
        )
        if sig in seen:
            return
        seen.add(sig)
        targets.append(
            DropTarget(
                QRect(geo),
                action,
                anchor_key,
                grid_col,
                stack=stack,
                drag_col=swap_drag_col,
            )
        )

    def _cols_for_insert(anchor_key: str) -> tuple[int, ...]:
        _anchor_w, anchor_p = by_key[anchor_key]
        drag_span = min(col_span(drag_prefs), GRID_COLS)
        if drag_compact or drag_span < 2:
            return (0, 1)
        return (_anchor_col(anchor_key, anchor_p, static_geos, container_width, spacing),)

    for anchor_key in base:
        anchor_widget, anchor_prefs = by_key[anchor_key]
        anchor_compact = _is_compact_widget(anchor_widget)
        anchor_geo = static_geos.get(anchor_key)
        anchor_col = (
            _anchor_col(
                anchor_key, anchor_prefs, static_geos, container_width, spacing
            )
            if anchor_geo is not None
            else -1
        )

        for col in _cols_for_insert(anchor_key):
            # Drop sur une carte de l'autre colonne → swap, pas insertion
            if (
                anchor_geo is not None
                and col == anchor_col
                and drag_col in (0, 1)
                and drag_col != anchor_col
            ):
                continue
            order = _preview_insert_before(keys, drag_key, anchor_key)
            geo = _drag_geometry(
                width=container_width,
                spacing=spacing,
                order=order,
                by_key=by_key,
                drag_key=drag_key,
                forced_col=col,
                stack_anchor=None,
            )
            if geo is None:
                continue
            if geo_grid_column(geo, container_width, spacing) != col:
                continue
            _add(geo, "insert_before", anchor_key, col)

        if drag_compact and anchor_compact:
            for col in (0, 1):
                order = _preview_insert_after(keys, drag_key, anchor_key)
                geo = _drag_geometry(
                    width=container_width,
                    spacing=spacing,
                    order=order,
                    by_key=by_key,
                    drag_key=drag_key,
                    forced_col=col,
                    stack_anchor=anchor_key,
                )
                if geo is None:
                    continue
                if geo_grid_column(geo, container_width, spacing) != col:
                    continue
                _add(geo, "insert_after", anchor_key, col, stack=True)

        # Échange direct : la carte ancre prend la place d'origine du drag
        if anchor_geo is not None and anchor_geo.width() <= col_w + spacing // 2:
            _add(
                QRect(anchor_geo),
                "swap",
                anchor_key,
                anchor_col,
                swap_drag_col=drag_col,
            )


    return targets


def _distance2(point: QPoint, rect: QRect) -> int:
    cx, cy = rect.center().x(), rect.center().y()
    return (cx - point.x()) ** 2 + (cy - point.y()) ** 2


def _y_distance2(point: QPoint, rect: QRect) -> int:
    return (rect.center().y() - point.y()) ** 2


def pick_drop_target(
    targets: list[DropTarget],
    point: QPoint,
    *,
    container_width: int,
    spacing: int,
    drag_compact: bool,
    previous: DropTarget | None = None,
) -> DropTarget | None:
    """Choisit la destination sous le curseur."""
    if not targets:
        return None

    col_w = _column_width(container_width, spacing)
    pointer_col = grid_column_at_x(point.x(), container_width, spacing)
    hit_pad = 10

    if previous is not None:
        sticky = previous.rect.adjusted(-14, -14, 14, 14)
        if sticky.contains(point):
            if (
                drag_compact
                and previous.rect.width() > col_w + spacing // 2
            ):
                narrow = [
                    t
                    for t in targets
                    if t.anchor_key == previous.anchor_key
                    and t.grid_col == pointer_col
                    and t.action == previous.action
                    and t.rect.width() <= col_w + spacing // 2
                ]
                if narrow:
                    return min(narrow, key=lambda t: _y_distance2(point, t.rect))
            return previous

    inside = [
        t
        for t in targets
        if t.rect.adjusted(-hit_pad, -hit_pad, hit_pad, hit_pad).contains(point)
    ]
    if inside:
        swap_inside = [t for t in inside if t.action == "swap"]
        if swap_inside:
            return min(swap_inside, key=lambda t: _distance2(point, t.rect))
        wide = [t for t in inside if t.rect.width() > col_w + spacing // 2]
        if drag_compact and wide:
            anchor_key = min(wide, key=lambda t: _distance2(point, t.rect)).anchor_key
            narrow = [
                t
                for t in targets
                if t.anchor_key == anchor_key
                and t.grid_col == pointer_col
                and t.rect.width() <= col_w + spacing // 2
            ]
            if narrow:
                best = min(narrow, key=lambda t: _y_distance2(point, t.rect))
                return best
        pool = inside
    else:
        pool = [
            t
            for t in targets
            if t.grid_col == pointer_col
            or t.rect.width() > col_w + spacing // 2
        ]
        if not pool:
            pool = list(targets)

    col_pool = [t for t in pool if t.grid_col == pointer_col]
    if col_pool:
        pool = col_pool

    if drag_compact:
        best = min(pool, key=lambda t: _y_distance2(point, t.rect))
    else:
        best = min(pool, key=lambda t: _distance2(point, t.rect))

    if best.action == "insert_before" and best.rect.width() > col_w + spacing // 2:
        result = DropTarget(
            best.rect,
            best.action,
            best.anchor_key,
            pointer_col,
            best.stack,
        )
    else:
        result = best


    return result


def apply_drop_target(
    drag_key: str,
    target: DropTarget,
    *,
    drag_compact: bool,
    anchor_compact: bool,
) -> bool:
    """Applique le drop ; retourne True si l'ordre a changé."""
    if target.action == "insert_before":
        insert_field_before(drag_key, target.anchor_key)
        set_card_grid_col(drag_key, target.grid_col)
        clear_stack_under(drag_key)
    elif target.action == "insert_after":
        insert_field_after(drag_key, target.anchor_key)
        set_card_grid_col(drag_key, target.grid_col)
        if not target.stack:
            clear_stack_under(drag_key)
    elif target.action == "swap":
        swap_field_order(drag_key, target.anchor_key)
        set_card_grid_col(drag_key, target.grid_col)
        if target.drag_col in (0, 1):
            set_card_grid_col(target.anchor_key, target.drag_col)
        clear_stack_under(drag_key)
        clear_stack_under(target.anchor_key)
    else:
        return False
    return True


def target_identity(target: DropTarget) -> tuple:
    return (
        target.action,
        target.anchor_key,
        target.grid_col,
        target.drag_col,
        target.rect.x(),
        target.rect.y(),
        target.stack,
    )
