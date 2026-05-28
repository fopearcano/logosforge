"""Regression tests for the Manuscript editor not being destroyed mid-typing.

Bug: Typing in the manuscript editor triggered a 500ms autosave timer that
called the parent's `_on_data_changed`, which in turn called
`_refresh_active_view()` → `WritingCoreView.refresh()` → `_clear_canvas()`,
which destroyed the active editor widget via `deleteLater()`.  The visible
symptom was the editor appearing greyed out / non-editable.

Fix: routine content saves and in-place format changes route through a
lightweight `on_content_saved` callback that updates dirty/version state but
does NOT trigger a view refresh of the editor itself.
"""

from __future__ import annotations

import pytest
from PySide6.QtWidgets import QApplication

from storyplanner.db import Database
from storyplanner.ui.writing_core_view import WritingCoreView


@pytest.fixture(scope="module", autouse=True)
def _qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def _make_project(db: Database):
    proj = db.create_project("Novel")
    s1 = db.create_scene(proj.id, "Opening", content="The storm began.")
    s2 = db.create_scene(proj.id, "Rising", content="She ran.")
    return proj, s1, s2


# -- callback wiring ---------------------------------------------------------

def test_save_scene_uses_content_saved_callback_not_data_changed():
    db = Database()
    proj, s1, _ = _make_project(db)
    data_calls = []
    content_calls = []
    view = WritingCoreView(
        db, proj.id,
        on_data_changed=lambda: data_calls.append(1),
        on_content_saved=lambda: content_calls.append(1),
    )
    view._save_scene(s1.id)
    assert content_calls == [1]
    assert data_calls == []


def test_format_change_uses_content_saved_callback():
    db = Database()
    proj, _, _ = _make_project(db)
    data_calls = []
    content_calls = []
    view = WritingCoreView(
        db, proj.id,
        on_data_changed=lambda: data_calls.append(1),
        on_content_saved=lambda: content_calls.append(1),
    )
    db.update_project_writing_format(proj.id, "screenplay")
    view.reload_project_format()
    assert content_calls, "Expected content_saved to be called on format change"
    assert data_calls == []


def test_falls_back_to_on_data_changed_when_no_content_saved():
    db = Database()
    proj, s1, _ = _make_project(db)
    data_calls = []
    view = WritingCoreView(
        db, proj.id,
        on_data_changed=lambda: data_calls.append(1),
    )
    view._save_scene(s1.id)
    assert data_calls == [1]


def test_create_scene_after_uses_content_saved():
    db = Database()
    proj, s1, _ = _make_project(db)
    data_calls = []
    content_calls = []
    view = WritingCoreView(
        db, proj.id,
        on_data_changed=lambda: data_calls.append(1),
        on_content_saved=lambda: content_calls.append(1),
    )
    view._create_scene_after(s1.id)
    assert content_calls, "Expected content_saved when continuation scene created"
    assert data_calls == []


# -- the actual regression: editor must not be destroyed during typing ------

def test_save_scene_does_not_destroy_editor():
    """The editor widget the user is typing in must survive its own autosave."""
    db = Database()
    proj, s1, _ = _make_project(db)

    rebuilt = []

    def fake_refresh_callback():
        rebuilt.append(1)

    view = WritingCoreView(
        db, proj.id,
        on_data_changed=fake_refresh_callback,
        on_content_saved=lambda: None,
    )
    editor_before = view._editors[s1.id]
    editor_id_before = id(editor_before)

    view._save_scene(s1.id)

    editor_after = view._editors[s1.id]
    assert id(editor_after) == editor_id_before
    assert editor_after is editor_before
    assert rebuilt == [], "on_data_changed (refresh trigger) must NOT fire on a content save"


def test_save_scene_persists_content_to_db():
    """Content saves still happen — only the destructive refresh is skipped."""
    db = Database()
    proj, s1, _ = _make_project(db)
    view = WritingCoreView(db, proj.id, on_content_saved=lambda: None)
    editor = view._editors[s1.id]
    editor.setPlainText("Brand new paragraph.")
    view._save_scene(s1.id)
    scene = db.get_scene_by_id(s1.id)
    assert "Brand new paragraph" in (scene.content or "")


# -- main window wiring ------------------------------------------------------

def test_main_window_has_on_scene_content_saved_method():
    from storyplanner.ui.main_window import MainWindow
    assert hasattr(MainWindow, "_on_scene_content_saved"), (
        "MainWindow must expose _on_scene_content_saved for the lightweight save path"
    )


def test_on_scene_content_saved_does_not_refresh_active_view():
    """The whole point of the split: content saves must not refresh the view."""
    import inspect
    from storyplanner.ui.main_window import MainWindow
    source = inspect.getsource(MainWindow._on_scene_content_saved)
    assert "_refresh_active_view" not in source, (
        "_on_scene_content_saved must NOT call _refresh_active_view "
        "(that's what destroyed the editor during typing)"
    )


def test_on_data_changed_still_refreshes_active_view():
    """Structural changes (new/deleted scene from outside Manuscript) still refresh."""
    import inspect
    from storyplanner.ui.main_window import MainWindow
    source = inspect.getsource(MainWindow._on_data_changed)
    assert "_refresh_active_view" in source
