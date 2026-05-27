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


def swap_field_order(from_key: str, to_key: str) -> List[str]:
    """Échange les positions de deux champs (drop carte sur carte)."""
    order = load_field_order()
    if from_key not in order or to_key not in order or from_key == to_key:
        return order
    i, j = order.index(from_key), order.index(to_key)
    order[i], order[j] = order[j], order[i]
    save_widget_preferences(load_visible_fields(), order)
    return order
