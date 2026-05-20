"""Application entry."""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

from PyQt6.QtWidgets import QApplication

from starlink_widget.core.config import load_config
from starlink_widget.ui.main_window import MainWindow

# #region agent log
_DEBUG_LOG = Path(__file__).resolve().parents[1] / "debug-26b621.log"


def _dbg(location: str, message: str, data: dict | None = None, hypothesis_id: str = "") -> None:
    try:
        payload = {
            "sessionId": "26b621",
            "timestamp": int(time.time() * 1000),
            "location": location,
            "message": message,
            "data": data or {},
            "hypothesisId": hypothesis_id,
        }
        with open(_DEBUG_LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps(payload) + "\n")
    except OSError:
        pass


# #endregion


def main() -> int:
    # #region agent log
    _dbg("app.py:main", "startup_begin", hypothesis_id="A")
    # #endregion
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    config = load_config()
    try:
        window = MainWindow(config)
    except Exception as exc:
        # #region agent log
        _dbg(
            "app.py:main",
            "startup_failed",
            {"error": type(exc).__name__, "detail": str(exc)[:500]},
            hypothesis_id="A",
        )
        # #endregion
        raise
    # #region agent log
    _dbg(
        "app.py:main",
        "startup_ok",
        {"tiles": len(window._metric_tiles)},
        hypothesis_id="A",
    )
    # #endregion
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
