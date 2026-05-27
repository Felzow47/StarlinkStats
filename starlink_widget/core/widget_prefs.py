"""Préférences d'affichage du widget (visibilité + ordre, persistance QSettings)."""

from __future__ import annotations

import json
from typing import List, Set

from PyQt6.QtCore import QSettings

from starlink_widget.core.display_fields import (
    DEFAULT_VISIBLE_KEYS,
    DISPLAY_FIELDS,
    FIELD_BY_KEY,
    HEADER_KEYS,
)

SETTINGS_ORG = "StarlinkWidget"
SETTINGS_APP = "Widget"
VISIBLE_FIELDS_KEY = "visible_fields"
FIELD_ORDER_KEY = "field_order"
STACK_UNDER_KEY = "stack_under"

DEFAULT_FIELD_ORDER: List[str] = [f.key for f in DISPLAY_FIELDS]


def load_field_order() -> List[str]:
    settings = QSettings(SETTINGS_ORG, SETTINGS_APP)
    raw = settings.value(FIELD_ORDER_KEY)
    order: List[str] = []
    if raw:
        try:
            order = [k for k in json.loads(str(raw)) if k in FIELD_BY_KEY]
        except (json.JSONDecodeError, TypeError):
            order = []
    if not order:
        order = list(DEFAULT_FIELD_ORDER)
    for key in DEFAULT_FIELD_ORDER:
        if key not in order:
            order.append(key)
    return order


def load_visible_fields() -> Set[str]:
    settings = QSettings(SETTINGS_ORG, SETTINGS_APP)
    raw = settings.value(VISIBLE_FIELDS_KEY)
    if not raw:
        return set(DEFAULT_VISIBLE_KEYS)
    try:
        keys = json.loads(str(raw))
        valid = {k for k in keys if k in FIELD_BY_KEY}
        return valid if valid else set(DEFAULT_VISIBLE_KEYS)
    except (json.JSONDecodeError, TypeError):
        return set(DEFAULT_VISIBLE_KEYS)


def load_ordered_metric_keys() -> List[str]:
    visible = load_visible_fields()
    order = load_field_order()
    return [k for k in order if k in visible and k not in HEADER_KEYS]


def save_widget_preferences(visible: Set[str], order: List[str]) -> None:
    valid_visible = {k for k in visible if k in FIELD_BY_KEY}
    if not valid_visible:
        valid_visible = set(DEFAULT_VISIBLE_KEYS)

    valid_order = [k for k in order if k in FIELD_BY_KEY]
    for key in DEFAULT_FIELD_ORDER:
        if key not in valid_order:
            valid_order.append(key)

    settings = QSettings(SETTINGS_ORG, SETTINGS_APP)
    settings.setValue(VISIBLE_FIELDS_KEY, json.dumps(sorted(valid_visible)))
    settings.setValue(FIELD_ORDER_KEY, json.dumps(valid_order))
    settings.sync()


def reset_widget_preferences() -> None:
    """Remet visibilité et ordre des champs aux valeurs par défaut."""
    save_widget_preferences(set(DEFAULT_VISIBLE_KEYS), list(DEFAULT_FIELD_ORDER))


def reorder_field(from_key: str, to_key: str) -> List[str]:
    """Place from_key à la position de to_key dans l'ordre global."""
    order = load_field_order()
    if from_key not in order or to_key not in order or from_key == to_key:
        return order
    order.remove(from_key)
    order.insert(order.index(to_key), from_key)
    save_widget_preferences(load_visible_fields(), order)
    return order


def load_stack_under() -> dict[str, str]:
    """Cartes compactes à empiler sous une carte ancre (colonne)."""
    settings = QSettings(SETTINGS_ORG, SETTINGS_APP)
    raw = settings.value(STACK_UNDER_KEY)
    if not raw:
        return {}
    try:
        data = json.loads(str(raw))
        return {
            str(k): str(v)
            for k, v in data.items()
            if k in FIELD_BY_KEY and v in FIELD_BY_KEY
        }
    except (json.JSONDecodeError, TypeError):
        return {}


def set_card_grid_col(key: str, col: int) -> None:
    from starlink_widget.core.card_prefs import CardPrefs, get_card_pref, save_card_pref

    if key not in FIELD_BY_KEY or col not in (0, 1):
        return
    prefs = get_card_pref(key)
    save_card_pref(
        key,
        CardPrefs(
            prefs.size,
            prefs.graph,
            prefs.col_span,
            prefs.height_px,
            col,
            prefs.x,
            prefs.y,
            prefs.width_px,
        ).normalized(),
    )


def set_stack_under(child_key: str, anchor_key: str) -> None:
    if child_key not in FIELD_BY_KEY or anchor_key not in FIELD_BY_KEY:
        return
    mapping = load_stack_under()
    mapping[child_key] = anchor_key
    settings = QSettings(SETTINGS_ORG, SETTINGS_APP)
    settings.setValue(STACK_UNDER_KEY, json.dumps(mapping))
    settings.sync()


def clear_stack_under(child_key: str) -> None:
    mapping = load_stack_under()
    if child_key not in mapping:
        return
    del mapping[child_key]
    settings = QSettings(SETTINGS_ORG, SETTINGS_APP)
    settings.setValue(STACK_UNDER_KEY, json.dumps(mapping))
    settings.sync()


def insert_field_before(from_key: str, anchor_key: str) -> List[str]:
    """Insère from_key juste avant anchor_key (carte large au-dessus d'une compacte)."""
    order = load_field_order()
    if (
        from_key not in order
        or anchor_key not in order
        or from_key == anchor_key
    ):
        return order
    order.remove(from_key)
    order.insert(order.index(anchor_key), from_key)
    save_widget_preferences(load_visible_fields(), order)
    clear_stack_under(from_key)
    return order


def insert_field_at_start(from_key: str) -> List[str]:
    """Insère from_key en tête de l'ordre (premier emplacement grille)."""
    order = load_field_order()
    if from_key not in order:
        return order
    order.remove(from_key)
    order.insert(0, from_key)
    save_widget_preferences(load_visible_fields(), order)
    clear_stack_under(from_key)
    return order


def insert_field_after(from_key: str, anchor_key: str) -> List[str]:
    """Insère from_key juste après anchor_key (empilement / zone compacte)."""
    order = load_field_order()
    if (
        from_key not in order
        or anchor_key not in order
        or from_key == anchor_key
    ):
        return order
    order.remove(from_key)
    order.insert(order.index(anchor_key) + 1, from_key)
    save_widget_preferences(load_visible_fields(), order)
    set_stack_under(from_key, anchor_key)
    return order


def swap_card_grid_cols(key_a: str, key_b: str) -> None:
    """Échange les colonnes fixes de deux cartes (déplacement compact isolé)."""
    from starlink_widget.core.card_prefs import CardPrefs, get_card_pref, save_card_pref

    pa = get_card_pref(key_a)
    pb = get_card_pref(key_b)
    save_card_pref(
        key_a,
        CardPrefs(pa.size, pa.graph, pa.col_span, pa.height_px, pb.grid_col).normalized(),
    )
    save_card_pref(
        key_b,
        CardPrefs(pb.size, pb.graph, pb.col_span, pb.height_px, pa.grid_col).normalized(),
    )


def swap_field_order(from_key: str, to_key: str) -> List[str]:
    """Échange les positions de deux champs (drop carte sur carte)."""
    order = load_field_order()
    if from_key not in order or to_key not in order or from_key == to_key:
        return order
    i, j = order.index(from_key), order.index(to_key)
    order[i], order[j] = order[j], order[i]
    save_widget_preferences(load_visible_fields(), order)
    clear_stack_under(from_key)
    clear_stack_under(to_key)
    return order
