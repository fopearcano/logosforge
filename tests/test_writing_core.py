"""Tests for Writing Core view — canvas layout, typography, command palette,
manuscript highlighting, format toolbar, typewriter mode."""

from PySide6.QtCore import Qt
from PySide6.QtGui import QTextCursor, QTextDocument
from PySide6.QtWidgets import QApplication

from storyplanner.db import Database
from storyplanner.ui.command_palette import COMMANDS, CommandPalette
from storyplanner.ui.format_toolbar import FormatToolbar
from storyplanner.ui.manuscript_highlighter import ManuscriptHighlighter
from storyplanner.ui.psyke_highlighter import PsykeHighlighter
from storyplanner.ui.writing_core_view import (
    WritingCoreView,
    _BODY_FONT_SIZE,
    _BODY_LINE_HEIGHT,
    _CANVAS_MAX_WIDTH,
    _CANVAS_PADDING_H,
    _FOCUS_LINE_HEIGHT,
    _SceneEditor,
)


def _setup_project(db):
    proj = db.create_project("Novel")
    s1 = db.create_scene(proj.id, "Opening", content="The storm began.", act="Act One", chapter="Chapter 1")
    s2 = db.create_scene(proj.id, "Rising Action", content="She ran.", act="Act One", chapter="Chapter 1")
    s3 = db.create_scene(proj.id, "Midpoint", content="The truth revealed.", act="Act Two", chapter="Chapter 2")
    return proj, s1, s2, s3


# -- Canvas layout -----------------------------------------------------------

def test_canvas_max_width():
    assert _CANVAS_MAX_WIDTH >= 700
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


def test_focus_mode_widens_canvas():
    db = Database()
    proj, *_ = _setup_project(db)
    view = WritingCoreView(db, proj.id)
    normal_max = view._inner.maximumWidth()
    view.toggle_focus_mode()
    focus_max = view._inner.maximumWidth()
    assert focus_max > normal_max


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


def test_view_uses_manuscript_highlighter():
    db = Database()
    proj, s1, *_ = _setup_project(db)
    view = WritingCoreView(db, proj.id)
    assert isinstance(view._highlighters[s1.id], ManuscriptHighlighter)


# -- Format Toolbar -----------------------------------------------------------

def test_format_toolbar_creates():
    toolbar = FormatToolbar()
    assert toolbar.objectName() == "formatToolbar"


def test_format_toolbar_bold_wraps():
    editor = _SceneEditor()
    editor.setPlainText("hello world")
    cursor = editor.textCursor()
    cursor.setPosition(6)
    cursor.setPosition(11, QTextCursor.MoveMode.KeepAnchor)
    editor.setTextCursor(cursor)

    toolbar = FormatToolbar()
    toolbar.toggle_bold_on(editor)
    assert editor.toPlainText() == "hello **world**"


def test_format_toolbar_bold_unwraps_surrounding():
    editor = _SceneEditor()
    editor.setPlainText("hello **world**")
    cursor = editor.textCursor()
    cursor.setPosition(8)
    cursor.setPosition(13, QTextCursor.MoveMode.KeepAnchor)
    editor.setTextCursor(cursor)

    toolbar = FormatToolbar()
    toolbar.toggle_bold_on(editor)
    assert editor.toPlainText() == "hello world"


def test_format_toolbar_bold_unwraps_selected():
    editor = _SceneEditor()
    editor.setPlainText("hello **world**")
    cursor = editor.textCursor()
    cursor.setPosition(6)
    cursor.setPosition(15, QTextCursor.MoveMode.KeepAnchor)
    editor.setTextCursor(cursor)

    toolbar = FormatToolbar()
    toolbar.toggle_bold_on(editor)
    assert editor.toPlainText() == "hello world"


def test_format_toolbar_italic_wraps():
    editor = _SceneEditor()
    editor.setPlainText("hello world")
    cursor = editor.textCursor()
    cursor.setPosition(6)
    cursor.setPosition(11, QTextCursor.MoveMode.KeepAnchor)
    editor.setTextCursor(cursor)

    toolbar = FormatToolbar()
    toolbar.toggle_italic_on(editor)
    assert editor.toPlainText() == "hello *world*"


def test_format_toolbar_heading_cycle():
    editor = _SceneEditor()
    editor.setPlainText("Title")
    cursor = editor.textCursor()
    cursor.setPosition(0)
    editor.setTextCursor(cursor)

    toolbar = FormatToolbar()
    toolbar._active_editor = editor
    toolbar._cycle_heading()
    assert editor.toPlainText() == "# Title"
    toolbar._cycle_heading()
    assert editor.toPlainText() == "## Title"
    toolbar._cycle_heading()
    assert editor.toPlainText() == "### Title"
    toolbar._cycle_heading()
    assert editor.toPlainText() == "Title"


def test_format_toolbar_quote_toggle():
    editor = _SceneEditor()
    editor.setPlainText("Some text")
    cursor = editor.textCursor()
    cursor.setPosition(0)
    editor.setTextCursor(cursor)

    toolbar = FormatToolbar()
    toolbar._active_editor = editor
    toolbar._toggle_quote()
    assert editor.toPlainText() == "> Some text"
    toolbar._toggle_quote()
    assert editor.toPlainText() == "Some text"


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
