"""Tests for the Plan view — Acts → Chapters → Scenes hierarchy."""

from PySide6.QtWidgets import QApplication

from storyplanner.db import Database
from storyplanner.ui.plan_view import (
    PlanView,
    _UNTITLED_ACT,
    _UNTITLED_CHAPTER,
    _act_summaries,
    _chapter_summaries,
    _delete_act,
    _delete_chapter,
    _rename_act,
    _rename_chapter,
    _save_act_summary,
    _save_chapter_summary,
    build_plan_tree,
)


def _make_project():
    db = Database()
    proj = db.create_project("Test")
    return db, proj


def test_build_plan_tree_empty():
    db, proj = _make_project()
    assert build_plan_tree(db, proj.id) == []


def test_build_plan_tree_groups_by_act_and_chapter():
    db, proj = _make_project()
    db.create_scene(proj.id, "Scene 1", act="Act One", chapter="Ch 1")
    db.create_scene(proj.id, "Scene 2", act="Act One", chapter="Ch 1")
    db.create_scene(proj.id, "Scene 3", act="Act One", chapter="Ch 2")
    db.create_scene(proj.id, "Scene 4", act="Act Two", chapter="Ch 3")

    tree = build_plan_tree(db, proj.id)
    assert len(tree) == 2
    act_one_name, act_one_chapters = tree[0]
    assert act_one_name == "Act One"
    assert len(act_one_chapters) == 2
    assert act_one_chapters[0][0] == "Ch 1"
    assert len(act_one_chapters[0][1]) == 2
    assert act_one_chapters[1][0] == "Ch 2"
    assert len(act_one_chapters[1][1]) == 1


def test_build_plan_tree_handles_untitled():
    db, proj = _make_project()
    db.create_scene(proj.id, "Loose Scene")
    tree = build_plan_tree(db, proj.id)
    assert tree == [(_UNTITLED_ACT, [(_UNTITLED_CHAPTER, [tree[0][1][0][1][0]])])]


def test_save_and_read_act_summary():
    db, proj = _make_project()
    _save_act_summary(db, proj.id, "Act One", "First half of the journey")
    summaries = _act_summaries(db, proj.id)
    assert summaries["Act One"] == "First half of the journey"


def test_save_act_summary_empty_removes_key():
    db, proj = _make_project()
    _save_act_summary(db, proj.id, "Act One", "Some text")
    _save_act_summary(db, proj.id, "Act One", "")
    summaries = _act_summaries(db, proj.id)
    assert "Act One" not in summaries


def test_save_and_read_chapter_summary():
    db, proj = _make_project()
    _save_chapter_summary(db, proj.id, "Ch 1", "Setup")
    assert _chapter_summaries(db, proj.id)["Ch 1"] == "Setup"


def test_rename_act_updates_scenes_and_summary():
    db, proj = _make_project()
    s1 = db.create_scene(proj.id, "Scene 1", act="Act One")
    s2 = db.create_scene(proj.id, "Scene 2", act="Act Two")
    _save_act_summary(db, proj.id, "Act One", "First act")

    _rename_act(db, proj.id, "Act One", "Beginning")

    assert db.get_scene_by_id(s1.id).act == "Beginning"
    assert db.get_scene_by_id(s2.id).act == "Act Two"
    summaries = _act_summaries(db, proj.id)
    assert summaries.get("Beginning") == "First act"
    assert "Act One" not in summaries


def test_rename_chapter_updates_scenes_and_summary():
    db, proj = _make_project()
    s1 = db.create_scene(proj.id, "Scene 1", chapter="Ch 1")
    s2 = db.create_scene(proj.id, "Scene 2", chapter="Ch 2")
    _save_chapter_summary(db, proj.id, "Ch 1", "Opening")

    _rename_chapter(db, proj.id, "Ch 1", "Prologue")

    assert db.get_scene_by_id(s1.id).chapter == "Prologue"
    assert db.get_scene_by_id(s2.id).chapter == "Ch 2"
    assert _chapter_summaries(db, proj.id).get("Prologue") == "Opening"


def test_delete_act_clears_scene_labels():
    db, proj = _make_project()
    s1 = db.create_scene(proj.id, "Scene 1", act="Act One")
    s2 = db.create_scene(proj.id, "Scene 2", act="Act Two")
    _save_act_summary(db, proj.id, "Act One", "Notes")

    _delete_act(db, proj.id, "Act One")

    assert db.get_scene_by_id(s1.id).act == ""
    assert db.get_scene_by_id(s2.id).act == "Act Two"
    assert "Act One" not in _act_summaries(db, proj.id)


def test_delete_chapter_clears_scene_labels():
    db, proj = _make_project()
    s1 = db.create_scene(proj.id, "Scene 1", chapter="Ch 1")
    s2 = db.create_scene(proj.id, "Scene 2", chapter="Ch 2")

    _delete_chapter(db, proj.id, "Ch 1")

    assert db.get_scene_by_id(s1.id).chapter == ""
    assert db.get_scene_by_id(s2.id).chapter == "Ch 2"


# -- Widget tests -----------------------------------------------------------

def test_plan_view_constructs_empty():
    QApplication.instance() or QApplication([])
    db, proj = _make_project()
    view = PlanView(db, proj.id)
    assert view is not None


def test_plan_view_renders_tree():
    QApplication.instance() or QApplication([])
    db, proj = _make_project()
    db.create_scene(proj.id, "S1", act="One", chapter="A")
    db.create_scene(proj.id, "S2", act="One", chapter="A")
    db.create_scene(proj.id, "S3", act="Two", chapter="B")
    view = PlanView(db, proj.id)
    assert view._content_layout.count() > 0


def test_plan_view_data_changed_callback():
    QApplication.instance() or QApplication([])
    db, proj = _make_project()
    calls: list[int] = []
    view = PlanView(db, proj.id, on_data_changed=lambda: calls.append(1))
    s = db.create_scene(proj.id, "S1")
    view._save_scene_summary(s.id, "Updated summary")
    assert len(calls) == 1
    assert db.get_scene_by_id(s.id).summary == "Updated summary"


def test_plan_view_save_act_summary_uses_storage_key():
    QApplication.instance() or QApplication([])
    db, proj = _make_project()
    db.create_scene(proj.id, "S1", act="My Act")
    view = PlanView(db, proj.id)
    view._save_act_summary("My Act", "An act summary")
    assert _act_summaries(db, proj.id)["My Act"] == "An act summary"


def test_plan_view_untitled_act_summary_stored_under_empty_key():
    QApplication.instance() or QApplication([])
    db, proj = _make_project()
    db.create_scene(proj.id, "S1")
    view = PlanView(db, proj.id)
    view._save_act_summary(_UNTITLED_ACT, "Loose scenes")
    assert _act_summaries(db, proj.id)[""] == "Loose scenes"


# -- Sidebar grouping --------------------------------------------------------

def test_main_window_has_outline_button():
    from storyplanner.ui.main_window import MainWindow
    QApplication.instance() or QApplication([])
    db, proj = _make_project()
    win = MainWindow(db, proj.id)
    assert "Outline" in win.sidebar_buttons


def test_main_window_plan_group_contains_planning_views():
    from storyplanner.ui.main_window import MainWindow
    QApplication.instance() or QApplication([])
    db, proj = _make_project()
    win = MainWindow(db, proj.id)
    for label in ("Outline", "Scenes", "Timeline", "Grid", "Plot"):
        assert label in win.sidebar_buttons, f"{label} missing from sidebar"


def test_old_plan_label_removed():
    """After merge, sidebar uses 'Outline' (not 'Plan') as the entry."""
    from storyplanner.ui.main_window import MainWindow
    QApplication.instance() or QApplication([])
    db, proj = _make_project()
    win = MainWindow(db, proj.id)
    assert "Plan" not in win.sidebar_buttons


# -- View modes --------------------------------------------------------------

def test_plan_view_default_mode_is_list():
    QApplication.instance() or QApplication([])
    db, proj = _make_project()
    view = PlanView(db, proj.id)
    assert view._view_mode == "list"
    assert view._stack.currentIndex() == 0


def test_plan_view_switch_to_grid():
    QApplication.instance() or QApplication([])
    db, proj = _make_project()
    db.create_scene(proj.id, "S1", act="One", chapter="A")
    db.create_scene(proj.id, "S2", act="One", chapter="B")
    view = PlanView(db, proj.id)
    view._set_view_mode("grid")
    assert view._view_mode == "grid"
    assert view._stack.currentIndex() == 1


def test_plan_view_switch_to_matrix():
    QApplication.instance() or QApplication([])
    db, proj = _make_project()
    db.create_scene(proj.id, "S1", act="One", chapter="A")
    view = PlanView(db, proj.id)
    view._set_view_mode("matrix")
    assert view._view_mode == "matrix"
    assert view._stack.currentIndex() == 2


def test_grid_view_shows_one_card_per_scene():
    QApplication.instance() or QApplication([])
    db, proj = _make_project()
    db.create_scene(proj.id, "S1", act="One", chapter="A")
    db.create_scene(proj.id, "S2", act="One", chapter="B")
    db.create_scene(proj.id, "S3", act="Two", chapter="C")
    view = PlanView(db, proj.id)
    view._set_view_mode("grid")
    assert view._grid_widget is not None
    assert view._grid_widget.count() == 3


def test_grid_view_uses_flat_4_column_icon_mode():
    from PySide6.QtWidgets import QListView, QAbstractItemView
    QApplication.instance() or QApplication([])
    db, proj = _make_project()
    db.create_scene(proj.id, "S1")
    view = PlanView(db, proj.id)
    view._set_view_mode("grid")
    grid = view._grid_widget
    assert grid.viewMode() == QListView.ViewMode.IconMode
    assert grid.isWrapping()
    assert grid.flow() == QListView.Flow.LeftToRight
    assert grid.dragDropMode() == QAbstractItemView.DragDropMode.InternalMove


def test_grid_view_cards_carry_scene_ids():
    from PySide6.QtCore import Qt
    QApplication.instance() or QApplication([])
    db, proj = _make_project()
    s1 = db.create_scene(proj.id, "First")
    s2 = db.create_scene(proj.id, "Second")
    view = PlanView(db, proj.id)
    view._set_view_mode("grid")
    ids = [
        view._grid_widget.item(i).data(Qt.ItemDataRole.UserRole)
        for i in range(view._grid_widget.count())
    ]
    assert ids == [s1.id, s2.id]


def test_grid_view_shows_same_scenes_as_db():
    """Grid blocks must mirror db.get_all_scenes — the Outline is the source of truth."""
    QApplication.instance() or QApplication([])
    db, proj = _make_project()
    db.create_scene(proj.id, "From Plan", act="One", chapter="A")
    db.create_scene(proj.id, "Direct DB", act="Two", chapter="B")
    view = PlanView(db, proj.id)
    view._set_view_mode("grid")
    db_count = len(db.get_all_scenes(proj.id))
    assert view._grid_widget.count() == db_count


def test_grid_view_empty_state_shows_message():
    QApplication.instance() or QApplication([])
    db, proj = _make_project()
    view = PlanView(db, proj.id)
    view._set_view_mode("grid")
    assert view._grid_widget is None
    assert view._grid_layout.count() == 1


def test_matrix_view_has_act_rows_and_chapter_columns():
    QApplication.instance() or QApplication([])
    db, proj = _make_project()
    db.create_scene(proj.id, "S1", act="Act One", chapter="Ch 1")
    db.create_scene(proj.id, "S2", act="Act Two", chapter="Ch 2")
    view = PlanView(db, proj.id)
    view._set_view_mode("matrix")
    # 1 corner + 2 chapter headers + 2 act rows × (1 row label + 2 cells) = 9
    assert view._matrix_layout.count() == 9


def test_grid_reorder_persists_new_order():
    QApplication.instance() or QApplication([])
    db, proj = _make_project()
    s1 = db.create_scene(proj.id, "First")
    s2 = db.create_scene(proj.id, "Second")
    s3 = db.create_scene(proj.id, "Third")
    view = PlanView(db, proj.id)
    view._on_grid_reordered([s3.id, s1.id, s2.id])
    ordered = db.get_all_scenes(proj.id)
    assert [s.id for s in ordered] == [s3.id, s1.id, s2.id]


def test_grid_reorder_does_not_drop_or_dup_scenes():
    """After a reorder, every original scene must still exist exactly once."""
    QApplication.instance() or QApplication([])
    db, proj = _make_project()
    ids = [
        db.create_scene(proj.id, f"Scene {i}").id
        for i in range(5)
    ]
    view = PlanView(db, proj.id)
    new_order = list(reversed(ids))
    view._on_grid_reordered(new_order)
    after = [s.id for s in db.get_all_scenes(proj.id)]
    assert sorted(after) == sorted(ids)
    assert after == new_order


# -- Cross-section linking ---------------------------------------------------

def test_scene_added_in_plan_appears_in_get_all_scenes():
    QApplication.instance() or QApplication([])
    db, proj = _make_project()
    view = PlanView(db, proj.id)
    initial = len(db.get_all_scenes(proj.id))
    db.create_scene(proj.id, "Through Plan", act="One", chapter="A")
    view.refresh()
    assert len(db.get_all_scenes(proj.id)) == initial + 1


def test_rename_act_propagates_to_scene_records():
    db, proj = _make_project()
    s1 = db.create_scene(proj.id, "S1", act="Old Act")
    s2 = db.create_scene(proj.id, "S2", act="Old Act")
    _rename_act(db, proj.id, "Old Act", "New Act")
    for scene_id in (s1.id, s2.id):
        assert db.get_scene_by_id(scene_id).act == "New Act"


def test_rename_chapter_propagates_to_scenes_view_data():
    db, proj = _make_project()
    s1 = db.create_scene(proj.id, "S1", chapter="Old Ch")
    _rename_chapter(db, proj.id, "Old Ch", "New Ch")
    chapters = db.get_scene_chapters(proj.id)
    assert "New Ch" in chapters
    assert "Old Ch" not in chapters
    assert db.get_scene_by_id(s1.id).chapter == "New Ch"


def test_delete_act_clears_label_visible_to_other_views():
    db, proj = _make_project()
    s1 = db.create_scene(proj.id, "S1", act="Act One")
    s2 = db.create_scene(proj.id, "S2", act="Act Two")
    _delete_act(db, proj.id, "Act One")
    fresh = {s.id: s for s in db.get_all_scenes(proj.id)}
    assert fresh[s1.id].act == ""
    assert fresh[s2.id].act == "Act Two"


def test_scene_summary_change_visible_through_db():
    QApplication.instance() or QApplication([])
    db, proj = _make_project()
    s = db.create_scene(proj.id, "S1")
    view = PlanView(db, proj.id)
    view._save_scene_summary(s.id, "Plan-edited summary")
    assert db.get_scene_by_id(s.id).summary == "Plan-edited summary"


# -- Quantum influence -------------------------------------------------------

def test_outline_mode_badge_default_classical():
    QApplication.instance() or QApplication([])
    db, proj = _make_project()
    view = PlanView(db, proj.id)
    assert view._mode_badge.text() == "Classical"


def test_outline_mode_badge_reflects_lambda():
    from storyplanner.quantum_outliner.state import (
        OutlineMode, get_state, reset_state,
    )
    QApplication.instance() or QApplication([])
    db, proj = _make_project()
    reset_state(proj.id)
    state = get_state(proj.id)
    state.outline_mode = OutlineMode.LAMBDA
    view = PlanView(db, proj.id)
    assert "Lambda" in view._mode_badge.text()
    reset_state(proj.id)
