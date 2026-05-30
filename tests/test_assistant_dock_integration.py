"""MainWindow integration tests for the Smart Assistant dock (Phase 1).

Every section (Manuscript / Outline / Plot / Timeline / Graph) must use the
same single AssistantDock + AssistantPanel instance, so panel behaviour is
identical regardless of the active section.
"""

from __future__ import annotations

import warnings

import pytest
from PySide6.QtWidgets import QApplication

warnings.filterwarnings("ignore")

from storyplanner.db import Database
from storyplanner.ui.main_window import MainWindow


@pytest.fixture(scope="module", autouse=True)
def _qapp():
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture(autouse=True)
def _isolated_settings(monkeypatch, tmp_path):
    import storyplanner.settings as settings
    settings._instance = None
    monkeypatch.setattr(settings, "CONFIG_DIR", tmp_path, raising=False)
    monkeypatch.setattr(settings, "SETTINGS_FILE", tmp_path / "settings.json", raising=False)
    yield
    settings._instance = None


def _window():
    db = Database()
    pid = db.create_project("P").id
    db.create_scene(pid, "S1", act="Act I", plotline="Main")
    win = MainWindow(db, pid)
    win.resize(1400, 900)
    return win


def test_window_has_single_dock_and_panel():
    win = _window()
    assert win._assistant_dock is not None
    assert win._assistant_dock.panel is win._assistant_panel


@pytest.mark.parametrize("show", [
    "_show_manuscript", "_show_plan", "_show_plot", "_show_timeline", "_show_graph",
])
def test_every_section_uses_the_same_dock(show):
    win = _window()
    getattr(win, show)()
    QApplication.instance().processEvents()
    # Content lives inside the one dock; the panel instance never changes.
    assert win._assistant_dock.content() is win.content_area
    assert win._assistant_dock.panel is win._assistant_panel


def test_section_switch_keeps_panel_visibility():
    win = _window()
    win._toggle_assistant()  # show
    assert win._assistant_dock.is_panel_user_visible()
    win._show_plot()
    QApplication.instance().processEvents()
    assert win._assistant_dock.is_panel_user_visible()
    win._show_graph()
    QApplication.instance().processEvents()
    assert win._assistant_dock.is_panel_user_visible()


def test_toggle_assistant_routes_through_dock():
    win = _window()
    assert not win._assistant_dock.is_panel_user_visible()
    win._toggle_assistant()
    assert win._assistant_dock.is_panel_user_visible()
    win._toggle_assistant()
    assert not win._assistant_dock.is_panel_user_visible()


def test_overlay_toggle_sets_dock_floating():
    win = _window()
    win._toggle_assistant()
    win._on_overlay_toggled(True)
    assert win._assistant_dock.is_floating()
    win._on_overlay_toggled(False)
    assert not win._assistant_dock.is_floating()


def test_pin_and_collapse_persist_to_settings():
    import storyplanner.settings as settings
    win = _window()
    win._assistant_dock.set_pinned(True)
    win._assistant_dock.set_collapsed(True)
    mgr = settings.get_manager()
    assert mgr.get("assistant_pinned") is True
    assert mgr.get("assistant_collapsed") is True


def test_apply_layout_for_width_delegates_without_error():
    win = _window()
    win._toggle_assistant()
    # The legacy hook now delegates to the dock; must not raise at any width.
    for w in (1600, 1200, 900, 700, 500):
        win.resize(w, 800)
        win._apply_layout_for_width(w)
    QApplication.instance().processEvents()
