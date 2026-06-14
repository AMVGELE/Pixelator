from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from pixelator.gui.main_window import MainWindow


def main(argv: list[str] | None = None) -> int:
    app = QApplication(argv if argv is not None else sys.argv)
    window = MainWindow()
    window.show()
    return app.exec()
