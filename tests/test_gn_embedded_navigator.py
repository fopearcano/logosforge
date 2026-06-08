"""Graphic Novel Manuscript — embedded Page/Panel Navigator (Alpha-safe).

The standalone left-panel Pages route was fullscreen-hostile, so it is disabled
for Alpha. Graphic Novel Page/Panel navigation now lives **inside the Manuscript**
as an embedded Scene -> Page -> Panel navigator + selected-item editor
(`GraphicNovelManuscriptView`) over the shared `Scene.content` body. These tests
cover sidebar safety, navigator visibility (GN only), structure, the empty-state
ladder, editing/persistence, shared-body/export, and structural fullscreen safety.
"""

from __future__ import annotations

import warnings

import pytest
from PySide6.QtWidgets import QApplication, QLineEdit

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


def _nav(db, pid):
    from storyplanner.ui.graphic_novel_manuscript_view import (
        GraphicNovelManuscriptView)
    return GraphicNovelManuscriptView(db, pid, on_data_changed=lambda: None)


def _body(db, sid):
    return gnb.load_scene_script(db, sid)


def _find(view, predicate):
    t = view._tree
    stack = [t.topLevelItem(i) for i in range(t.topLevelItemCount())]
    while stack:
        it = stack.pop()
        if predicate(it):
            return it
        for i in range(it.childCount()):
            stack.append(it.child(i))
    return None


def _detail_widget(view, object_name):
    return view._detail_host.findChild(QLineEdit, object_name) or \
        view._detail_host.findChild(object, object_name)


# ==========================================================================
# 1-4  Sidebar: standalone Pages disabled + inert route
# ==========================================================================


def test_pages_sidebar_item_hidden_for_alpha():
    from storyplanner.ui.main_window import MainWindow
    db = Database()
    win = MainWindow(db, _gn(db))
    assert "Pages" not in win._nav_labels
    assert "Pages" not in win.sidebar_buttons


def test_pages_route_does_not_mount_old_standalone_widget():
    from storyplanner.ui.main_window import MainWindow
    from storyplanner.ui.graphic_novel_scene_pages_view import (
        GraphicNovelScenePagesView)
    db = Database()
    win = MainWindow(db, _gn(db))
    win._show_gn_pages()
    assert not isinstance(win.content_area, GraphicNovelScenePagesView)


def test_pages_route_lands_on_embedded_navigator():
    from storyplanner.ui.main_window import MainWindow
    from storyplanner.ui.graphic_novel_manuscript_view import (
        GraphicNovelManuscriptView)
    db = Database()
    win = MainWindow(db, _gn(db))
    win._show_gn_pages()
    assert isinstance(win.content_area, GraphicNovelManuscriptView)


def test_pages_route_does_not_minimize_main_window():
    from storyplanner.ui.main_window import MainWindow
    db = Database()
    win = MainWindow(db, _gn(db))
    calls = {"min": 0, "hide": 0, "close": 0}
    win.showMinimized = lambda: calls.__setitem__("min", calls["min"] + 1)  # type: ignore
    win.hide = lambda: calls.__setitem__("hide", calls["hide"] + 1)         # type: ignore
    win.close = lambda: calls.__setitem__("close", calls["close"] + 1)      # type: ignore
    win._show_gn_pages()
    assert calls == {"min": 0, "hide": 0, "close": 0}


# ==========================================================================
# 5-9  Navigator visibility — GN Manuscript only
# ==========================================================================


def test_gn_manuscript_mounts_embedded_navigator():
    from storyplanner.ui.main_window import MainWindow
    from storyplanner.ui.graphic_novel_manuscript_view import (
        GraphicNovelManuscriptView)
    db = Database()
    win = MainWindow(db, _gn(db))
    win._show_manuscript()
    assert isinstance(win.content_area, GraphicNovelManuscriptView)


@pytest.mark.parametrize("engine", ["novel", "screenplay", "stage_script",
                                    "series"])
def test_navigator_not_used_in_non_gn_modes(engine):
    from storyplanner.ui.main_window import MainWindow
    from storyplanner.ui.writing_core_view import WritingCoreView
    db = Database()
    pid = db.create_project(engine, narrative_engine=engine,
                            default_writing_format=engine).id
    win = MainWindow(db, pid)
    win._show_manuscript()
    assert isinstance(win.content_area, WritingCoreView)


# ==========================================================================
# 10-14  Navigator structure
# ==========================================================================


def test_navigator_shows_scene_page_panel_tree():
    db = Database()
    pid = _gn(db)
    sid = _scene(db, pid, "Cold Open")
    v = _nav(db, pid)
    v.select_scene(sid)
    v._add_page(); v._add_panel()
    scene_item = _find(v, lambda it: "Cold Open" in it.text(0))
    assert scene_item is not None
    page_item = scene_item.child(0)
    assert page_item.text(0).startswith("Page 1")
    assert page_item.child(0).text(0).startswith("Panel 1")


def test_navigator_panel_snippet_updates_after_edit():
    db = Database()
    pid = _gn(db)
    sid = _scene(db, pid)
    v = _nav(db, pid)
    v.select_scene(sid)
    v._add_page(); v._add_panel()
    v._commit_panel_field(0, 0, "visual_description", "Rooftop chase")
    panel_item = _find(v, lambda it: it.text(0).startswith("Panel 1"))
    assert "Rooftop chase" in panel_item.text(0)


def test_navigator_page_groups_collapse_expandable():
    db = Database()
    pid = _gn(db)
    sid = _scene(db, pid)
    v = _nav(db, pid)
    v.select_scene(sid)
    v._add_page(); v._add_panel()
    page_item = _find(v, lambda it: it.text(0).startswith("Page 1"))
    assert page_item.childCount() == 1            # panel under the page
    page_item.setExpanded(False)
    assert page_item.isExpanded() is False


# ==========================================================================
# 15-26  Empty-state ladder + editing
# ==========================================================================


def test_no_scene_shows_create_scene_action():
    from PySide6.QtWidgets import QPushButton
    db = Database()
    pid = _gn(db)                                  # no scenes
    v = _nav(db, pid)
    btn = v._detail_host.findChild(QPushButton, "gnDetailCreateScene")
    assert btn is not None


def test_scene_without_page_shows_add_page():
    from PySide6.QtWidgets import QPushButton
    db = Database()
    pid = _gn(db)
    sid = _scene(db, pid)
    v = _nav(db, pid)
    v.select_scene(sid)
    assert v._detail_host.findChild(QPushButton, "gnDetailAddPage") is not None


def test_page_without_panel_shows_add_panel():
    from PySide6.QtWidgets import QPushButton
    db = Database()
    pid = _gn(db)
    sid = _scene(db, pid)
    v = _nav(db, pid)
    v.select_scene(sid)
    v._add_page()                                  # selects the new page
    assert v._detail_host.findChild(QPushButton, "gnDetailAddPanel") is not None


def test_add_page_creates_shared_page():
    db = Database()
    pid = _gn(db)
    sid = _scene(db, pid)
    v = _nav(db, pid)
    v.select_scene(sid)
    v._add_page()
    assert len(_body(db, sid).pages) == 1


def test_add_panel_creates_shared_panel():
    db = Database()
    pid = _gn(db)
    sid = _scene(db, pid)
    v = _nav(db, pid)
    v.select_scene(sid)
    v._add_page(); v._add_panel()
    assert len(_body(db, sid).pages[0].panels) == 1


@pytest.mark.parametrize("field,value", [
    ("visual_description", "A rain-soaked alley"),
    ("caption", "Later that night"),
    ("dialogue", "We have to move."),
    ("sfx", "KRAKOOM"),
    ("notes", "low angle"),
])
def test_panel_field_edit_persists(field, value):
    db = Database()
    pid = _gn(db)
    sid = _scene(db, pid)
    v = _nav(db, pid)
    v.select_scene(sid)
    v._add_page(); v._add_panel()
    v._commit_panel_field(0, 0, field, value)
    assert getattr(_body(db, sid).pages[0].panels[0], field) == value


def test_delete_panel_with_confirmation(monkeypatch):
    monkeypatch.setattr(safe_dialogs, "question", lambda *a, **k: True)
    db = Database()
    pid = _gn(db)
    sid = _scene(db, pid)
    v = _nav(db, pid)
    v.select_scene(sid)
    v._add_page(); v._add_panel(); v._add_panel()
    n = len(_body(db, sid).pages[0].panels)
    v._sel = {"kind": "panel", "scene_id": sid, "page": 0, "panel": 0}
    v._delete_selected()
    assert len(_body(db, sid).pages[0].panels) == n - 1


def test_cancel_delete_panel_keeps_body(monkeypatch):
    monkeypatch.setattr(safe_dialogs, "question", lambda *a, **k: False)
    db = Database()
    pid = _gn(db)
    sid = _scene(db, pid)
    v = _nav(db, pid)
    v.select_scene(sid)
    v._add_page(); v._add_panel()
    v._sel = {"kind": "panel", "scene_id": sid, "page": 0, "panel": 0}
    v._delete_selected()
    assert len(_body(db, sid).pages[0].panels) == 1


def test_move_panel_reorders(monkeypatch):
    db = Database()
    pid = _gn(db)
    sid = _scene(db, pid)
    v = _nav(db, pid)
    v.select_scene(sid)
    v._add_page()
    v._add_panel(); v._commit_panel_field(0, 0, "visual_description", "first")
    v._add_panel(); v._commit_panel_field(0, 1, "visual_description", "second")
    v._sel = {"kind": "panel", "scene_id": sid, "page": 0, "panel": 1}
    v._move_up()
    panels = _body(db, sid).pages[0].panels
    assert panels[0].visual_description == "second"


# ==========================================================================
# 27-32  Shared body / export
# ==========================================================================


def test_navigator_uses_shared_scene_content_body():
    db = Database()
    pid = _gn(db)
    sid = _scene(db, pid)
    v = _nav(db, pid)
    v.select_scene(sid)
    v._add_page(); v._add_panel()
    v._commit_panel_field(0, 0, "visual_description", "SHARED")
    # The Manuscript/export path (Scene.content) sees the same body.
    assert "SHARED" in (db.get_scene_by_id(sid).content or "")


def test_project_switch_isolates_pages(tmp_path):
    db = Database(str(tmp_path / "iso.db"))
    a = _gn(db, "A")
    sa = _scene(db, a, "A-scene")
    va = _nav(db, a)
    va.select_scene(sa)
    va._add_page()
    b = _gn(db, "B")                                # empty project
    vb = _nav(db, b)
    assert vb._tree.topLevelItemCount() == 0


def test_save_reload_preserves_pages_panels():
    db = Database()
    pid = _gn(db)
    sid = _scene(db, pid)
    v = _nav(db, pid)
    v.select_scene(sid)
    v._add_page(); v._add_panel()
    v._commit_panel_field(0, 0, "visual_description", "KEEP")
    reloaded = gnb.load_scene_script(db, sid)      # fresh read
    assert reloaded.pages[0].panels[0].visual_description == "KEEP"


def test_export_uses_shared_body_no_image_or_comfyui():
    db = Database()
    pid = _gn(db)
    sid = _scene(db, pid)
    v = _nav(db, pid)
    v.select_scene(sid)
    v._add_page(); v._add_panel()
    v._commit_panel_field(0, 0, "visual_description", "EXPORTABLE")
    md = gnb.export_project_markdown(db, pid)
    assert "EXPORTABLE" in md
    low = md.lower()
    for banned in ("comfyui", "image prompt", "lora", "img2img", "txt2img"):
        assert banned not in low


def test_panel_model_has_no_image_generation_fields():
    fields = set(vars(gnb.Panel()).keys())
    for banned in ("image", "prompt", "comfyui", "lora", "seed", "sampler"):
        assert not any(banned in f for f in fields), banned


# ==========================================================================
# 33-35  Structural fullscreen safety
# ==========================================================================


def test_navigator_creates_no_new_top_level_window():
    from storyplanner.ui.main_window import MainWindow
    db = Database()
    win = MainWindow(db, _gn(db))
    before = set(QApplication.topLevelWidgets())
    win._show_manuscript()
    new_visible = [w for w in (set(QApplication.topLevelWidgets()) - before)
                   if w.isVisible()]
    assert new_visible == []


def test_navigator_content_is_embedded_child():
    from storyplanner.ui.main_window import MainWindow
    db = Database()
    win = MainWindow(db, _gn(db))
    win._show_manuscript()
    assert win.content_area.window() is win


def test_manuscript_activation_does_not_minimize():
    from storyplanner.ui.main_window import MainWindow
    db = Database()
    win = MainWindow(db, _gn(db))
    calls = {"min": 0, "hide": 0}
    win.showMinimized = lambda: calls.__setitem__("min", calls["min"] + 1)  # type: ignore
    win.hide = lambda: calls.__setitem__("hide", calls["hide"] + 1)         # type: ignore
    win._show_manuscript()
    assert calls == {"min": 0, "hide": 0}
