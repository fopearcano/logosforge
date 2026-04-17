"""Application factory — creates the QApplication and MainWindow."""

import sys

from PySide6.QtWidgets import QApplication

from storyplanner.db import Database
from storyplanner.ui.main_window import MainWindow
from storyplanner.ui.theme import build_stylesheet

DB_PATH = "storyplanner.db"


def create_app() -> tuple[QApplication, MainWindow]:
    app = QApplication.instance() or QApplication(sys.argv)
    app.setStyleSheet(build_stylesheet())

    db = Database(DB_PATH)

    # Use the first project, or create a default one
    projects = db.get_all_projects()
    if projects:
        project = projects[0]
    else:
        project = db.create_project("My Story")

    window = MainWindow(db, project.id)
    return app, window
