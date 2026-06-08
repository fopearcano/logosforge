"""Graphic Novel Manuscript = Page/Panel editor (Alpha-safe access path).

The standalone left-panel Pages section is deferred for Alpha (macOS fullscreen
window-management bug), so the **Manuscript** is the Graphic Novel Page/Panel
editor: in GN mode `_show_manuscript` mounts `GraphicNovelScenePagesView`
(`embedded_as_manuscript=True`) over the shared `Scene.content` body. These tests
verify the editor is reachable, its empty states guide the user (Create Scene →
Add Page → Add Panel), the panel fields persist, and non-GN modes are unchanged.
"""

from __future__ import annotations

import warnings

import pytest
from PySide6.QtWidgets import QApplication, QPushButton

warnings.filterwarnings("ignore")

from storyplanner.db import Database
from storyplanner import graphic_novel_blocks as gnb
from storyplanner import story_structure as ss
from storyplanner.ui import safe_dialogs


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


def _gn(db, title="GN"):
    return db.create_project(title, narrative_engine="graphic_novel",
                             default_writing_format="graphic_novel").id


def _scene(db, pid, title="P1"):
    return ss.create_scene(db, pid, act="Act 1", chapter="Chapter 1",
                           title=title).id


def _editor(db, pid, scene_id=None):
    from storyplanner.ui.graphic_novel_scene_pages_view import (
        GraphicNovelScenePagesView)
    return GraphicNovelScenePagesView(db, pid, scene_id=scene_id,
                                      embedded_as_manuscript=True)


def _btn(view, object_name):
    b = view.findChild(QPushButton, object_name)
    return b


def _body(db, sid):
    return gnb.load_scene_script(db, sid)


# ==========================================================================
# 1, 6, 7  Manuscript mounts the Page/Panel editor (not generic prose)
# ==========================================================================


def test_gn_manuscript_mounts_page_panel_editor():
    from storyplanner.ui.main_window import MainWindow
    from storyplanner.ui.graphic_novel_scene_pages_view import (
        GraphicNovelScenePagesView)
    db = Database()
    pid = _gn(db)
    _scene(db, pid)
    win = MainWindow(db, pid)
    win._show_manuscript()
    assert isinstance(win.content_area, GraphicNovelScenePagesView)


def test_gn_manuscript_is_not_generic_prose_editor():
    from storyplanner.ui.main_window import MainWindow
    from storyplanner.ui.writing_core_view import WritingCoreView
    db = Database()
    pid = _gn(db)
    _scene(db, pid)
    win = MainWindow(db, pid)
    win._show_manuscript()
    assert not isinstance(win.content_area, WritingCoreView)


def test_page_panel_actions_are_present_not_only_scene():
    # "+ Scene" must not be the only primary action — "+ Page"/"+ Panel" are the
    # primary Page/Panel-editing actions.
    db = Database()
    pid = _gn(db)
    v = _editor(db, pid, _scene(db, pid))
    assert _btn(v, "gnPagesAddScene") is not None     # scene management
    assert _btn(v, "gnPages_Page") is not None        # + Page
    assert _btn(v, "gnPages_Panel") is not None       # + Panel


# ==========================================================================
# 2-5  Empty-state ladder: Create Scene -> Add Page -> Add Panel -> fields
# ==========================================================================


def test_no_scene_shows_create_scene_action():
    db = Database()
    pid = _gn(db)                                      # no scenes
    v = _editor(db, pid)
    assert v._scene_id is None
    assert _btn(v, "gnPagesAddScene") is not None
    # Empty state guides to creating a scene (not a blank prose state).
    texts = [lbl.text() for lbl in v.findChildren(type(v._heading))]
    assert any("Graphic Novel" in t for t in texts)


def test_create_scene_then_editor_shows_add_page():
    db = Database()
    pid = _gn(db)
    v = _editor(db, pid)
    v._create_scene()                                 # create in place
    assert v._scene_id is not None
    assert len(db.get_all_scenes(pid)) == 1
    assert _btn(v, "gnPages_Page") is not None        # Add Page now actionable


def test_scene_without_page_then_add_panel_seeds_page():
    db = Database()
    pid = _gn(db)
    v = _editor(db, pid, _scene(db, pid))
    assert v._script.pages == []
    v._add_panel()                                    # seeds a page + a panel
    assert len(v._script.pages) == 1
    assert len(v._script.pages[0].panels) == 1


def test_panels_expose_editable_fields():
    db = Database()
    pid = _gn(db)
    sid = _scene(db, pid)
    v = _editor(db, pid, sid)
    v._add_page(); v._add_panel()
    # The panel card exposes editable Visual / Caption / Dialogue / SFX / Notes.
    assert v._panel_cards
    assert set(v._panel_cards[0]._editors) == {
        "visual_description", "caption", "dialogue", "sfx", "notes"}


# ==========================================================================
# 8-14  Add Page/Panel + field persistence (shared Scene.content body)
# ==========================================================================


def test_add_page_creates_shared_page():
    db = Database()
    pid = _gn(db)
    sid = _scene(db, pid)
    v = _editor(db, pid, sid)
    v._add_page()
    assert len(_body(db, sid).pages) == 1


def test_add_panel_creates_shared_panel():
    db = Database()
    pid = _gn(db)
    sid = _scene(db, pid)
    v = _editor(db, pid, sid)
    v._add_page(); v._add_panel()
    assert len(_body(db, sid).pages[0].panels) == 1


@pytest.mark.parametrize("field,value", [
    ("visual_description", "A rain-soaked alley"),
    ("caption", "Later that night"),
    ("dialogue", "We have to move."),
    ("sfx", "KRAKOOM"),
    ("notes", "low angle, dutch tilt"),
])
def test_panel_field_edit_persists_to_shared_body(field, value):
    db = Database()
    pid = _gn(db)
    sid = _scene(db, pid)
    v = _editor(db, pid, sid)
    v._add_page(); v._add_panel()
    v._set_panel_field(0, 0, field, value)
    panel = _body(db, sid).pages[0].panels[0]
    assert getattr(panel, field) == value


# ==========================================================================
# 15-16  Collapse/expand + delete with confirmation
# ==========================================================================


def test_panel_card_collapse_expand():
    db = Database()
    pid = _gn(db)
    sid = _scene(db, pid)
    v = _editor(db, pid, sid)
    v._add_page(); v._add_panel()
    card = v._panel_cards[0]
    assert card.is_collapsed() is False
    card.set_collapsed(True)
    assert card.is_collapsed() is True


def test_delete_panel_confirms_then_mutates(monkeypatch):
    seen = {}
    monkeypatch.setattr(safe_dialogs, "question",
                        lambda *a, **k: seen.setdefault("asked", True) or True)
    db = Database()
    pid = _gn(db)
    sid = _scene(db, pid)
    v = _editor(db, pid, sid)
    v._add_page(); v._add_panel(); v._add_panel()
    n = len(_body(db, sid).pages[0].panels)
    v._delete_panel(0, 0, confirm=True)
    assert seen.get("asked") is True                  # window-modal confirm used
    assert len(_body(db, sid).pages[0].panels) == n - 1


def test_cancel_delete_panel_keeps_body(monkeypatch):
    monkeypatch.setattr(safe_dialogs, "question", lambda *a, **k: False)
    db = Database()
    pid = _gn(db)
    sid = _scene(db, pid)
    v = _editor(db, pid, sid)
    v._add_page(); v._add_panel()
    n = len(_body(db, sid).pages[0].panels)
    v._delete_panel(0, 0, confirm=True)
    assert len(_body(db, sid).pages[0].panels) == n


# ==========================================================================
# Regression: non-GN Manuscript unchanged
# ==========================================================================


@pytest.mark.parametrize("engine", ["novel", "screenplay", "stage_script",
                                    "series"])
def test_non_gn_manuscript_is_writing_core_view(engine):
    from storyplanner.ui.main_window import MainWindow
    from storyplanner.ui.writing_core_view import WritingCoreView
    db = Database()
    pid = db.create_project(engine, narrative_engine=engine,
                            default_writing_format=engine).id
    win = MainWindow(db, pid)
    win._show_manuscript()
    assert isinstance(win.content_area, WritingCoreView)
