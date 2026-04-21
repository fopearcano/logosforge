"""Writing Core — continuous manuscript editor.

Scenes render as bare inline sections (muted title + editor) in a single
720 px column with 44 px spacing. No containers, no cards, no borders.
"""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QEasingCurve, QEvent, QPropertyAnimation, Qt, QTimer
from PySide6.QtGui import (
    QColor,
    QFont,
    QKeyEvent,
    QKeySequence,
    QPainter,
    QShortcut,
    QTextBlockFormat,
    QTextBlockUserData,
    QTextCharFormat,
    QTextCursor,
)
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFrame,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QTextEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from storyplanner.auto_link import AutoLinkSuggester, Suggestion
from storyplanner.creative_layer import compute_review_metrics
from storyplanner.db import Database
from storyplanner.settings import get_manager as get_settings
from storyplanner.ui import theme
from storyplanner.ui.command_palette import CommandPalette
from storyplanner.ui.entity_hover import EntityHoverHandler, EntityHoverPanel
from storyplanner.ui.format_toolbar import FormatToolbar
from storyplanner.ui.manuscript_highlighter import ManuscriptHighlighter
from storyplanner.ui.psyke_highlighter import PsykeClickHandler
from storyplanner.ui.psyke_quick_create import PsykeQuickCreateDialog
from storyplanner.ui.suggestion_banner import SuggestionBanner
from storyplanner.temporal_psyke import TemporalGraph
from storyplanner.writing_formats import ALL_FORMATS, FORMAT_ORDER, WritingFormat


_CANVAS_MAX_WIDTH = 720
_CANVAS_PADDING_H = 48
_BODY_FONT_SIZE = 18
_BODY_LINE_HEIGHT = 1.65
_FOCUS_LINE_HEIGHT = 1.75
_FADE_ALPHA_PARA = 70
_FADE_ALPHA_SCENE = 110

_ELEMENT_TRANSITIONS: dict[str, dict[str, str]] = {
    "screenplay": {
        "scene_heading": "action",
        "action": "action",
        "character": "dialogue",
        "dialogue": "action",
        "parenthetical": "dialogue",
        "transition": "scene_heading",
    },
    "novel": {
        "chapter": "body",
        "scene_break": "body",
        "body": "body",
    },
    "graphic_novel": {
        "page": "panel",
        "panel": "description",
        "description": "character",
        "character": "dialogue",
        "dialogue": "character",
        "caption": "panel",
        "sfx": "panel",
    },
    "stage_script": {
        "act": "scene",
        "scene": "stage_direction",
        "stage_direction": "character",
        "character": "dialogue",
        "dialogue": "character",
        "parenthetical": "dialogue",
    },
    "series": {
        "episode": "act_break",
        "cold_open": "scene_heading",
        "act_break": "scene_heading",
        "scene_heading": "action",
        "action": "action",
        "character": "dialogue",
        "dialogue": "action",
    },
}


class _BlockData(QTextBlockUserData):
    """Stores the element type for a single text block."""

    def __init__(self, element: str = "") -> None:
        super().__init__()
        self.element = element


class _SceneEditor(QTextEdit):
    """Borderless editor with focus-fade overlay and cross-scene navigation.

    Uses QTextEdit (not QPlainTextEdit) so that QTextBlockFormat margins
    are honoured by the full QTextDocumentLayout.
    """

    slash_pressed = None
    _on_nav_next = None
    _on_nav_prev = None
    _on_new_block = None

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("writingCoreEditor")
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed,
        )
        self.setCursorWidth(2)
        self.setPlaceholderText("Start writing…")
        self.setAcceptRichText(False)
        self._auto_height_timer = QTimer(self)
        self._auto_height_timer.setSingleShot(True)
        self._auto_height_timer.setInterval(30)
        self._auto_height_timer.timeout.connect(self._adjust_height)
        self.textChanged.connect(self._schedule_resize)
        self._scene_id: int | None = None
        self._focus_fade_enabled = False
        self._fade_block = -1
        self._fade_bg = "#0f1219"
        self._fade_alpha_para = _FADE_ALPHA_PARA
        self._fade_alpha_scene = _FADE_ALPHA_SCENE
        self.cursorPositionChanged.connect(self._check_fade_block)

    # -- auto height --

    def _schedule_resize(self) -> None:
        self._auto_height_timer.start()

    def _adjust_height(self) -> None:
        doc = self.document()
        doc.setTextWidth(self.viewport().width())
        height = int(doc.size().height()) + 20
        self.setFixedHeight(max(height, 120))

    def showEvent(self, event):
        super().showEvent(event)
        QTimer.singleShot(10, self._adjust_height)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._adjust_height()

    # -- focus fade overlay --

    def set_focus_fade(self, enabled: bool, bg_color: str = "") -> None:
        self._focus_fade_enabled = enabled
        if bg_color:
            self._fade_bg = bg_color
        self.viewport().update()

    def _check_fade_block(self) -> None:
        if not self._focus_fade_enabled:
            return
        bn = self.textCursor().blockNumber()
        if bn != self._fade_block:
            self._fade_block = bn
            self.viewport().update()

    def paintEvent(self, event) -> None:
        super().paintEvent(event)
        if not self._focus_fade_enabled:
            return
        focused = self.hasFocus()
        active = self.textCursor().blockNumber() if focused else -1
        alpha = self._fade_alpha_para if focused else self._fade_alpha_scene
        color = QColor(self._fade_bg)
        color.setAlpha(alpha)
        painter = QPainter(self.viewport())
        layout = self.document().documentLayout()
        scroll_y = self.verticalScrollBar().value()
        vh = self.viewport().height()
        block = self.document().begin()
        while block.isValid():
            rect = layout.blockBoundingRect(block)
            rect.translate(0, -scroll_y)
            if rect.top() > vh:
                break
            if block.blockNumber() != active and rect.bottom() >= 0:
                painter.fillRect(rect.toRect(), color)
            block = block.next()
        painter.end()

    def focusInEvent(self, event) -> None:
        super().focusInEvent(event)
        if self._focus_fade_enabled:
            self.viewport().update()

    def focusOutEvent(self, event) -> None:
        super().focusOutEvent(event)
        if self._focus_fade_enabled:
            self.viewport().update()

    # -- keyboard --

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            prev_elem = None
            data = self.textCursor().block().userData()
            if isinstance(data, _BlockData):
                prev_elem = data.element
            super().keyPressEvent(event)
            if self._on_new_block is not None:
                self._on_new_block(self, prev_elem)
            return
        if event.key() in (Qt.Key.Key_Down, Qt.Key.Key_Up):
            old_pos = self.textCursor().position()
            super().keyPressEvent(event)
            if self.textCursor().position() == old_pos:
                if event.key() == Qt.Key.Key_Down and self._on_nav_next is not None:
                    self._on_nav_next()
                elif event.key() == Qt.Key.Key_Up and self._on_nav_prev is not None:
                    self._on_nav_prev()
            return
        if (
            event.text() == "/"
            and self.textCursor().atBlockStart()
            and self.slash_pressed is not None
        ):
            self.slash_pressed(self)
            return
        super().keyPressEvent(event)




class WritingCoreView(QWidget):
    """Immersive continuous manuscript writing view."""

    focus_mode_changed = None

    def __init__(
        self,
        db: Database,
        project_id: int,
        on_data_changed: Callable[[], None] | None = None,
        on_focus_mode_changed: Callable[[bool], None] | None = None,
        on_open_psyke_entry: Callable[[int], None] | None = None,
    ) -> None:
        super().__init__()
        self.setMinimumWidth(0)
        self._db = db
        self._project_id = project_id
        self._on_data_changed = on_data_changed
        self._on_focus_mode_changed = on_focus_mode_changed
        self._on_open_psyke_entry = on_open_psyke_entry
        project = db.get_project_by_id(project_id)
        fmt_name = (project.format_mode if project else "novel") or "novel"
        self._format: WritingFormat = ALL_FORMATS.get(fmt_name, ALL_FORMATS["novel"])
        self._focus_mode = False
        self._use_serif = False
        self._editors: dict[int, _SceneEditor] = {}
        self._save_timers: dict[int, QTimer] = {}
        self._scene_widgets: list[QWidget] = []
        self._header_widgets: list[QWidget] = []
        self._highlighters: dict[int, ManuscriptHighlighter] = {}
        self._click_handlers: dict[int, PsykeClickHandler] = {}
        self._hover_handlers: dict[int, EntityHoverHandler] = {}
        self._suggestion_banners: dict[int, SuggestionBanner] = {}
        self._flow_mode = False
        self._typewriter_mode = False
        self._review_mode = False
        self._review_overlay: QWidget | None = None
        self._active_editor: _SceneEditor | None = None

        self._psyke_term_map: dict[str, int] = {}
        self._psyke_entry_cache: dict[int, object] = {}
        self._scene_sort_orders: dict[int, int] = {}
        self._temporal_graph: TemporalGraph | None = None

        self._auto_link_suggester = AutoLinkSuggester(db, project_id)
        self._auto_link_timer = QTimer(self)
        self._auto_link_timer.setSingleShot(True)
        self._auto_link_timer.setInterval(1500)
        self._auto_link_timer.timeout.connect(self._refresh_suggestions)

        self._command_palette: CommandPalette | None = None
        self._palette_source_editor: _SceneEditor | None = None
        self._element_shortcuts: list[QShortcut] = []
        self._focus_fade = True
        self._tw_anim: QPropertyAnimation | None = None
        self._topbar_anim: QPropertyAnimation | None = None

        self._build_ui()
        self._setup_shortcuts()
        self.refresh()

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # -- Top bar (minimal, shows in normal mode) -------------------------
        self._top_bar = QWidget()
        self._top_bar.setObjectName("writingTopBar")
        tb_layout = QHBoxLayout(self._top_bar)
        tb_layout.setContentsMargins(16, 6, 16, 6)
        tb_layout.setSpacing(8)

        self._word_count_label = QLabel("")
        self._word_count_label.setStyleSheet(
            f"color: {theme.TEXT_MUTED}; font-size: 11px;"
            " background: transparent;"
        )
        tb_layout.addWidget(self._word_count_label)

        self._format_combo = QComboBox()
        self._format_combo.setObjectName("writingFormatCombo")
        self._format_combo.setFixedWidth(130)
        for key in FORMAT_ORDER:
            fmt = ALL_FORMATS[key]
            self._format_combo.addItem(fmt.label, key)
        idx = FORMAT_ORDER.index(self._format.name) if self._format.name in FORMAT_ORDER else 0
        self._format_combo.setCurrentIndex(idx)
        self._format_combo.currentIndexChanged.connect(self._on_format_changed)
        tb_layout.addWidget(self._format_combo)

        self._element_combo = QComboBox()
        self._element_combo.setObjectName("writingElementCombo")
        self._element_combo.setFixedWidth(140)
        self._populate_element_combo()
        self._element_combo.currentIndexChanged.connect(self._on_element_changed)
        tb_layout.addWidget(self._element_combo)

        tb_layout.addStretch()

        self._font_toggle = QPushButton("Serif")
        self._font_toggle.setFlat(True)
        self._font_toggle.setStyleSheet(
            f"color: {theme.TEXT_MUTED}; font-size: 11px;"
            " background: transparent; padding: 2px 8px;"
        )
        self._font_toggle.clicked.connect(self._toggle_font)
        tb_layout.addWidget(self._font_toggle)

        self._flow_btn = QPushButton("Flow")
        self._flow_btn.setFlat(True)
        self._flow_btn.setToolTip("Hide structural headers")
        self._flow_btn.setStyleSheet(
            f"color: {theme.TEXT_MUTED}; font-size: 11px;"
            " background: transparent; padding: 2px 8px;"
        )
        self._flow_btn.clicked.connect(self.toggle_flow_mode)
        tb_layout.addWidget(self._flow_btn)

        self._typewriter_btn = QPushButton("Typewriter")
        self._typewriter_btn.setFlat(True)
        self._typewriter_btn.setToolTip("Keep cursor line centered")
        self._typewriter_btn.setStyleSheet(
            f"color: {theme.TEXT_MUTED}; font-size: 11px;"
            " background: transparent; padding: 2px 8px;"
        )
        self._typewriter_btn.clicked.connect(self.toggle_typewriter_mode)
        tb_layout.addWidget(self._typewriter_btn)

        self._review_btn = QPushButton("Review")
        self._review_btn.setFlat(True)
        self._review_btn.setToolTip("Show review metrics overlay")
        self._review_btn.setStyleSheet(
            f"color: {theme.TEXT_MUTED}; font-size: 11px;"
            " background: transparent; padding: 2px 8px;"
        )
        self._review_btn.clicked.connect(self.toggle_review_mode)
        tb_layout.addWidget(self._review_btn)

        self._focus_btn = QPushButton("Focus")
        self._focus_btn.setFlat(True)
        self._focus_btn.setStyleSheet(
            f"color: {theme.TEXT_MUTED}; font-size: 11px;"
            " background: transparent; padding: 2px 8px;"
        )
        self._focus_btn.clicked.connect(self.toggle_focus_mode)
        tb_layout.addWidget(self._focus_btn)

        self._topbar_opacity = QGraphicsOpacityEffect(self._top_bar)
        self._topbar_opacity.setOpacity(0.4)
        self._top_bar.setGraphicsEffect(self._topbar_opacity)
        self._top_bar.installEventFilter(self)
        outer.addWidget(self._top_bar)

        # -- Focus bar (shown only in focus mode) ----------------------------
        self._focus_bar = QWidget()
        self._focus_bar.setObjectName("writingFocusBar")
        fb_layout = QHBoxLayout(self._focus_bar)
        fb_layout.setContentsMargins(16, 4, 16, 4)
        fb_layout.setSpacing(8)

        self._focus_word_label = QLabel("")
        self._focus_word_label.setStyleSheet(
            f"color: {theme.TEXT_MUTED}; font-size: 11px;"
            " background: transparent;"
        )
        fb_layout.addWidget(self._focus_word_label)
        fb_layout.addStretch()

        exit_focus = QPushButton("Exit Focus")
        exit_focus.setFlat(True)
        exit_focus.setStyleSheet(
            f"color: {theme.TEXT_MUTED}; font-size: 11px;"
            " background: transparent; padding: 2px 8px;"
        )
        exit_focus.clicked.connect(self.toggle_focus_mode)
        fb_layout.addWidget(exit_focus)

        self._focus_bar.hide()
        outer.addWidget(self._focus_bar)

        # -- Canvas scroll area -----------------------------------------------
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        self._scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self._scroll.setObjectName("writingScroll")
        outer.addWidget(self._scroll)

        self._canvas = QWidget()
        self._canvas.setObjectName("writingCanvas")
        self._canvas_layout = QVBoxLayout(self._canvas)
        self._canvas_layout.setContentsMargins(0, 32, 0, 64)
        self._canvas_layout.setSpacing(0)

        self._inner = QWidget()
        self._inner.setMaximumWidth(_CANVAS_MAX_WIDTH)
        self._inner.setMinimumWidth(0)
        self._inner.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred,
        )
        self._inner_layout = QVBoxLayout(self._inner)
        self._inner_layout.setContentsMargins(0, 0, 0, 0)
        self._inner_layout.setSpacing(0)

        center_row = QHBoxLayout()
        center_row.setContentsMargins(_CANVAS_PADDING_H, 0, _CANVAS_PADDING_H, 0)
        center_row.addStretch(1)
        center_row.addWidget(self._inner, stretch=999)
        center_row.addStretch(1)
        self._canvas_layout.addLayout(center_row)
        self._canvas_layout.addStretch()
        self._scroll.setWidget(self._canvas)

        self._format_toolbar = FormatToolbar(self._scroll.viewport())
        self._entity_hover_panel = EntityHoverPanel(self._scroll.viewport())
        self._scroll.verticalScrollBar().valueChanged.connect(
            self._on_scroll,
        )

    def _setup_shortcuts(self) -> None:
        esc = QShortcut(QKeySequence(Qt.Key.Key_Escape), self)
        esc.activated.connect(self._exit_focus_mode)
        focus = QShortcut(
            QKeySequence("Ctrl+Shift+F"), self,
            context=Qt.ShortcutContext.WidgetWithChildrenShortcut,
        )
        focus.activated.connect(self.toggle_focus_mode)

        bold_sc = QShortcut(
            QKeySequence("Ctrl+B"), self,
            context=Qt.ShortcutContext.WidgetWithChildrenShortcut,
        )
        bold_sc.activated.connect(self._shortcut_bold)

        italic_sc = QShortcut(
            QKeySequence("Ctrl+I"), self,
            context=Qt.ShortcutContext.WidgetWithChildrenShortcut,
        )
        italic_sc.activated.connect(self._shortcut_italic)

        tw_sc = QShortcut(
            QKeySequence("Ctrl+Shift+T"), self,
            context=Qt.ShortcutContext.WidgetWithChildrenShortcut,
        )
        tw_sc.activated.connect(self.toggle_typewriter_mode)

        self._setup_element_shortcuts()

    def _setup_element_shortcuts(self) -> None:
        for sc in self._element_shortcuts:
            sc.setEnabled(False)
            sc.deleteLater()
        self._element_shortcuts.clear()
        for elem in self._format.elements:
            if elem.shortcut:
                sc = QShortcut(
                    QKeySequence(elem.shortcut), self,
                    context=Qt.ShortcutContext.WidgetWithChildrenShortcut,
                )
                sc.activated.connect(
                    lambda name=elem.name: self._shortcut_element(name),
                )
                self._element_shortcuts.append(sc)

    # -- Top bar auto-fade ----------------------------------------------------

    def eventFilter(self, obj, event) -> bool:
        if obj is self._top_bar:
            if event.type() == QEvent.Type.Enter:
                self._animate_topbar(1.0)
            elif event.type() == QEvent.Type.Leave:
                self._animate_topbar(0.4)
        return super().eventFilter(obj, event)

    def _animate_topbar(self, target: float) -> None:
        if self._topbar_anim is None:
            self._topbar_anim = QPropertyAnimation(
                self._topbar_opacity, b"opacity",
            )
            self._topbar_anim.setDuration(200)
            self._topbar_anim.setEasingCurve(QEasingCurve.Type.InOutQuad)
        self._topbar_anim.stop()
        self._topbar_anim.setStartValue(self._topbar_opacity.opacity())
        self._topbar_anim.setEndValue(target)
        self._topbar_anim.start()

    # -- Data loading ---------------------------------------------------------

    def refresh(self) -> None:
        self._clear_canvas()
        scenes = self._db.get_all_scenes(self._project_id)

        self._scene_sort_orders = {s.id: s.sort_order for s in scenes}
        self._temporal_graph = TemporalGraph(self._db, self._project_id)

        current_act = None
        current_chapter = None
        first_scene = True

        for scene in scenes:
            act = (scene.act or "").strip()
            chapter = (scene.chapter or "").strip()

            if act and act != current_act:
                current_act = act
                self._add_act_header(act)

            if chapter and chapter != current_chapter:
                current_chapter = chapter
                self._add_chapter_header(chapter)

            self._add_scene_block(scene, is_first=first_scene)
            first_scene = False

        if scenes:
            self._add_end_action(scenes[-1].id)
        else:
            self._add_empty_state()

        self._update_word_count()
        self._apply_typography()
        self.refresh_psyke_terms()
        self._refresh_suggestions()

        if self._flow_mode:
            for w in self._header_widgets:
                w.setVisible(False)

    def _clear_canvas(self) -> None:
        self._format_toolbar.untrack_all()
        self._entity_hover_panel.hide()
        self._editors.clear()
        self._save_timers.clear()
        self._scene_widgets.clear()
        self._header_widgets.clear()
        self._highlighters.clear()
        self._click_handlers.clear()
        self._hover_handlers.clear()
        self._suggestion_banners.clear()
        while self._inner_layout.count():
            item = self._inner_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

    # -- Canvas building blocks -----------------------------------------------

    def _add_act_header(self, act: str) -> None:
        label = QLabel(act.upper())
        label.setObjectName("writingActHeader")
        label.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self._inner_layout.addSpacing(40)
        self._inner_layout.addWidget(label)
        self._inner_layout.addSpacing(12)
        self._scene_widgets.append(label)
        self._header_widgets.append(label)

    def _add_chapter_header(self, chapter: str) -> None:
        label = QLabel(chapter)
        label.setObjectName("writingChapterHeader")
        label.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self._inner_layout.addSpacing(32)
        self._inner_layout.addWidget(label)
        self._inner_layout.addSpacing(16)
        self._scene_widgets.append(label)
        self._header_widgets.append(label)

    def _add_scene_block(self, scene, *, is_first: bool = False) -> None:
        if not is_first:
            self._inner_layout.addSpacing(44)

        title_text = (scene.title or "").strip()
        if title_text and title_text.lower() not in ("untitled", "untitled scene"):
            title = QLabel(title_text)
            title.setObjectName("writingSceneTitle")
            title.setAlignment(Qt.AlignmentFlag.AlignLeft)
            self._inner_layout.addWidget(title)
            self._inner_layout.addSpacing(2)
            self._scene_widgets.append(title)

        editor = _SceneEditor()
        editor._scene_id = scene.id
        editor.setPlainText(scene.content or "")
        editor.slash_pressed = self._on_slash_pressed
        editor.set_focus_fade(self._focus_fade, theme.BG_DARK)
        editor._on_nav_next = lambda e=editor: self._navigate_next_editor(e)
        editor._on_nav_prev = lambda e=editor: self._navigate_prev_editor(e)
        editor._on_new_block = self._on_new_block_created
        editor.textChanged.connect(
            lambda sid=scene.id: self._schedule_save(sid)
        )
        editor.cursorPositionChanged.connect(
            lambda e=editor: self._on_editor_cursor_moved(e),
        )
        self._inner_layout.addWidget(editor)
        self._scene_widgets.append(editor)

        highlighter = ManuscriptHighlighter(editor.document())
        self._highlighters[scene.id] = highlighter

        click_handler = PsykeClickHandler(
            editor, highlighter, on_jump=self._on_psyke_jump,
        )
        click_handler.set_term_map(self._psyke_term_map)
        self._click_handlers[scene.id] = click_handler

        hover_handler = EntityHoverHandler(
            editor, highlighter, self._psyke_term_map,
            self._scroll.viewport(),
            on_show=self._on_entity_hover_show,
            on_hide=self._on_entity_hover_hide,
        )
        self._hover_handlers[scene.id] = hover_handler

        self._format_toolbar.track_editor(editor)
        editor.cursorPositionChanged.connect(
            lambda e=editor: self._on_cursor_for_typewriter(e),
        )

        banner = SuggestionBanner()
        banner.accepted.connect(self._on_suggestion_accepted)
        banner.dismissed.connect(self._on_suggestion_dismissed)
        banner.ignored.connect(self._on_suggestion_ignored)
        self._inner_layout.addWidget(banner)
        self._suggestion_banners[scene.id] = banner

        self._editors[scene.id] = editor

    def _add_end_action(self, last_scene_id: int | None) -> None:
        btn = QPushButton("+")
        btn.setFlat(True)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setObjectName("writingEndAction")
        btn.setFixedHeight(28)
        btn.setToolTip("New Scene")
        btn.clicked.connect(
            lambda: self._create_scene_after(last_scene_id)
        )
        self._inner_layout.addSpacing(32)
        self._inner_layout.addWidget(btn)
        self._scene_widgets.append(btn)

    def _add_empty_state(self) -> None:
        msg = QLabel("Begin writing.")
        msg.setObjectName("writingEmptyState")
        msg.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._inner_layout.addSpacing(80)
        self._inner_layout.addWidget(msg)
        self._inner_layout.addSpacing(16)
        btn = QPushButton("+ New Scene")
        btn.setFlat(True)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setObjectName("writingEndAction")
        btn.clicked.connect(lambda: self._create_scene_after(None))
        self._inner_layout.addWidget(
            btn, alignment=Qt.AlignmentFlag.AlignCenter,
        )


    # -- PSYKE highlighting ----------------------------------------------------

    def refresh_psyke_terms(self) -> None:
        entries = self._db.get_all_psyke_entries(self._project_id)
        terms: list[str] = []
        self._psyke_term_map.clear()
        self._psyke_entry_cache.clear()
        for e in entries:
            self._psyke_entry_cache[e.id] = e
            if e.name.strip():
                terms.append(e.name)
                self._psyke_term_map[e.name.lower()] = e.id
            if e.aliases:
                for alias in e.aliases.split(","):
                    alias = alias.strip()
                    if alias:
                        terms.append(alias)
                        self._psyke_term_map[alias.lower()] = e.id
        for highlighter in self._highlighters.values():
            highlighter.refresh_patterns(terms)
        for handler in self._click_handlers.values():
            handler.set_term_map(self._psyke_term_map)
        for handler in self._hover_handlers.values():
            handler.set_term_map(self._psyke_term_map)

    # -- Flow mode (hide headers) ----------------------------------------------

    def toggle_flow_mode(self) -> None:
        self._flow_mode = not self._flow_mode
        for w in self._header_widgets:
            w.setVisible(not self._flow_mode)
        self._flow_btn.setText("Structure" if self._flow_mode else "Flow")

    def is_flow_mode(self) -> bool:
        return self._flow_mode

    # -- Format / element system -----------------------------------------------

    def _populate_element_combo(self) -> None:
        self._element_combo.blockSignals(True)
        self._element_combo.clear()
        for elem in self._format.elements:
            label = elem.name.replace("_", " ").title()
            self._element_combo.addItem(label, elem.name)
        idx = next(
            (i for i, e in enumerate(self._format.elements)
             if e.name == self._format.default_element),
            0,
        )
        self._element_combo.setCurrentIndex(idx)
        self._element_combo.blockSignals(False)

    def _on_format_changed(self, index: int) -> None:
        key = self._format_combo.itemData(index)
        if not key or key not in ALL_FORMATS:
            return
        self._format = ALL_FORMATS[key]
        self._db.update_project_format(self._project_id, key)
        self._populate_element_combo()
        self._setup_element_shortcuts()
        self._apply_format_to_all_blocks()

    def _on_element_changed(self, index: int) -> None:
        if index < 0:
            return
        elem_name = self._element_combo.itemData(index)
        if not elem_name:
            return
        editor = self._active_editor
        if editor is None:
            focused = QApplication.focusWidget()
            if isinstance(focused, _SceneEditor):
                editor = focused
        if editor is not None:
            self._apply_element_to_block(editor, elem_name)

    def _get_element_style(self, name: str):
        for e in self._format.elements:
            if e.name == name:
                return e
        return None

    def _build_element_formats(self, elem):
        _align_map = {
            "center": Qt.AlignmentFlag.AlignCenter,
            "right": Qt.AlignmentFlag.AlignRight,
        }
        bfmt = QTextBlockFormat()
        bfmt.setAlignment(_align_map.get(elem.align, Qt.AlignmentFlag.AlignLeft))
        bfmt.setLeftMargin(elem.left_margin)
        bfmt.setRightMargin(elem.right_margin)
        bfmt.setTopMargin(elem.top_spacing)
        bfmt.setBottomMargin(elem.bottom_spacing)
        lh = elem.line_height
        if self._focus_mode:
            lh = max(lh, _FOCUS_LINE_HEIGHT)
        bfmt.setLineHeight(
            lh * 100,
            QTextBlockFormat.LineHeightTypes.ProportionalHeight.value,
        )

        families = (
            ["Georgia", "Noto Serif", "serif"]
            if self._use_serif
            else ["Segoe UI", "Noto Sans", "sans-serif"]
        )
        font = QFont()
        font.setFamilies(families)
        font.setPixelSize(elem.font_size)
        font.setBold(elem.bold)
        font.setItalic(elem.italic)
        font.setCapitalization(
            QFont.Capitalization.AllUppercase
            if elem.all_caps
            else QFont.Capitalization.MixedCase,
        )

        cfmt = QTextCharFormat()
        cfmt.setFont(font)
        if elem.color_key == "muted":
            cfmt.setForeground(QColor(theme.TEXT_MUTED))
        return bfmt, cfmt

    def _apply_element_to_block(
        self, editor: _SceneEditor, element_name: str,
    ) -> None:
        elem = self._get_element_style(element_name)
        if elem is None:
            return
        cursor = editor.textCursor()
        pos = cursor.position()
        cursor.block().setUserData(_BlockData(element_name))

        bfmt, cfmt = self._build_element_formats(elem)

        cursor.movePosition(QTextCursor.MoveOperation.StartOfBlock)
        cursor.movePosition(
            QTextCursor.MoveOperation.EndOfBlock,
            QTextCursor.MoveMode.KeepAnchor,
        )
        cursor.setBlockFormat(bfmt)
        cursor.setCharFormat(cfmt)

        cursor.setPosition(pos)
        cursor.setCharFormat(cfmt)
        editor.setTextCursor(cursor)

    def _apply_format_to_all_blocks(self) -> None:
        default_name = self._format.default_element
        for editor in self._editors.values():
            block = editor.document().begin()
            while block.isValid():
                data = block.userData()
                elem_name = default_name
                if isinstance(data, _BlockData) and data.element:
                    if self._get_element_style(data.element):
                        elem_name = data.element
                elem = self._get_element_style(elem_name)
                if elem:
                    block.setUserData(_BlockData(elem_name))
                    bfmt, cfmt = self._build_element_formats(elem)
                    cursor = QTextCursor(block)
                    cursor.movePosition(
                        QTextCursor.MoveOperation.EndOfBlock,
                        QTextCursor.MoveMode.KeepAnchor,
                    )
                    cursor.setBlockFormat(bfmt)
                    cursor.setCharFormat(cfmt)
                block = block.next()

    def _on_editor_cursor_moved(self, editor: _SceneEditor) -> None:
        if editor.hasFocus():
            self._active_editor = editor
        data = editor.textCursor().block().userData()
        elem_name = (
            data.element
            if isinstance(data, _BlockData) and data.element
            else self._format.default_element
        )
        self._element_combo.blockSignals(True)
        for i in range(self._element_combo.count()):
            if self._element_combo.itemData(i) == elem_name:
                self._element_combo.setCurrentIndex(i)
                break
        self._element_combo.blockSignals(False)

    def _on_new_block_created(
        self, editor: _SceneEditor, previous_element: str | None,
    ) -> None:
        transitions = _ELEMENT_TRANSITIONS.get(self._format.name, {})
        if previous_element and previous_element in transitions:
            next_elem = transitions[previous_element]
        else:
            next_elem = self._format.default_element
        self._apply_element_to_block(editor, next_elem)
        self._element_combo.blockSignals(True)
        for i in range(self._element_combo.count()):
            if self._element_combo.itemData(i) == next_elem:
                self._element_combo.setCurrentIndex(i)
                break
        self._element_combo.blockSignals(False)

    def _shortcut_element(self, element_name: str) -> None:
        focused = QApplication.focusWidget()
        if not isinstance(focused, _SceneEditor):
            return
        self._apply_element_to_block(focused, element_name)
        self._element_combo.blockSignals(True)
        for i in range(self._element_combo.count()):
            if self._element_combo.itemData(i) == element_name:
                self._element_combo.setCurrentIndex(i)
                break
        self._element_combo.blockSignals(False)

    # -- Review mode -----------------------------------------------------------

    def toggle_review_mode(self) -> None:
        self._review_mode = not self._review_mode
        if self._review_mode:
            self._show_review_overlay()
        else:
            self._hide_review_overlay()
        self._review_btn.setText("Close Review" if self._review_mode else "Review")

    def is_review_mode(self) -> bool:
        return self._review_mode

    def _show_review_overlay(self) -> None:
        if self._review_overlay is not None:
            self._review_overlay.deleteLater()

        metrics = compute_review_metrics(self._db, self._project_id)
        overlay = QFrame(self._scroll)
        overlay.setObjectName("reviewOverlay")
        overlay.setFixedWidth(260)

        lay = QVBoxLayout(overlay)
        lay.setContentsMargins(12, 10, 12, 10)
        lay.setSpacing(4)

        title = QLabel("Review")
        title.setObjectName("reviewOverlayTitle")
        lay.addWidget(title)

        lay.addWidget(QLabel(f"Words: {metrics.total_words:,}"))
        lay.addWidget(QLabel(f"Scenes: {metrics.total_scenes}"))
        lay.addWidget(QLabel(f"Avg scene: {metrics.avg_scene_words} words"))

        if metrics.total_scenes > 0:
            sid_s, wc_s = metrics.shortest_scene
            sid_l, wc_l = metrics.longest_scene
            lay.addWidget(QLabel(f"Shortest: scene {sid_s} ({wc_s}w)"))
            lay.addWidget(QLabel(f"Longest: scene {sid_l} ({wc_l}w)"))

        pb = metrics.pacing_balance
        lay.addWidget(QLabel(
            f"Pacing: {pb['short']}S / {pb['medium']}M / {pb['long']}L"
        ))

        if metrics.flagged_scenes:
            sep = QFrame()
            sep.setFrameShape(QFrame.Shape.HLine)
            sep.setStyleSheet(f"color: {theme.BORDER};")
            lay.addWidget(sep)
            flags_label = QLabel(f"Flags ({len(metrics.flagged_scenes)})")
            flags_label.setObjectName("reviewOverlayTitle")
            lay.addWidget(flags_label)
            for hint in metrics.flagged_scenes[:8]:
                lay.addWidget(QLabel(f"  {hint.message}"))

        overlay.adjustSize()
        overlay.move(self._scroll.width() - overlay.width() - 16, 12)
        overlay.show()
        self._review_overlay = overlay

    def _hide_review_overlay(self) -> None:
        if self._review_overlay is not None:
            self._review_overlay.deleteLater()
            self._review_overlay = None

    # -- Scene CRUD -----------------------------------------------------------

    def _create_scene_after(
        self, after_scene_id: int | None, chapter: str = "",
    ) -> None:
        new_scene = self._db.create_scene(
            self._project_id, "Untitled",
            chapter=chapter if chapter else None,
        )

        if after_scene_id is not None:
            scenes = self._db.get_all_scenes(self._project_id)
            idx_new = next(
                (i for i, s in enumerate(scenes) if s.id == new_scene.id),
                None,
            )
            idx_target = next(
                (i for i, s in enumerate(scenes) if s.id == after_scene_id),
                None,
            )
            if idx_new is not None and idx_target is not None:
                while idx_new > idx_target + 1:
                    self._db.move_scene_up(new_scene.id)
                    idx_new -= 1

        if self._on_data_changed:
            self._on_data_changed()
        self.refresh()

        if new_scene.id in self._editors:
            editor = self._editors[new_scene.id]
            editor.setFocus()
            self._scroll.ensureWidgetVisible(editor)

    # -- Auto-save ------------------------------------------------------------

    def _schedule_save(self, scene_id: int) -> None:
        if scene_id not in self._save_timers:
            timer = QTimer(self)
            timer.setSingleShot(True)
            timer.setInterval(500)
            timer.timeout.connect(lambda sid=scene_id: self._save_scene(sid))
            self._save_timers[scene_id] = timer
        self._save_timers[scene_id].start()
        self._auto_link_timer.start()
        self._update_word_count()

    def _save_scene(self, scene_id: int) -> None:
        editor = self._editors.get(scene_id)
        if editor is None:
            return
        self._db.update_scene_content(scene_id, editor.toPlainText())
        if self._on_data_changed:
            self._on_data_changed()

    # -- Command palette ------------------------------------------------------

    def _ensure_command_palette(self) -> CommandPalette:
        if self._command_palette is None:
            self._command_palette = CommandPalette()
            self._command_palette.command_selected.connect(self._on_command)
        return self._command_palette

    def _on_slash_pressed(self, editor: _SceneEditor) -> None:
        self._palette_source_editor = editor
        palette = self._ensure_command_palette()
        cursor_rect = editor.cursorRect()
        global_pos = editor.mapToGlobal(cursor_rect.bottomLeft())
        palette.open_at(global_pos)

    def _on_command(self, key: str) -> None:
        editor = self._palette_source_editor
        if key == "scene":
            sid = editor._scene_id if editor else None
            self._create_scene_after(sid)
        elif key == "chapter":
            self._create_chapter_from_command(editor)
        elif key == "focus":
            self.toggle_focus_mode()
        elif key == "psyke":
            pass
        elif key.startswith("ai_"):
            pass

    def _create_chapter_from_command(
        self, editor: _SceneEditor | None,
    ) -> None:
        sid = editor._scene_id if editor else None
        scenes = self._db.get_all_scenes(self._project_id)
        chapter_num = 1
        for s in scenes:
            if s.chapter and s.chapter.startswith("Chapter"):
                try:
                    n = int(s.chapter.split()[-1])
                    chapter_num = max(chapter_num, n + 1)
                except ValueError:
                    pass
        chapter_name = f"Chapter {chapter_num}"
        self._create_scene_after(sid, chapter=chapter_name)

    # -- Typography -----------------------------------------------------------

    def _apply_typography(self) -> None:
        serif = self._use_serif
        family = "Georgia, 'Noto Serif', serif" if serif else "'Segoe UI', 'Noto Sans', sans-serif"
        lh = _FOCUS_LINE_HEIGHT if self._focus_mode else _BODY_LINE_HEIGHT
        line_spacing_px = int(_BODY_FONT_SIZE * lh)

        text_color = (
            "#e0d8cc" if theme.current_palette() == "Dark"
            else theme.TEXT_PRIMARY
        )
        sel_bg = (
            "#2a2618" if theme.current_palette() == "Dark"
            else theme.SELECTION_BG
        )

        editor_style = (
            f"#writingCoreEditor {{"
            f"  background-color: transparent;"
            f"  color: {text_color};"
            f"  border: none;"
            f"  padding: 0;"
            f"  font-family: {family};"
            f"  font-size: {_BODY_FONT_SIZE}px;"
            f"  selection-background-color: {sel_bg};"
            f"  selection-color: {theme.SELECTION_TEXT};"
            f"}}"
        )

        act_style = (
            f"#writingActHeader {{"
            f"  color: {theme.TEXT_MUTED};"
            f"  font-size: 11px;"
            f"  font-weight: bold;"
            f"  letter-spacing: 2.5px;"
            f"  background: transparent;"
            f"  padding: 0;"
            f"}}"
        )

        chapter_style = (
            f"#writingChapterHeader {{"
            f"  color: {theme.TEXT_PRIMARY};"
            f"  font-size: 20px;"
            f"  font-weight: bold;"
            f"  font-family: {family};"
            f"  background: transparent;"
            f"  padding: 0;"
            f"}}"
        )

        scene_title_style = (
            f"#writingSceneTitle {{"
            f"  color: {theme.TEXT_MUTED};"
            f"  font-size: 13px;"
            f"  font-weight: normal;"
            f"  font-family: {family};"
            f"  background: transparent;"
            f"  padding: 0;"
            f"}}"
        )

        end_action_style = (
            f"#writingEndAction {{"
            f"  color: {theme.TEXT_MUTED};"
            f"  font-size: 13px;"
            f"  background: transparent;"
            f"  border: none;"
            f"  padding: 0;"
            f"}}"
            f"#writingEndAction:hover {{"
            f"  color: {theme.ACCENT};"
            f"}}"
        )

        canvas_bg = theme.BG_DARK
        canvas_style = (
            f"#writingCanvas {{"
            f"  background-color: {canvas_bg};"
            f"}}"
        )

        scroll_style = (
            f"#writingScroll {{"
            f"  background-color: {canvas_bg};"
            f"  border: none;"
            f"}}"
        )

        empty_style = (
            f"#writingEmptyState {{"
            f"  color: {theme.TEXT_MUTED};"
            f"  font-size: 15px;"
            f"  background: transparent;"
            f"}}"
        )

        focus_dim = ""
        if self._focus_mode:
            focus_dim = (
                f"#writingTopBar {{ background: transparent; }}"
                f"#writingFocusBar {{ background: transparent; }}"
            )
        else:
            focus_dim = (
                f"#writingTopBar {{"
                f"  background-color: {theme.BG_PANEL};"
                f"  border-bottom: 1px solid {theme.BORDER};"
                f"}}"
            )


        review_style = (
            f"#reviewOverlay {{"
            f"  background-color: {theme.BG_PANEL};"
            f"  border: 1px solid {theme.BORDER};"
            f"  border-radius: 8px;"
            f"  color: {theme.TEXT_SECONDARY};"
            f"  font-size: 11px;"
            f"}}"
            f"#reviewOverlayTitle {{"
            f"  color: {theme.TEXT_PRIMARY};"
            f"  font-size: 12px;"
            f"  font-weight: bold;"
            f"  background: transparent;"
            f"}}"
        )

        format_toolbar_style = (
            f"#formatToolbar {{"
            f"  background: {theme.BG_PANEL};"
            f"  border: 1px solid {theme.BORDER};"
            f"  border-radius: 6px;"
            f"}}"
            f"#formatToolbar QPushButton {{"
            f"  background: transparent;"
            f"  color: {theme.TEXT_SECONDARY};"
            f"  border: none;"
            f"  border-radius: 4px;"
            f"  padding: 2px 8px;"
            f"  font-size: 12px;"
            f"  min-height: 20px;"
            f"  min-width: 24px;"
            f"}}"
            f"#formatToolbar QPushButton:hover {{"
            f"  background: {theme.BG_HOVER};"
            f"  color: {theme.TEXT_PRIMARY};"
            f"}}"
            f"#formatToolbarSep {{"
            f"  background: {theme.BORDER};"
            f"}}"
        )

        entity_hover_style = (
            f"#entityHoverPanel {{"
            f"  background: {theme.BG_PANEL};"
            f"  border: 1px solid {theme.BORDER};"
            f"  border-radius: 6px;"
            f"}}"
            f"#entityHoverName {{"
            f"  color: {theme.TEXT_PRIMARY};"
            f"  font-weight: bold;"
            f"  font-size: 13px;"
            f"  background: transparent;"
            f"}}"
            f"#entityHoverType {{"
            f"  color: {theme.TEXT_MUTED};"
            f"  font-size: 11px;"
            f"  background: transparent;"
            f"}}"
            f"#entityHoverState {{"
            f"  color: {theme.ACCENT};"
            f"  font-size: 12px;"
            f"  font-style: italic;"
            f"  background: transparent;"
            f"}}"
            f"#entityHoverNotes {{"
            f"  color: {theme.TEXT_SECONDARY};"
            f"  font-size: 11px;"
            f"  background: transparent;"
            f"}}"
        )

        suggestion_style = (
            f"#suggestionBanner {{"
            f"  background: {theme.BG_PANEL};"
            f"  border: 1px solid {theme.BORDER};"
            f"  border-left: 2px solid {theme.ACCENT};"
            f"  border-radius: 4px;"
            f"  margin: 4px 0 4px 0;"
            f"}}"
            f"#suggestionBannerIcon {{"
            f"  color: {theme.ACCENT};"
            f"  font-size: 12px;"
            f"  background: transparent;"
            f"  padding: 0 2px;"
            f"}}"
            f"#suggestionBannerLabel {{"
            f"  color: {theme.TEXT_SECONDARY};"
            f"  font-size: 12px;"
            f"  background: transparent;"
            f"}}"
            f"#suggestionBannerBtn {{"
            f"  color: {theme.TEXT_MUTED};"
            f"  background: transparent;"
            f"  border: none;"
            f"  font-size: 12px;"
            f"  padding: 2px 6px;"
            f"}}"
            f"#suggestionBannerBtn:hover {{"
            f"  color: {theme.TEXT_PRIMARY};"
            f"}}"
        )

        combo_style = (
            f"#writingFormatCombo, #writingElementCombo {{"
            f"  background: transparent;"
            f"  color: {theme.TEXT_MUTED};"
            f"  border: 1px solid {theme.BORDER};"
            f"  border-radius: 4px;"
            f"  padding: 2px 8px;"
            f"  font-size: 11px;"
            f"}}"
            f"#writingFormatCombo:hover, #writingElementCombo:hover {{"
            f"  color: {theme.TEXT_PRIMARY};"
            f"  border-color: {theme.TEXT_MUTED};"
            f"}}"
            f"#writingFormatCombo QAbstractItemView,"
            f"#writingElementCombo QAbstractItemView {{"
            f"  background: {theme.BG_PANEL};"
            f"  color: {theme.TEXT_PRIMARY};"
            f"  border: 1px solid {theme.BORDER};"
            f"  selection-background-color: {theme.BG_HOVER};"
            f"}}"
        )

        full_style = (
            editor_style + act_style + chapter_style + scene_title_style
            + end_action_style
            + canvas_style + scroll_style + empty_style + focus_dim
            + review_style
            + format_toolbar_style + entity_hover_style + suggestion_style
            + combo_style
        )
        self.setStyleSheet(full_style)

        self._apply_format_to_all_blocks()

    def _toggle_font(self) -> None:
        self._use_serif = not self._use_serif
        self._font_toggle.setText("Sans" if self._use_serif else "Serif")
        self._apply_typography()

    # -- Focus mode -----------------------------------------------------------

    def toggle_focus_mode(self) -> None:
        self._focus_mode = not self._focus_mode
        self._top_bar.setVisible(not self._focus_mode)
        self._focus_bar.setVisible(self._focus_mode)
        if not self._focus_mode:
            self._topbar_opacity.setOpacity(0.4)

        para_alpha = 90 if self._focus_mode else _FADE_ALPHA_PARA
        scene_alpha = 130 if self._focus_mode else _FADE_ALPHA_SCENE

        if self._focus_mode:
            self._canvas_layout.setContentsMargins(0, 24, 0, 64)
            self._inner.setMaximumWidth(_CANVAS_MAX_WIDTH + 60)
        else:
            self._canvas_layout.setContentsMargins(0, 32, 0, 64)
            self._inner.setMaximumWidth(_CANVAS_MAX_WIDTH)

        for editor in self._editors.values():
            editor._fade_alpha_para = para_alpha
            editor._fade_alpha_scene = scene_alpha
            editor.viewport().update()

        self._apply_typography()
        self._update_word_count()

        if self._on_focus_mode_changed:
            self._on_focus_mode_changed(self._focus_mode)

    def _exit_focus_mode(self) -> None:
        if self._focus_mode:
            self.toggle_focus_mode()

    # -- Word count -----------------------------------------------------------

    def _update_word_count(self) -> None:
        total = 0
        for editor in self._editors.values():
            text = editor.toPlainText()
            total += len(text.split()) if text.strip() else 0
        label = f"{total:,} words"
        self._word_count_label.setText(label)
        self._focus_word_label.setText(label)

    # -- Typewriter mode ------------------------------------------------------

    def toggle_typewriter_mode(self) -> None:
        self._typewriter_mode = not self._typewriter_mode
        self._typewriter_btn.setText(
            "Exit Typewriter" if self._typewriter_mode else "Typewriter",
        )

    def is_typewriter_mode(self) -> bool:
        return self._typewriter_mode

    def _on_cursor_for_typewriter(self, editor: _SceneEditor) -> None:
        if not self._typewriter_mode or not editor.hasFocus():
            return
        rect = editor.cursorRect()
        cursor_y = editor.mapTo(self._canvas, rect.center()).y()
        viewport_h = self._scroll.viewport().height()
        target = max(0, cursor_y - viewport_h // 2)
        sb = self._scroll.verticalScrollBar()
        target = min(target, sb.maximum())
        if self._tw_anim is None:
            self._tw_anim = QPropertyAnimation(sb, b"value")
            self._tw_anim.setDuration(120)
            self._tw_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._tw_anim.stop()
        self._tw_anim.setStartValue(sb.value())
        self._tw_anim.setEndValue(target)
        self._tw_anim.start()

    # -- Cross-scene navigation ------------------------------------------------

    def _navigate_next_editor(self, current: _SceneEditor) -> None:
        editors = list(self._editors.values())
        try:
            idx = editors.index(current)
        except ValueError:
            return
        if idx < len(editors) - 1:
            nxt = editors[idx + 1]
            nxt.setFocus()
            cursor = nxt.textCursor()
            cursor.movePosition(QTextCursor.MoveOperation.Start)
            nxt.setTextCursor(cursor)
            self._scroll.ensureWidgetVisible(nxt, 50, 50)

    def _navigate_prev_editor(self, current: _SceneEditor) -> None:
        editors = list(self._editors.values())
        try:
            idx = editors.index(current)
        except ValueError:
            return
        if idx > 0:
            prev = editors[idx - 1]
            prev.setFocus()
            cursor = prev.textCursor()
            cursor.movePosition(QTextCursor.MoveOperation.End)
            prev.setTextCursor(cursor)
            self._scroll.ensureWidgetVisible(prev, 50, 50)

    # -- Format shortcuts -----------------------------------------------------

    def _shortcut_bold(self) -> None:
        focused = QApplication.focusWidget()
        if isinstance(focused, _SceneEditor):
            self._format_toolbar.toggle_bold_on(focused)

    def _shortcut_italic(self) -> None:
        focused = QApplication.focusWidget()
        if isinstance(focused, _SceneEditor):
            self._format_toolbar.toggle_italic_on(focused)

    def _on_scroll(self) -> None:
        ft = self._format_toolbar
        if ft.isVisible() and ft._active_editor is not None:
            ft._reposition(ft._active_editor)
        self._entity_hover_panel.schedule_hide()

    # -- PSYKE entity interaction ---------------------------------------------

    def _on_psyke_jump(self, entry_id: int) -> None:
        if self._on_open_psyke_entry:
            self._on_open_psyke_entry(entry_id)

    def _on_entity_hover_show(
        self,
        entry_id: int,
        editor: QTextEdit,
        pos,
    ) -> None:
        entry = self._psyke_entry_cache.get(entry_id)
        if entry is None:
            return

        state_text = ""
        scene_id = getattr(editor, "_scene_id", None)
        if scene_id and self._temporal_graph:
            sort_order = self._scene_sort_orders.get(scene_id, 0)
            state = self._temporal_graph.get_entry_state_at(
                entry_id, sort_order,
            )
            if state and state.has_progression:
                state_text = state.progression_text

        notes = (entry.notes or "").strip()
        if len(notes) > 180:
            notes = notes[:177] + "..."

        self._entity_hover_panel.show_entity(
            name=entry.name,
            entry_type=entry.entry_type,
            state_text=state_text,
            notes=notes,
            pos=pos,
        )

    def _on_entity_hover_hide(self) -> None:
        self._entity_hover_panel.schedule_hide()

    # -- Auto-link suggestions -------------------------------------------------

    def _get_ignored_keys(self) -> list[str]:
        raw = get_settings().get("auto_link_ignored") or []
        if isinstance(raw, list):
            return [str(k) for k in raw]
        return []

    def _persist_ignored_key(self, key: str) -> None:
        keys = self._get_ignored_keys()
        if key in keys:
            return
        keys.append(key)
        get_settings().set("auto_link_ignored", keys)

    def _refresh_suggestions(self) -> None:
        if not self._suggestion_banners:
            return
        ignored = self._get_ignored_keys()
        grouped = self._auto_link_suggester.suggest_for_project(
            ignored_keys=ignored,
        )
        for scene_id, banner in self._suggestion_banners.items():
            suggestions = grouped.get(scene_id, [])
            if suggestions:
                banner.show_suggestion(suggestions[0])
            else:
                banner.clear()

    def _on_suggestion_accepted(self, suggestion: Suggestion) -> None:
        kind = suggestion.kind
        if kind == "create":
            self._accept_create(suggestion)
        elif kind == "alias":
            self._accept_alias(suggestion)
        elif kind == "relation":
            self._accept_relation(suggestion)
        elif kind == "memory":
            self._accept_memory(suggestion)

        self._close_banner_for(suggestion)
        self.refresh_psyke_terms()
        self._refresh_suggestions()
        if self._on_data_changed:
            self._on_data_changed()

    def _accept_create(self, suggestion: Suggestion) -> None:
        dialog = PsykeQuickCreateDialog(
            self, initial_name=str(suggestion.data.get("name", "")),
        )
        if dialog.exec() != PsykeQuickCreateDialog.DialogCode.Accepted:
            return
        values = dialog.get_values()
        if not values.get("name"):
            return
        self._db.create_psyke_entry(
            self._project_id,
            name=values["name"],
            entry_type=values.get("entry_type", "other"),
            aliases=values.get("aliases", ""),
            notes=values.get("notes", ""),
            is_global=values.get("is_global", False),
        )

    def _accept_alias(self, suggestion: Suggestion) -> None:
        entry_id = suggestion.data.get("entry_id")
        alias = suggestion.data.get("alias", "")
        if entry_id is None or not alias:
            return
        entry = self._db.get_psyke_entry_by_id(entry_id)
        if entry is None:
            return
        existing = [a.strip() for a in (entry.aliases or "").split(",") if a.strip()]
        if alias not in existing:
            existing.append(alias)
        self._db.update_psyke_entry(
            entry_id=entry_id,
            name=entry.name,
            entry_type=entry.entry_type,
            aliases=", ".join(existing),
            notes=entry.notes or "",
            is_global=entry.is_global,
        )

    def _accept_relation(self, suggestion: Suggestion) -> None:
        a = suggestion.data.get("entry_id")
        b = suggestion.data.get("related_entry_id")
        if a is None or b is None:
            return
        self._db.add_psyke_relation(a, b)

    def _accept_memory(self, suggestion: Suggestion) -> None:
        entry_id = suggestion.data.get("entry_id")
        text = suggestion.data.get("text", "").strip()
        scene_id = suggestion.data.get("scene_id")
        if entry_id is None or not text:
            return
        self._db.create_psyke_progression(
            entry_id=entry_id, text=text, scene_id=scene_id,
        )

    def _on_suggestion_dismissed(self, suggestion: Suggestion) -> None:
        self._close_banner_for(suggestion)
        self._refresh_suggestions()

    def _on_suggestion_ignored(self, suggestion: Suggestion) -> None:
        self._persist_ignored_key(suggestion.entity_key)
        self._close_banner_for(suggestion)
        self._refresh_suggestions()

    def _close_banner_for(self, suggestion: Suggestion) -> None:
        for banner in self._suggestion_banners.values():
            if banner.current is suggestion:
                banner.clear()

    # -- Public API -----------------------------------------------------------

    def scroll_to_scene(self, scene_id: int) -> None:
        editor = self._editors.get(scene_id)
        if editor:
            self._scroll.ensureWidgetVisible(editor, 50, 50)
            editor.setFocus()
