"""Manuscript right-side Navigator (IDE-style document outline).

The Manuscript writing area shows a compact canonical Act → Chapter → Scene
navigator on the right (replacing the old per-header "Actions" buttons). It is
read/navigate only: clicking a unit opens it in the editor; it never edits
structure or body, uses canonical numbering, and never shows orphans before Acts.
"""

from __future__ import annotations

import warnings

import pytest
from PySide6.QtWidgets import QApplication, QPushButton, QTreeWidgetItem

warnings.filterwarnings("ignore")

from storyplanner.db import Database
from storyplanner import story_structure as ss
from storyplanner.ui.main_window import MainWindow
from storyplanner.ui.manuscript_navigator import (
    ManuscriptNavigator,
    _ROLE_KIND,
    _ROLE_SCENE_ID,
)
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


def _novel(db):
    return db.create_project("P", narrative_engine="novel").id


def _manuscript(db, pid):
    return WritingCoreView(db, pid, structured_list=True)


def _all_items(tree) -> list[QTreeWidgetItem]:
    out: list[QTreeWidgetItem] = []

    def walk(it):
        out.append(it)
        for i in range(it.childCount()):
            walk(it.child(i))
    for i in range(tree.topLevelItemCount()):
        walk(tree.topLevelItem(i))
    return out


def _labels(tree) -> list[str]:
    return [it.text(0) for it in _all_items(tree)]


def _scene_item(tree, scene_id):
    for it in _all_items(tree):
        if it.data(0, _ROLE_KIND) == "scene" and it.data(0, _ROLE_SCENE_ID) == scene_id:
            return it
    return None


# ==========================================================================
# 1-3  Right-side navigator with canonical order + numbering
# ==========================================================================


def test_manuscript_has_navigator_not_actions_panel():
    db = Database()
    pid = _novel(db)
    ss.create_scene(db, pid, act="Act I", chapter="Ch1", title="S", content="x")
    mv = _manuscript(db, pid)
    assert isinstance(mv._navigator, ManuscriptNavigator)
    # The old per-header "Actions" buttons are gone.
    assert not [b for b in mv.findChildren(QPushButton)
                if b.objectName() == "writingActionsBtn"]


def test_navigator_canonical_order_and_numbering():
    db = Database()
    pid = _novel(db)
    ss.create_scene(db, pid, act="Act I", chapter="Ch1", title="Opening", content="x")
    ss.create_scene(db, pid, act="Act I", chapter="Ch1", title="Next", content="y")
    nav = ManuscriptNavigator(db, pid)
    labels = _labels(nav._tree)
    assert "Act 1: Act I" in labels
    assert "Chapter 1.1: Ch1" in labels
    assert "1.1.1: Opening" in labels and "1.1.2: Next" in labels


def test_navigator_highlights_current_unit():
    db = Database()
    pid = _novel(db)
    a = ss.create_scene(db, pid, act="Act I", chapter="Ch1", title="A", content="x").id
    b = ss.create_scene(db, pid, act="Act I", chapter="Ch1", title="B", content="y").id
    nav = ManuscriptNavigator(db, pid)
    nav.set_current(b)
    cur = nav._tree.currentItem()
    assert cur is not None and cur.data(0, _ROLE_SCENE_ID) == b


# ==========================================================================
# 5-6  Clicking navigates / opens in Manuscript
# ==========================================================================


def test_clicking_scene_opens_it_in_manuscript():
    db = Database()
    pid = _novel(db)
    a = ss.create_scene(db, pid, act="Act I", chapter="Ch1", title="A", content="x").id
    b = ss.create_scene(db, pid, act="Act I", chapter="Ch1", title="B", content="y").id
    mv = _manuscript(db, pid)
    item = _scene_item(mv._navigator._tree, b)
    assert item is not None
    mv._navigator._on_item_chosen(item)
    assert mv._selected_scene_id == b              # opened in Manuscript


def test_clicking_chapter_opens_first_scene():
    db = Database()
    pid = _novel(db)
    first = ss.create_scene(db, pid, act="Act I", chapter="Ch1", title="A",
                            content="x").id
    ss.create_scene(db, pid, act="Act I", chapter="Ch1", title="B", content="y")
    opened: list[int] = []
    nav = ManuscriptNavigator(db, pid, on_select=opened.append)
    chapter_item = next(it for it in _all_items(nav._tree)
                        if it.data(0, _ROLE_KIND) == "chapter")
    nav._on_item_chosen(chapter_item)
    assert opened == [first]                        # chapter → its first scene


# ==========================================================================
# 7-9  Refresh on change / switch; no orphans before Acts
# ==========================================================================


def test_navigator_refreshes_after_structure_change():
    db = Database()
    pid = _novel(db)
    ss.create_scene(db, pid, act="Act I", chapter="Ch1", title="A", content="x")
    mv = _manuscript(db, pid)
    assert "Act 2: Act II" not in _labels(mv._navigator._tree)
    ss.create_scene(db, pid, act="Act II", chapter="Ch2", title="B", content="y")
    mv.refresh()
    assert "Act 2: Act II" in _labels(mv._navigator._tree)


def test_navigator_refreshes_after_project_switch(tmp_path):
    db = Database(str(tmp_path / "sp.db"))
    a = _novel(db)
    ss.create_scene(db, a, act="Act A", chapter="Ch", title="S", content="x")
    b = _novel(db)
    win = MainWindow(db, a)
    win.sidebar_buttons["Manuscript"].click()
    assert "Act 1: Act A" in _labels(win.content_area._navigator._tree)
    win._switch_project(b)
    win.sidebar_buttons["Manuscript"].click()
    # B is empty → navigator shows no Act A.
    assert "Act 1: Act A" not in _labels(win.content_area._navigator._tree)


def test_navigator_never_shows_orphan_before_acts():
    db = Database()
    pid = _novel(db)
    db.create_scene(pid, "Loose", content="x")     # orphan (no act/chapter)
    ss.create_scene(db, pid, act="Act I", chapter="Ch1", title="Real", content="y")
    mv = _manuscript(db, pid)                       # repairs on render
    tree = mv._navigator._tree
    # Every top-level node is an Act (never a floating Scene).
    tops = [tree.topLevelItem(i) for i in range(tree.topLevelItemCount())]
    assert tops and all(it.data(0, _ROLE_KIND) == "act" for it in tops)


def test_navigator_does_not_write_body():
    db = Database()
    pid = _novel(db)
    sid = ss.create_scene(db, pid, act="Act I", chapter="Ch1", title="S",
                          summary="OUTLINE_NOTE", content="REAL PROSE").id
    mv = _manuscript(db, pid)
    mv._navigator._on_item_chosen(_scene_item(mv._navigator._tree, sid))
    bodies = " ".join(e.toPlainText() for e in mv.findChildren(_SceneEditor))
    assert "REAL PROSE" in bodies and "OUTLINE_NOTE" not in bodies
    assert db.get_scene_by_id(sid).content == "REAL PROSE"
