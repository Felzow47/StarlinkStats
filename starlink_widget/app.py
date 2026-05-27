"""Application entry."""

from __future__ import annotations

import sys
import traceback

from PyQt6.QtWidgets import QApplication

from starlink_widget.core.config import load_config
from starlink_widget.debug_log import debug_exception, debug_log
from starlink_widget.ui.main_window import MainWindow


def _debug_excepthook(exc_type, exc, tb) -> None:
    # #region agent log
    debug_log(
        "app.py:excepthook",
        "uncaught exception",
        {"traceback": "".join(traceback.format_exception(exc_type, exc, tb))},
        hypothesis_id="E",
    )
    # #endregion
    sys.__excepthook__(exc_type, exc, tb)


def main() -> int:
    sys.excepthook = _debug_excepthook
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    config = load_config()
    window = MainWindow(config)
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
