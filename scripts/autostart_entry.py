"""Lanceur au logon (mode dev) : impose la racine du projet, indépendamment du cwd."""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
os.chdir(ROOT)
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if "--autostart" not in sys.argv:
    sys.argv.append("--autostart")

from starlink_widget.app import main

if __name__ == "__main__":
    raise SystemExit(main())
