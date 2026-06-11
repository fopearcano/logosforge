"""Graphic Novel pre-finalization refactor — canonical Act → Page → Scene → Panel.

The Graphic Novel Outline's visible hierarchy is **Project → Act → Page →
Scene → Panel** and the Manuscript derives from it: an Act owns its act-wide
Pages and its Scenes; a Panel belongs to exactly one Scene and sits on exactly
one Page; a Scene can span several Pages (its panels distributed across them);
one Page can hold Panels from several Scenes ("Scene … continued" labels in
page-first physical order). Storage stays the scene-local body script — the
act-wide coordinates come from :mod:`graphic_novel_structure` over the single
new nullable ``Scene.gn_page_start`` offset (NULL = auto-chain after the
previous scene, i.e. the exact legacy layout). Chapters are hidden in Graphic
Novel mode (compat labels only); other writing modes are untouched; the
standalone Pages section stays disabled.
"""

from __future__ import annotations

import sqlite3
import warnings

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QLabel, QPushButton, QSpinBox,
)

warnings.filterwarnings("ignore")

from storyplanner.db import Database
from storyplanner import graphic_novel_blocks as gnb
from storyplanner import graphic_novel_outline as gno
from storyplanner import graphic_novel_structure as gns
from storyplanner import story_structure as ss
from storyplanner.ui import safe_dialogs

_ROLE = Qt.ItemDataRole.UserRole


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


def _scene(db, pid, title="S", act="Act 1"):
    return ss.create_scene(db, pid, act=act, title=title).id


def _pages(db, sid, n, panels_per_page=1):
    for i in range(n):
        gno.add_page(db, sid)
        for _ in range(panels_per_page):
            gno.add_panel(db, sid, i)


def _outline(db, pid, **callbacks):
    from storyplanner.ui.graphic_novel_outline_view import GraphicNovelOutlineView
    callbacks.setdefault("on_data_changed", lambda: None)
    callbacks.setdefault("on_open_manuscript", lambda i: None)
    return GraphicNovelOutlineView(db, pid, **callbacks)


def _manuscript(db, pid):
    from storyplanner.ui.graphic_novel_manuscript_view import (
        GraphicNovelManuscriptView)
    return GraphicNovelManuscriptView(db, pid, on_data_changed=lambda: None)


def _find(tree, predicate):
    stack = [tree.topLevelItem(i) for i in range(tree.topLevelItemCount())]
    while stack:
        it = stack.pop(0)
        if predicate(it):
            return it
        for i in range(it.childCount()):
            stack.append(it.child(i))
    return None


def _shared_page_project(db):
    """The spec example: Act 1 — Scene A spans Pages 1–2; Scene B pinned to
    start on Page 2, so Page 2 holds panels from BOTH scenes."""
    pid = _gn(db)
    a = _scene(db, pid, "A")
    b = _scene(db, pid, "B")
    _pages(db, a, 2)
    _pages(db, b, 2)
    assert gns.set_scene_start_page(db, b, 2)
    return pid, a, b


# ==========================================================================
# 1. Model — act-wide page coordinates (gn_page_start + auto-chain)
# ==========================================================================


def test_gn_page_start_defaults_to_none():
    db = Database()
    pid = _gn(db)
    sid = _scene(db, pid)
    assert db.get_scene_by_id(sid).gn_page_start is None


def test_first_scene_auto_chains_to_page_one():
    db = Database()
    pid = _gn(db)
    sid = _scene(db, pid)
    _pages(db, sid, 1)
    _act, placement = gns.find_placement(db, pid, sid)
    assert placement.start_page == 1 and placement.explicit is False


def test_auto_chain_starts_after_previous_scene():
    db = Database()
    pid = _gn(db)
    a = _scene(db, pid, "A")
    b = _scene(db, pid, "B")
    _pages(db, a, 3)
    _pages(db, b, 1)
    _act, pb = gns.find_placement(db, pid, b)
    assert pb.start_page == 4                      # A used 1-3
    assert pb.explicit is False


def test_scene_spans_multiple_pages():
    db = Database()
    pid = _gn(db)
    sid = _scene(db, pid)
    _pages(db, sid, 3)
    _act, placement = gns.find_placement(db, pid, sid)
    assert (placement.start_page, placement.end_page) == (1, 3)
    [( _act2, pages, _pl )] = [
        (a, p, pl) for a, p, pl in gns.act_view(db, pid)]
    assert [no for no, _s in pages] == [1, 2, 3]
    # Continuation: pages after the scene's first are marked continued.
    flags = [s.continued for _no, slices in pages for s in slices]
    assert flags == [False, True, True]


def test_pinned_start_lets_two_scenes_share_a_page():
    db = Database()
    pid, a, b = _shared_page_project(db)
    view = gns.act_view(db, pid)
    (_act, pages, _placements) = view[0]
    by_no = dict(pages)
    assert sorted(by_no) == [1, 2, 3]
    # Page 2 = Scene A (continued) + Scene B (its first page).
    page2 = [(s.placement.scene.title, s.continued) for s in by_no[2]]
    assert page2 == [("A", True), ("B", False)]
    assert [s.placement.scene.title for s in by_no[1]] == ["A"]
    assert [(s.placement.scene.title, s.continued)
            for s in by_no[3]] == [("B", True)]


def test_panel_belongs_to_one_scene_and_one_page():
    db = Database()
    pid, _a, _b = _shared_page_project(db)
    seen = set()
    for _act, pages, _pl in gns.act_view(db, pid):
        for no, slices in pages:
            for sl in slices:
                for panel in sl.page.panels:
                    key = (sl.placement.scene.id, sl.local_idx,
                           panel.number)
                    assert key not in seen        # placed exactly once
                    seen.add(key)
    assert len(seen) == 4                          # 2 scenes × 2 pages × 1


def test_release_pin_returns_to_auto_chain():
    db = Database()
    pid, _a, b = _shared_page_project(db)
    assert gns.set_scene_start_page(db, b, None)
    _act, pb = gns.find_placement(db, pid, b)
    assert pb.start_page == 3 and pb.explicit is False


@pytest.mark.parametrize("bad", [0, -1, "nope"])
def test_invalid_start_page_is_refused(bad):
    db = Database()
    pid = _gn(db)
    sid = _scene(db, pid)
    assert gns.set_scene_start_page(db, sid, bad) is False
    assert db.get_scene_by_id(sid).gn_page_start is None
    _ = pid


def test_garbage_stored_value_falls_back_to_auto():
    db = Database()
    pid = _gn(db)
    a = _scene(db, pid, "A")
    _pages(db, a, 1)
    scene = db.get_scene_by_id(a)
    # Defensive: a corrupt/legacy value must never break the layout.
    for raw in (None, -3, 0):
        db.set_scene_gn_page_start(a, raw)
        _act, placement = gns.find_placement(db, pid, a)
        assert placement.start_page == 1
        _ = scene


def test_page_numbers_reset_per_act():
    db = Database()
    pid = _gn(db)
    a = _scene(db, pid, "A", act="Act 1")
    c = _scene(db, pid, "C", act="Act 2")
    _pages(db, a, 2)
    _pages(db, c, 1)
    view = {act: pages for act, pages, _pl in gns.act_view(db, pid)}
    assert [no for no, _ in view["Act 1"]] == [1, 2]
    assert [no for no, _ in view["Act 2"]] == [1]  # acts own their pages


def test_empty_scene_occupies_no_pages_and_does_not_advance():
    db = Database()
    pid = _gn(db)
    a = _scene(db, pid, "A")
    empty = _scene(db, pid, "Empty")
    b = _scene(db, pid, "B")
    _pages(db, a, 2)
    _pages(db, b, 1)
    _act, pe = gns.find_placement(db, pid, empty)
    assert pe.page_count == 0
    assert gns.scene_page_range_label(pe) == "no pages yet"
    _act, pb = gns.find_placement(db, pid, b)
    assert pb.start_page == 3                      # Empty did not advance


def test_backward_pin_does_not_shrink_the_chain():
    db = Database()
    pid = _gn(db)
    a = _scene(db, pid, "A")
    b = _scene(db, pid, "B")
    c = _scene(db, pid, "C")
    _pages(db, a, 4)
    _pages(db, b, 1)
    _pages(db, c, 1)
    gns.set_scene_start_page(db, b, 2)             # B shares A's Page 2
    _act, pc = gns.find_placement(db, pid, c)
    assert pc.start_page == 5                      # after A's high water


def test_scene_page_range_label_forms():
    db = Database()
    pid = _gn(db)
    a = _scene(db, pid, "A")
    _pages(db, a, 1)
    _act, pa = gns.find_placement(db, pid, a)
    assert gns.scene_page_range_label(pa) == "Page 1"
    _pages(db, a, 2)
    _act, pa = gns.find_placement(db, pid, a)
    assert gns.scene_page_range_label(pa) == "Pages 1–3"


def test_migration_adds_column_to_legacy_db(tmp_path):
    path = str(tmp_path / "legacy.db")
    db = Database(path)
    pid = _gn(db)
    sid = _scene(db, pid, "Legacy")
    # Simulate a pre-refactor database: drop the new column entirely.
    raw = sqlite3.connect(path)
    raw.execute("ALTER TABLE scene DROP COLUMN gn_page_start")
    raw.commit()
    raw.close()
    db2 = Database(path)                           # migration runs on open
    assert db2.get_scene_by_id(sid).gn_page_start is None
    db2.set_scene_gn_page_start(sid, 7)
    db3 = Database(path)                           # idempotent on re-open
    assert db3.get_scene_by_id(sid).gn_page_start == 7


def test_pin_persists_across_reopen(tmp_path):
    path = str(tmp_path / "persist.db")
    db = Database(path)
    pid, _a, b = _shared_page_project(db)
    db2 = Database(path)
    _act, pb = gns.find_placement(db2, pid, b)
    assert pb.start_page == 2 and pb.explicit is True


# ==========================================================================
# 2. Outline — visible Act → Page → Scene → Panel hierarchy
# ==========================================================================


def test_outline_tree_is_act_page_scene_panel():
    db = Database()
    pid, _a, _b = _shared_page_project(db)
    v = _outline(db, pid)
    act = v._tree.topLevelItem(0)
    assert act.text(0) == "Act 1"
    kinds = [act.child(i).data(0, _ROLE)["kind"]
             for i in range(act.childCount())]
    assert kinds == ["act_page", "act_page", "act_page"]
    page1 = act.child(0)
    scene = page1.child(0)
    assert scene.data(0, _ROLE)["kind"] == "scene_page"
    assert scene.child(0).data(0, _ROLE)["kind"] == "panel"


def test_outline_page_first_physical_order():
    db = Database()
    pid, _a, _b = _shared_page_project(db)
    v = _outline(db, pid)
    act = v._tree.topLevelItem(0)
    labels = [act.child(i).text(0) for i in range(act.childCount())]
    assert labels == ["Page 1", "Page 2", "Page 3"]


def test_outline_continued_label_for_spanning_scene():
    db = Database()
    pid, _a, _b = _shared_page_project(db)
    v = _outline(db, pid)
    page2 = _find(v._tree, lambda it: it.text(0) == "Page 2")
    texts = [page2.child(i).text(0) for i in range(page2.childCount())]
    assert any(t.startswith("Scene — A (continued)") for t in texts)
    assert any(t.startswith("Scene — B") and "(continued)" not in t
               for t in texts)


def test_outline_shared_page_lists_both_scenes():
    db = Database()
    pid, a, b = _shared_page_project(db)
    v = _outline(db, pid)
    page2 = _find(v._tree, lambda it: it.text(0) == "Page 2")
    ids = [page2.child(i).data(0, _ROLE)["scene_id"]
           for i in range(page2.childCount())]
    assert ids == [a, b]


def test_outline_hides_chapter_everywhere():
    db = Database()
    pid, _a, _b = _shared_page_project(db)
    v = _outline(db, pid)
    assert _find(v._tree, lambda it: "Chapter" in it.text(0)) is None
    # The stored compat label still exists — it is just never shown.
    assert db.get_scene_by_id(_a).chapter


def test_outline_empty_scene_visible_under_act():
    db = Database()
    pid = _gn(db)
    _scene(db, pid, "Lonely")
    v = _outline(db, pid)
    item = _find(v._tree, lambda it: "Lonely" in it.text(0))
    assert item is not None and "no pages yet" in item.text(0)
    assert item.data(0, _ROLE)["kind"] == "scene"
    assert item.parent().data(0, _ROLE)["kind"] == "act"


def test_outline_empty_state_a_offers_create_act():
    db = Database()
    v = _outline(db, _gn(db))
    msgs = [w.text() for w in v._detail_host.findChildren(QLabel)]
    assert "Create an Act to begin your Graphic Novel." in msgs
    btn = v._detail_host.findChild(QPushButton, "gnOutlineDetailAddAct")
    assert btn is not None and btn.text() == "+ Act"


def test_outline_add_act_button_creates_act_one():
    db = Database()
    pid = _gn(db)
    v = _outline(db, pid)
    v._detail_host.findChild(QPushButton, "gnOutlineDetailAddAct").click()
    assert ss.list_acts(db, pid) == ["Act 1"]
    assert v._tree.topLevelItem(0).text(0) == "Act 1"


def test_outline_toolbar_add_act_appends_act_two():
    db = Database()
    pid = _gn(db)
    _scene(db, pid, "A")
    v = _outline(db, pid)
    v._add_act()
    assert ss.list_acts(db, pid) == ["Act 1", "Act 2"]


def test_outline_add_page_on_empty_act_seeds_scene():
    db = Database()
    pid = _gn(db)
    sid = _scene(db, pid, "Solo")
    v = _outline(db, pid)
    v._sel = {"kind": "act", "act": "Act 1"}
    v._add_page()                                   # acts own pages
    assert len(gnb.load_scene_script(db, sid).pages) == 1
    assert v._sel["kind"] == "scene_page" and v._sel["page_no"] == 1


def test_outline_add_page_selects_new_scene_page():
    db = Database()
    pid = _gn(db)
    sid = _scene(db, pid)
    _pages(db, sid, 1)
    v = _outline(db, pid)
    v._sel = {"kind": "scene", "act": "Act 1", "scene_id": sid}
    v._add_page()
    assert v._sel == {"kind": "scene_page", "act": "Act 1", "scene_id": sid,
                      "page": 1, "page_no": 2, "continued": True}


def test_outline_act_page_detail_lists_contributing_scenes():
    db = Database()
    pid, _a, _b = _shared_page_project(db)
    v = _outline(db, pid)
    v._sel = {"kind": "act_page", "act": "Act 1", "page_no": 2}
    v._render_detail()
    texts = " ".join(w.text() for w in v._detail_host.findChildren(QLabel))
    assert "more than one scene" in texts
    assert "Scene A — continued" in texts and "Scene B" in texts


def test_outline_start_page_controls_pin_and_release():
    db = Database()
    pid = _gn(db)
    a = _scene(db, pid, "A")
    b = _scene(db, pid, "B")
    _pages(db, a, 2)
    _pages(db, b, 1)
    v = _outline(db, pid)
    v._sel = {"kind": "scene_page", "act": "Act 1", "scene_id": b,
              "page": 0, "page_no": 3, "continued": False}
    v._render_detail()
    spin = v._detail_host.findChild(QSpinBox, "gnOutlineStartPage")
    auto = v._detail_host.findChild(QCheckBox, "gnOutlineStartAuto")
    assert spin.value() == 3 and auto.isChecked()   # auto-chained today
    assert spin.isEnabled() is False                # spin follows the chain
    spin.setValue(2)
    auto.setChecked(False)                          # pin it
    assert db.get_scene_by_id(b).gn_page_start == 2
    _act, pb = gns.find_placement(db, pid, b)
    assert pb.start_page == 2 and pb.explicit
    # Release back to auto.
    v._sel = {"kind": "scene", "act": "Act 1", "scene_id": b}
    v._render_detail()
    auto = v._detail_host.findChild(QCheckBox, "gnOutlineStartAuto")
    assert not auto.isChecked()
    auto.setChecked(True)
    assert db.get_scene_by_id(b).gn_page_start is None


def test_outline_panel_deep_link_uses_scene_local_page():
    db = Database()
    pid, _a, b = _shared_page_project(db)
    hits = []
    v = _outline(db, pid, on_open_panel=lambda s, p, c: hits.append((s, p, c)))
    page2 = _find(v._tree, lambda it: it.text(0) == "Page 2")
    b_group = page2.child(1)                        # Scene B on act Page 2
    assert b_group.data(0, _ROLE)["scene_id"] == b
    v._activate(b_group.child(0))
    assert hits == [(b, 0, 0)]                      # local page idx, not 2


def test_outline_scene_page_double_click_opens_manuscript():
    db = Database()
    pid = _gn(db)
    sid = _scene(db, pid)
    _pages(db, sid, 1)
    opened = []
    v = _outline(db, pid, on_open_manuscript=opened.append)
    group = _find(v._tree,
                  lambda it: (it.data(0, _ROLE) or {}).get("kind")
                  == "scene_page")
    v._activate(group)
    assert opened == [sid]


def test_outline_selection_never_mutates_shared_page():
    db = Database()
    pid, a, b = _shared_page_project(db)
    before = (db.get_scene_by_id(a).content, db.get_scene_by_id(b).content,
              db.get_scene_by_id(b).gn_page_start)
    v = _outline(db, pid)
    page2 = _find(v._tree, lambda it: it.text(0) == "Page 2")
    for i in range(page2.childCount()):
        v._tree.setCurrentItem(page2.child(i))
    assert (db.get_scene_by_id(a).content, db.get_scene_by_id(b).content,
            db.get_scene_by_id(b).gn_page_start) == before


def test_outline_delete_scene_page_removes_only_that_local_page(monkeypatch):
    monkeypatch.setattr(safe_dialogs, "question", lambda *a, **k: True)
    db = Database()
    pid, a, _b = _shared_page_project(db)
    v = _outline(db, pid)
    v._sel = {"kind": "scene_page", "act": "Act 1", "scene_id": a,
              "page": 1, "page_no": 2, "continued": True}
    v._delete_selected()
    assert len(gnb.load_scene_script(db, a).pages) == 1


def test_outline_move_panel_to_page_shows_act_wide_numbers():
    db = Database()
    pid, _a, b = _shared_page_project(db)        # B pinned: local pages → 2,3
    v = _outline(db, pid)
    v._sel = {"kind": "panel", "act": "Act 1", "scene_id": b,
              "page": 0, "panel": 0, "page_no": 2}
    v._render_detail()
    buttons = [w.text() for w in v._detail_host.findChildren(QPushButton)]
    assert "Page 3" in buttons                   # B's other local page = act 3
    assert "Page 1" not in buttons               # not B's page; not offered


# ==========================================================================
# 3. Manuscript — derives from the Outline structure
# ==========================================================================


def test_manuscript_page_headers_use_act_wide_numbers():
    db = Database()
    pid, _a, b = _shared_page_project(db)
    m = _manuscript(db, pid)
    m.select_scene(b)
    heads = [w.text() for w in m._host.findChildren(QLabel)
             if w.objectName() == "gnPageHeader"]
    assert heads == ["PAGE 2", "PAGE 3"]


def test_manuscript_context_shows_act_and_page_range_no_chapter():
    db = Database()
    pid, _a, b = _shared_page_project(db)
    m = _manuscript(db, pid)
    m.select_scene(b)
    ctx = [w.text() for w in m._host.findChildren(QLabel)
           if w.objectName() == "gnScriptContext"][0]
    assert "Act 1" in ctx and "Pages 2–3" in ctx and "SCENE: B" in ctx
    assert "Chapter" not in ctx


def test_manuscript_scene_combo_hides_chapter():
    db = Database()
    pid, _a, _b = _shared_page_project(db)
    m = _manuscript(db, pid)
    labels = [m._scene_combo.itemText(i) for i in range(m._scene_combo.count())]
    assert labels and all("Chapter" not in t for t in labels)
    assert all("Act 1" in t for t in labels)


def test_manuscript_renumbers_when_other_scene_grows():
    db = Database()
    pid = _gn(db)
    a = _scene(db, pid, "A")
    b = _scene(db, pid, "B")
    _pages(db, a, 1)
    _pages(db, b, 1)
    m = _manuscript(db, pid)
    m.select_scene(b)
    heads = [w.text() for w in m._host.findChildren(QLabel)
             if w.objectName() == "gnPageHeader"]
    assert heads == ["PAGE 2"]
    gno.add_page(db, a)                            # A grows → B shifts
    m.refresh()
    heads = [w.text() for w in m._host.findChildren(QLabel)
             if w.objectName() == "gnPageHeader"]
    assert heads == ["PAGE 3"]


def test_manuscript_panel_blocks_grouped_by_page_for_spanning_scene():
    db = Database()
    pid, _a, b = _shared_page_project(db)
    m = _manuscript(db, pid)
    m.select_scene(b)
    # Scene selected → its panels grouped under its (act-wide) pages.
    assert ("panel", 0, 0) in m._field_editors
    assert ("panel", 1, 0) in m._field_editors


def test_manuscript_panel_selection_keeps_local_coordinates():
    db = Database()
    pid, _a, b = _shared_page_project(db)
    m = _manuscript(db, pid)
    m.select_scene(b)
    m.select_panel(1, 0)                           # local page idx
    assert m.current_panel_ref() == (b, 1, 0)      # voice/commit unchanged


def test_manuscript_empty_state_then_act_then_page_ladder():
    db = Database()
    pid = _gn(db)
    m = _manuscript(db, pid)
    msgs = [w.text() for w in m._host.findChildren(QLabel)
            if w.objectName() == "gnScriptEmpty"]
    assert msgs == ["Create an Act to begin your Graphic Novel."]   # state A
    m._host.findChild(QPushButton, "gnScriptCreateAct").click()
    assert ss.list_acts(db, pid) == ["Act 1"]
    assert m._host.findChild(QPushButton, "gnDetailAddPage") is not None  # B


# ==========================================================================
# 4. Outline ⇄ Manuscript mirroring (one body, one coordinate system)
# ==========================================================================


def test_pinning_in_outline_renumbers_manuscript():
    db = Database()
    pid = _gn(db)
    a = _scene(db, pid, "A")
    b = _scene(db, pid, "B")
    _pages(db, a, 2)
    _pages(db, b, 1)
    m = _manuscript(db, pid)
    m.select_scene(b)
    gns.set_scene_start_page(db, b, 2)             # the Outline's control
    m.refresh()
    heads = [w.text() for w in m._host.findChildren(QLabel)
             if w.objectName() == "gnPageHeader"]
    assert heads == ["PAGE 2"]                     # shares A's Page 2


def test_outline_add_page_appears_in_manuscript_numbering():
    db = Database()
    pid = _gn(db)
    sid = _scene(db, pid)
    v = _outline(db, pid)
    v._sel = {"kind": "scene", "act": "Act 1", "scene_id": sid}
    v._add_page()
    m = _manuscript(db, pid)
    m.select_scene(sid)
    heads = [w.text() for w in m._host.findChildren(QLabel)
             if w.objectName() == "gnPageHeader"]
    assert heads == ["PAGE 1"]


def test_manuscript_add_page_appears_as_new_act_page_in_outline():
    db = Database()
    pid = _gn(db)
    sid = _scene(db, pid)
    _pages(db, sid, 1)
    m = _manuscript(db, pid)
    m.select_scene(sid)
    m._add_page()
    v = _outline(db, pid)
    assert _find(v._tree, lambda it: it.text(0) == "Page 2") is not None


def test_panel_field_edit_mirrors_into_outline_snippet():
    db = Database()
    pid, _a, b = _shared_page_project(db)
    gno.set_panel_field(db, b, 1, 0, "visual_description", "MIRRORED")
    v = _outline(db, pid)
    item = _find(v._tree, lambda it: "MIRRORED" in it.text(0))
    assert item is not None
    assert item.data(0, _ROLE)["page_no"] == 3     # B local 2 → act Page 3


# ==========================================================================
# 5. Export — Act → Page → Scene → Panel with assignments
# ==========================================================================


def test_export_page_first_with_assignments_and_continued():
    db = Database()
    pid, _a, _b = _shared_page_project(db)
    gno.set_panel_field(db, _a, 1, 0, "dialogue", "A2_LINE")
    gno.set_panel_field(db, _b, 0, 0, "dialogue", "B1_LINE")
    md = gns.export_structure_markdown(db, pid)
    assert "## Act 1" in md
    assert md.index("### Page 1") < md.index("### Page 2") < md.index(
        "### Page 3")
    assert "**Scene: A — continued**" in md        # spanning marker
    assert "(Scene: A → Page 2)" in md             # explicit assignments
    assert "(Scene: B → Page 2)" in md
    a2 = md.index("A2_LINE")
    b1 = md.index("B1_LINE")
    assert a2 < b1                                 # shared page, story order


def test_export_panel_text_appears_exactly_once():
    db = Database()
    pid, a, _b = _shared_page_project(db)
    gno.set_panel_field(db, a, 0, 0, "dialogue", "ONLY_ONCE_LINE")
    md = gns.export_structure_markdown(db, pid)
    assert md.count("ONLY_ONCE_LINE") == 1


def test_export_hides_chapter_and_lists_empty_scenes():
    db = Database()
    pid = _gn(db)
    a = _scene(db, pid, "A")
    _scene(db, pid, "Empty")
    _pages(db, a, 1)
    md = gns.export_structure_markdown(db, pid)
    assert "Chapter" not in md
    assert "_Scenes without pages:_" in md and "- Empty" in md


def test_export_no_image_data_or_secrets():
    db = Database()
    pid, _a, _b = _shared_page_project(db)
    settings = db.get_project_settings(pid) or {}
    settings["api_key"] = "sk-SECRET"
    db.save_project_settings(pid, settings)
    md = gns.export_structure_markdown(db, pid)
    low = md.lower()
    for banned in ("comfyui", "image prompt", "lora", "img2img", "txt2img"):
        assert banned not in low
    assert "sk-SECRET" not in md and "SECRET" not in md


def test_legacy_export_name_delegates_to_canonical():
    db = Database()
    pid, _a, _b = _shared_page_project(db)
    assert gno.export_outline_markdown(db, pid) == \
        gns.export_structure_markdown(db, pid)


# ==========================================================================
# 6. Compatibility, isolation and regression
# ==========================================================================


def test_legacy_null_offsets_reproduce_sequential_layout():
    # A pre-refactor project (all gn_page_start NULL) reads exactly as the
    # old sequential chain — non-destructive adapter, no data rewrite.
    db = Database()
    pid = _gn(db)
    a = _scene(db, pid, "A")
    b = _scene(db, pid, "B")
    _pages(db, a, 2)
    _pages(db, b, 2)
    bodies = (db.get_scene_by_id(a).content, db.get_scene_by_id(b).content)
    view = gns.act_view(db, pid)
    (_act, pages, placements) = view[0]
    assert [no for no, _s in pages] == [1, 2, 3, 4]
    assert [p.start_page for p in placements] == [1, 3]
    # Bodies untouched (still scene-local PAGE 1..n script).
    assert (db.get_scene_by_id(a).content,
            db.get_scene_by_id(b).content) == bodies
    assert "PAGE 1" in bodies[1]                   # scene-local storage


def test_orphan_scenes_group_under_unassigned_without_crash():
    db = Database()
    pid = _gn(db)
    sid = db.create_scene(pid, title="Orphan").id  # no act label at all
    gno.add_page(db, sid)
    view = dict((act, pages) for act, pages, _pl in gns.act_view(db, pid))
    assert ss.UNASSIGNED_ACT in view
    assert [no for no, _s in view[ss.UNASSIGNED_ACT]] == [1]
    v = _outline(db, pid)                          # renders without error
    assert _find(v._tree, lambda it: "Orphan" in it.text(0)) is not None


def test_other_modes_ignore_gn_page_start():
    db = Database()
    for engine in ("novel", "screenplay", "stage_script", "series"):
        pid = db.create_project(engine, narrative_engine=engine,
                                default_writing_format=engine).id
        sid = ss.create_scene(db, pid, act="Act 1", chapter="Chapter 1",
                              title="S").id
        assert db.get_scene_by_id(sid).gn_page_start is None


def test_non_gn_outline_still_plan_view():
    from storyplanner.ui.main_window import MainWindow
    from storyplanner.ui.plan_view import PlanView
    db = Database()
    pid = db.create_project("novel", narrative_engine="novel",
                            default_writing_format="novel").id
    win = MainWindow(db, pid)
    win._show_plan()
    assert isinstance(win.content_area, PlanView)


def test_standalone_pages_still_hidden_and_inert():
    from storyplanner.ui.main_window import MainWindow
    from storyplanner.ui.graphic_novel_scene_pages_view import (
        GraphicNovelScenePagesView)
    db = Database()
    win = MainWindow(db, _gn(db))
    assert "Pages" not in win._nav_labels and "Pages" not in win.sidebar_buttons
    win._show_gn_pages()
    assert not isinstance(win.content_area, GraphicNovelScenePagesView)


def test_outline_mount_fullscreen_safe():
    from storyplanner.ui.main_window import MainWindow
    db = Database()
    win = MainWindow(db, _gn(db))
    before = set(QApplication.topLevelWidgets())
    win._show_plan()
    new_visible = [w for w in (set(QApplication.topLevelWidgets()) - before)
                   if w.isVisible()]
    assert new_visible == [] and win.content_area.window() is win


def test_project_isolation_of_placements(tmp_path):
    db = Database(str(tmp_path / "iso.db"))
    p1 = _gn(db, "One")
    a = _scene(db, p1, "A")
    _pages(db, a, 3)
    p2 = _gn(db, "Two")
    c = _scene(db, p2, "C")
    _pages(db, c, 1)
    _act, pc = gns.find_placement(db, p2, c)
    assert pc.start_page == 1                      # other project invisible
    assert gns.find_placement(db, p2, a) == (None, None)


def test_body_grammar_and_renumber_untouched():
    # The storage format stays the scene-local script; _renumber still
    # numbers pages 1..n per scene regardless of act-wide coordinates.
    db = Database()
    pid, _a, b = _shared_page_project(db)
    script = gnb.load_scene_script(db, b)
    assert [p.number for p in script.pages] == [1, 2]
    gnb._renumber(script)
    assert [p.number for p in script.pages] == [1, 2]
    _ = pid
