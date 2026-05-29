"""Tests for the Graphic Novel Page & Panel management UI."""

import pytest

from storyplanner.db import Database
from storyplanner.ui.graphic_novel_pages_view import GraphicNovelPagesView


@pytest.fixture(autouse=True)
def _isolated_settings(monkeypatch, tmp_path):
    import storyplanner.settings as settings
    settings._instance = None
    monkeypatch.setattr(settings, "CONFIG_DIR", tmp_path)
    monkeypatch.setattr(settings, "SETTINGS_FILE", tmp_path / "settings.json")
    yield
    settings._instance = None


def _gn(db):
    return db.create_project(
        "GN", narrative_engine="graphic_novel",
        default_writing_format="graphic_novel",
    )


def _view(db, project_id):
    return GraphicNovelPagesView(db, project_id)


# =========================================================================
# 1. reorder_gn_pages service helper
# =========================================================================

def test_reorder_gn_pages_renumbers():
    db = Database()
    p = _gn(db)
    a = db.create_gn_page(p.id)
    b = db.create_gn_page(p.id)
    c = db.create_gn_page(p.id)
    db.reorder_gn_pages(p.id, [c.id, a.id, b.id])
    pages = db.get_gn_pages(p.id)  # ordered by page_number
    assert [pg.id for pg in pages] == [c.id, a.id, b.id]
    assert [pg.page_number for pg in pages] == [1, 2, 3]


def test_reorder_gn_pages_ignores_foreign_pages():
    db = Database()
    p1 = _gn(db)
    p2 = _gn(db)
    a = db.create_gn_page(p1.id)
    foreign = db.create_gn_page(p2.id)
    db.reorder_gn_pages(p1.id, [foreign.id, a.id])  # foreign id ignored
    assert db.get_gn_page_by_id(foreign.id).project_id == p2.id
    assert db.get_gn_page_by_id(a.id).page_number == 2


# =========================================================================
# 2. Page CRUD + reorder via the view
# =========================================================================

def test_view_detects_gn_mode():
    db = Database()
    p = _gn(db)
    view = _view(db, p.id)
    assert view.is_graphic_novel_mode() is True


def test_add_pages_persists_and_lists():
    db = Database()
    p = _gn(db)
    view = _view(db, p.id)
    p1 = view.add_page()
    p2 = view.add_page()
    assert view.page_ids() == [p1, p2]
    assert len(db.get_gn_pages(p.id)) == 2


def test_delete_selected_page():
    db = Database()
    p = _gn(db)
    view = _view(db, p.id)
    p1 = view.add_page()
    p2 = view.add_page()
    view.select_page(p1)
    view.delete_selected_page()
    assert view.page_ids() == [p2]
    assert db.get_gn_page_by_id(p1) is None


def test_move_page_reorders():
    db = Database()
    p = _gn(db)
    view = _view(db, p.id)
    p1 = view.add_page()
    p2 = view.add_page()
    p3 = view.add_page()
    view.select_page(p3)
    view.move_page(-1)
    assert view.page_ids() == [p1, p3, p2]
    assert [pg.page_number for pg in db.get_gn_pages(p.id)] == [1, 2, 3]


def test_move_page_at_edge_is_noop():
    db = Database()
    p = _gn(db)
    view = _view(db, p.id)
    p1 = view.add_page()
    p2 = view.add_page()
    view.select_page(p1)
    view.move_page(-1)  # already first
    assert view.page_ids() == [p1, p2]


def test_save_page_edits_persists():
    db = Database()
    p = _gn(db)
    view = _view(db, p.id)
    p1 = view.add_page()
    view.select_page(p1)
    view._page_density.setCurrentText("dense")
    view._page_reveal.setCurrentText("cliffhanger")
    view._page_splash.setChecked(True)
    view._page_beat.setText("dread")
    view._page_summary.setPlainText("The reveal.")
    view.save_page_edits()
    page = db.get_gn_page_by_id(p1)
    assert page.density_level == "dense"
    assert page.reveal_type == "cliffhanger"
    assert page.splash_page is True
    assert page.emotional_beat == "dread"
    assert page.summary == "The reveal."


# =========================================================================
# 3. Panel CRUD + reorder via the view
# =========================================================================

def test_add_panels_for_selected_page():
    db = Database()
    p = _gn(db)
    view = _view(db, p.id)
    p1 = view.add_page()
    view.select_page(p1)
    pn1 = view.add_panel()
    pn2 = view.add_panel()
    assert view.panel_ids() == [pn1, pn2]
    assert len(db.get_gn_panels_for_page(p1)) == 2


def test_panels_scoped_to_selected_page():
    db = Database()
    p = _gn(db)
    view = _view(db, p.id)
    p1 = view.add_page()
    p2 = view.add_page()
    view.select_page(p1)
    view.add_panel()
    view.select_page(p2)
    assert view.panel_ids() == []   # p2 has no panels


def test_add_panel_without_page_is_noop():
    db = Database()
    p = _gn(db)
    view = _view(db, p.id)
    # No pages exist → no current page.
    assert view.current_page_id() is None
    assert view.add_panel() is None


def test_save_panel_edits_persists_csv_fields():
    db = Database()
    p = _gn(db)
    view = _view(db, p.id)
    p1 = view.add_page()
    view.select_page(p1)
    pn1 = view.add_panel()
    view.select_panel(pn1)
    view._panel_desc.setPlainText("Hero kicks the door")
    view._panel_shot.setCurrentText("wide")
    view._panel_camera.setCurrentText("low_angle")
    view._panel_chars.setText("Hero, Villain")
    view._panel_motifs.setText("rain, neon")
    view._panel_transition.setCurrentText("action_to_action")
    view._panel_priority.setValue(2)
    view.save_panel_edits()
    panel = db.get_gn_panel_by_id(pn1)
    assert panel.description == "Hero kicks the door"
    assert panel.shot_type == "wide"
    assert panel.camera_angle == "low_angle"
    assert panel.characters_present == "Hero,Villain"
    assert panel.visual_motifs == "rain,neon"
    assert panel.transition_type == "action_to_action"
    assert panel.reading_priority == 2


def test_move_panel_reorders():
    db = Database()
    p = _gn(db)
    view = _view(db, p.id)
    p1 = view.add_page()
    view.select_page(p1)
    pn1 = view.add_panel()
    pn2 = view.add_panel()
    view.select_panel(pn2)
    view.move_panel(-1)
    assert view.panel_ids() == [pn2, pn1]
    assert [x.panel_number for x in db.get_gn_panels_for_page(p1)] == [1, 2]


def test_delete_selected_panel():
    db = Database()
    p = _gn(db)
    view = _view(db, p.id)
    p1 = view.add_page()
    view.select_page(p1)
    pn1 = view.add_panel()
    pn2 = view.add_panel()
    view.select_panel(pn1)
    view.delete_selected_panel()
    assert view.panel_ids() == [pn2]
    assert db.get_gn_panel_by_id(pn1) is None


def test_deleting_page_removes_its_panels():
    db = Database()
    p = _gn(db)
    view = _view(db, p.id)
    p1 = view.add_page()
    view.select_page(p1)
    pn1 = view.add_panel()
    view.select_page(p1)
    view.delete_selected_page()
    assert db.get_gn_panel_by_id(pn1) is None


# =========================================================================
# 4. data_changed signal
# =========================================================================

def test_data_changed_emitted_on_mutations():
    db = Database()
    p = _gn(db)
    seen = []
    view = GraphicNovelPagesView(db, p.id, on_data_changed=lambda: seen.append(1))
    view.add_page()
    assert seen  # callback fired
    n = len(seen)
    view.select_page(view.page_ids()[0])
    view.add_panel()
    assert len(seen) > n


# =========================================================================
# 5. Inert for non-Graphic-Novel projects
# =========================================================================

def test_novel_view_is_inert():
    db = Database()
    p = db.create_project("Novel")
    view = GraphicNovelPagesView(db, p.id)
    assert view.is_graphic_novel_mode() is False
    assert view.add_page() is None
    assert view.page_ids() == []
    assert view.panel_ids() == []
    assert db.get_gn_pages(p.id) == []


# =========================================================================
# 6. Main window mounting + engine gating
# =========================================================================

def test_main_window_mounts_pages_for_gn():
    from storyplanner.ui.main_window import MainWindow
    db = Database()
    p = _gn(db)
    win = MainWindow(db, p.id)
    assert "Pages" in win.sidebar_buttons
    assert "Pages" in win._nav_labels
    win._show_gn_pages()
    assert isinstance(win.content_area, GraphicNovelPagesView)


def test_main_window_hides_pages_for_novel():
    from storyplanner.ui.main_window import MainWindow
    db = Database()
    p = db.create_project("Novel")
    win = MainWindow(db, p.id)
    assert "Pages" not in win.sidebar_buttons
    assert "Pages" not in win._nav_labels
