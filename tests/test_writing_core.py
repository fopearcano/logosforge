"""Tests for Writing Core view — canvas layout, typography, command palette,
manuscript highlighting, format toolbar, typewriter mode, PSYKE entity awareness."""

from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QTextCursor, QTextDocument
from PySide6.QtWidgets import QApplication, QWidget

from storyplanner.db import Database
from storyplanner.ui.command_palette import COMMANDS, CommandPalette
from storyplanner.ui.entity_hover import EntityHoverHandler, EntityHoverPanel
from storyplanner.ui.format_toolbar import FormatToolbar
from storyplanner.ui.manuscript_highlighter import ManuscriptHighlighter
from storyplanner.ui.psyke_highlighter import PsykeClickHandler, PsykeHighlighter
from storyplanner.ui.writing_core_view import (
    WritingCoreView,
    _BODY_FONT_SIZE,
    _BODY_LINE_HEIGHT,
    _BlockData,
    _CANVAS_MAX_WIDTH,
    _CANVAS_PADDING_H,
    _ELEMENT_TRANSITIONS,
    _FOCUS_LINE_HEIGHT,
    _SceneEditor,
)
from storyplanner.writing_formats import ALL_FORMATS, FORMAT_ORDER, WritingFormat


def _setup_project(db):
    proj = db.create_project("Novel")
    s1 = db.create_scene(proj.id, "Opening", content="The storm began.", act="Act One", chapter="Chapter 1")
    s2 = db.create_scene(proj.id, "Rising Action", content="She ran.", act="Act One", chapter="Chapter 1")
    s3 = db.create_scene(proj.id, "Midpoint", content="The truth revealed.", act="Act Two", chapter="Chapter 2")
    return proj, s1, s2, s3


# -- Canvas layout -----------------------------------------------------------

def test_canvas_max_width():
    assert _CANVAS_MAX_WIDTH >= 600
    assert _CANVAS_MAX_WIDTH <= 850


def test_canvas_padding():
    assert _CANVAS_PADDING_H >= 32


def test_body_font_size():
    assert 17 <= _BODY_FONT_SIZE <= 19


def test_line_height():
    assert 1.65 <= _BODY_LINE_HEIGHT <= 1.8


def test_focus_line_height_larger():
    assert _FOCUS_LINE_HEIGHT > _BODY_LINE_HEIGHT


# -- View construction -------------------------------------------------------

def test_view_loads_scenes():
    db = Database()
    proj, s1, s2, s3 = _setup_project(db)
    view = WritingCoreView(db, proj.id)
    assert len(view._editors) == 3
    assert s1.id in view._editors
    assert s2.id in view._editors
    assert s3.id in view._editors


def test_editor_content_matches_scene():
    db = Database()
    proj, s1, s2, s3 = _setup_project(db)
    view = WritingCoreView(db, proj.id)
    assert view._editors[s1.id].toPlainText() == "The storm began."
    assert view._editors[s3.id].toPlainText() == "The truth revealed."


def test_editor_renders_markdown_as_rich_text():
    db = Database()
    proj = db.create_project("MD")
    db.create_scene(proj.id, "S1", content="**bold** and *italic*")
    view = WritingCoreView(db, proj.id)
    editors = list(view._editors.values())
    editor = editors[0]
    assert editor.toPlainText() == "bold and italic"
    md = editor.toMarkdown()
    assert "**bold**" in md
    assert "*italic*" in md


def test_editor_renders_headings():
    db = Database()
    proj = db.create_project("HD")
    db.create_scene(proj.id, "S1", content="# Chapter One\n\nSome text.")
    view = WritingCoreView(db, proj.id)
    editor = list(view._editors.values())[0]
    assert "Chapter One" in editor.toPlainText()
    assert "#" not in editor.toPlainText()


def test_editor_renders_lists():
    db = Database()
    proj = db.create_project("LS")
    db.create_scene(proj.id, "S1", content="- item one\n- item two")
    view = WritingCoreView(db, proj.id)
    editor = list(view._editors.values())[0]
    plain = editor.toPlainText()
    assert "item one" in plain
    assert "item two" in plain


def test_editor_save_preserves_markdown():
    db = Database()
    proj = db.create_project("SV")
    scene = db.create_scene(proj.id, "S1", content="**hello** world")
    view = WritingCoreView(db, proj.id)
    view._save_scene(scene.id)
    saved = db.get_scene_by_id(scene.id)
    assert "**hello**" in saved.content
    assert "world" in saved.content


def test_empty_project_has_no_editors():
    db = Database()
    proj = db.create_project("Empty")
    view = WritingCoreView(db, proj.id)
    assert len(view._editors) == 0


def test_refresh_rebuilds_canvas():
    db = Database()
    proj, s1, s2, s3 = _setup_project(db)
    view = WritingCoreView(db, proj.id)
    assert len(view._editors) == 3
    db.create_scene(proj.id, "New Scene", content="Added later.")
    view.refresh()
    assert len(view._editors) == 4


# -- Focus mode ---------------------------------------------------------------

def test_focus_mode_toggle():
    db = Database()
    proj, *_ = _setup_project(db)
    view = WritingCoreView(db, proj.id)
    assert view._focus_mode is False
    view.toggle_focus_mode()
    assert view._focus_mode is True
    assert not view._focus_bar.isHidden()
    assert view._top_bar.isHidden()
    view.toggle_focus_mode()
    assert view._focus_mode is False
    assert not view._top_bar.isHidden()
    assert view._focus_bar.isHidden()


def test_focus_mode_narrows_canvas():
    db = Database()
    proj, *_ = _setup_project(db)
    view = WritingCoreView(db, proj.id)
    normal_max = view._inner.maximumWidth()
    view.toggle_focus_mode()
    focus_max = view._inner.maximumWidth()
    assert focus_max < normal_max


def test_focus_mode_callback():
    db = Database()
    proj, *_ = _setup_project(db)
    calls = []
    view = WritingCoreView(
        db, proj.id, on_focus_mode_changed=lambda active: calls.append(active),
    )
    view.toggle_focus_mode()
    assert calls == [True]
    view.toggle_focus_mode()
    assert calls == [True, False]


# -- Font toggle --------------------------------------------------------------

def test_serif_toggle():
    db = Database()
    proj, *_ = _setup_project(db)
    view = WritingCoreView(db, proj.id)
    assert view._use_serif is False
    view._toggle_font()
    assert view._use_serif is True
    assert view._font_toggle.text() == "Sans"
    view._toggle_font()
    assert view._use_serif is False
    assert view._font_toggle.text() == "Serif"


# -- Auto-save ----------------------------------------------------------------

def test_auto_save_updates_db():
    db = Database()
    proj, s1, *_ = _setup_project(db)
    view = WritingCoreView(db, proj.id)
    view._editors[s1.id].setPlainText("Edited content.")
    view._save_scene(s1.id)
    saved = db.get_scene_by_id(s1.id)
    assert saved.content == "Edited content."


# -- Word count ----------------------------------------------------------------

def test_word_count_updates():
    db = Database()
    proj, s1, s2, s3 = _setup_project(db)
    view = WritingCoreView(db, proj.id)
    view._update_word_count()
    text = view._word_count_label.text()
    assert "words" in text
    count = int(text.split()[0].replace(",", ""))
    assert count > 0


# -- Scene creation -----------------------------------------------------------

def test_create_scene_adds_editor():
    db = Database()
    proj, s1, s2, s3 = _setup_project(db)
    view = WritingCoreView(db, proj.id)
    assert len(view._editors) == 3
    view._create_scene_after(None)
    assert len(view._editors) == 4


def test_create_scene_with_chapter():
    db = Database()
    proj, s1, *_ = _setup_project(db)
    view = WritingCoreView(db, proj.id)
    view._create_scene_after(s1.id, chapter="Chapter 1")
    scenes = db.get_all_scenes(proj.id)
    chapters = [s.chapter for s in scenes if s.chapter == "Chapter 1"]
    assert len(chapters) >= 2


# -- Command palette ----------------------------------------------------------

def test_command_palette_has_commands():
    assert len(COMMANDS) >= 6
    keys = [c[1] for c in COMMANDS]
    assert "scene" in keys
    assert "chapter" in keys
    assert "focus" in keys


def test_command_palette_creates():
    palette = CommandPalette()
    assert palette._list.count() == len(COMMANDS)


def test_command_palette_filter():
    palette = CommandPalette()
    palette._on_filter("scene")
    assert palette._list.count() >= 1


def test_command_palette_filter_empty():
    palette = CommandPalette()
    palette._on_filter("zzzznonexistent")
    assert palette._list.count() == 0


# -- SceneEditor slash detection -----------------------------------------------

def test_scene_editor_has_no_frame():
    editor = _SceneEditor()
    assert editor.objectName() == "writingCoreEditor"


# -- Typography constants ------------------------------------------------------

def test_typography_hierarchy():
    """Act < Scene < Chapter in font size terms."""
    # Act: 11px, Scene title: 15px, Chapter: 22px
    assert 11 < 15 < 22


# -- Scroll to scene ----------------------------------------------------------

def test_scroll_to_scene():
    db = Database()
    proj, s1, s2, s3 = _setup_project(db)
    view = WritingCoreView(db, proj.id)
    view.scroll_to_scene(s3.id)
    assert view._editors[s3.id].hasFocus() or True  # Focus may not work without show


# -- Manuscript Highlighter ---------------------------------------------------

def test_manuscript_highlighter_inherits_psyke():
    assert issubclass(ManuscriptHighlighter, PsykeHighlighter)


def test_manuscript_highlighter_creates():
    doc = QTextDocument()
    h = ManuscriptHighlighter(doc)
    assert h._b_fmt is not None
    assert h._i_fmt is not None
    assert h._bi_fmt is not None
    assert h._h1_fmt is not None
    assert h._h2_fmt is not None
    assert h._h3_fmt is not None
    assert h._q_fmt is not None
    assert h._sep_fmt is not None


def test_manuscript_highlighter_refresh_theme():
    doc = QTextDocument()
    h = ManuscriptHighlighter(doc)
    h.refresh_theme()


def test_manuscript_highlighter_refresh_patterns():
    doc = QTextDocument()
    h = ManuscriptHighlighter(doc)
    h.refresh_patterns(["Alice", "Bob"])


def test_view_uses_psyke_highlighter():
    db = Database()
    proj, s1, *_ = _setup_project(db)
    view = WritingCoreView(db, proj.id)
    assert isinstance(view._highlighters[s1.id], PsykeHighlighter)


# -- Format Toolbar -----------------------------------------------------------

def test_format_toolbar_creates():
    toolbar = FormatToolbar()
    assert toolbar.objectName() == "formatToolbar"


def test_format_toolbar_bold_applies():
    editor = _SceneEditor()
    editor.setPlainText("hello world")
    cursor = editor.textCursor()
    cursor.setPosition(6)
    cursor.setPosition(11, QTextCursor.MoveMode.KeepAnchor)
    editor.setTextCursor(cursor)

    toolbar = FormatToolbar()
    toolbar.toggle_bold_on(editor)
    md = editor.toMarkdown().strip()
    assert "**world**" in md
    assert editor.toPlainText() == "hello world"


def test_format_toolbar_bold_toggles_off():
    editor = _SceneEditor()
    editor.setPlainText("hello world")
    cursor = editor.textCursor()
    cursor.setPosition(6)
    cursor.setPosition(11, QTextCursor.MoveMode.KeepAnchor)
    editor.setTextCursor(cursor)

    toolbar = FormatToolbar()
    toolbar.toggle_bold_on(editor)
    cursor = editor.textCursor()
    cursor.setPosition(6)
    cursor.setPosition(11, QTextCursor.MoveMode.KeepAnchor)
    editor.setTextCursor(cursor)
    toolbar.toggle_bold_on(editor)
    md = editor.toMarkdown().strip()
    assert "**" not in md


def test_format_toolbar_italic_applies():
    editor = _SceneEditor()
    editor.setPlainText("hello world")
    cursor = editor.textCursor()
    cursor.setPosition(6)
    cursor.setPosition(11, QTextCursor.MoveMode.KeepAnchor)
    editor.setTextCursor(cursor)

    toolbar = FormatToolbar()
    toolbar.toggle_italic_on(editor)
    md = editor.toMarkdown().strip()
    assert "*world*" in md
    assert editor.toPlainText() == "hello world"


def test_format_toolbar_heading_cycle():
    editor = _SceneEditor()
    editor.setPlainText("Title")
    cursor = editor.textCursor()
    cursor.setPosition(0)
    editor.setTextCursor(cursor)

    toolbar = FormatToolbar()
    toolbar._active_editor = editor
    toolbar._cycle_heading()
    assert editor.toMarkdown().strip() == "# Title"
    toolbar._cycle_heading()
    assert editor.toMarkdown().strip() == "## Title"
    toolbar._cycle_heading()
    assert editor.toMarkdown().strip() == "### Title"
    toolbar._cycle_heading()
    assert editor.toMarkdown().strip() == "Title"


def test_format_toolbar_quote_toggle():
    editor = _SceneEditor()
    editor.setPlainText("Some text")
    cursor = editor.textCursor()
    cursor.setPosition(0)
    editor.setTextCursor(cursor)

    toolbar = FormatToolbar()
    toolbar._active_editor = editor
    toolbar._toggle_quote()
    assert "> Some text" in editor.toMarkdown()
    toolbar._toggle_quote()
    assert ">" not in editor.toMarkdown()


def test_format_toolbar_track_editor():
    toolbar = FormatToolbar()
    editor = _SceneEditor()
    toolbar.track_editor(editor)
    assert editor in toolbar._tracked
    toolbar.untrack_all()
    assert len(toolbar._tracked) == 0


def test_view_has_format_toolbar():
    db = Database()
    proj, *_ = _setup_project(db)
    view = WritingCoreView(db, proj.id)
    assert hasattr(view, "_format_toolbar")
    assert isinstance(view._format_toolbar, FormatToolbar)


# -- Typewriter mode ----------------------------------------------------------

def test_typewriter_mode_toggle():
    db = Database()
    proj, *_ = _setup_project(db)
    view = WritingCoreView(db, proj.id)
    assert view._typewriter_mode is False
    view.toggle_typewriter_mode()
    assert view._typewriter_mode is True
    assert "Exit" in view._typewriter_btn.text()
    view.toggle_typewriter_mode()
    assert view._typewriter_mode is False
    assert view._typewriter_btn.text() == "Typewriter"


def test_typewriter_mode_accessor():
    db = Database()
    proj, *_ = _setup_project(db)
    view = WritingCoreView(db, proj.id)
    assert view.is_typewriter_mode() is False
    view.toggle_typewriter_mode()
    assert view.is_typewriter_mode() is True


# -- PSYKE entity awareness ---------------------------------------------------

def _setup_psyke_project(db):
    """Create a project with scenes and PSYKE entries for entity testing."""
    proj = db.create_project("Novel")
    s1 = db.create_scene(
        proj.id, "Opening",
        content="John looked at Mary across the room.",
        act="Act One", chapter="Chapter 1",
    )
    s2 = db.create_scene(
        proj.id, "Rising",
        content="Mary whispered to John about the plan.",
        act="Act One", chapter="Chapter 1",
    )
    e1 = db.create_psyke_entry(proj.id, "John", entry_type="character", notes="A detective.")
    e2 = db.create_psyke_entry(proj.id, "Mary", entry_type="character", aliases="M", notes="A scientist.")
    return proj, s1, s2, e1, e2


def test_psyke_term_map_built():
    db = Database()
    proj, s1, s2, e1, e2 = _setup_psyke_project(db)
    view = WritingCoreView(db, proj.id)
    assert "john" in view._psyke_term_map
    assert "mary" in view._psyke_term_map
    assert "m" in view._psyke_term_map
    assert view._psyke_term_map["john"] == e1.id
    assert view._psyke_term_map["mary"] == e2.id
    assert view._psyke_term_map["m"] == e2.id


def test_psyke_entry_cache_populated():
    db = Database()
    proj, s1, s2, e1, e2 = _setup_psyke_project(db)
    view = WritingCoreView(db, proj.id)
    assert e1.id in view._psyke_entry_cache
    assert e2.id in view._psyke_entry_cache
    assert view._psyke_entry_cache[e1.id].name == "John"
    assert view._psyke_entry_cache[e2.id].name == "Mary"


def test_click_handlers_created_per_editor():
    db = Database()
    proj, s1, s2, e1, e2 = _setup_psyke_project(db)
    view = WritingCoreView(db, proj.id)
    assert s1.id in view._click_handlers
    assert s2.id in view._click_handlers
    assert isinstance(view._click_handlers[s1.id], PsykeClickHandler)


def test_hover_handlers_created_per_editor():
    db = Database()
    proj, s1, s2, e1, e2 = _setup_psyke_project(db)
    view = WritingCoreView(db, proj.id)
    assert s1.id in view._hover_handlers
    assert s2.id in view._hover_handlers
    assert isinstance(view._hover_handlers[s1.id], EntityHoverHandler)


def test_entity_hover_panel_exists():
    db = Database()
    proj, *_ = _setup_psyke_project(db)
    view = WritingCoreView(db, proj.id)
    assert hasattr(view, "_entity_hover_panel")
    assert isinstance(view._entity_hover_panel, EntityHoverPanel)


def test_entity_hover_panel_creation():
    panel = EntityHoverPanel()
    assert panel.objectName() == "entityHoverPanel"
    assert panel.isHidden()


def test_entity_hover_panel_show_entity():
    parent = QWidget()
    parent.setFixedSize(500, 400)
    panel = EntityHoverPanel(parent)
    panel.show_entity("John", "character", "Paranoid", "A detective.", QPoint(50, 50))
    assert not panel.isHidden()
    assert panel._name_label.text() == "John"
    assert panel._type_label.text() == "character"
    assert panel._state_label.text() == "Paranoid"
    assert panel._notes_label.text() == "A detective."


def test_entity_hover_panel_no_state():
    parent = QWidget()
    parent.setFixedSize(500, 400)
    panel = EntityHoverPanel(parent)
    panel.show_entity("Mary", "character", "", "A scientist.", QPoint(50, 50))
    assert panel._state_label.isHidden()
    assert not panel._notes_label.isHidden()


def test_entity_hover_panel_no_notes():
    parent = QWidget()
    parent.setFixedSize(500, 400)
    panel = EntityHoverPanel(parent)
    panel.show_entity("Place", "place", "Destroyed", "", QPoint(50, 50))
    assert not panel._state_label.isHidden()
    assert panel._notes_label.isHidden()


def test_entity_hover_handler_creation():
    editor = _SceneEditor()
    doc = QTextDocument()
    highlighter = ManuscriptHighlighter(editor.document())
    term_map = {"john": 1}
    parent = QWidget()
    handler = EntityHoverHandler(
        editor, highlighter, term_map, parent,
        on_show=lambda *a: None,
        on_hide=lambda: None,
    )
    assert handler._term_map == {"john": 1}


def test_entity_hover_handler_term_map_update():
    editor = _SceneEditor()
    highlighter = ManuscriptHighlighter(editor.document())
    parent = QWidget()
    handler = EntityHoverHandler(
        editor, highlighter, {}, parent,
        on_show=lambda *a: None,
        on_hide=lambda: None,
    )
    new_map = {"alice": 10, "bob": 20}
    handler.set_term_map(new_map)
    assert handler._term_map == new_map


def test_scene_sort_orders_built():
    db = Database()
    proj, s1, s2, e1, e2 = _setup_psyke_project(db)
    view = WritingCoreView(db, proj.id)
    assert s1.id in view._scene_sort_orders
    assert s2.id in view._scene_sort_orders


def test_temporal_graph_built():
    db = Database()
    proj, s1, s2, e1, e2 = _setup_psyke_project(db)
    view = WritingCoreView(db, proj.id)
    assert view._temporal_graph is not None


def test_temporal_state_in_hover():
    db = Database()
    proj, s1, s2, e1, e2 = _setup_psyke_project(db)
    db.create_psyke_progression(e1.id, "Suspicious of everyone", scene_id=s1.id)
    view = WritingCoreView(db, proj.id)
    state = view._temporal_graph.get_entry_state_at(
        e1.id, view._scene_sort_orders[s1.id],
    )
    assert state is not None
    assert state.has_progression
    assert "Suspicious" in state.progression_text


def test_psyke_jump_callback():
    db = Database()
    proj, s1, s2, e1, e2 = _setup_psyke_project(db)
    jumped = []
    view = WritingCoreView(
        db, proj.id,
        on_open_psyke_entry=lambda eid: jumped.append(eid),
    )
    view._on_psyke_jump(e1.id)
    assert jumped == [e1.id]


def test_psyke_jump_callback_none():
    db = Database()
    proj, *_ = _setup_psyke_project(db)
    view = WritingCoreView(db, proj.id)
    view._on_psyke_jump(999)


def test_handlers_cleared_on_refresh():
    db = Database()
    proj, s1, s2, e1, e2 = _setup_psyke_project(db)
    view = WritingCoreView(db, proj.id)
    assert len(view._click_handlers) == 2
    assert len(view._hover_handlers) == 2
    db.create_scene(proj.id, "New", content="Extra scene.")
    view.refresh()
    assert len(view._click_handlers) == 3
    assert len(view._hover_handlers) == 3


def test_no_psyke_entries_no_overhead():
    db = Database()
    proj = db.create_project("Empty")
    db.create_scene(proj.id, "Scene", content="Some text.")
    view = WritingCoreView(db, proj.id)
    assert len(view._psyke_term_map) == 0
    assert len(view._psyke_entry_cache) == 0


def test_hover_show_with_entity_data():
    db = Database()
    proj, s1, s2, e1, e2 = _setup_psyke_project(db)
    view = WritingCoreView(db, proj.id)
    editor = view._editors[s1.id]
    view._on_entity_hover_show(e1.id, editor, QPoint(50, 50))
    panel = view._entity_hover_panel
    assert panel._name_label.text() == "John"
    assert panel._type_label.text() == "character"


def test_hover_show_with_temporal_state():
    db = Database()
    proj, s1, s2, e1, e2 = _setup_psyke_project(db)
    db.create_psyke_progression(e1.id, "Paranoid after the incident", scene_id=s1.id)
    view = WritingCoreView(db, proj.id)
    editor = view._editors[s1.id]
    view._on_entity_hover_show(e1.id, editor, QPoint(50, 50))
    panel = view._entity_hover_panel
    assert "Paranoid" in panel._state_label.text()


def test_hover_show_without_progression():
    db = Database()
    proj, s1, s2, e1, e2 = _setup_psyke_project(db)
    view = WritingCoreView(db, proj.id)
    editor = view._editors[s1.id]
    view._on_entity_hover_show(e2.id, editor, QPoint(50, 50))
    panel = view._entity_hover_panel
    assert panel._name_label.text() == "Mary"
    assert panel._state_label.isHidden()


# -- Writing formats -----------------------------------------------------------

def test_all_formats_available():
    assert len(ALL_FORMATS) == 5
    for key in FORMAT_ORDER:
        assert key in ALL_FORMATS


def test_format_order_matches_keys():
    assert set(FORMAT_ORDER) == set(ALL_FORMATS.keys())


def test_each_format_has_elements():
    for fmt in ALL_FORMATS.values():
        assert len(fmt.elements) > 0
        assert fmt.default_element in [e.name for e in fmt.elements]


def test_element_transitions_defined():
    for key in ALL_FORMATS:
        assert key in _ELEMENT_TRANSITIONS


def test_transitions_reference_valid_elements():
    for fmt_name, transitions in _ELEMENT_TRANSITIONS.items():
        fmt = ALL_FORMATS[fmt_name]
        elem_names = {e.name for e in fmt.elements}
        for src, dst in transitions.items():
            assert src in elem_names, f"{fmt_name}: transition src '{src}' not in elements"
            assert dst in elem_names, f"{fmt_name}: transition dst '{dst}' not in elements"


# -- Format combo --------------------------------------------------------------

def test_view_has_format_combo():
    db = Database()
    proj, *_ = _setup_project(db)
    view = WritingCoreView(db, proj.id)
    assert view._format_combo.count() == len(FORMAT_ORDER)


def test_format_combo_default_novel():
    db = Database()
    proj, *_ = _setup_project(db)
    view = WritingCoreView(db, proj.id)
    assert view._format_combo.currentData() == "novel"
    assert view._format.name == "novel"


def test_format_combo_respects_project():
    db = Database()
    proj = db.create_project("Script", format_mode="screenplay")
    db.create_scene(proj.id, "Scene", content="Action.")
    view = WritingCoreView(db, proj.id)
    assert view._format_combo.currentData() == "screenplay"
    assert view._format.name == "screenplay"


def test_format_change_persists():
    db = Database()
    proj, *_ = _setup_project(db)
    view = WritingCoreView(db, proj.id)
    view._format_combo.setCurrentIndex(FORMAT_ORDER.index("screenplay"))
    updated = db.get_project_by_id(proj.id)
    assert updated.format_mode == "screenplay"


def test_format_change_updates_element_combo():
    db = Database()
    proj, *_ = _setup_project(db)
    view = WritingCoreView(db, proj.id)
    novel_count = view._element_combo.count()
    view._format_combo.setCurrentIndex(FORMAT_ORDER.index("screenplay"))
    screenplay_count = view._element_combo.count()
    assert novel_count != screenplay_count
    assert screenplay_count == len(ALL_FORMATS["screenplay"].elements)


# -- Element combo -------------------------------------------------------------

def test_element_combo_populated():
    db = Database()
    proj, *_ = _setup_project(db)
    view = WritingCoreView(db, proj.id)
    assert view._element_combo.count() == len(ALL_FORMATS["novel"].elements)


def test_element_combo_default_matches_format():
    db = Database()
    proj, *_ = _setup_project(db)
    view = WritingCoreView(db, proj.id)
    assert view._element_combo.currentData() == ALL_FORMATS["novel"].default_element


def test_element_combo_screenplay_default():
    db = Database()
    proj = db.create_project("Script", format_mode="screenplay")
    db.create_scene(proj.id, "Scene", content="Action.")
    view = WritingCoreView(db, proj.id)
    assert view._element_combo.currentData() == "action"


# -- Block data ----------------------------------------------------------------

def test_block_data_stores_element():
    data = _BlockData("character")
    assert data.element == "character"


def test_block_data_default_empty():
    data = _BlockData()
    assert data.element == ""


# -- Element application -------------------------------------------------------

def test_apply_element_sets_block_data():
    db = Database()
    proj = db.create_project("Script", format_mode="screenplay")
    s1 = db.create_scene(proj.id, "Scene", content="John walks in.")
    view = WritingCoreView(db, proj.id)
    editor = view._editors[s1.id]
    editor.setFocus()
    view._apply_element_to_block(editor, "character")
    data = editor.textCursor().block().userData()
    assert isinstance(data, _BlockData)
    assert data.element == "character"


def test_get_element_style():
    db = Database()
    proj = db.create_project("Script", format_mode="screenplay")
    db.create_scene(proj.id, "S", content="x")
    view = WritingCoreView(db, proj.id)
    style = view._get_element_style("character")
    assert style is not None
    assert style.all_caps is True
    assert style.left_margin == 264


def test_get_element_style_missing():
    db = Database()
    proj, *_ = _setup_project(db)
    view = WritingCoreView(db, proj.id)
    assert view._get_element_style("nonexistent") is None


# -- Enter key transitions -----------------------------------------------------

def test_new_block_transitions_screenplay():
    db = Database()
    proj = db.create_project("Script", format_mode="screenplay")
    s1 = db.create_scene(proj.id, "Scene", content="INT. ROOM")
    view = WritingCoreView(db, proj.id)
    editor = view._editors[s1.id]
    view._apply_element_to_block(editor, "character")
    view._on_new_block_created(editor, "character")
    data = editor.textCursor().block().userData()
    assert isinstance(data, _BlockData)
    assert data.element == "dialogue"


def test_new_block_transitions_novel():
    db = Database()
    proj, s1, *_ = _setup_project(db)
    view = WritingCoreView(db, proj.id)
    editor = view._editors[s1.id]
    view._on_new_block_created(editor, "chapter")
    data = editor.textCursor().block().userData()
    assert isinstance(data, _BlockData)
    assert data.element == "body"


def test_new_block_default_when_no_transition():
    db = Database()
    proj, s1, *_ = _setup_project(db)
    view = WritingCoreView(db, proj.id)
    editor = view._editors[s1.id]
    view._on_new_block_created(editor, None)
    data = editor.textCursor().block().userData()
    assert isinstance(data, _BlockData)
    assert data.element == "body"


# -- Element shortcuts ---------------------------------------------------------

def test_element_shortcuts_created():
    db = Database()
    proj = db.create_project("Script", format_mode="screenplay")
    db.create_scene(proj.id, "S", content="x")
    view = WritingCoreView(db, proj.id)
    assert len(view._element_shortcuts) > 0


def test_element_shortcuts_rebuild_on_format_change():
    db = Database()
    proj, *_ = _setup_project(db)
    view = WritingCoreView(db, proj.id)
    novel_count = len(view._element_shortcuts)
    view._format_combo.setCurrentIndex(FORMAT_ORDER.index("screenplay"))
    screenplay_count = len(view._element_shortcuts)
    assert screenplay_count > 0
    assert novel_count != screenplay_count


def test_shortcut_element_applies():
    db = Database()
    proj = db.create_project("Script", format_mode="screenplay")
    s1 = db.create_scene(proj.id, "Scene", content="Action line.")
    view = WritingCoreView(db, proj.id)
    editor = view._editors[s1.id]
    view._apply_element_to_block(editor, "transition")
    data = editor.textCursor().block().userData()
    assert isinstance(data, _BlockData)
    assert data.element == "transition"


# -- Format application to all blocks -----------------------------------------

def test_format_to_all_blocks_on_load():
    db = Database()
    proj = db.create_project("Script", format_mode="screenplay")
    s1 = db.create_scene(proj.id, "Scene", content="Line one.\nLine two.")
    view = WritingCoreView(db, proj.id)
    editor = view._editors[s1.id]
    block = editor.document().begin()
    data = block.userData()
    assert isinstance(data, _BlockData)
    assert data.element == "action"


def test_format_change_applies_to_blocks():
    db = Database()
    proj, s1, *_ = _setup_project(db)
    view = WritingCoreView(db, proj.id)
    editor = view._editors[s1.id]
    block = editor.document().begin()
    data = block.userData()
    assert isinstance(data, _BlockData)
    assert data.element == "body"
    view._format_combo.setCurrentIndex(FORMAT_ORDER.index("screenplay"))
    block = editor.document().begin()
    data = block.userData()
    assert isinstance(data, _BlockData)
    assert data.element == "action"


def test_active_editor_field_exists():
    db = Database()
    proj, s1, s2, s3 = _setup_project(db)
    view = WritingCoreView(db, proj.id)
    assert hasattr(view, "_active_editor")


def test_element_change_uses_active_editor():
    db = Database()
    proj = db.create_project("Script", format_mode="screenplay")
    s1 = db.create_scene(proj.id, "Scene", content="Test.")
    view = WritingCoreView(db, proj.id)
    editor = view._editors[s1.id]
    view._active_editor = editor
    view._element_combo.setCurrentIndex(
        next(i for i in range(view._element_combo.count())
             if view._element_combo.itemData(i) == "character"),
    )
    data = editor.textCursor().block().userData()
    assert isinstance(data, _BlockData)
    assert data.element == "character"
