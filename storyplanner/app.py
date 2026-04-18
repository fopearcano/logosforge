"""Application factory — creates the QApplication and MainWindow."""

import sys

from PySide6.QtWidgets import QApplication

from storyplanner import preferences
from storyplanner.db import Database
from storyplanner.settings import get_manager as get_settings
from storyplanner.ui.main_window import MainWindow
from storyplanner.ui import theme

DB_PATH = "storyplanner.db"


def create_app() -> tuple[QApplication, MainWindow]:
    app = QApplication.instance() or QApplication(sys.argv)

    mgr = get_settings()
    saved = str(mgr.get("appearance"))
    if saved in theme.PALETTE_NAMES:
        theme.set_palette(saved)

    app.setStyleSheet(theme.build_stylesheet())

    db = Database(DB_PATH)

    projects = db.get_all_projects()
    if projects:
        project = projects[0]
    else:
        project = db.create_project("My Story")

    window = MainWindow(db, project.id)

    last_path = str(mgr.get("last_project_path") or "")
    if last_path:
        window.load_file_quiet(last_path)

    return app, window
