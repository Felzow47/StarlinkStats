"""QSS styles for health states."""

from starlink_widget.core.state import HealthState

BASE_STYLE = """
QWidget#StarlinkWidget {
    border-radius: 10px;
    border: 3px solid #333;
    color: #e8e8e8;
    font-family: "Segoe UI", sans-serif;
}
QLabel {
    background: transparent;
    color: #e8e8e8;
}
QLabel#statusLabel {
    font-size: 15px;
    font-weight: bold;
}
QLabel#detailLabel {
    font-size: 11px;
}
QLabel#alertLabel {
    font-size: 11px;
    color: #ffcc66;
}
"""

STATE_COLORS = {
    HealthState.GREEN: ("#1a3d1a", "#3dcc3d"),
    HealthState.ORANGE: ("#4a3520", "#ff9933"),
    HealthState.RED: ("#4a1515", "#ff3333"),
    HealthState.HIDDEN: ("#1a1a1a", "#333333"),
}

FLASH_RED_BG = "#8b0000"
FLASH_RED_BORDER = "#ff0000"


def style_for_state(state: HealthState, flashing: bool = False) -> str:
    bg, border = STATE_COLORS.get(state, STATE_COLORS[HealthState.RED])
    if flashing and state == HealthState.RED:
        bg = FLASH_RED_BG
        border = FLASH_RED_BORDER
    return (
        BASE_STYLE
        + f"""
QWidget#StarlinkWidget {{
    background-color: {bg};
    border-color: {border};
}}
"""
    )
