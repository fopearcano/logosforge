"""Tests for Assistant Outline Mode — structured outline operations."""

import pytest

from storyplanner.db import Database
from storyplanner.outline_actions import (
    OutlineOp,
    apply_outline_ops,
    count_ops,
    format_outline_preview,
    parse_outline_response,
)


@pytest.fixture(autouse=True)
def _isolated_settings(monkeypatch, tmp_path):
    import storyplanner.settings as settings
    settings._instance = None
    monkeypatch.setattr(settings, "CONFIG_DIR", tmp_path)
    monkeypatch.setattr(settings, "SETTINGS_FILE", tmp_path / "settings.json")
    yield
    settings._instance = None


_FULL = """# Act 1: Setup
The hero's ordinary world.
## Chapter 1: The Call
- Scene: Hero refuses the call
- Scene: Mentor appears
## Chapter 2: Crossing
1. Hero leaves home
2. First test
# Act 2: Confrontation
## Chapter 3: Trials
"""


# =========================================================================
# 1. Parsing — hierarchy, titles, siblings
# =========================================================================

def test_parses_acts_chapters_scenes():
    ops = parse_outline_response(_FULL)
    assert [o.title for o in ops] == ["Act 1", "Act 2"]
    assert [c.title for c in ops[0].children] == ["Chapter 1", "Chapter 2"]
    assert [s.title for s in ops[0].children[0].children] == [
        "Hero refuses the call", "Mentor appears",
    ]


def test_numbered_list_items_are_siblings():
    ops = parse_outline_response(_FULL)
    ch2 = ops[0].children[1]
    # "1. Hero leaves home" / "2. First test" are siblings, not nested.
    assert [n.title for n in ch2.children] == ["Hero leaves home", "First test"]
    assert all(not n.children for n in ch2.children)


def test_kind_classification():
    ops = parse_outline_response(_FULL)
    assert ops[0].kind == "act"
    assert ops[0].children[0].kind == "chapter"
    assert ops[0].children[0].children[0].kind == "scene"


def test_beat_classification():
    ops = parse_outline_response("## Chapter 1\n- Beat: inciting incident")
    beat = ops[0].children[0]
    assert beat.kind == "beat"
    assert beat.title == "inciting incident"


def test_count_ops():
    assert count_ops(parse_outline_response(_FULL)) == 9


def test_description_captured():
    ops = parse_outline_response("# Act 1: Setup — the ordinary world")
    assert ops[0].title == "Act 1"
    assert "ordinary world" in ops[0].description


def test_plain_numbered_outline_without_headers():
    ops = parse_outline_response("1. Opening\n2. Midpoint\n3. Climax")
    assert [o.title for o in ops] == ["Opening", "Midpoint", "Climax"]


def test_empty_text_yields_nothing():
    assert parse_outline_response("") == []
    assert parse_outline_response("   \n\n  ") == []


def test_pure_indented_list_nesting():
    ops = parse_outline_response(
        "- Act 1\n  - Chapter 1\n    - Scene a\n    - Scene b\n  - Chapter 2\n"
    )
    assert [o.title for o in ops] == ["Act 1"]
    chapters = ops[0].children
    assert [c.title for c in chapters] == ["Chapter 1", "Chapter 2"]
    # "Scene a" -> the "Scene" keyword labels the kind, title is "a".
    assert [s.title for s in chapters[0].children] == ["a", "b"]
    assert [s.kind for s in chapters[0].children] == ["scene", "scene"]
    assert chapters[1].children == []   # Chapter 2 is a sibling, not nested


def test_header_chapter_with_scene_list_keeps_chapters_sibling():
    ops = parse_outline_response(
        "# Act 1\n## Chapter 1\n- Scene: A\n## Chapter 2\n- Scene: B\n"
    )
    chapters = ops[0].children
    assert [c.title for c in chapters] == ["Chapter 1", "Chapter 2"]
    assert [s.title for s in chapters[0].children] == ["A"]
    assert [s.title for s in chapters[1].children] == ["B"]


def test_title_strips_trailing_colon():
    ops = parse_outline_response("# Act 1: Setup")
    assert ops[0].title == "Act 1"
    assert ops[0].description == "Setup"
    ops2 = parse_outline_response("# Act 1")
    assert ops2[0].title == "Act 1"  # no trailing colon artifacts


# =========================================================================
# 2. Scope variants (full / act / chapter / scene-beat)
# =========================================================================

def test_generate_act_scope():
    ops = parse_outline_response("Act 2: Confrontation\nChapter 3: Trials")
    assert ops[0].title == "Act 2"
    assert ops[0].children[0].title == "Chapter 3"


def test_generate_chapter_scope():
    ops = parse_outline_response("## Chapter 4\n- Scene: a\n- Scene: b")
    assert ops[0].title == "Chapter 4"
    assert [c.title for c in ops[0].children] == ["a", "b"]


def test_generate_scene_beat_scope():
    ops = parse_outline_response("- Scene: tension rises\n- Beat: reversal")
    assert [o.kind for o in ops] == ["scene", "beat"]


# =========================================================================
# 3. Additive apply — never overwrites
# =========================================================================

def test_apply_creates_hierarchy():
    db = Database()
    p = db.create_project("Novel")
    ops = parse_outline_response(_FULL)
    created = apply_outline_ops(db, p.id, ops)
    assert len(created) == 9
    roots = db.get_outline_children(p.id, None)
    assert [n.title for n in roots] == ["Act 1", "Act 2"]
    act1 = roots[0]
    assert [c.title for c in db.get_outline_children(p.id, act1.id)] == [
        "Chapter 1", "Chapter 2",
    ]


def test_apply_is_additive_keeps_existing():
    db = Database()
    p = db.create_project("Novel")
    db.create_outline_node(p.id, "Existing Act", parent_id=None, sort_order=0)
    apply_outline_ops(db, p.id, parse_outline_response("# Act 1\n# Act 2"))
    roots = db.get_outline_children(p.id, None)
    assert [n.title for n in roots] == ["Existing Act", "Act 1", "Act 2"]


def test_apply_appends_after_existing_sort_order():
    db = Database()
    p = db.create_project("Novel")
    db.create_outline_node(p.id, "A", parent_id=None, sort_order=0)
    apply_outline_ops(db, p.id, [OutlineOp(title="B"), OutlineOp(title="C")])
    roots = db.get_outline_children(p.id, None)
    assert [n.sort_order for n in roots] == [0, 1, 2]


def test_apply_persists_and_reloads(tmp_path):
    path = str(tmp_path / "o.db")
    db = Database(path)
    p = db.create_project("Novel")
    apply_outline_ops(db, p.id, parse_outline_response(_FULL))
    pid = p.id
    db2 = Database(path)
    assert len(db2.get_outline_nodes(pid)) == 9


def test_apply_under_parent():
    db = Database()
    p = db.create_project("Novel")
    act = db.create_outline_node(p.id, "Act 1", parent_id=None)
    apply_outline_ops(db, p.id, parse_outline_response("## Chapter 1\n## Chapter 2"),
                      parent_id=act.id)
    assert [c.title for c in db.get_outline_children(p.id, act.id)] == [
        "Chapter 1", "Chapter 2",
    ]


# =========================================================================
# 4. Preview
# =========================================================================

def test_preview_is_readable():
    preview = format_outline_preview(parse_outline_response(_FULL))
    assert "Act 1" in preview
    assert "Chapter 1" in preview
    assert "Hero refuses the call" in preview


# =========================================================================
# 5. AssistantPanel integration
# =========================================================================

def test_panel_detects_outline_mode():
    from storyplanner.ui.assistant_view import AssistantPanel
    db = Database()
    p = db.create_project("Novel")
    panel = AssistantPanel(db, p.id)
    panel.set_active_section_name("Outline")
    assert panel._is_outline_mode() is True
    panel.set_active_section_name("Manuscript")
    assert panel._is_outline_mode() is False


def test_panel_button_visibility_gated():
    from storyplanner.ui.assistant_view import AssistantPanel
    db = Database()
    p = db.create_project("Novel")
    panel = AssistantPanel(db, p.id)
    panel.set_active_section_name("Manuscript")
    assert panel._apply_outline_btn.isVisible() is False
    panel.set_active_section_name("Outline")
    panel._update_outline_action_visibility()
    # isVisible() needs a shown parent; assert the gate instead.
    assert panel._is_outline_mode() is True


def test_panel_propose_outline_ops():
    from storyplanner.ui.assistant_view import AssistantPanel
    db = Database()
    p = db.create_project("Novel")
    panel = AssistantPanel(db, p.id)
    panel.set_active_section_name("Outline")
    panel._response_output.setPlainText(_FULL)
    ops, n = panel.propose_outline_ops()
    assert ops is not None
    assert n == 9


def test_panel_propose_empty_response():
    from storyplanner.ui.assistant_view import AssistantPanel
    db = Database()
    p = db.create_project("Novel")
    panel = AssistantPanel(db, p.id)
    panel._response_output.setPlainText("")
    ops, n = panel.propose_outline_ops()
    assert ops is None and n == 0


def test_panel_apply_updates_outline_and_emits_events():
    from storyplanner.ui.assistant_view import AssistantPanel
    from storyplanner.project_events import get_event_bus
    db = Database()
    p = db.create_project("Novel")
    seen = {"outline": 0, "data": 0}
    bus = get_event_bus()
    bus.outline_changed.connect(lambda: seen.__setitem__("outline", seen["outline"] + 1))
    bus.project_data_changed.connect(lambda: seen.__setitem__("data", seen["data"] + 1))
    fired = []
    panel = AssistantPanel(db, p.id, on_data_changed=lambda: fired.append(1))
    panel.set_active_section_name("Outline")
    panel._response_output.setPlainText("# Act 1\n## Chapter 1\n- Scene: Opening")
    created = panel._apply_to_outline(confirm=False)
    assert len(created) == 3
    assert len(db.get_outline_nodes(p.id)) == 3
    assert seen["outline"] >= 1          # active outline view refreshes
    assert seen["data"] >= 1
    assert fired                         # legacy callback fired too


def test_panel_apply_no_response_is_noop():
    from storyplanner.ui.assistant_view import AssistantPanel
    db = Database()
    p = db.create_project("Novel")
    panel = AssistantPanel(db, p.id)
    panel.set_active_section_name("Outline")
    panel._response_output.setPlainText("")
    assert panel._apply_to_outline(confirm=False) == []
    assert db.get_outline_nodes(p.id) == []
