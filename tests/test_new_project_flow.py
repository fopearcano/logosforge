"""Part 3 — Create New project flow is clean (no fullscreen/minimize glitch).

Exactly one project switch, one final navigation target (Dashboard), the
projects list refreshes, and no showNormal/showMinimized side effects occur.
(True fullscreen behavior is macOS-specific and not testable headlessly.)
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
def reset_settings(monkeypatch, tmp_path):
    import storyplanner.settings as settings
    settings._instance = None
    monkeypatch.setattr(settings, "CONFIG_DIR", tmp_path)
    monkeypatch.setattr(settings, "SETTINGS_FILE", tmp_path / "settings.json")
    import storyplanner.gomckee_bridge as gb
    monkeypatch.setattr(gb, "is_gomckee_enabled", lambda: False, raising=False)
    yield
    settings._instance = None


class _FakeDialog:
    def __init__(self, *a, **k): ...
    def exec(self): return True
    def get_title(self): return "Fresh"
    def get_engine(self): return "novel"
    def get_format(self): return "novel"


def _patch_dialog(monkeypatch):
    import storyplanner.ui.new_project_dialog as npd
    monkeypatch.setattr(npd, "NewProjectDialog", _FakeDialog, raising=False)


def test_create_new_one_switch_one_target_no_minimize(monkeypatch):
    db = Database()
    a = db.create_project("A", narrative_engine="novel").id
    win = MainWindow(db, a)
    _patch_dialog(monkeypatch)

    counters = {"switch": 0, "normal": 0, "minimized": 0, "refresh": 0}

    orig_switch = win._switch_project
    monkeypatch.setattr(
        win, "_switch_project",
        lambda nid, *a, **k: (counters.__setitem__("switch", counters["switch"] + 1),
                              orig_switch(nid, *a, **k))[1],
    )
    monkeypatch.setattr(
        win, "showNormal",
        lambda: counters.__setitem__("normal", counters["normal"] + 1),
    )
    monkeypatch.setattr(
        win, "showMinimized",
        lambda: counters.__setitem__("minimized", counters["minimized"] + 1),
    )
    orig_refresh = win._refresh_projects_view
    monkeypatch.setattr(
        win, "_refresh_projects_view",
        lambda *a, **k: (counters.__setitem__("refresh", counters["refresh"] + 1),
                         orig_refresh(*a, **k))[1],
    )

    win._on_new_project()

    assert counters["switch"] == 1            # exactly one project switch
    assert win._current_section == "Dashboard"  # one final navigation target
    assert counters["normal"] == 0            # never showNormal
    assert counters["minimized"] == 0         # never minimize
    assert counters["refresh"] == 1           # projects list refreshed once


def test_create_new_switches_to_fresh_empty_project(monkeypatch):
    db = Database()
    a = db.create_project("A", narrative_engine="novel").id
    db.create_scene(a, "Old", content="old")
    win = MainWindow(db, a)
    _patch_dialog(monkeypatch)
    win._on_new_project()
    new_id = win._project_id
    assert new_id != a
    assert db.get_all_scenes(new_id) == []     # clean new project
