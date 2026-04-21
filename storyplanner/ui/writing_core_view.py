"""Writing Core — immersive, continuous manuscript writing experience.

Presents all scenes as a flowing vertical document with typographic hierarchy,
inline micro-interactions, command palette, focus mode, and creative layer
(context hints, rhythm dots, PSYKE highlighting, review mode).
"""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QEvent, Qt, QTimer
from PySide6.QtGui import (
    QFont,
    QFontDatabase,
    QKeyEvent,
    QKeySequence,
    QShortcut,
    QTextBlockFormat,
    QTextCursor,
)
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from storyplanner.auto_link import AutoLinkSuggester, Suggestion
from storyplanner.creative_layer import (
    analyze_paragraph_rhythm,
    generate_scene_hints,
    compute_review_metrics,
)
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


_CANVAS_MAX_WIDTH = 720
_CANVAS_PADDING_H = 48
_BODY_FONT_SIZE = 18
_BODY_LINE_HEIGHT = 1.65
_FOCUS_LINE_HEIGHT = 1.75


class _SceneEditor(QPlainTextEdit):
    """Borderless editor that blends into the canvas."""

    slash_pressed = None

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("writingCoreEditor")
        self.setFrameShape(QPlainTextEdit.Shape.NoFrame)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._auto_height_timer = QTimer(self)
        self._auto_height_timer.setSingleShot(True)
        self._auto_height_timer.setInterval(30)
        self._auto_height_timer.timeout.connect(self._adjust_height)
        self.textChanged.connect(self._schedule_resize)
        self._scene_id: int | None = None

    def _schedule_resize(self) -> None:
        self._auto_height_timer.start()

    def _adjust_height(self) -> None:
        doc = self.document()
        doc.setTextWidth(self.viewport().width())
        height = int(doc.size().height()) + 20
        min_h = 80
        self.setFixedHeight(max(height, min_h))

    def showEvent(self, event):
        super().showEvent(event)
        QTimer.singleShot(10, self._adjust_height)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._adjust_height()

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if (
            event.text() == "/"
            and self.textCursor().atBlockStart()
            and self.slash_pressed is not None
        ):
            self.slash_pressed(self)
            return
        super().keyPressEvent(event)


class _InlineAction(QPushButton):
    """Near-invisible gutter action that reveals its label on hover."""

    _IDLE_TEXT = "+"

    def __init__(self, text: str, parent: QWidget | None = None) -> None:
        super().__init__(self._IDLE_TEXT, parent)
        self._hover_text = text
        self.setFlat(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setObjectName("writingInlineAction")
        self.setFixedHeight(22)
        self.setToolTip(text)

    def enterEvent(self, event) -> None:  # type: ignore[override]
        self.setText(self._hover_text)
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:  # type: ignore[override]
        self.setText(self._IDLE_TEXT)
        super().leaveEvent(event)


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
        self._db = db
        self._project_id = project_id
        self._on_data_changed = on_data_changed
        self._on_focus_mode_changed = on_focus_mode_changed
        self._on_open_psyke_entry = on_open_psyke_entry
        self._focus_mode = False
        self._use_serif = False
        self._editors: dict[int, _SceneEditor] = {}
        self._save_timers: dict[int, QTimer] = {}
        self._scene_widgets: list[QWidget] = []
        self._header_widgets: list[QWidget] = []
        self._hint_containers: dict[int, QWidget] = {}
        self._rhythm_containers: dict[int, QWidget] = {}
        self._highlighters: dict[int, ManuscriptHighlighter] = {}
        self._click_handlers: dict[int, PsykeClickHandler] = {}
        self._hover_handlers: dict[int, EntityHoverHandler] = {}
        self._suggestion_banners: dict[int, SuggestionBanner] = {}
        self._flow_mode = False
        self._typewriter_mode = False
        self._review_mode = False
        self._review_overlay: QWidget | None = None

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
        self._canvas_layout.setContentsMargins(
            _CANVAS_PADDING_H, 32, _CANVAS_PADDING_H, 64,
        )
        self._canvas_layout.setSpacing(0)
        self._canvas_layout.setAlignment(Qt.AlignmentFlag.AlignHCenter)

        self._inner = QWidget()
        self._inner.setMaximumWidth(_CANVAS_MAX_WIDTH)
        self._inner_layout = QVBoxLayout(self._inner)
        self._inner_layout.setContentsMargins(0, 0, 0, 0)
        self._inner_layout.setSpacing(0)

        self._canvas_layout.addWidget(
            self._inner, alignment=Qt.AlignmentFlag.AlignHCenter,
        )
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

    # -- Data loading ---------------------------------------------------------

    def refresh(self) -> None:
        self._clear_canvas()
        scenes = self._db.get_all_scenes(self._project_id)

        self._scene_sort_orders = {s.id: s.sort_order for s in scenes}
        self._temporal_graph = TemporalGraph(self._db, self._project_id)

        current_act = None
        current_chapter = None

        for scene in scenes:
            act = (scene.act or "").strip()
            chapter = (scene.chapter or "").strip()

            if act and act != current_act:
                current_act = act
                self._add_act_header(act)

            if chapter and chapter != current_chapter:
                current_chapter = chapter
                self._add_chapter_header(chapter)
                self._add_new_scene_action(after_scene_id=None, chapter=chapter)

            self._add_scene_block(scene)
            self._add_new_scene_action(after_scene_id=scene.id)

        if not scenes:
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
        self._hint_containers.clear()
        self._rhythm_containers.clear()
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

    def _add_scene_block(self, scene) -> None:
        container = QWidget()
        container.setObjectName("writingSceneBlock")
        block_layout = QVBoxLayout(container)
        block_layout.setContentsMargins(0, 0, 0, 0)
        block_layout.setSpacing(2)

        if scene.title:
            title = QLabel(scene.title)
            title.setObjectName("writingSceneTitle")
            title.setAlignment(Qt.AlignmentFlag.AlignLeft)
            block_layout.addWidget(title)
            block_layout.addSpacing(6)
            self._header_widgets.append(title)

        editor = _SceneEditor()
        editor._scene_id = scene.id
        editor.setPlainText(scene.content or "")
        editor.slash_pressed = self._on_slash_pressed
        editor.textChanged.connect(
            lambda sid=scene.id: self._schedule_save(sid)
        )
        block_layout.addWidget(editor)

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
        block_layout.addWidget(banner)
        self._suggestion_banners[scene.id] = banner

        hint_container = self._build_hint_row(scene)
        block_layout.addWidget(hint_container)
        self._hint_containers[scene.id] = hint_container

        rhythm_container = self._build_rhythm_row(scene)
        block_layout.addWidget(rhythm_container)
        self._rhythm_containers[scene.id] = rhythm_container

        self._editors[scene.id] = editor
        self._inner_layout.addWidget(container)
        self._inner_layout.addSpacing(20)
        self._scene_widgets.append(container)

    def _add_new_scene_action(
        self, after_scene_id: int | None = None, chapter: str = "",
    ) -> None:
        btn = _InlineAction("+ New Scene")
        btn.clicked.connect(
            lambda _, sid=after_scene_id, ch=chapter: self._create_scene_after(sid, ch)
        )
        self._inner_layout.addWidget(btn)
        self._inner_layout.addSpacing(12)
        self._scene_widgets.append(btn)

    def _add_empty_state(self) -> None:
        msg = QLabel("Begin writing.\nPress / for commands, or click below.")
        msg.setObjectName("writingEmptyState")
        msg.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._inner_layout.addSpacing(80)
        self._inner_layout.addWidget(msg)
        self._inner_layout.addSpacing(24)

        btn = _InlineAction("+ Create First Scene")
        btn.clicked.connect(lambda: self._create_scene_after(None))
        self._inner_layout.addWidget(
            btn, alignment=Qt.AlignmentFlag.AlignCenter,
        )

    # -- Hints -----------------------------------------------------------------

    def _build_hint_row(self, scene) -> QWidget:
        container = QWidget()
        container.setObjectName("writingHintRow")
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 2, 0, 2)
        layout.setSpacing(8)

        hints = generate_scene_hints(self._db, self._project_id, scene.id)
        for hint in hints:
            lbl = QLabel(hint.message)
            lbl.setObjectName("writingHint")
            layout.addWidget(lbl)
        layout.addStretch()

        if not hints:
            container.hide()

        return container

    # -- Rhythm dots -----------------------------------------------------------

    def _build_rhythm_row(self, scene) -> QWidget:
        container = QWidget()
        container.setObjectName("writingRhythmRow")
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 2, 0, 0)
        layout.setSpacing(3)

        content = scene.content or ""
        rhythm = analyze_paragraph_rhythm(content, scene.id)

        for dot in rhythm.dots:
            d = QLabel()
            d.setFixedSize(8, 8)
            if dot.length == "short":
                d.setObjectName("rhythmDotShort")
            elif dot.length == "long":
                d.setObjectName("rhythmDotLong")
            else:
                d.setObjectName("rhythmDotMedium")
            d.setToolTip(f"{dot.word_count} words")
            layout.addWidget(d)
        layout.addStretch()

        if not rhythm.dots:
            container.hide()

        return container

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

        editor_style = (
            f"#writingCoreEditor {{"
            f"  background-color: transparent;"
            f"  color: {theme.TEXT_PRIMARY};"
            f"  border: none;"
            f"  padding: 0;"
            f"  font-family: {family};"
            f"  font-size: {_BODY_FONT_SIZE}px;"
            f"  selection-background-color: {theme.SELECTION_BG};"
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
            f"  color: {theme.TEXT_PRIMARY};"
            f"  font-size: 22px;"
            f"  font-weight: 600;"
            f"  font-family: {family};"
            f"  background: transparent;"
            f"  padding: 0;"
            f"}}"
        )

        sep_style = ""

        scene_block_style = (
            f"#writingSceneBlock {{"
            f"  background: transparent;"
            f"  border: none;"
            f"}}"
        )

        inline_action_style = (
            f"#writingInlineAction {{"
            f"  color: {theme.TEXT_MUTED};"
            f"  font-size: 12px;"
            f"  background: transparent;"
            f"  border: none;"
            f"  padding: 0;"
            f"  text-align: center;"
            f"}}"
            f"#writingInlineAction:hover {{"
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

        hint_style = (
            f"#writingHintRow {{"
            f"  background: transparent;"
            f"}}"
            f"#writingHint {{"
            f"  color: {theme.TEXT_MUTED};"
            f"  font-size: 12px;"
            f"  font-style: italic;"
            f"  background: transparent;"
            f"  padding: 0 4px;"
            f"}}"
        )

        rhythm_style = (
            f"#writingRhythmRow {{"
            f"  background: transparent;"
            f"}}"
            f"#rhythmDotShort {{"
            f"  background-color: {theme.ACCENT};"
            f"  border-radius: 4px;"
            f"}}"
            f"#rhythmDotMedium {{"
            f"  background-color: {theme.TEXT_MUTED};"
            f"  border-radius: 4px;"
            f"}}"
            f"#rhythmDotLong {{"
            f"  background-color: {theme.STATUS_ERR};"
            f"  border-radius: 4px;"
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

        full_style = (
            editor_style + act_style + chapter_style + scene_title_style
            + sep_style + scene_block_style + inline_action_style
            + canvas_style + scroll_style + empty_style + focus_dim
            + hint_style + rhythm_style + review_style
            + format_toolbar_style + entity_hover_style + suggestion_style
        )
        self.setStyleSheet(full_style)

        for editor in self._editors.values():
            self._apply_line_spacing(editor, lh)

    def _apply_line_spacing(self, editor: _SceneEditor, lh: float) -> None:
        cursor = editor.textCursor()
        cursor.select(QTextCursor.SelectionType.Document)
        fmt = QTextBlockFormat()
        fmt.setLineHeight(
            lh * 100, QTextBlockFormat.LineHeightTypes.ProportionalHeight.value,
        )
        cursor.mergeBlockFormat(fmt)

    def _toggle_font(self) -> None:
        self._use_serif = not self._use_serif
        self._font_toggle.setText("Sans" if self._use_serif else "Serif")
        self._apply_typography()

    # -- Focus mode -----------------------------------------------------------

    def toggle_focus_mode(self) -> None:
        self._focus_mode = not self._focus_mode
        self._top_bar.setVisible(not self._focus_mode)
        self._focus_bar.setVisible(self._focus_mode)

        if self._focus_mode:
            self._canvas_layout.setContentsMargins(
                _CANVAS_PADDING_H, 24, _CANVAS_PADDING_H, 64,
            )
            self._inner.setMaximumWidth(_CANVAS_MAX_WIDTH + 40)
            for c in self._hint_containers.values():
                c.setVisible(False)
            for c in self._rhythm_containers.values():
                c.setVisible(False)
        else:
            self._canvas_layout.setContentsMargins(
                _CANVAS_PADDING_H, 32, _CANVAS_PADDING_H, 64,
            )
            self._inner.setMaximumWidth(_CANVAS_MAX_WIDTH)
            for scene_id, c in self._hint_containers.items():
                c.setVisible(bool(c.findChildren(QLabel)))
            for c in self._rhythm_containers.values():
                c.setVisible(bool(c.findChildren(QLabel)))

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
        target = cursor_y - viewport_h // 2
        sb = self._scroll.verticalScrollBar()
        sb.setValue(max(0, min(target, sb.maximum())))

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
        editor: QPlainTextEdit,
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
