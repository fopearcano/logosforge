"""Application factory — creates the QApplication and MainWindow."""

import sys

from PySide6.QtWidgets import QApplication

from storyplanner.ui.main_window import MainWindow


def create_app() -> tuple[QApplication, MainWindow]:
    app = QApplication.instance() or QApplication(sys.argv)
    window = MainWindow()
    return app, window
