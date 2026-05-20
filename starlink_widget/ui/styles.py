"""Palette et styles type app Starlink (dark, cartes, typo hiérarchisée)."""

from starlink_widget.core.state import HealthState

WIDGET_WIDTH = 300
CORNER_RADIUS = 16
INNER_RADIUS = 12

# Fond carte principale (proche iOS / Starlink dark)
CARD_BG = (22, 22, 24, 242)
CARD_BG_FLASH = (48, 18, 22, 248)
CARD_BORDER = (255, 255, 255, 18)  # ~7 % blanc

# Tuiles métriques internes (style carte Starlink)
TILE_BG = (38, 38, 42, 250)
TILE_BORDER = (255, 255, 255, 14)

TEXT_PRIMARY = "#ffffff"
TEXT_SECONDARY = "#8e8e93"
TEXT_TERTIARY = "#636366"

OK_GREEN = "#34c759"
WARN_AMBER = "#ff9f0a"
ERR_RED = "#ff453a"
FLASH_RED = "#ff375f"

STATE_COLORS = {
    HealthState.GREEN: OK_GREEN,
    HealthState.ORANGE: WARN_AMBER,
    HealthState.RED: ERR_RED,
    HealthState.HIDDEN: TEXT_TERTIARY,
}


def status_color(state: HealthState, flashing: bool = False) -> str:
    if flashing and state == HealthState.RED:
        return FLASH_RED
    return STATE_COLORS.get(state, ERR_RED)


def format_status_title(raw: str) -> str:
    """Titre lisible façon app (pas tout en majuscules)."""
    mapping = {
        "EN LIGNE": "En ligne",
        "SANS INTERNET": "Sans Internet",
        "ANTENNE HORS LIGNE": "Antenne hors ligne",
        "Hors réseau Starlink": "Hors réseau",
    }
    if raw in mapping:
        return mapping[raw]
    if raw.startswith("EN LIGNE — "):
        return "En ligne"
    return raw.capitalize() if raw.isupper() else raw


def label_styles() -> str:
    return f"""
QWidget#StarlinkWidget {{
    background: transparent;
    color: {TEXT_PRIMARY};
    font-family: "Segoe UI Variable", "Segoe UI", sans-serif;
}}
QLabel {{
    background: transparent;
    color: {TEXT_PRIMARY};
}}
QLabel#statusTitle {{
    font-size: 17px;
    font-weight: 700;
    letter-spacing: -0.3px;
}}
QLabel#statusSubtitle {{
    font-size: 11px;
    font-weight: 400;
    color: {TEXT_SECONDARY};
}}
QLabel#alertLabel {{
    font-size: 11px;
    font-weight: 500;
    color: {WARN_AMBER};
}}
QLabel#metricTitle {{
    font-size: 10px;
    font-weight: 500;
    color: {TEXT_SECONDARY};
}}
QLabel#metricValue {{
    font-size: 18px;
    font-weight: 700;
    letter-spacing: -0.5px;
}}
QLabel#metricUnit {{
    font-size: 11px;
    font-weight: 500;
    color: {TEXT_SECONDARY};
}}
QLabel#versionLabel {{
    font-size: 9px;
    color: {TEXT_TERTIARY};
}}
"""
