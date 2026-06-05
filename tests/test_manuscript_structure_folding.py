"""Part 2 — Manuscript IDE-like structural folding + numbering.

The Manuscript shows the Outline structure as numbered, foldable Act/Chapter
headers with visually-distinct descriptions, while the body editor stays a
plain prose surface. Body text is never contaminated by outline descriptions.
"""

from __future__ import annotations

import warnings

import pytest
from PySide6.QtWidgets import QApplication, QLabel

warnings.filterwarnings("ignore")

from storyplanner.db import Database
from storyplanner.ui.main_window import MainWindow
from storyplanner.ui.writing_core_view import (
    WritingCoreView,
    _FoldHeader,
    _SceneEditor,
)


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


def _proj(db):
    return db.create_project("P", narrative_engine="screenplay",
                             default_writing_format="screenplay").id


def _texts(view, object_name):
    return [w.text() for w in view.findChildren(QLabel)
            if w.objectName() == object_name]


def _editor_bodies(view):
    return [e.toPlainText() for e in view.findChildren(_SceneEditor)]


# ==========================================================================
# Structural headers + numbering
# ==========================================================================


def test_manuscript_shows_numbered_act_chapter_scene_headers():
    db = Database()
    pid = _proj(db)
    db.create_scene(pid, "Opening", act="Act I", chapter="Chapter One",
                    content="body")
    view = WritingCoreView(db, pid)

    acts = _texts(view, "writingActHeader")
    chapters = _texts(view, "writingChapterHeader")
    scenes = _texts(view, "writingSceneTitle")

    assert any("ACT I" in t and "1" in t for t in acts)
    assert any("Chapter One" in t and "1.1" in t for t in chapters)
    assert any("1.1.1" in t and "Opening" in t for t in scenes)


def test_scene_number_uses_available_levels():
    assert WritingCoreView._scene_number(1, 1, 1) == "1.1.1"
    assert WritingCoreView._scene_number(2, 3, 4) == "2.3.4"
    assert WritingCoreView._scene_number(1, 0, 2) == "1.2"   # act, no chapter
    assert WritingCoreView._scene_number(0, 0, 5) == "5"      # neither


def test_fold_headers_are_clickable_type():
    db = Database()
    pid = _proj(db)
    db.create_scene(pid, "S", act="Act I", chapter="Ch1", content="x")
    view = WritingCoreView(db, pid)
    assert any(isinstance(w, _FoldHeader) for w in view.findChildren(_FoldHeader))


# ==========================================================================
# Descriptions are distinct metadata, never body
# ==========================================================================


def test_descriptions_are_separate_from_body():
    db = Database()
    pid = _proj(db)
    db.create_scene(pid, "Opening", act="Act I", chapter="Ch1",
                    summary="SCENE_PLAN_SENTINEL", content="REAL_BODY")
    view = WritingCoreView(db, pid)

    descriptions = _texts(view, "writingSceneDescription")
    bodies = _editor_bodies(view)

    assert any("SCENE_PLAN_SENTINEL" in d for d in descriptions)  # shown distinctly
    assert any("REAL_BODY" in b for b in bodies)                  # body present
    # Planning text never leaks into the prose editor.
    assert all("SCENE_PLAN_SENTINEL" not in b for b in bodies)


def test_empty_body_shows_placeholder_not_description():
    db = Database()
    pid = _proj(db)
    db.create_scene(pid, "Opening", act="Act I", chapter="Ch1",
                    summary="SCENE_PLAN_SENTINEL", content="")
    view = WritingCoreView(db, pid)

    editors = view.findChildren(_SceneEditor)
    assert editors
    for e in editors:
        assert e.toPlainText() == ""                       # body stays empty
        assert e.placeholderText() == "Start writing…"     # neutral placeholder
    # The summary is still visible — but as distinct metadata, not as prose.
    assert any("SCENE_PLAN_SENTINEL" in d
               for d in _texts(view, "writingSceneDescription"))


# ==========================================================================
# Collapse / expand
# ==========================================================================


def test_collapse_act_hides_its_children_safely():
    db = Database()
    pid = _proj(db)
    db.create_scene(pid, "A1", act="Act I", chapter="Ch1", content="a1")
    db.create_scene(pid, "A2", act="Act I", chapter="Ch1", content="a2")
    db.create_scene(pid, "B1", act="Act II", chapter="Ch2", content="b1")
    view = WritingCoreView(db, pid)
    assert len(view._editors) == 3

    view._toggle_fold("act::Act I")          # collapse Act I
    assert len(view._editors) == 1           # only Act II scene built
    # Act I's own header stays visible (it's the toggle).
    assert any("ACT I" in t for t in _texts(view, "writingActHeader"))

    view._toggle_fold("act::Act I")          # expand again
    assert len(view._editors) == 3


def test_collapse_chapter_hides_only_its_scenes():
    db = Database()
    pid = _proj(db)
    db.create_scene(pid, "A1", act="Act I", chapter="Ch1", content="a1")
    db.create_scene(pid, "A2", act="Act I", chapter="Ch2", content="a2")
    view = WritingCoreView(db, pid)
    assert len(view._editors) == 2

    view._toggle_fold("chap::Act I::Ch1")
    assert len(view._editors) == 1           # Ch2 scene still present
    # Both chapter headers still render (Ch1 collapsed, Ch2 expanded).
    chs = " ".join(_texts(view, "writingChapterHeader"))
    assert "Ch1" in chs and "Ch2" in chs


def test_body_remains_editable_after_render():
    db = Database()
    pid = _proj(db)
    db.create_scene(pid, "S", act="Act I", chapter="Ch1", content="hello")
    view = WritingCoreView(db, pid)
    editor = next(iter(view._editors.values()))
    assert not editor.isReadOnly()
    assert "hello" in editor.toPlainText()


# ==========================================================================
# Structure refresh / project isolation
# ==========================================================================


def test_deleting_scene_refreshes_manuscript_structure():
    db = Database()
    pid = _proj(db)
    s1 = db.create_scene(pid, "S1", act="Act I", chapter="Ch1", content="x").id
    db.create_scene(pid, "S2", act="Act II", chapter="Ch2", content="y")
    view = WritingCoreView(db, pid)
    assert len(view._editors) == 2
    db.delete_scene(s1)
    view.refresh()
    assert len(view._editors) == 1                   # live structure updated
    # A freshly built manuscript reflects the deletion with no stale Act I.
    fresh = WritingCoreView(db, pid)
    acts = _texts(fresh, "writingActHeader")
    assert len(acts) == 1 and "ACT II" in acts[0]


def test_fresh_view_starts_expanded():
    db = Database()
    pid = _proj(db)
    db.create_scene(pid, "S", act="Act I", chapter="Ch1", content="x")
    view = WritingCoreView(db, pid)
    assert view._collapsed == set()


def test_project_switch_clears_structure_and_fold_state():
    db = Database()
    a = _proj(db)
    db.create_scene(a, "A-scene", act="Act A", chapter="Ch", content="x")
    b = _proj(db)
    win = MainWindow(db, a)
    win.sidebar_buttons["Manuscript"].click()
    assert isinstance(win.content_area, WritingCoreView)
    win.content_area._toggle_fold("act::Act A")
    win._switch_project(b)
    win.sidebar_buttons["Manuscript"].click()
    # Rebuilt fresh for B: no old structure, no carried-over fold state.
    assert isinstance(win.content_area, WritingCoreView)
    assert win.content_area._collapsed == set()
    assert win.content_area._editors == {}


def test_new_project_shows_no_old_structure():
    db = Database()
    a = _proj(db)
    db.create_scene(a, "A-scene", act="Act A", chapter="Ch", content="x")
    b = _proj(db)
    win = MainWindow(db, a)
    win._switch_project(b)
    win.sidebar_buttons["Manuscript"].click()
    from PySide6.QtWidgets import QLabel as _QL
    acts = [w.text() for w in win.content_area.findChildren(_QL)
            if w.objectName() == "writingActHeader"]
    assert acts == []
