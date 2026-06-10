"""Graphic Novel Manuscript — comics SCRIPT editor (not an outliner).

The GN Manuscript renders the selected scene's whole script inline — PAGE
blocks containing Panel cards whose five fields (Visual / Caption / Dialogue /
SFX / Notes) are always visible and editable in place. Structure management /
navigation stays in the GN Outline; both surfaces read/write the same shared
``Scene.content`` body and therefore mirror automatically. These tests cover
mount routing, the script-editor shape (no tree), the empty-state ladder,
inline editing/persistence, scene navigation, Outline⇄Manuscript mirroring,
structural fullscreen safety, and the export/no-image-generation guards.
"""

from __future__ import annotations

import warnings

import pytest
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QTreeWidget,
)

warnings.filterwarnings("ignore")

from storyplanner.db import Database
from storyplanner import graphic_novel_blocks as gnb
from storyplanner import graphic_novel_outline as gno
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


def _view(db, pid):
    from storyplanner.ui.graphic_novel_manuscript_view import (
        GraphicNovelManuscriptView)
    return GraphicNovelManuscriptView(db, pid, on_data_changed=lambda: None)


def _body(db, sid):
    return gnb.load_scene_script(db, sid)


def _scripted_view(db, *, pages=1, panels=1):
    """A GN project + scene with pages×panels and a view on it."""
    pid = _gn(db)
    sid = _scene(db, pid)
    script = gnb.GraphicNovelScript()
    for p in range(pages):
        page = gnb.add_page(script, title=f"T{p + 1}")
        for _ in range(panels):
            gnb.add_panel(page)
    gnb._renumber(script)
    gnb.save_scene_script(db, sid, script)
    v = _view(db, pid)
    v.select_scene(sid)
    return pid, sid, v


def _labels(view):
    return [w.text() for w in view._host.findChildren(QLabel)]


# ==========================================================================
# 1-9  Mount routing + standalone Pages stays disabled
# ==========================================================================


def test_gn_manuscript_mounts_script_editor():
    from storyplanner.ui.main_window import MainWindow
    from storyplanner.ui.graphic_novel_manuscript_view import (
        GraphicNovelManuscriptView)
    db = Database()
    win = MainWindow(db, _gn(db))
    win._show_manuscript()
    assert isinstance(win.content_area, GraphicNovelManuscriptView)


@pytest.mark.parametrize("engine", ["novel", "screenplay", "stage_script",
                                    "series"])
def test_non_gn_modes_keep_writing_core(engine):
    from storyplanner.ui.main_window import MainWindow
    from storyplanner.ui.writing_core_view import WritingCoreView
    db = Database()
    pid = db.create_project(engine, narrative_engine=engine,
                            default_writing_format=engine).id
    win = MainWindow(db, pid)
    win._show_manuscript()
    assert isinstance(win.content_area, WritingCoreView)


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


def test_pages_route_lands_on_script_editor():
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
# 10-17  Script-editor shape — NOT an outliner
# ==========================================================================


def test_manuscript_contains_no_tree_widget():
    db = Database()
    _pid, _sid, v = _scripted_view(db, pages=2, panels=2)
    assert v.findChildren(QTreeWidget) == []


def test_scene_selector_is_flat_combo_not_tree():
    db = Database()
    _pid, _sid, v = _scripted_view(db)
    combo = v.findChild(QComboBox, "gnScriptSceneSelect")
    assert combo is not None and combo.count() == 1


def test_page_headers_rendered_inline_in_order():
    db = Database()
    _pid, _sid, v = _scripted_view(db, pages=3)
    heads = [w.text() for w in v._host.findChildren(QLabel)
             if w.objectName() == "gnPageHeader"]
    assert heads == ["PAGE 1", "PAGE 2", "PAGE 3"]


def test_panel_headers_rendered_inline_in_order():
    db = Database()
    _pid, _sid, v = _scripted_view(db, pages=1, panels=3)
    heads = [w.text() for w in v._host.findChildren(QLabel)
             if w.objectName() == "gnPanelHeader"]
    assert heads == ["Panel 1", "Panel 2", "Panel 3"]


def test_all_panel_fields_visible_simultaneously():
    # 2 pages × 2 panels -> every field of every panel inline at once.
    db = Database()
    _pid, _sid, v = _scripted_view(db, pages=2, panels=2)
    for key, _label, multiline, _h in (
            ("visual_description", "Visual", True, 0),
            ("caption", "Caption", False, 0),
            ("dialogue", "Dialogue", True, 0),
            ("sfx", "SFX", False, 0),
            ("notes", "Notes", True, 0)):
        cls = QPlainTextEdit if multiline else QLineEdit
        editors = [w for w in v._host.findChildren(cls)
                   if w.objectName() == f"gnPanelField_{key}"]
        assert len(editors) == 4, key


def test_panel_fields_are_labeled():
    db = Database()
    _pid, _sid, v = _scripted_view(db)
    texts = _labels(v)
    for label in ("Visual", "Caption", "Dialogue", "SFX", "Notes"):
        assert label in texts


def test_field_editors_are_editable_in_place():
    db = Database()
    _pid, _sid, v = _scripted_view(db)
    for loc, ed in v._field_editors.items():
        if loc[0] != "panel":
            continue
        assert isinstance(ed, (QLineEdit, QPlainTextEdit))
        assert not (ed.isReadOnly() if hasattr(ed, "isReadOnly") else False)


def test_script_flows_inside_scroll_host():
    db = Database()
    _pid, _sid, v = _scripted_view(db, pages=2)
    blocks = [w for w in v._host.findChildren(QPushButton)
              if w.objectName() == "gnDetailAddPanel"]
    assert len(blocks) == 2                      # one "+ Panel" per page block
    assert v._scroll.widget() is v._host


# ==========================================================================
# 18-23  Empty-state ladder A → B → C → D
# ==========================================================================


def test_state_a_no_scene_offers_create_scene():
    db = Database()
    v = _view(db, _gn(db))                       # project without scenes
    assert v._host.findChild(QPushButton, "gnDetailCreateScene") is not None
    assert v._scene_combo.count() == 0


def test_state_a_create_scene_advances_to_add_page():
    db = Database()
    pid = _gn(db)
    v = _view(db, pid)
    v._add_scene()
    assert len(ss.list_scenes(db, pid)) == 1
    assert v._host.findChild(QPushButton, "gnDetailAddPage") is not None


def test_state_b_scene_without_pages_offers_add_page():
    db = Database()
    pid = _gn(db)
    sid = _scene(db, pid)
    v = _view(db, pid)
    v.select_scene(sid)
    assert v._host.findChild(QPushButton, "gnDetailAddPage") is not None


def test_state_b_add_page_advances_to_page_block():
    db = Database()
    pid = _gn(db)
    sid = _scene(db, pid)
    v = _view(db, pid)
    v.select_scene(sid)
    v._add_page()
    heads = [w for w in v._host.findChildren(QLabel)
             if w.objectName() == "gnPageHeader"]
    assert [w.text() for w in heads] == ["PAGE 1"]


def test_state_c_page_without_panels_offers_add_panel():
    db = Database()
    pid = _gn(db)
    sid = _scene(db, pid)
    v = _view(db, pid)
    v.select_scene(sid)
    v._add_page()
    assert any(w.objectName() == "gnPageNoPanels"
               for w in v._host.findChildren(QLabel))
    assert v._host.findChild(QPushButton, "gnDetailAddPanel") is not None


def test_state_d_panels_render_full_script_blocks():
    db = Database()
    pid = _gn(db)
    sid = _scene(db, pid)
    v = _view(db, pid)
    v.select_scene(sid)
    v._add_page(); v._add_panel()
    assert not any(w.objectName() == "gnPageNoPanels"
                   for w in v._host.findChildren(QLabel))
    assert ("panel", 0, 0, "visual_description") in v._field_editors


# ==========================================================================
# 24-40  Inline editing + persistence (shared Scene.content body)
# ==========================================================================


@pytest.mark.parametrize("field,value", [
    ("visual_description", "A rain-soaked alley"),
    ("caption", "Later that night"),
    ("dialogue", "We have to move."),
    ("sfx", "KRAKOOM"),
    ("notes", "low angle"),
])
def test_panel_field_commit_persists(field, value):
    db = Database()
    _pid, sid, v = _scripted_view(db)
    v._commit_panel_field(0, 0, field, value)
    assert getattr(_body(db, sid).pages[0].panels[0], field) == value


def test_line_edit_widget_commit_wiring():
    db = Database()
    _pid, sid, v = _scripted_view(db)
    ed = v._field_editors[("panel", 0, 0, "caption")]
    ed.setText("From the widget")
    ed.editingFinished.emit()
    assert _body(db, sid).pages[0].panels[0].caption == "From the widget"


def test_plain_text_widget_commit_wiring():
    db = Database()
    _pid, sid, v = _scripted_view(db)
    ed = v._field_editors[("panel", 0, 0, "dialogue")]
    ed.setPlainText("Spoken line")
    ed.committed.emit()
    assert _body(db, sid).pages[0].panels[0].dialogue == "Spoken line"


def test_page_title_edit_persists():
    db = Database()
    _pid, sid, v = _scripted_view(db)
    ed = v._field_editors[("page", 0, "title")]
    ed.setText("Rooftops")
    ed.editingFinished.emit()
    assert _body(db, sid).pages[0].title == "Rooftops"


def test_page_notes_edit_persists():
    db = Database()
    _pid, sid, v = _scripted_view(db)
    ed = v._field_editors[("page", 0, "summary")]
    ed.setPlainText("Splash page")
    ed.committed.emit()
    assert _body(db, sid).pages[0].summary == "Splash page"


def test_add_page_appends_to_shared_body():
    db = Database()
    _pid, sid, v = _scripted_view(db)
    v._add_page()
    assert [p.number for p in _body(db, sid).pages] == [1, 2]


def test_add_panel_targets_its_page():
    db = Database()
    _pid, sid, v = _scripted_view(db, pages=2, panels=1)
    v._add_panel(0)                              # the first page's "+ Panel"
    body = _body(db, sid)
    assert len(body.pages[0].panels) == 2
    assert len(body.pages[1].panels) == 1


def test_add_panel_button_click_adds_to_first_page():
    db = Database()
    _pid, sid, v = _scripted_view(db, pages=2, panels=1)
    btn = [w for w in v._host.findChildren(QPushButton)
           if w.objectName() == "gnDetailAddPanel"][0]
    btn.click()
    assert len(_body(db, sid).pages[0].panels) == 2


def test_delete_panel_confirmed_removes_and_renumbers(monkeypatch):
    monkeypatch.setattr(safe_dialogs, "question", lambda *a, **k: True)
    db = Database()
    _pid, sid, v = _scripted_view(db, pages=1, panels=3)
    v._delete_panel(0, 0)
    panels = _body(db, sid).pages[0].panels
    assert [p.number for p in panels] == [1, 2]


def test_delete_panel_cancelled_keeps_body(monkeypatch):
    monkeypatch.setattr(safe_dialogs, "question", lambda *a, **k: False)
    db = Database()
    _pid, sid, v = _scripted_view(db, pages=1, panels=2)
    v._delete_panel(0, 0)
    assert len(_body(db, sid).pages[0].panels) == 2


def test_delete_page_confirmed_removes_and_renumbers(monkeypatch):
    monkeypatch.setattr(safe_dialogs, "question", lambda *a, **k: True)
    db = Database()
    _pid, sid, v = _scripted_view(db, pages=2, panels=1)
    v._delete_page(0)
    body = _body(db, sid)
    assert len(body.pages) == 1 and body.pages[0].number == 1


def test_delete_page_cancelled_keeps_body(monkeypatch):
    monkeypatch.setattr(safe_dialogs, "question", lambda *a, **k: False)
    db = Database()
    _pid, sid, v = _scripted_view(db, pages=2, panels=1)
    v._delete_page(0)
    assert len(_body(db, sid).pages) == 2


def test_move_panel_reorders_within_page():
    db = Database()
    _pid, sid, v = _scripted_view(db, pages=1, panels=2)
    v._commit_panel_field(0, 0, "visual_description", "first")
    v._commit_panel_field(0, 1, "visual_description", "second")
    v._move_panel(0, 1, -1)
    panels = _body(db, sid).pages[0].panels
    assert panels[0].visual_description == "second"
    assert [p.number for p in panels] == [1, 2]


def test_commit_unchanged_value_is_noop():
    db = Database()
    _pid, sid, v = _scripted_view(db)
    v._commit_panel_field(0, 0, "caption", "same")
    before = db.get_scene_by_id(sid).content
    v._commit_panel_field(0, 0, "caption", "same")   # identical -> no rewrite
    assert db.get_scene_by_id(sid).content == before


def test_save_reload_round_trip():
    db = Database()
    _pid, sid, v = _scripted_view(db)
    v._commit_panel_field(0, 0, "visual_description", "KEEP")
    assert _body(db, sid).pages[0].panels[0].visual_description == "KEEP"


# ==========================================================================
# 41-47  Scene selection / navigation
# ==========================================================================


def test_select_scene_loads_that_scenes_script():
    db = Database()
    pid = _gn(db)
    s1 = _scene(db, pid, "One")
    s2 = _scene(db, pid, "Two")
    gno.add_page(db, s2); gno.add_panel(db, s2, 0)
    gno.set_panel_field(db, s2, 0, 0, "visual_description", "SECOND-SCENE")
    v = _view(db, pid)
    v.select_scene(s2)
    ed = v._field_editors[("panel", 0, 0, "visual_description")]
    assert ed.toPlainText() == "SECOND-SCENE"
    v.select_scene(s1)
    assert v._host.findChild(QPushButton, "gnDetailAddPage") is not None


def test_scene_combo_lists_scenes_in_canonical_order():
    db = Database()
    pid = _gn(db)
    s1 = _scene(db, pid, "One")
    s2 = _scene(db, pid, "Two")
    v = _view(db, pid)
    ids = [v._scene_combo.itemData(i) for i in range(v._scene_combo.count())]
    assert ids == [s1, s2]


def test_scene_combo_switch_changes_script():
    db = Database()
    pid = _gn(db)
    _s1 = _scene(db, pid, "One")
    s2 = _scene(db, pid, "Two")
    gno.add_page(db, s2)
    v = _view(db, pid)                            # lands on scene One
    v._scene_combo.setCurrentIndex(1)             # user picks scene Two
    assert v._scene_id == s2
    heads = [w for w in v._host.findChildren(QLabel)
             if w.objectName() == "gnPageHeader"]
    assert [w.text() for w in heads] == ["PAGE 1"]


def test_select_panel_focuses_visual_field(monkeypatch):
    db = Database()
    _pid, _sid, v = _scripted_view(db, pages=2, panels=2)
    target = v._field_editors[("panel", 1, 1, "visual_description")]
    seen = {"focus": 0, "visible": None}
    monkeypatch.setattr(target, "setFocus",
                        lambda *a: seen.__setitem__("focus", seen["focus"] + 1))
    monkeypatch.setattr(v._scroll, "ensureWidgetVisible",
                        lambda w, *a: seen.__setitem__("visible", w))
    v.select_panel(1, 1)
    assert seen["focus"] == 1 and seen["visible"] is target


def test_select_page_focuses_title_field(monkeypatch):
    db = Database()
    _pid, _sid, v = _scripted_view(db, pages=2)
    target = v._field_editors[("page", 1, "title")]
    seen = {"focus": 0}
    monkeypatch.setattr(target, "setFocus",
                        lambda *a: seen.__setitem__("focus", seen["focus"] + 1))
    monkeypatch.setattr(v._scroll, "ensureWidgetVisible", lambda w, *a: None)
    v.select_page(1)
    assert seen["focus"] == 1


def test_outline_open_in_manuscript_routes_to_scene():
    from storyplanner.ui.main_window import MainWindow
    from storyplanner.ui.graphic_novel_manuscript_view import (
        GraphicNovelManuscriptView)
    db = Database()
    pid = _gn(db)
    _s1 = _scene(db, pid, "One")
    s2 = _scene(db, pid, "Two")
    win = MainWindow(db, pid)
    win._open_unit_in_manuscript(s2)              # Outline double-click path
    view = win.content_area
    assert isinstance(view, GraphicNovelManuscriptView)
    assert view._scene_id == s2


def test_outline_view_still_mounts_for_plan_section():
    from storyplanner.ui.main_window import MainWindow
    from storyplanner.ui.graphic_novel_outline_view import (
        GraphicNovelOutlineView)
    db = Database()
    win = MainWindow(db, _gn(db))
    win._show_plan()
    assert isinstance(win.content_area, GraphicNovelOutlineView)


# ==========================================================================
# 48-55  Outline ⇄ Manuscript mirroring over ONE shared body
# ==========================================================================


def test_outline_edit_appears_in_manuscript_fields():
    db = Database()
    pid = _gn(db)
    sid = _scene(db, pid)
    v = _view(db, pid)
    v.select_scene(sid)
    gno.add_page(db, sid); gno.add_panel(db, sid, 0)
    gno.set_panel_field(db, sid, 0, 0, "dialogue", "FROM_OUTLINE")
    v.refresh()
    ed = v._field_editors[("panel", 0, 0, "dialogue")]
    assert ed.toPlainText() == "FROM_OUTLINE"


def test_manuscript_edit_appears_in_outline_data():
    db = Database()
    _pid, sid, v = _scripted_view(db)
    v._commit_panel_field(0, 0, "visual_description", "FROM_MANUSCRIPT")
    # The Outline reads the same Scene.content body.
    script = gnb.load_scene_script(db, sid)
    assert gno.panel_snippet(script.pages[0].panels[0]).startswith(
        "FROM_MANUSCRIPT"[:12])
    assert "FROM_MANUSCRIPT" in (db.get_scene_by_id(sid).content or "")


def test_no_second_store_single_body():
    db = Database()
    _pid, sid, v = _scripted_view(db)
    v._commit_panel_field(0, 0, "sfx", "WHAM")
    reloaded = gnb.load_scene_script(db, sid)
    assert reloaded.pages[0].panels[0].sfx == "WHAM"


def test_refresh_skips_rebuild_when_data_unchanged():
    db = Database()
    _pid, _sid, v = _scripted_view(db)
    ed_before = v._field_editors[("panel", 0, 0, "visual_description")]
    v.refresh()                                   # nothing changed
    assert v._field_editors[("panel", 0, 0, "visual_description")] is ed_before


def test_refresh_rebuilds_on_external_change():
    db = Database()
    _pid, sid, v = _scripted_view(db)
    gno.set_panel_field(db, sid, 0, 0, "caption", "EXTERNAL")
    v.refresh()
    ed = v._field_editors[("panel", 0, 0, "caption")]
    assert ed.text() == "EXTERNAL"


def test_focus_location_captured_for_restore(monkeypatch):
    db = Database()
    _pid, sid, v = _scripted_view(db)
    ed = v._field_editors[("panel", 0, 0, "dialogue")]
    monkeypatch.setattr(QApplication, "focusWidget",
                        staticmethod(lambda: ed))
    restored = {}
    monkeypatch.setattr(v, "_restore_focus",
                        lambda loc: restored.setdefault("loc", loc))
    gno.set_panel_field(db, sid, 0, 0, "caption", "X")   # external change
    v.refresh()
    assert restored["loc"][0] == ("panel", 0, 0, "dialogue")


def test_restore_focus_targets_matching_editor(monkeypatch):
    db = Database()
    _pid, _sid, v = _scripted_view(db)
    ed = v._field_editors[("panel", 0, 0, "dialogue")]
    ed.setPlainText("hello")
    seen = {"focus": 0}
    monkeypatch.setattr(ed, "setFocus",
                        lambda *a: seen.__setitem__("focus", seen["focus"] + 1))
    v._restore_focus((("panel", 0, 0, "dialogue"), 3))
    assert seen["focus"] == 1
    assert ed.textCursor().position() == 3


def test_project_switch_isolation(tmp_path):
    db = Database(str(tmp_path / "iso.db"))
    a = _gn(db, "A")
    sa = _scene(db, a, "A-scene")
    va = _view(db, a)
    va.select_scene(sa)
    va._add_page()
    b = _gn(db, "B")                              # empty project
    vb = _view(db, b)
    assert vb._scene_combo.count() == 0
    assert vb._host.findChild(QPushButton, "gnDetailCreateScene") is not None


# ==========================================================================
# 56-59  Structural fullscreen safety
# ==========================================================================


def test_mount_creates_no_new_top_level_window():
    from storyplanner.ui.main_window import MainWindow
    db = Database()
    win = MainWindow(db, _gn(db))
    before = set(QApplication.topLevelWidgets())
    win._show_manuscript()
    new_visible = [w for w in (set(QApplication.topLevelWidgets()) - before)
                   if w.isVisible()]
    assert new_visible == []


def test_script_editor_is_embedded_child():
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


def test_no_dialog_children_on_mount():
    db = Database()
    _pid, _sid, v = _scripted_view(db, pages=2, panels=2)
    assert v.findChildren(QDialog) == []


# ==========================================================================
# 60-64  Export + no-image-generation guards
# ==========================================================================


def test_export_uses_shared_body():
    db = Database()
    pid, _sid, v = _scripted_view(db)
    v._commit_panel_field(0, 0, "visual_description", "EXPORTABLE")
    assert "EXPORTABLE" in gnb.export_project_markdown(db, pid)


def test_export_has_no_image_generation_terms():
    db = Database()
    pid, _sid, v = _scripted_view(db)
    v._commit_panel_field(0, 0, "visual_description", "A quiet street")
    low = gnb.export_project_markdown(db, pid).lower()
    for banned in ("comfyui", "image prompt", "lora", "img2img", "txt2img"):
        assert banned not in low


def test_panel_model_has_no_image_generation_fields():
    fields = set(vars(gnb.Panel()).keys())
    for banned in ("image", "prompt", "comfyui", "lora", "seed", "sampler"):
        assert not any(banned in f for f in fields), banned


def test_view_module_has_no_image_generation_refs():
    # Scan the CODE only (docstrings state the "no image generation" rule and
    # would trip a raw text scan).
    import ast
    import inspect
    from storyplanner.ui import graphic_novel_manuscript_view as mod
    tree = ast.parse(inspect.getsource(mod))
    for node in ast.walk(tree):
        body = getattr(node, "body", None)
        if (isinstance(body, list) and body and isinstance(body[0], ast.Expr)
                and isinstance(body[0].value, ast.Constant)
                and isinstance(body[0].value.value, str)):
            body[0].value.value = ""
    code = ast.unparse(tree).lower()
    for banned in ("comfyui", "img2img", "txt2img", "image prompt",
                   "image_generation"):
        assert banned not in code, banned


def test_view_never_imports_standalone_pages_widget():
    import inspect
    from storyplanner.ui import graphic_novel_manuscript_view as mod
    src = inspect.getsource(mod)
    assert "graphic_novel_scene_pages_view" not in src
    assert "GraphicNovelScenePagesView" not in src
