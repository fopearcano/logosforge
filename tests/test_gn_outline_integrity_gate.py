"""Graphic Novel Outline/Page/Panel — post-fix integrity gate.

A focused gate that re-verifies the corrected Graphic Novel architecture
(Chapter owns Pages, Scene owns Panels, Panel assigned to Page, Scene spans Pages,
Outline ⇄ Manuscript mirror the same shared body, standalone Pages disabled). It
complements the detailed suites (`test_gn_outline.py`, `test_gn_embedded_navigator.py`,
`test_gn_pages_manuscript_sync.py`) with the audit's specific data-integrity,
standalone-Pages-safety, export, and no-image-generation invariants.
"""

from __future__ import annotations

import warnings

import pytest
from PySide6.QtWidgets import QApplication

warnings.filterwarnings("ignore")

from storyplanner.db import Database
from storyplanner import graphic_novel_blocks as gnb
from storyplanner import graphic_novel_outline as gno
from storyplanner import story_structure as ss


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


def _scene(db, pid, title="S", act="Act 1", chapter="Chapter 1"):
    return ss.create_scene(db, pid, act=act, chapter=chapter, title=title).id


def _body(db, sid):
    return gnb.load_scene_script(db, sid)


# ==========================================================================
# Data-model integrity (§2)
# ==========================================================================


def test_move_panel_to_page_preserves_body():
    db = Database()
    pid = _gn(db)
    sid = _scene(db, pid)
    gno.add_page(db, sid)
    gno.add_panel(db, sid, 0)
    gno.set_panel_field(db, sid, 0, 0, "visual_description", "KEEP_BODY")
    gno.add_page(db, sid)
    assert gno.move_panel_to_page(db, sid, 0, 0, 1)
    body = _body(db, sid)
    assert body.pages[1].panels[0].visual_description == "KEEP_BODY"
    assert len(body.pages[0].panels) == 0


def test_reorder_scenes_preserves_panels():
    db = Database()
    pid = _gn(db)
    a = _scene(db, pid, "A")
    b = _scene(db, pid, "B")
    gno.add_page(db, a); gno.add_panel(db, a, 0); gno.add_panel(db, a, 0)
    before = _body(db, a).panel_count()
    db.reorder_scenes(pid, [b, a])
    assert _body(db, a).panel_count() == before == 2


def test_round_trip_no_duplicate_panels():
    db = Database()
    pid = _gn(db)
    sid = _scene(db, pid)
    gno.add_page(db, sid)
    gno.add_panel(db, sid, 0); gno.add_panel(db, sid, 0)
    content = db.get_scene_by_id(sid).content
    reparsed = gnb.parse_graphic_novel_text(content)
    assert reparsed.panel_count() == 2


def test_panel_has_single_canonical_body():
    db = Database()
    pid = _gn(db)
    sid = _scene(db, pid)
    gno.add_page(db, sid); gno.add_panel(db, sid, 0)
    gno.set_panel_field(db, sid, 0, 0, "dialogue", "ONCE_ONLY")
    content = db.get_scene_by_id(sid).content
    assert content.count("ONCE_ONLY") == 1


def test_rename_page_persists():
    db = Database()
    pid = _gn(db)
    sid = _scene(db, pid)
    gno.add_page(db, sid)
    assert gno.set_page_field(db, sid, 0, "title", "Splash Page")
    assert _body(db, sid).pages[0].title == "Splash Page"


def test_page_lists_its_panels_and_scene_lists_its_panels():
    db = Database()
    pid = _gn(db)
    a = _scene(db, pid, "A")
    b = _scene(db, pid, "B")
    gno.add_page(db, a); gno.add_panel(db, a, 0)      # A page 1
    gno.add_panel(db, b, None)                        # B page 1
    scenes = gno.scenes_in_chapter(db, pid, "Act 1", "Chapter 1")
    pv = dict(gno.chapter_page_view(db, scenes))
    # Page 1 lists panels from both scenes; each scene lists its own panel.
    assert len(pv[1]) == 2
    assert _body(db, a).panel_count() == 1 and _body(db, b).panel_count() == 1


# ==========================================================================
# Outline ⇄ Manuscript mirror the SAME body (§5)
# ==========================================================================


def test_outline_and_manuscript_share_one_body():
    from storyplanner.ui.graphic_novel_outline_view import GraphicNovelOutlineView
    from storyplanner.ui.graphic_novel_manuscript_view import (
        GraphicNovelManuscriptView)
    db = Database()
    pid = _gn(db)
    sid = _scene(db, pid)
    # Edit via the Outline data layer.
    gno.add_page(db, sid); gno.add_panel(db, sid, 0)
    gno.set_panel_field(db, sid, 0, 0, "visual_description", "MIRROR")
    # Both views read the same Scene.content.
    o = GraphicNovelOutlineView(db, pid, on_data_changed=lambda: None)
    m = GraphicNovelManuscriptView(db, pid, on_data_changed=lambda: None)
    m.select_scene(sid)
    assert "MIRROR" in (db.get_scene_by_id(sid).content or "")
    # Outline tree shows the panel snippet.
    found = None
    stack = [o._scene_tree.topLevelItem(i)
             for i in range(o._scene_tree.topLevelItemCount())]
    while stack:
        it = stack.pop()
        if "MIRROR" in it.text(0):
            found = it
            break
        stack.extend(it.child(i) for i in range(it.childCount()))
    assert found is not None


# ==========================================================================
# Standalone Pages disabled + fullscreen safety (§6)
# ==========================================================================


def test_standalone_pages_hidden_and_inert():
    from storyplanner.ui.main_window import MainWindow
    from storyplanner.ui.graphic_novel_scene_pages_view import (
        GraphicNovelScenePagesView)
    db = Database()
    win = MainWindow(db, _gn(db))
    assert "Pages" not in win._nav_labels and "Pages" not in win.sidebar_buttons
    win._show_gn_pages()
    assert not isinstance(win.content_area, GraphicNovelScenePagesView)


def test_outline_activation_fullscreen_safe():
    from storyplanner.ui.main_window import MainWindow
    db = Database()
    win = MainWindow(db, _gn(db))
    calls = {"min": 0, "hide": 0, "close": 0}
    win.showMinimized = lambda: calls.__setitem__("min", calls["min"] + 1)  # type: ignore
    win.hide = lambda: calls.__setitem__("hide", calls["hide"] + 1)         # type: ignore
    win.close = lambda: calls.__setitem__("close", calls["close"] + 1)      # type: ignore
    before = set(QApplication.topLevelWidgets())
    win._show_plan()
    new_visible = [w for w in (set(QApplication.topLevelWidgets()) - before)
                   if w.isVisible()]
    assert calls == {"min": 0, "hide": 0, "close": 0}
    assert new_visible == [] and win.content_area.window() is win


# ==========================================================================
# Export (§7) + no image generation (§8)
# ==========================================================================


def test_export_has_page_and_scene_assignment_no_secrets():
    db = Database()
    pid = _gn(db)
    sid = _scene(db, pid, "Cold Open")
    gno.add_page(db, sid); gno.add_panel(db, sid, 0)
    gno.set_panel_field(db, sid, 0, 0, "visual_description", "PANELBODY")
    settings = db.get_project_settings(pid) or {}
    settings["api_key"] = "sk-SECRET"
    db.save_project_settings(pid, settings)
    md = gno.export_outline_markdown(db, pid)
    assert "Cold Open" in md and "Page 1" in md and "PANELBODY" in md
    assert "Page view" in md                       # page-order cross-reference
    assert "SECRET" not in md and "sk-" not in md
    low = md.lower()
    for banned in ("comfyui", "image prompt", "lora", "img2img", "txt2img"):
        assert banned not in low


def test_logos_registry_has_no_image_or_comfyui_action():
    from storyplanner.logos import actions as A
    blob = " ".join((a.name + " " + a.label).lower() for a in A.list_actions())
    for banned in ("comfyui", "image gen", "generate image", "image prompt",
                   "img2img", "txt2img", "lora "):
        assert banned not in blob, banned


def test_canvas_plot_hidden_in_gn_mode():
    from storyplanner.ui.main_window import MainWindow
    db = Database()
    win = MainWindow(db, _gn(db))
    assert "Plot" not in win._nav_labels
    btn = win.sidebar_buttons.get("Plot")
    assert btn is None or btn.property("nav_available") is False


def test_panel_model_has_no_image_generation_fields():
    fields = set(vars(gnb.Panel()).keys())
    assert fields == {"number", "visual_description", "caption", "dialogue",
                      "sfx", "notes"}
