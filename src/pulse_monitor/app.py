"""Ponto de entrada da IHM Pulse Monitor."""

from __future__ import annotations

import sys

from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication

from pulse_monitor.ui.main_window import MainWindow


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("Pulse Monitor")
    app.setFont(QFont("Sans Serif", 10))

    window = MainWindow(start_acquisition=True)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
