"""Application entry."""

from __future__ import annotations

import sys
import time
import traceback

from PyQt6.QtWidgets import QApplication

from starlink_widget.core.config import load_config
from starlink_widget.debug_log import debug_exception, debug_log
from starlink_widget.ui.boot_screen import BootScreen
from starlink_widget.ui.main_window import MainWindow

AUTOSTART_FLAG = "--autostart"
AUTOSTART_DELAY_SECONDS = 30


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
    autostart_launch = AUTOSTART_FLAG in sys.argv[1:]
    if autostart_launch:
        time.sleep(AUTOSTART_DELAY_SECONDS)
    qt_argv = [sys.argv[0], *[arg for arg in sys.argv[1:] if arg != AUTOSTART_FLAG]]
    app = QApplication(qt_argv)
    app.setQuitOnLastWindowClosed(False)
    config = load_config()
    window = MainWindow(config)
    if not autostart_launch:
        boot_screen = BootScreen()
        boot_screen.run_and_wait_confirmation()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
