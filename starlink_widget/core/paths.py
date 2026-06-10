"""Chemins application (dev source ou exe PyInstaller installe)."""

from __future__ import annotations

import sys
from pathlib import Path


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def app_root() -> Path:
    """Racine install / projet (config.json, scripts/)."""
    if is_frozen():
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[2]


def scripts_dir() -> Path:
    return app_root() / "scripts"


def app_icon_path() -> Path | None:
    """Icone application (.ico), dev ou installe."""
    for rel in (
        Path("assets") / "starlink_widget.ico",
        Path("starlink_widget.ico"),
    ):
        path = app_root() / rel
        if path.is_file():
            return path
    return None
