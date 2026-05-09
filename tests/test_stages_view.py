"""Tests for StagesView UI: nav, tree rendering, action flow."""

from storyplanner.db import Database
from storyplanner.stages import capture_scope, save_snapshot
from storyplanner.ui.main_window import MainWindow
from storyplanner.ui.stages_view import StagesView


def _setup():
    db = Database()
    proj = db.create_project("StagesUITest")
    return db, proj


# -- Navigation --------------------------------------------------------------

def test_stages_button_in_sidebar():
    db, proj = _setup()
    win = MainWindow(db, proj.id)
    assert "Stages" in win.sidebar_buttons


def test_stages_in_nav_labels():
    db, proj = _setup()
    win = MainWindow(db, proj.id)
    assert "Stages" in win._nav_labels


def test_show_stages_swaps_central_view():
    db, proj = _setup()
    win = MainWindow(db, proj.id)
    win._show_stages()
    assert isinstance(win.content_area, StagesView)


# -- Tree rendering ---------------------------------------------------------

def test_tree_lists_existing_stages():
    db, proj = _setup()
    db.create_stage(proj.id, "Draft 1")
    db.create_stage(proj.id, "Draft 2")
    view = StagesView(db, proj.id)
    # 2 root items expected
    root = view._tree.invisibleRootItem()
    assert root.childCount() == 2


def test_tree_nests_child_stages():
    db, proj = _setup()
    parent = db.create_stage(proj.id, "Parent")
    db.create_stage(proj.id, "Child", parent_stage_id=parent.id)
    view = StagesView(db, proj.id)
    root = view._tree.invisibleRootItem()
    parent_item = root.child(0)
    assert parent_item.childCount() == 1
    assert parent_item.child(0).text(0) == "Child"


# -- Snapshot action --------------------------------------------------------

def test_snapshot_action_creates_snapshot():
    db, proj = _setup()
    scene = db.create_scene(proj.id, "S1", content="hello")
    stage = db.create_stage(
        proj.id, "St", scope_type="scene", scope_id=scene.id,
    )
    view = StagesView(db, proj.id)
    view._selected_stage_id = stage.id
    view._on_take_snapshot()
    assert len(db.get_stage_snapshots(stage.id)) == 1


def test_snapshot_without_selection_shows_message():
    db, proj = _setup()
    view = StagesView(db, proj.id)
    view._selected_stage_id = None
    view._on_take_snapshot()
    assert "Select" in view._restore_status.text()


# -- Restore confirmation flow ----------------------------------------------

def test_restore_requires_two_clicks():
    db, proj = _setup()
    scene = db.create_scene(proj.id, "S1", content="original")
    stage = db.create_stage(
        proj.id, "St", scope_type="scene", scope_id=scene.id,
    )
    snap = save_snapshot(
        db, stage.id, capture_scope(db, proj.id, "scene", scene.id),
    )
    db.update_scene_content(scene.id, "edited")
    view = StagesView(db, proj.id)
    view._selected_stage_id = stage.id
    view._selected_snapshot_id = snap.id

    view._on_restore()
    # First click: scene unchanged, confirm button visible
    assert db.get_scene_by_id(scene.id).content == "edited"
    assert view._confirm_btn.isVisible() or view._pending_restore_snapshot_id == snap.id

    view._on_confirm_restore()
    # After confirm: scene restored
    assert db.get_scene_by_id(scene.id).content == "original"


def test_restore_creates_safety_snapshot():
    db, proj = _setup()
    scene = db.create_scene(proj.id, "S1", content="original")
    stage = db.create_stage(
        proj.id, "St", scope_type="scene", scope_id=scene.id,
    )
    snap = save_snapshot(
        db, stage.id, capture_scope(db, proj.id, "scene", scene.id),
    )
    db.update_scene_content(scene.id, "current state")
    view = StagesView(db, proj.id)
    view._selected_stage_id = stage.id
    view._selected_snapshot_id = snap.id
    view._on_restore()
    view._on_confirm_restore()
    safety_stages = [
        s for s in db.get_all_stages(proj.id) if s.name == "Safety (auto)"
    ]
    assert len(safety_stages) == 1
    safety_snaps = db.get_stage_snapshots(safety_stages[0].id)
    assert len(safety_snaps) == 1
    assert "current state" in safety_snaps[0].data_json


# -- Compare action ---------------------------------------------------------

def test_compare_action_renders_diff():
    db, proj = _setup()
    scene = db.create_scene(proj.id, "S1", content="version 1")
    stage = db.create_stage(
        proj.id, "St", scope_type="scene", scope_id=scene.id,
    )
    snap = save_snapshot(
        db, stage.id, capture_scope(db, proj.id, "scene", scene.id),
    )
    db.update_scene_content(scene.id, "version 2")
    view = StagesView(db, proj.id)
    view._selected_stage_id = stage.id
    view._selected_snapshot_id = snap.id
    view._on_compare()
    diff_text = view._diff_view.toPlainText()
    assert "version 1" in diff_text
    assert "version 2" in diff_text


# -- Status change ----------------------------------------------------------

def test_status_change_persists():
    db, proj = _setup()
    stage = db.create_stage(proj.id, "X", scope_type="project", status="alternate")
    view = StagesView(db, proj.id)
    # select that stage
    view._selected_stage_id = stage.id
    idx = view._status_combo.findData("canonical")
    view._status_combo.setCurrentIndex(idx)
    # currentIndexChanged triggered _on_status_change
    fetched = db.get_stage(stage.id)
    assert fetched.status == "canonical"


# -- Reload from new view -----------------------------------------------------

def test_stages_persist_across_view_recreation():
    db, proj = _setup()
    db.create_stage(proj.id, "Persisted")
    view1 = StagesView(db, proj.id)
    assert view1._tree.invisibleRootItem().childCount() == 1
    view2 = StagesView(db, proj.id)
    assert view2._tree.invisibleRootItem().childCount() == 1
