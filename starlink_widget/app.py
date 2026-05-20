"""Application entry."""

from __future__ import annotations

import sys

from PyQt6.QtWidgets import QApplication

from starlink_widget.core.config import load_config
from starlink_widget.ui.main_window import MainWindow


def main() -> int:
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    config = load_config()
    window = MainWindow(config)
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
