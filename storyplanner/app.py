"""Application factory — creates the QApplication and MainWindow."""

import os
import sys

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from storyplanner import preferences
from storyplanner.db import Database
from storyplanner.paths import get_assets_path
from storyplanner.plugin_manager import get_plugin_manager
from storyplanner.settings import get_manager as get_settings
from storyplanner.ui.main_window import MainWindow
from storyplanner.ui import theme

DB_PATH = "storyplanner.db"


def _set_macos_app_name(name: str) -> None:
    """Set CFBundleName so macOS shows the correct name in the menu bar and dock."""
    if sys.platform != "darwin":
        return
    try:
        from Foundation import NSBundle
        info = NSBundle.mainBundle().infoDictionary()
        info["CFBundleName"] = name
    except Exception:
        pass


def create_app() -> tuple[QApplication, MainWindow]:
    _set_macos_app_name("Logosforge")
    QApplication.setApplicationName("Logosforge")
    QApplication.setApplicationDisplayName("Logosforge")
    QApplication.setOrganizationName("Logosforge")
    app = QApplication.instance() or QApplication(sys.argv)

    assets = get_assets_path()
    for icon_name in ("icon.png", "icon.svg"):
        icon_path = str(assets / icon_name)
        if os.path.exists(icon_path):
            app.setWindowIcon(QIcon(icon_path))
            break

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

    pm = get_plugin_manager()
    pm.discover()
    pm.set_app_context(db, project.id)
    pm.load_enabled()

    window = MainWindow(db, project.id)

    last_path = str(mgr.get("last_project_path") or "")
    if last_path:
        window.load_file_quiet(last_path)

    # Always land on Projects at startup — never Dashboard by default.
    # Runs after any session restore so it wins the final navigation and
    # rebuilds the Projects list against current data.
    window.show_initial_section()

    window._refresh_plugins_menu()

    return app, window
