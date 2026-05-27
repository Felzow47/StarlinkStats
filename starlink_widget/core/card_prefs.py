"""Préférences par carte (taille hauteur, largeur colonnes, graphique)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Dict

from PyQt6.QtCore import QSettings

from starlink_widget.core.display_fields import FIELD_BY_KEY, supports_graph

SETTINGS_ORG = "StarlinkWidget"
SETTINGS_APP = "Widget"
CARD_PREFS_KEY = "card_prefs"

SIZE_SMALL = 1
SIZE_MEDIUM = 2
SIZE_LARGE = 3


@dataclass
class CardPrefs:
    size: int = SIZE_MEDIUM
    graph: bool = False
    col_span: int = 1  # 1 = demi-largeur, 2 = pleine largeur (2 colonnes)

    def normalized(self) -> "CardPrefs":
        size = max(SIZE_SMALL, min(SIZE_LARGE, self.size))
        span = 2 if self.col_span >= 2 else 1
        graph = self.graph
        return CardPrefs(size, graph, span)


DEFAULT_CARD_PREFS: Dict[str, CardPrefs] = {
    "downlink": CardPrefs(SIZE_MEDIUM, True, 1),
    "uplink": CardPrefs(SIZE_MEDIUM, True, 1),
    "pop_ping_latency": CardPrefs(SIZE_MEDIUM, True, 1),
    "pop_ping_drop_rate": CardPrefs(SIZE_MEDIUM, True, 1),
}


def _default_for(key: str) -> CardPrefs:
    if key in DEFAULT_CARD_PREFS:
        d = DEFAULT_CARD_PREFS[key]
        return CardPrefs(d.size, d.graph, d.col_span)
    return CardPrefs()


def load_card_prefs() -> Dict[str, CardPrefs]:
    settings = QSettings(SETTINGS_ORG, SETTINGS_APP)
    raw = settings.value(CARD_PREFS_KEY)
    result: Dict[str, CardPrefs] = {}
    if raw:
        try:
            data = json.loads(str(raw))
            for key, cfg in data.items():
                if key not in FIELD_BY_KEY:
                    continue
                size = int(cfg.get("size", SIZE_MEDIUM))
                graph = bool(cfg.get("graph", False))
                span = int(cfg.get("col_span", 1))
                prefs = CardPrefs(size, graph, span).normalized()
                if prefs.graph and not supports_graph(key):
                    prefs = CardPrefs(prefs.size, False, prefs.col_span)
                result[key] = prefs
        except (json.JSONDecodeError, TypeError, ValueError):
            pass
    return result


def get_card_pref(key: str) -> CardPrefs:
    prefs = load_card_prefs()
    if key in prefs:
        return prefs[key]
    return _default_for(key)


def save_card_pref(key: str, prefs: CardPrefs) -> None:
    if key not in FIELD_BY_KEY:
        return
    prefs = prefs.normalized()
    if prefs.graph and not supports_graph(key):
        prefs = CardPrefs(prefs.size, False, prefs.col_span)
    all_prefs = load_card_prefs()
    all_prefs[key] = prefs
    _save_all(all_prefs)


def _save_all(all_prefs: Dict[str, CardPrefs]) -> None:
    data = {
        k: {"size": v.size, "graph": v.graph, "col_span": v.col_span}
        for k, v in all_prefs.items()
    }
    settings = QSettings(SETTINGS_ORG, SETTINGS_APP)
    settings.setValue(CARD_PREFS_KEY, json.dumps(data))
    settings.sync()


def col_span(prefs: CardPrefs) -> int:
    return prefs.col_span


def reset_card_prefs() -> None:
    """Supprime les préférences carte sauvegardées (retour aux défauts par champ)."""
    settings = QSettings(SETTINGS_ORG, SETTINGS_APP)
    settings.remove(CARD_PREFS_KEY)
    settings.sync()
