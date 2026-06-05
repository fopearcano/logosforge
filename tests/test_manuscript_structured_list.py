"""Manuscript = compact selectable structure list + selected-unit editor.

The heavy inline structure view (numbered gutter / foldable blocks / inline
descriptions) is gone. Manuscript shows a compact left outliner; the editor on
the right opens ONLY the selected writing unit. Body text never carries Outline
descriptions, and the primary-unit adapter drives the add-button label.
"""

from __future__ import annotations

import re
import warnings

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QLabel

warnings.filterwarnings("ignore")

from storyplanner.db import Database
from storyplanner.ui.main_window import MainWindow
from storyplanner.ui.writing_core_view import WritingCoreView, _SceneEditor


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


def _screenplay(db):
    return db.create_project("P", narrative_engine="screenplay",
                             default_writing_format="screenplay").id


def _manuscript(db, pid):
    return WritingCoreView(db, pid, structured_list=True)


def _leaf_for(view, sid):
    tree = view._structure_tree

    def walk(item):
        for i in range(item.childCount()):
            c = item.child(i)
            if c.data(0, Qt.ItemDataRole.UserRole) == sid:
                return c
            r = walk(c)
            if r:
                return r
        return None

    for i in range(tree.topLevelItemCount()):
        r = walk(tree.topLevelItem(i))
        if r:
            return r
    return None


# ==========================================================================
# Heavy structure view is gone
# ==========================================================================


def test_no_numbered_structural_gutter():
    # The numbering helper/folding machinery were removed entirely.
    assert not hasattr(WritingCoreView, "_scene_number")
    assert not hasattr(WritingCoreView, "_toggle_fold")
    db = Database()
    pid = _screenplay(db)
    db.create_scene(pid, "Opening", act="Act I", chapter="Ch1", content="body")
    view = _manuscript(db, pid)
    # No "1.1.1"-style numbers appear on any rendered label.
    for w in view.findChildren(QLabel):
        assert not re.search(r"\b\d+\.\d+\.\d+\b", w.text() or "")


def test_no_foldable_block_class():
    import storyplanner.ui.writing_core_view as wcv
    assert not hasattr(wcv, "_FoldHeader")


# ==========================================================================
# Compact selectable structure list + selected-unit editor
# ==========================================================================


def test_manuscript_shows_structure_list():
    db = Database()
    pid = _screenplay(db)
    db.create_scene(pid, "S1", act="Act I", chapter="Ch1", content="a")
    db.create_scene(pid, "S2", act="Act II", chapter="Ch2", content="b")
    view = _manuscript(db, pid)
    assert view._structure_tree.topLevelItemCount() == 2   # two acts


def test_selecting_a_unit_opens_only_that_unit_body():
    db = Database()
    pid = _screenplay(db)
    s1 = db.create_scene(pid, "S1", act="Act I", chapter="Ch1", content="AAA").id
    s2 = db.create_scene(pid, "S2", act="Act II", chapter="Ch2", content="BBB").id
    view = _manuscript(db, pid)
    # First scene auto-selected → exactly one live editor showing its body.
    assert list(view._editors.keys()) == [s1]
    assert view._editors[s1].toPlainText() == "AAA"
    # Select S2 via the list → the live editor set swaps to only S2's body.
    view._on_structure_item_clicked(_leaf_for(view, s2), 0)
    assert view._selected_scene_id == s2
    assert list(view._editors.keys()) == [s2]
    assert view._editors[s2].toPlainText() == "BBB"


def test_empty_selected_unit_shows_placeholder():
    db = Database()
    pid = _screenplay(db)
    db.create_scene(pid, "Empty", act="Act I", chapter="Ch1", content="")
    view = _manuscript(db, pid)
    editors = view.findChildren(_SceneEditor)
    assert len(editors) == 1
    assert editors[0].toPlainText() == ""
    assert editors[0].placeholderText() == "Start writing…"


def test_outline_description_not_shown_as_body():
    db = Database()
    pid = _screenplay(db)
    db.create_scene(pid, "S", act="Act I", chapter="Ch1",
                    summary="PLAN_SENTINEL", content="REAL_BODY")
    view = _manuscript(db, pid)
    bodies = " ".join(e.toPlainText() for e in view.findChildren(_SceneEditor))
    assert "REAL_BODY" in bodies
    assert "PLAN_SENTINEL" not in bodies              # summary never in body
    # The summary is surfaced only as compact read-only metadata.
    assert view._structure_meta.text() == "PLAN_SENTINEL"


def test_existing_body_text_displays_and_is_editable():
    db = Database()
    pid = _screenplay(db)
    db.create_scene(pid, "S", act="Act I", chapter="Ch1", content="hello world")
    view = _manuscript(db, pid)
    editor = next(iter(view._editors.values()))
    assert "hello world" in editor.toPlainText()
    assert not editor.isReadOnly()


# ==========================================================================
# Mode-aware add button (primary-unit adapter)
# ==========================================================================


def test_novel_add_button_is_chapter():
    db = Database()
    pid = db.create_project("N", narrative_engine="novel").id
    view = WritingCoreView(db, pid, structured_list=True)
    assert view.add_button_text() == "+ Chapter"
    assert view._structure_add_btn.text() == "+ Chapter"


def test_non_novel_add_button_is_scene():
    db = Database()
    pid = _screenplay(db)
    view = WritingCoreView(db, pid, structured_list=True)
    assert view.add_button_text() == "+ Scene"
    assert view._structure_add_btn.text() == "+ Scene"


def test_add_unit_creates_and_selects_new_unit():
    db = Database()
    pid = _screenplay(db)
    db.create_scene(pid, "S1", act="Act I", chapter="Ch1", content="a")
    view = _manuscript(db, pid)
    view._add_unit_from_list()
    scenes = db.get_all_scenes(pid)
    assert len(scenes) == 2
    # The newest unit is selected and shown.
    assert view._selected_scene_id in {s.id for s in scenes}
    assert len(view._editors) == 1


# ==========================================================================
# Project switch clears selection + reloads list (via MainWindow)
# ==========================================================================


def test_project_switch_clears_selection_and_reloads_list():
    db = Database()
    a = _screenplay(db)
    db.create_scene(a, "A-scene", act="Act A", chapter="Ch", content="x")
    b = _screenplay(db)
    win = MainWindow(db, a)
    win.sidebar_buttons["Manuscript"].click()
    assert isinstance(win.content_area, WritingCoreView)
    assert win.content_area._selected_scene_id is not None
    win._switch_project(b)
    win.sidebar_buttons["Manuscript"].click()
    # Rebuilt fresh for B (empty): no carried-over selection, empty list.
    assert win.content_area._selected_scene_id is None
    assert win.content_area._structure_tree.topLevelItemCount() == 0
    assert win.content_area._editors == {}


def test_manuscript_via_mainwindow_is_structured():
    db = Database()
    pid = _screenplay(db)
    db.create_scene(pid, "S", act="Act I", chapter="Ch1", content="x")
    win = MainWindow(db, pid)
    win.sidebar_buttons["Manuscript"].click()
    assert isinstance(win.content_area, WritingCoreView)
    assert win.content_area._structured_list is True
    assert hasattr(win.content_area, "_structure_tree")


# ==========================================================================
# Writing-first: editor-only canvas + lightweight context header
# ==========================================================================


def test_canvas_is_editor_only_no_inline_title():
    db = Database()
    pid = _screenplay(db)
    db.create_scene(pid, "My Scene", act="Act I", chapter="Ch1", content="body")
    view = _manuscript(db, pid)
    # No big inline scene-title block sits in the writing canvas.
    titles = [w.text() for w in view.findChildren(QLabel)
              if w.objectName() == "writingSceneTitle"]
    assert titles == []


def test_context_header_shows_breadcrumb_and_summary():
    db = Database()
    pid = _screenplay(db)
    db.create_scene(pid, "Opening", act="Act I", chapter="Ch1",
                    summary="hero wakes", content="body")
    view = _manuscript(db, pid)
    crumb = view._context_crumb.text()
    assert "ACT I" in crumb and "Ch1" in crumb and "Opening" in crumb
    assert view._structure_meta.text() == "hero wakes"      # summary, not body


def test_context_header_updates_on_selection():
    db = Database()
    pid = _screenplay(db)
    db.create_scene(pid, "First", act="Act I", chapter="Ch1", content="a")
    s2 = db.create_scene(pid, "Second", act="Act II", chapter="Ch2",
                         content="b").id
    view = _manuscript(db, pid)
    view._on_structure_item_clicked(_leaf_for(view, s2), 0)
    crumb = view._context_crumb.text()
    assert "ACT II" in crumb and "Second" in crumb
