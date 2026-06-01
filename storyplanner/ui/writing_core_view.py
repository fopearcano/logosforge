"""Writing Core — continuous manuscript editor.

Scenes render as bare inline sections (muted title + editor) in a single
720 px column with 44 px spacing. No containers, no cards, no borders.
"""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QEasingCurve, QEvent, QPointF, QPropertyAnimation, Qt, QThread, QTimer, Signal
from PySide6.QtGui import (
    QAction,
    QBrush,
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
    QTextListFormat,
)
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFrame,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QMenu,
    QTextEdit,
    QToolTip,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from storyplanner.auto_link import AutoLinkSuggester, Suggestion
from storyplanner.grammar_checker import Issue as GrammarIssue, check_text, detect_language
from storyplanner.context_assistant import ContextAssistant, ContextHint, HintRateLimiter
from storyplanner.style_analysis import (
    STYLE_SENSITIVITY_LEVELS,
    StyleContext,
    StyleHint,
    StyleSuggestion,
    build_style_context,
    detect_style_hints,
    generate_style_suggestions,
)
from storyplanner.paragraph_energy import (
    FlowHint,
    ParagraphEnergy,
    SENSITIVITY_LEVELS,
    StoryContext,
    analyze_scene_energy,
    build_story_context,
    detect_flow_hints,
)
from storyplanner.creative_layer import compute_review_metrics
from storyplanner.dialogue_attribution import DialogueSegment, attribute_dialogue
from storyplanner.voice_consistency import (
    VOICE_SENSITIVITY_LEVELS,
    VoiceDeviation,
    check_consistency,
    sensitivity_threshold,
)
from storyplanner.voice_learner import (
    VoiceRewrite,
    adjust_voice_for_state,
    generate_voice_rewrites,
)
from storyplanner.db import Database
from storyplanner.structural_intelligence import StructuralCache
from storyplanner.settings import get_manager as get_settings
from storyplanner.ui import theme
from storyplanner.ui.command_palette import CommandPalette
from storyplanner.ui.context_hint_banner import ContextHintBanner
from storyplanner.ui.entity_hover import EntityHoverHandler, EntityHoverPanel
from storyplanner.ui.format_toolbar import FormatToolbar
from storyplanner.ui.psyke_highlighter import PsykeClickHandler, PsykeHighlighter
from storyplanner.ui.psyke_quick_create import PsykeQuickCreateDialog
from storyplanner.ui.suggestion_banner import SuggestionBanner
from storyplanner.temporal_psyke import TemporalGraph
from storyplanner.writing_formats import ALL_FORMATS, WritingFormat


_CANVAS_MAX_WIDTH = 680
_CANVAS_PADDING_H = 64
_BODY_FONT_SIZE = 18

_FONT_PRESETS: dict[str, list[str]] = {
    "serif": ["Georgia", "Noto Serif", "serif"],
    "sans": ["Segoe UI", "Helvetica Neue", "Helvetica", "Arial", "Noto Sans", "sans-serif"],
    "georgia": ["Georgia", "serif"],
    "times": ["Times New Roman", "Times", "serif"],
    "garamond": ["Garamond", "EB Garamond", "serif"],
    "baskerville": ["Baskerville", "Libre Baskerville", "serif"],
    "palatino": ["Palatino", "Palatino Linotype", "Book Antiqua", "serif"],
    "charter": ["Charter", "Bitstream Charter", "serif"],
    "arial": ["Arial", "Liberation Sans", "sans-serif"],
    "helvetica": ["Helvetica", "Arial", "sans-serif"],
    "verdana": ["Verdana", "DejaVu Sans", "sans-serif"],
    "courier_new": ["Courier New", "Courier", "monospace"],
    "courier": ["Courier", "Courier New", "monospace"],
    "mono": ["Fira Code", "Consolas", "monospace"],
}
_FONT_PRESET_LABELS: dict[str, str] = {
    "serif": "Serif",
    "sans": "Sans-serif",
    "georgia": "Georgia",
    "times": "Times New Roman",
    "garamond": "Garamond",
    "baskerville": "Baskerville",
    "palatino": "Palatino",
    "charter": "Charter",
    "arial": "Arial",
    "helvetica": "Helvetica",
    "verdana": "Verdana",
    "courier_new": "Courier New",
    "courier": "Courier",
    "mono": "Monospace",
}
_FONT_PRESET_ORDER = [
    "serif", "sans", "georgia", "times", "garamond", "baskerville",
    "palatino", "charter", "arial", "helvetica", "verdana",
    "courier_new", "courier", "mono",
]
_TEXT_COLOR_PALETTE: list[tuple[str, str]] = [
    ("Default", ""),
    ("White", "#FFFFFF"),
    ("Off-white", "#F5F1E8"),
    ("Black", "#000000"),
    ("Gray", "#808080"),
    ("Red", "#D9534F"),
    ("Orange", "#F0AD4E"),
    ("Yellow", "#F1C40F"),
    ("Green", "#5CB85C"),
    ("Blue", "#3B8BEB"),
    ("Purple", "#9B59B6"),
]
_BG_COLOR_PALETTE: list[tuple[str, str]] = [
    ("Default dark", ""),
    ("Warm dark", "#1C1914"),
    ("Paper light", "#F5F1E8"),
    ("Soft green", "#1A2420"),
    ("Soft amber", "#221E14"),
    ("Black", "#000000"),
]
_FONT_SIZE_OPTIONS = [14, 15, 16, 17, 18, 19, 20, 22, 24]
_LANGUAGE_OPTIONS = [
    ("auto", "Auto"),
    ("en", "English"),
    ("it", "Italian"),
    ("es", "Spanish"),
    ("fr", "French"),
    ("de", "German"),
]
_BODY_LINE_HEIGHT = 1.5
_FOCUS_LINE_HEIGHT = 1.6
_FADE_ALPHA_PARA = 70
_FADE_ALPHA_SCENE = 110


def _element_text_color(color_key: str) -> str:
    """Resolve an ElementStyle.color_key to a live theme colour, or ""."""
    return {
        "muted": theme.TEXT_MUTED,
        "secondary": theme.TEXT_SECONDARY,
        "accent": theme.ACCENT,
    }.get(color_key, "")


def _element_bg_color(background_key: str) -> str:
    """Resolve an ElementStyle.background_key to a subtle band colour, or ""."""
    return {
        "panel": theme.BG_PANEL,
        "sfx": theme.BG_HOVER,
        "note": theme.BG_PANEL,
    }.get(background_key, "")

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
        "act_heading": "scene_heading",
        "scene_heading": "stage_direction",
        "stage_direction": "dialogue",
        "character": "dialogue",
        "dialogue": "character",
        "parenthetical": "dialogue",
        "aside": "dialogue",
        "cue": "dialogue",
        "transition": "scene_heading",
    },
    "series": {
        "season_heading": "episode_heading",
        "episode_heading": "act_heading",
        "act_heading": "scene_heading",
        "teaser": "scene_heading",
        "cold_open": "scene_heading",
        "scene_heading": "action",
        "action": "action",
        "character": "dialogue",
        "dialogue": "action",
        "a_plot": "scene_heading",
        "b_plot": "scene_heading",
        "c_plot": "scene_heading",
        "tag": "action",
    },
}


class _BlockData(QTextBlockUserData):
    """Stores the element type for a single text block."""

    def __init__(self, element: str = "") -> None:
        super().__init__()
        self.element = element


_GRAMMAR_CACHE: dict[int, list[GrammarIssue]] = {}

_STYLE_HINT_CACHE: dict[int, list[StyleHint]] = {}
_STYLE_HINT_CACHE_MAX = 512
_GRAMMAR_CACHE_MAX = 512


class _GrammarWorker(QThread):
    """Runs grammar checks off the main thread."""

    finished = Signal(int, object)

    def __init__(self, generation: int, scenes: dict[int, str]) -> None:
        super().__init__()
        self._generation = generation
        self._scenes = scenes
        self._cancelled = False

    def cancel(self) -> None:
        self._cancelled = True

    def run(self) -> None:
        results: dict[int, list[GrammarIssue]] = {}
        for scene_id, text in self._scenes.items():
            if self._cancelled:
                return
            if not text.strip():
                results[scene_id] = []
                continue
            paragraphs = text.split("\n")
            scene_issues: list[GrammarIssue] = []
            offset = 0
            for para in paragraphs:
                if self._cancelled:
                    return
                para_hash = hash(para)
                cached = _GRAMMAR_CACHE.get(para_hash)
                if cached is not None:
                    for issue in cached:
                        scene_issues.append(GrammarIssue(
                            start=issue.start + offset,
                            end=issue.end + offset,
                            issue_type=issue.issue_type,
                            message=issue.message,
                            suggestions=issue.suggestions,
                        ))
                else:
                    if para.strip():
                        para_issues = check_text(para)
                        if len(_GRAMMAR_CACHE) >= _GRAMMAR_CACHE_MAX:
                            _GRAMMAR_CACHE.clear()
                        _GRAMMAR_CACHE[para_hash] = para_issues
                        for issue in para_issues:
                            scene_issues.append(GrammarIssue(
                                start=issue.start + offset,
                                end=issue.end + offset,
                                issue_type=issue.issue_type,
                                message=issue.message,
                                suggestions=issue.suggestions,
                            ))
                offset += len(para) + 1
            results[scene_id] = scene_issues
        if not self._cancelled:
            self.finished.emit(self._generation, results)


class _StyleHintWorker(QThread):
    """Runs style hint detection off the main thread."""

    finished = Signal(int, object)

    def __init__(
        self,
        generation: int,
        scenes: dict[int, str],
        sensitivity: str = "medium",
    ) -> None:
        super().__init__()
        self._generation = generation
        self._scenes = scenes
        self._sensitivity = sensitivity
        self._cancelled = False

    def cancel(self) -> None:
        self._cancelled = True

    def run(self) -> None:
        results: dict[int, list[StyleHint]] = {}
        for scene_id, text in self._scenes.items():
            if self._cancelled:
                return
            if not text.strip():
                results[scene_id] = []
                continue
            paragraphs = text.split("\n")
            scene_hints: list[StyleHint] = []
            offset = 0
            for para in paragraphs:
                if self._cancelled:
                    return
                cache_key = (hash(para), self._sensitivity)
                cached = _STYLE_HINT_CACHE.get(cache_key)
                if cached is not None:
                    for h in cached:
                        scene_hints.append(StyleHint(
                            start=h.start + offset,
                            end=h.end + offset,
                            hint_type=h.hint_type,
                            message=h.message,
                        ))
                else:
                    if para.strip():
                        para_hints = detect_style_hints(
                            para, sensitivity=self._sensitivity,
                        )
                        if len(_STYLE_HINT_CACHE) >= _STYLE_HINT_CACHE_MAX:
                            _STYLE_HINT_CACHE.clear()
                        _STYLE_HINT_CACHE[cache_key] = para_hints
                        for h in para_hints:
                            scene_hints.append(StyleHint(
                                start=h.start + offset,
                                end=h.end + offset,
                                hint_type=h.hint_type,
                                message=h.message,
                            ))
                offset += len(para) + 1
            results[scene_id] = scene_hints
        if not self._cancelled:
            self.finished.emit(self._generation, results)


class _VoiceConsistencyWorker(QThread):
    """Runs voice consistency checks off the main thread."""

    finished = Signal(int, object)

    def __init__(
        self,
        generation: int,
        scenes: dict[int, str],
        characters: list,
        profiles: dict[int, dict],
        scene_states: dict[int, list[tuple[int, str]]] | None = None,
        threshold: float = 0.45,
    ) -> None:
        super().__init__()
        self._generation = generation
        self._scenes = scenes
        self._characters = characters
        self._profiles = profiles
        self._scene_states = scene_states or {}
        self._threshold = threshold
        self._cancelled = False

    def cancel(self) -> None:
        self._cancelled = True

    def _adjusted_profiles(self, scene_id: int) -> dict[int, dict]:
        states = self._scene_states.get(scene_id, [])
        if not states:
            return self._profiles
        adjusted: dict[int, dict] = {}
        state_by_char: dict[int, str] = {}
        for cid, st in states:
            state_by_char[cid] = st
        for cid, prof in self._profiles.items():
            st = state_by_char.get(cid, "")
            adjusted[cid] = adjust_voice_for_state(prof, st) if st else prof
        return adjusted

    def run(self) -> None:
        results: dict[int, list[VoiceDeviation]] = {}
        for scene_id, text in self._scenes.items():
            if self._cancelled:
                return
            if not text.strip():
                results[scene_id] = []
                continue
            segments = attribute_dialogue(text, self._characters)
            profiles = self._adjusted_profiles(scene_id)
            deviations = check_consistency(
                segments, profiles, threshold=self._threshold,
            )
            results[scene_id] = deviations
        if not self._cancelled:
            self.finished.emit(self._generation, results)


class _GrammarPopup(QWidget):
    """Floating popup for grammar/spelling issue fixes."""

    suggestion_chosen = Signal(object, str)  # (issue, replacement)
    issue_ignored = Signal(object)  # issue

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint,
        )
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, False)
        self.setObjectName("grammarPopup")

        self._issue: GrammarIssue | None = None
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(8, 6, 8, 6)
        self._layout.setSpacing(4)

        self._msg_label = QLabel()
        self._msg_label.setObjectName("grammarPopupMsg")
        self._msg_label.setWordWrap(True)
        self._layout.addWidget(self._msg_label)

        self._btn_row = QHBoxLayout()
        self._btn_row.setSpacing(4)
        self._layout.addLayout(self._btn_row)

        self._suggestion_btns: list[QPushButton] = []

        self._ignore_btn = QPushButton("Ignore")
        self._ignore_btn.setFlat(True)
        self._ignore_btn.setObjectName("grammarPopupIgnore")
        self._ignore_btn.clicked.connect(self._on_ignore)

        self.setStyleSheet(f"""
            #grammarPopup {{
                background: {theme.BG_PANEL};
                border: 1px solid {theme.BG_HOVER};
                border-radius: 6px;
            }}
            #grammarPopupMsg {{
                color: {theme.TEXT_SECONDARY};
                font-size: 11px;
            }}
            #grammarPopupIgnore {{
                color: {theme.TEXT_MUTED};
                font-size: 11px;
                padding: 2px 6px;
            }}
            QPushButton {{
                color: {theme.TEXT_PRIMARY};
                background: {theme.BG_INPUT};
                border: 1px solid {theme.BG_HOVER};
                border-radius: 4px;
                font-size: 12px;
                padding: 3px 10px;
            }}
            QPushButton:hover {{
                background: {theme.BG_HOVER};
            }}
        """)
        self.setMaximumWidth(320)

    def show_for_issue(self, issue: GrammarIssue, global_pos) -> None:
        self._issue = issue

        type_label = issue.issue_type.capitalize()
        self._msg_label.setText(f"<b>{type_label}:</b> {issue.message}")

        for btn in self._suggestion_btns:
            self._btn_row.removeWidget(btn)
            btn.deleteLater()
        self._suggestion_btns.clear()

        if self._ignore_btn.parent():
            self._btn_row.removeWidget(self._ignore_btn)

        for suggestion in issue.suggestions[:4]:
            btn = QPushButton(suggestion)
            btn.clicked.connect(
                lambda _, s=suggestion: self._on_suggestion(s),
            )
            self._btn_row.addWidget(btn)
            self._suggestion_btns.append(btn)

        self._btn_row.addWidget(self._ignore_btn)

        self.adjustSize()
        self.move(global_pos)
        self.show()

    def _on_suggestion(self, replacement: str) -> None:
        if self._issue is not None:
            self.suggestion_chosen.emit(self._issue, replacement)
        self.hide()

    def _on_ignore(self) -> None:
        if self._issue is not None:
            self.issue_ignored.emit(self._issue)
        self.hide()


class _StyleSuggestionPopup(QWidget):
    """Floating popup that shows 1-3 style suggestions + optional rewrite."""

    rewrite_accepted = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint,
        )
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, False)
        self.setObjectName("styleSuggestionPopup")
        self.setMaximumWidth(360)

        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(10, 8, 10, 8)
        self._layout.setSpacing(4)

        self._header = QLabel()
        self._header.setObjectName("styleSuggestionHeader")
        self._layout.addWidget(self._header)

        self._suggestion_labels: list[QLabel] = []
        self._rewrite_btn: QPushButton | None = None
        self._rewrite_text: str | None = None

        self.setStyleSheet(f"""
            #styleSuggestionPopup {{
                background: {theme.BG_PANEL};
                border: 1px solid {theme.BG_HOVER};
                border-radius: 6px;
            }}
            #styleSuggestionHeader {{
                color: {theme.TEXT_SECONDARY};
                font-size: 11px;
                font-weight: bold;
            }}
            .QLabel {{
                color: {theme.TEXT_PRIMARY};
                font-size: 12px;
                background: transparent;
            }}
            QPushButton {{
                color: {theme.TEXT_PRIMARY};
                background: {theme.BG_INPUT};
                border: 1px solid {theme.BG_HOVER};
                border-radius: 4px;
                font-size: 12px;
                padding: 3px 10px;
            }}
            QPushButton:hover {{
                background: {theme.BG_HOVER};
            }}
        """)

    def show_suggestions(
        self,
        suggestions: list[StyleSuggestion],
        rewrite: str | None,
        global_pos,
    ) -> None:
        for lbl in self._suggestion_labels:
            self._layout.removeWidget(lbl)
            lbl.deleteLater()
        self._suggestion_labels.clear()
        if self._rewrite_btn is not None:
            self._layout.removeWidget(self._rewrite_btn)
            self._rewrite_btn.deleteLater()
            self._rewrite_btn = None
        self._rewrite_text = None

        if not suggestions:
            self._header.setText("No suggestions — looks good!")
        else:
            self._header.setText("Style suggestions:")

        for s in suggestions:
            lbl = QLabel(f"  • {s.message}")
            lbl.setWordWrap(True)
            self._layout.addWidget(lbl)
            self._suggestion_labels.append(lbl)

        if rewrite is not None:
            self._rewrite_text = rewrite
            btn = QPushButton("Apply rewrite")
            btn.clicked.connect(self._on_rewrite)
            self._layout.addWidget(btn)
            self._rewrite_btn = btn

        self.adjustSize()
        self.move(global_pos)
        self.show()

    def _on_rewrite(self) -> None:
        if self._rewrite_text is not None:
            self.rewrite_accepted.emit(self._rewrite_text)
        self.hide()


class _VoiceRewritePopup(QWidget):
    """Floating popup that shows 1–2 voice-matched rewrite alternatives."""

    rewrite_accepted = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint,
        )
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, False)
        self.setObjectName("voiceRewritePopup")
        self.setMaximumWidth(400)

        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(10, 8, 10, 8)
        self._layout.setSpacing(4)

        self._header = QLabel()
        self._header.setObjectName("voiceRewriteHeader")
        self._layout.addWidget(self._header)

        self._option_widgets: list[QWidget] = []

        self.setStyleSheet(f"""
            #voiceRewritePopup {{
                background: {theme.BG_PANEL};
                border: 1px solid {theme.BG_HOVER};
                border-radius: 6px;
            }}
            #voiceRewriteHeader {{
                color: {theme.TEXT_SECONDARY};
                font-size: 11px;
                font-weight: bold;
            }}
            .QLabel {{
                color: {theme.TEXT_PRIMARY};
                font-size: 12px;
                background: transparent;
            }}
            QPushButton {{
                color: {theme.TEXT_PRIMARY};
                background: {theme.BG_INPUT};
                border: 1px solid {theme.BG_HOVER};
                border-radius: 4px;
                font-size: 12px;
                padding: 3px 10px;
            }}
            QPushButton:hover {{
                background: {theme.BG_HOVER};
            }}
        """)

    def show_rewrites(
        self,
        rewrites: list[VoiceRewrite],
        global_pos,
    ) -> None:
        for w in self._option_widgets:
            self._layout.removeWidget(w)
            w.deleteLater()
        self._option_widgets.clear()

        if not rewrites:
            self._header.setText("No voice rewrites needed — line matches profile.")
        else:
            self._header.setText("Rewrite in character voice:")

        for rw in rewrites:
            lbl = QLabel(f"  {rw.label}")
            lbl.setWordWrap(True)
            self._layout.addWidget(lbl)
            self._option_widgets.append(lbl)

            preview = QLabel(f'    "{rw.text}"')
            preview.setWordWrap(True)
            preview.setStyleSheet(f"color: {theme.TEXT_MUTED}; font-style: italic;")
            self._layout.addWidget(preview)
            self._option_widgets.append(preview)

            btn = QPushButton("Apply")
            btn.clicked.connect(lambda _c=False, t=rw.text: self._accept(t))
            self._layout.addWidget(btn)
            self._option_widgets.append(btn)

        self.adjustSize()
        self.move(global_pos)
        self.show()

    def _accept(self, text: str) -> None:
        self.rewrite_accepted.emit(text)
        self.hide()


class _SceneEditor(QTextEdit):
    """Borderless editor with focus-fade overlay and cross-scene navigation.

    Uses QTextEdit (not QPlainTextEdit) so that QTextBlockFormat margins
    are honoured by the full QTextDocumentLayout.
    """

    slash_pressed = None
    _on_nav_next = None
    _on_nav_prev = None
    _on_new_block = None
    _on_tab_cycle = None
    _on_psyke_context_action = None

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
        self.setAcceptRichText(True)
        self.setMouseTracking(True)
        self._auto_height_timer = QTimer(self)
        self._auto_height_timer.setSingleShot(True)
        self._auto_height_timer.setInterval(30)
        self._auto_height_timer.timeout.connect(self._adjust_height)
        self.textChanged.connect(self._schedule_resize)
        self._scene_id: int | None = None
        self._smart_quotes = False
        self._grammar_issues: list[GrammarIssue] = []
        self._grammar_enabled = False
        self._ignored_issues: set[tuple[str, str]] = set()
        self._style_hints: list[StyleHint] = []
        self._style_hints_enabled = False
        self._style_context: StyleContext | None = None
        self._voice_deviations: list[VoiceDeviation] = []
        self._voice_hints_enabled = False
        self._grammar_popup = _GrammarPopup()
        self._grammar_popup.suggestion_chosen.connect(self._on_popup_suggestion)
        self._grammar_popup.issue_ignored.connect(self._on_popup_ignore)
        self._style_suggestion_popup = _StyleSuggestionPopup()
        self._style_suggestion_popup.rewrite_accepted.connect(
            self._on_style_rewrite,
        )
        self._voice_rewrite_popup = _VoiceRewritePopup()
        self._voice_rewrite_popup.rewrite_accepted.connect(
            self._on_voice_rewrite,
        )
        self._voice_profile_data: dict | None = None
        self._voice_state_text: str = ""
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
        if event.key() == Qt.Key.Key_Tab and self._on_tab_cycle is not None:
            forward = not (event.modifiers() & Qt.KeyboardModifier.ShiftModifier)
            self._on_tab_cycle(self, forward)
            return
        if event.key() == Qt.Key.Key_Backtab and self._on_tab_cycle is not None:
            self._on_tab_cycle(self, False)
            return
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
        if self._try_auto_format(event):
            return
        super().keyPressEvent(event)

    def _try_auto_format(self, event: QKeyEvent) -> bool:
        ch = event.text()
        if not ch:
            return False
        cursor = self.textCursor()
        pos_in_block = cursor.positionInBlock()
        text = cursor.block().text()
        prev = text[pos_in_block - 1] if pos_in_block > 0 else ""

        if ch == "-" and prev == "-":
            cursor.movePosition(
                QTextCursor.MoveOperation.Left,
                QTextCursor.MoveMode.KeepAnchor, 1,
            )
            cursor.insertText("—")
            return True

        if self._smart_quotes and ch == '"':
            opens = pos_in_block == 0 or prev in (" ", "\t", "(", "[", "{", "—", "\n")
            cursor.insertText("“" if opens else "”")
            return True

        if self._smart_quotes and ch == "'":
            opens = pos_in_block == 0 or prev in (" ", "\t", "(", "[", "{", "—", "\n")
            cursor.insertText("‘" if opens else "’")
            return True

        if ch == "." and pos_in_block >= 2 and text[pos_in_block - 2:pos_in_block] == "..":
            cursor.movePosition(
                QTextCursor.MoveOperation.Left,
                QTextCursor.MoveMode.KeepAnchor, 2,
            )
            cursor.insertText("…")
            return True

        return False

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if (
            self._grammar_enabled
            and event.button() == Qt.MouseButton.LeftButton
        ):
            issue = self._issue_at_cursor(event.pos())
            if issue is not None:
                self._show_grammar_popup(issue, event.globalPos())
                return
        super().mousePressEvent(event)

    def contextMenuEvent(self, event) -> None:  # noqa: N802
        issue = self._issue_at_cursor(event.pos()) if self._grammar_enabled else None
        if issue is not None:
            self._show_grammar_popup(issue, event.globalPos())
            return

        menu = self.createStandardContextMenu()
        first_action = menu.actions()[0] if menu.actions() else None
        entry_id = self._resolve_psyke_at(event.pos())
        if entry_id is not None:
            psyke_sep = menu.insertSeparator(first_action)
            open_act = menu.addAction("Open in Story Bible")
            menu.removeAction(open_act)
            menu.insertAction(psyke_sep, open_act)
            open_act.triggered.connect(
                lambda _, eid=entry_id: self._fire_psyke_action("open", eid),
            )
        if self.textCursor().hasSelection():
            menu.addSeparator()
            style_act = menu.addAction("Style Improve")
            style_act.triggered.connect(
                lambda: self._show_style_suggestions(event.globalPos()),
            )
            if self._voice_profile_data is not None:
                voice_act = menu.addAction("Voice Rewrite")
                voice_act.triggered.connect(
                    lambda: self._show_voice_rewrites(event.globalPos()),
                )
        menu.exec(event.globalPos())
        menu.deleteLater()

    def _show_grammar_popup(self, issue: GrammarIssue, global_pos) -> None:
        self._grammar_popup.show_for_issue(issue, global_pos)

    def _apply_suggestion(self, issue: GrammarIssue, replacement: str) -> None:
        cursor = QTextCursor(self.document())
        cursor.setPosition(issue.start)
        cursor.setPosition(issue.end, QTextCursor.MoveMode.KeepAnchor)
        cursor.insertText(replacement)

    def _on_popup_suggestion(self, issue: GrammarIssue, replacement: str) -> None:
        self._apply_suggestion(issue, replacement)

    def _on_popup_ignore(self, issue: GrammarIssue) -> None:
        key = (issue.issue_type, issue.message)
        self._ignored_issues.add(key)
        self.apply_grammar_underlines()

    def _show_style_suggestions(self, global_pos) -> None:
        cursor = self.textCursor()
        if not cursor.hasSelection():
            return
        text = cursor.selectedText().replace(" ", "\n")
        suggestions, rewrite = generate_style_suggestions(
            text, context=self._style_context,
        )
        self._style_suggestion_popup.show_suggestions(
            suggestions, rewrite, global_pos,
        )

    def _on_style_rewrite(self, rewrite: str) -> None:
        cursor = self.textCursor()
        if cursor.hasSelection():
            cursor.insertText(rewrite)

    def _show_voice_rewrites(self, global_pos) -> None:
        cursor = self.textCursor()
        if not cursor.hasSelection():
            return
        if self._voice_profile_data is None:
            return
        text = cursor.selectedText().replace(" ", "\n")
        profile = adjust_voice_for_state(
            self._voice_profile_data, self._voice_state_text,
        )
        rewrites = generate_voice_rewrites(text, profile)
        self._voice_rewrite_popup.show_rewrites(rewrites, global_pos)

    def _on_voice_rewrite(self, rewrite: str) -> None:
        cursor = self.textCursor()
        if cursor.hasSelection():
            cursor.insertText(rewrite)

    def _resolve_psyke_at(self, pos) -> int | None:
        if self._on_psyke_context_action is None:
            return None
        cursor = self.cursorForPosition(pos)
        block = cursor.block()
        col = cursor.positionInBlock()
        text = block.text()
        cb = self._on_psyke_context_action
        return cb("resolve", text, col)

    def _fire_psyke_action(self, action: str, entry_id: int) -> None:
        if self._on_psyke_context_action:
            self._on_psyke_context_action(action, entry_id, 0)

    def apply_grammar_underlines(self) -> None:
        _STYLES = {
            "spelling": (
                QColor(theme.get("GRAMMAR_SPELLING")),
                QTextCharFormat.UnderlineStyle.WaveUnderline,
            ),
            "grammar": (
                QColor(theme.get("GRAMMAR_GRAMMAR")),
                QTextCharFormat.UnderlineStyle.WaveUnderline,
            ),
            "style": (
                QColor(theme.get("GRAMMAR_STYLE")),
                QTextCharFormat.UnderlineStyle.DotLine,
            ),
        }
        _DEFAULT = (QColor(theme.get("GRAMMAR_SPELLING")),
                     QTextCharFormat.UnderlineStyle.WaveUnderline)

        selections: list[QTextEdit.ExtraSelection] = []
        doc = self.document()
        doc_len = doc.characterCount()

        grammar_spans: list[tuple[int, int]] = []
        for issue in self._grammar_issues:
            if issue.start < 0 or issue.end > doc_len:
                continue
            key = (issue.issue_type, issue.message)
            if key in self._ignored_issues:
                continue
            grammar_spans.append((issue.start, issue.end))
            color, style = _STYLES.get(issue.issue_type, _DEFAULT)
            sel = QTextEdit.ExtraSelection()
            fmt = QTextCharFormat()
            fmt.setUnderlineStyle(style)
            fmt.setUnderlineColor(color)
            tip = issue.message
            if issue.suggestions:
                tip += f"  →  {', '.join(issue.suggestions[:3])}"
            fmt.setToolTip(tip)
            cursor = QTextCursor(doc)
            cursor.setPosition(issue.start)
            cursor.setPosition(issue.end, QTextCursor.MoveMode.KeepAnchor)
            sel.cursor = cursor
            sel.format = fmt
            selections.append(sel)

        voice_spans: list[tuple[int, int]] = []
        if self._voice_hints_enabled:
            voice_color = QColor(theme.get("VOICE_HINT"))
            for dev in self._voice_deviations:
                vs, ve = dev.segment.start_pos, dev.segment.end_pos
                if vs < 0 or ve > doc_len:
                    continue
                if any(
                    gs <= vs < ge or gs < ve <= ge
                    or (vs <= gs and ve >= ge)
                    for gs, ge in grammar_spans
                ):
                    continue
                voice_spans.append((vs, ve))
                sel = QTextEdit.ExtraSelection()
                fmt = QTextCharFormat()
                fmt.setUnderlineStyle(QTextCharFormat.UnderlineStyle.DashUnderline)
                fmt.setUnderlineColor(voice_color)
                reason_text = "; ".join(dev.reasons) if dev.reasons else "Voice deviation"
                fmt.setToolTip(reason_text)
                cursor = QTextCursor(doc)
                cursor.setPosition(vs)
                cursor.setPosition(ve, QTextCursor.MoveMode.KeepAnchor)
                sel.cursor = cursor
                sel.format = fmt
                selections.append(sel)

        occupied = grammar_spans + voice_spans
        if self._style_hints_enabled:
            hint_color = QColor(theme.get("STYLE_HINT"))
            for hint in self._style_hints:
                if hint.start < 0 or hint.end > doc_len:
                    continue
                if any(
                    os <= hint.start < oe or os < hint.end <= oe
                    or (hint.start <= os and hint.end >= oe)
                    for os, oe in occupied
                ):
                    continue
                sel = QTextEdit.ExtraSelection()
                fmt = QTextCharFormat()
                fmt.setUnderlineStyle(QTextCharFormat.UnderlineStyle.DotLine)
                fmt.setUnderlineColor(hint_color)
                fmt.setToolTip(hint.message)
                cursor = QTextCursor(doc)
                cursor.setPosition(hint.start)
                cursor.setPosition(hint.end, QTextCursor.MoveMode.KeepAnchor)
                sel.cursor = cursor
                sel.format = fmt
                selections.append(sel)

        self.setExtraSelections(selections)

    def _issue_at_cursor(self, pos) -> GrammarIssue | None:
        cursor = self.cursorForPosition(pos)
        abs_pos = cursor.position()
        for issue in self._grammar_issues:
            if issue.start <= abs_pos < issue.end:
                key = (issue.issue_type, issue.message)
                if key not in self._ignored_issues:
                    return issue
        return None


_GUTTER_WIDTH = 8
_GUTTER_DOT_RADIUS = 2.0
_ENERGY_DEBOUNCE_MS = 600


def _tension_dot_color(tension: float) -> QColor:
    if tension <= 0.2:
        c = QColor("#4ade80")
        c.setAlphaF(0.35)
    elif tension <= 0.4:
        c = QColor("#a3e635")
        c.setAlphaF(0.4)
    elif tension <= 0.6:
        c = QColor("#facc15")
        c.setAlphaF(0.5)
    elif tension <= 0.8:
        c = QColor("#fb923c")
        c.setAlphaF(0.55)
    else:
        c = QColor("#f87171")
        c.setAlphaF(0.6)
    return c


_HINT_COLOR = "#facc15"
_HINT_ALPHA = 0.45
_HINT_DIAMOND_SIZE = 2.5


class _EnergyGutter(QWidget):
    """Thin left-gutter widget showing per-paragraph energy dots and flow hints."""

    def __init__(self, editor: _SceneEditor, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._editor = editor
        self._enabled = True
        self._sensitivity = "medium"
        self._story_context: StoryContext | None = None
        self._energies: list[ParagraphEnergy] = []
        self._hints: list[FlowHint] = []
        self._hinted_paragraphs: dict[int, str] = {}
        self.setFixedWidth(_GUTTER_WIDTH)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
        self.setMouseTracking(True)

        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(_ENERGY_DEBOUNCE_MS)
        self._timer.timeout.connect(self._recompute)

        editor.textChanged.connect(self._schedule)

    def set_enabled(self, on: bool) -> None:
        self._enabled = on
        if on:
            self._recompute()
        else:
            self._energies.clear()
            self._hints.clear()
            self._hinted_paragraphs.clear()
            self._timer.stop()
            self.update()

    def set_story_context(self, context: StoryContext | None) -> None:
        self._story_context = context
        if self._enabled:
            self._recompute()

    def set_sensitivity(self, level: str) -> None:
        if level not in SENSITIVITY_LEVELS:
            return
        self._sensitivity = level
        if self._enabled:
            self._recompute()

    def initial_compute(self) -> None:
        if self._enabled:
            self._recompute()

    def _schedule(self) -> None:
        if self._enabled:
            self._timer.start()

    def _recompute(self) -> None:
        text = self._editor.toPlainText()
        scene_id = self._editor._scene_id or 0
        self._energies = analyze_scene_energy(scene_id, text, context=self._story_context)
        self._hints = detect_flow_hints(self._energies, self._sensitivity)
        self._hinted_paragraphs = {}
        for h in self._hints:
            mid = (h.start + h.end) // 2
            self._hinted_paragraphs[mid] = h.message
        self.update()

    def _block_energy_pairs(self):
        if not self._energies:
            return
        doc = self._editor.document()
        layout = doc.documentLayout()
        block = doc.begin()
        para_idx = 0
        while block.isValid() and para_idx < len(self._energies):
            if block.text().strip():
                rect = layout.blockBoundingRect(block)
                yield rect, self._energies[para_idx], para_idx
                para_idx += 1
            block = block.next()

    def paintEvent(self, event) -> None:
        if not self._energies:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        cx = self.width() / 2.0
        for rect, energy, idx in self._block_energy_pairs():
            cy = rect.top() + rect.height() / 2.0
            if idx in self._hinted_paragraphs:
                hint_color = QColor(_HINT_COLOR)
                hint_color.setAlphaF(_HINT_ALPHA)
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(hint_color)
                s = _HINT_DIAMOND_SIZE
                painter.save()
                painter.translate(cx, cy)
                painter.rotate(45)
                painter.drawRect(-s, -s, s * 2, s * 2)
                painter.restore()
            else:
                color = _tension_dot_color(energy.tension)
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(color)
                painter.drawEllipse(QPointF(cx, cy), _GUTTER_DOT_RADIUS, _GUTTER_DOT_RADIUS)
        painter.end()

    def event(self, ev) -> bool:
        if ev.type() == QEvent.Type.ToolTip:
            y = ev.pos().y()
            for rect, energy, idx in self._block_energy_pairs():
                if rect.top() <= y <= rect.bottom():
                    tip = (
                        f"Tension: {energy.tension:.0%}\n"
                        f"Pacing: {energy.pacing:.0%}\n"
                        f"Conflict: {energy.conflict:.0%}"
                    )
                    hint_msg = self._hinted_paragraphs.get(idx)
                    if hint_msg:
                        tip += f"\n\n{hint_msg}"
                    QToolTip.showText(ev.globalPos(), tip, self)
                    return True
            QToolTip.hideText()
            return True
        return super().event(ev)


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
        on_content_saved: Callable[[], None] | None = None,
    ) -> None:
        super().__init__()
        self.setMinimumWidth(0)
        self._db = db
        self._project_id = project_id
        self._on_data_changed = on_data_changed
        self._on_focus_mode_changed = on_focus_mode_changed
        self._on_open_psyke_entry = on_open_psyke_entry
        self._on_content_saved = on_content_saved or on_data_changed
        project = db.get_project_by_id(project_id)
        from storyplanner.project_compat import get_project_writing_format
        fmt_name = get_project_writing_format(project) or "novel"
        self._format: WritingFormat = ALL_FORMATS.get(fmt_name, ALL_FORMATS["novel"])
        _settings = db.get_project_settings(project_id)
        self._focus_mode = False
        self._pending_focus = bool(_settings.get("focus_mode", False))
        self._font_family_key: str = _settings.get("font_family", "sans")
        if self._font_family_key not in _FONT_PRESETS:
            self._font_family_key = "sans"
        self._font_size: int = _settings.get("font_size", _BODY_FONT_SIZE)
        if self._font_size not in _FONT_SIZE_OPTIONS:
            self._font_size = _BODY_FONT_SIZE
        self._first_line_indent: bool = bool(_settings.get("first_line_indent", False))
        self._smart_quotes: bool = bool(_settings.get("smart_quotes", False))
        self._pending_typewriter: bool = False
        self._pending_scroll: int = _settings.get("scroll_pos", 0)
        self._pending_cursor_scene: int | None = _settings.get("cursor_scene_id")
        self._pending_cursor_pos: int = _settings.get("cursor_pos", 0)
        self._current_language: str = _settings.get("current_language", "en")
        self._language_override: str = _settings.get("language_override", "auto")
        valid_codes = {code for code, _ in _LANGUAGE_OPTIONS}
        if self._language_override not in valid_codes:
            self._language_override = "auto"
        if self._language_override != "auto":
            self._current_language = self._language_override
        self._grammar_checking: bool = bool(_settings.get("grammar_checking", False))
        self._style_hints_checking: bool = bool(_settings.get("style_hints", False))
        self._style_sensitivity: str = str(_settings.get("style_sensitivity", "medium"))
        if self._style_sensitivity not in STYLE_SENSITIVITY_LEVELS:
            self._style_sensitivity = "medium"
        self._energy_enabled: bool = bool(_settings.get("energy_enabled", False))
        self._energy_sensitivity: str = str(_settings.get("energy_sensitivity", "medium"))
        if self._energy_sensitivity not in SENSITIVITY_LEVELS:
            self._energy_sensitivity = "medium"
        self._current_text_color: str = ""
        self._editors: dict[int, _SceneEditor] = {}
        self._save_timers: dict[int, QTimer] = {}
        self._scene_widgets: list[QWidget] = []
        self._highlighters: dict[int, PsykeHighlighter] = {}
        self._click_handlers: dict[int, PsykeClickHandler] = {}
        self._hover_handlers: dict[int, EntityHoverHandler] = {}
        self._suggestion_banners: dict[int, SuggestionBanner] = {}
        self._context_hint_banners: dict[int, ContextHintBanner] = {}
        self._energy_gutters: dict[int, _EnergyGutter] = {}
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

        self._context_assistant = ContextAssistant(db, project_id)
        self._hint_rate_limiter = HintRateLimiter()
        self._context_assist_timer = QTimer(self)
        self._context_assist_timer.setSingleShot(True)
        self._context_assist_timer.setInterval(2000)
        self._context_assist_timer.timeout.connect(self._run_context_analysis)
        self._context_assistant_enabled = True

        self._session_save_timer = QTimer(self)
        self._session_save_timer.setSingleShot(True)
        self._session_save_timer.setInterval(1000)
        self._session_save_timer.timeout.connect(self._persist_session_state)

        self._lang_detect_timer = QTimer(self)
        self._lang_detect_timer.setSingleShot(True)
        self._lang_detect_timer.setInterval(3000)
        self._lang_detect_timer.timeout.connect(self._run_language_detection)

        self._grammar_timer = QTimer(self)
        self._grammar_timer.setSingleShot(True)
        self._grammar_timer.setInterval(800)
        self._grammar_timer.timeout.connect(self._run_grammar_check)
        self._grammar_worker: _GrammarWorker | None = None
        self._grammar_generation: int = 0

        self._style_hint_timer = QTimer(self)
        self._style_hint_timer.setSingleShot(True)
        self._style_hint_timer.setInterval(900)
        self._style_hint_timer.timeout.connect(self._run_style_hints)
        self._style_hint_worker: _StyleHintWorker | None = None
        self._style_hint_generation: int = 0

        self._voice_hints_checking: bool = bool(_settings.get("voice_hints", False))
        self._voice_sensitivity: str = str(_settings.get("voice_sensitivity", "medium"))
        if self._voice_sensitivity not in VOICE_SENSITIVITY_LEVELS:
            self._voice_sensitivity = "medium"
        self._voice_hint_timer = QTimer(self)
        self._voice_hint_timer.setSingleShot(True)
        self._voice_hint_timer.setInterval(1100)
        self._voice_hint_timer.timeout.connect(self._run_voice_hints)
        self._voice_hint_worker: _VoiceConsistencyWorker | None = None
        self._voice_hint_generation: int = 0

        self._command_palette: CommandPalette | None = None
        self._palette_source_editor: _SceneEditor | None = None
        self._element_shortcuts: list[QShortcut] = []
        self._focus_fade = True
        self._tw_anim: QPropertyAnimation | None = None
        self._structural_cache = StructuralCache()

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

        _tb_btn_style = (
            f"color: {theme.TEXT_MUTED}; font-size: 11px;"
            " background: transparent; padding: 2px 8px;"
        )

        # 1. Wordcount
        self._word_count_label = QLabel("")
        self._word_count_label.setStyleSheet(
            f"color: {theme.TEXT_MUTED}; font-size: 11px;"
            " background: transparent;"
        )
        tb_layout.addWidget(self._word_count_label)

        # 2. Project format badge — read-only indicator + link to Project
        # Settings. The project's narrative engine and default writing format
        # are owned by the project model, not the manuscript editor.
        from storyplanner.project_compat import (
            ENGINE_LABELS,
            FORMAT_LABELS,
            get_project_narrative_engine,
            get_project_writing_format,
        )
        _proj = self._db.get_project_by_id(self._project_id)
        _engine_label = ENGINE_LABELS.get(
            get_project_narrative_engine(_proj), "Novel",
        )
        _format_label = FORMAT_LABELS.get(
            get_project_writing_format(_proj), "Prose",
        )
        self._format_badge = QPushButton(
            f"{_engine_label} · {_format_label}"
        )
        self._format_badge.setObjectName("writingFormatBadge")
        self._format_badge.setFlat(True)
        self._format_badge.setToolTip(
            "Project narrative engine and default writing format —"
            " click to change in Project Settings."
        )
        self._format_badge.setStyleSheet(_tb_btn_style)
        self._format_badge.clicked.connect(self._open_project_settings)
        tb_layout.addWidget(self._format_badge)

        # 3. ModeFormat
        self._element_combo = QComboBox()
        self._element_combo.setObjectName("writingElementCombo")
        self._element_combo.setFixedWidth(140)
        self._populate_element_combo()
        self._element_combo.currentIndexChanged.connect(self._on_element_changed)
        tb_layout.addWidget(self._element_combo)

        # 4. A-P (Text + Paragraph)
        self._ap_btn = QPushButton("A-P")
        self._ap_btn.setFlat(True)
        self._ap_btn.setToolTip("Text & Paragraph formatting")
        self._ap_btn.setStyleSheet(_tb_btn_style)
        self._ap_btn.clicked.connect(self._show_ap_menu)
        tb_layout.addWidget(self._ap_btn)

        # 5. Review
        self._review_btn = QPushButton("Review")
        self._review_btn.setFlat(True)
        self._review_btn.setToolTip("Review tools")
        self._review_btn.setStyleSheet(_tb_btn_style)
        self._review_btn.clicked.connect(self._show_review_menu)
        tb_layout.addWidget(self._review_btn)

        # 6. Focus
        self._focus_btn = QPushButton("Focus")
        self._focus_btn.setFlat(True)
        self._focus_btn.setStyleSheet(_tb_btn_style)
        self._focus_btn.clicked.connect(self.toggle_focus_mode)
        tb_layout.addWidget(self._focus_btn)

        # 7. Text/Bg
        self._textbg_btn = QPushButton("Text/Bg")
        self._textbg_btn.setFlat(True)
        self._textbg_btn.setToolTip("Font, color, and background options")
        self._textbg_btn.setStyleSheet(_tb_btn_style)
        self._textbg_btn.clicked.connect(self._show_text_bg_menu)
        tb_layout.addWidget(self._textbg_btn)

        tb_layout.addStretch()

        # Hidden combos kept for settings persistence and test compatibility
        self._font_combo = QComboBox()
        self._font_combo.setObjectName("writingFontCombo")
        self._font_combo.setVisible(False)
        for key in _FONT_PRESET_ORDER:
            self._font_combo.addItem(_FONT_PRESET_LABELS[key], key)
        _fc_idx = _FONT_PRESET_ORDER.index(self._font_family_key)
        self._font_combo.setCurrentIndex(_fc_idx)
        self._font_combo.currentIndexChanged.connect(self._on_font_family_changed)

        self._size_combo = QComboBox()
        self._size_combo.setObjectName("writingSizeCombo")
        self._size_combo.setVisible(False)
        for sz in _FONT_SIZE_OPTIONS:
            self._size_combo.addItem(f"{sz}", sz)
        _sz_idx = _FONT_SIZE_OPTIONS.index(self._font_size)
        self._size_combo.setCurrentIndex(_sz_idx)
        self._size_combo.currentIndexChanged.connect(self._on_font_size_changed)

        self._current_bg_color: str = ""

        # Hidden widgets for backward compat (tests, internal signal chains)
        self._color_btn = QPushButton("A")
        self._color_btn.setVisible(False)
        self._paragraph_btn = QPushButton("¶")
        self._paragraph_btn.setVisible(False)
        self._indent_btn = QPushButton("Indent")
        self._indent_btn.setVisible(False)
        self._smart_quotes_btn = QPushButton("“”")
        self._smart_quotes_btn.setVisible(False)

        self._topbar_opacity = QGraphicsOpacityEffect(self._top_bar)
        self._topbar_opacity.setOpacity(1.0)
        self._top_bar.setGraphicsEffect(self._topbar_opacity)
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
        self._canvas_layout.setContentsMargins(0, 48, 0, 120)
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

    # -- Top bar (always visible, no fade) ------------------------------------

    # -- Data loading ---------------------------------------------------------

    def _flush_pending_saves(self) -> None:
        """Persist any per-scene edits still waiting on their debounce timer.

        ``refresh()`` rebuilds every editor from the DB, so without flushing
        first, keystrokes typed within the last debounce window (timer pending,
        not yet fired) would be discarded by ``_clear_canvas`` — losing the
        user's most recent typing. Flushing writes the current editor text to the
        DB so the rebuild reads it back intact.
        """
        for scene_id, timer in list(self._save_timers.items()):
            if timer.isActive():
                timer.stop()
                self._save_scene(scene_id)

    def _focused_editor_state(self) -> tuple[int, int] | None:
        """(scene_id, cursor_position) of the focused editor, or None."""
        for scene_id, editor in self._editors.items():
            if editor.hasFocus():
                try:
                    return scene_id, editor.textCursor().position()
                except Exception:
                    return scene_id, 0
        return None

    def refresh(self) -> None:
        # Never lose in-progress typing or steal focus when a rebuild is
        # triggered (e.g. by an Assistant/Logos apply) while the editor is in
        # use: flush pending saves first, then restore focus + cursor after.
        self._flush_pending_saves()
        focus_state = self._focused_editor_state()

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
        self._restore_session_state()

        # Restore focus + cursor to the scene the user was editing (if it still
        # exists after the rebuild) so a refresh never interrupts typing flow.
        if focus_state is not None:
            sid, pos = focus_state
            editor = self._editors.get(sid)
            if editor is not None:
                try:
                    cursor = editor.textCursor()
                    cursor.setPosition(min(pos, len(editor.toPlainText())))
                    editor.setTextCursor(cursor)
                except Exception:
                    pass
                editor.setFocus()

    def _clear_canvas(self) -> None:
        self._format_toolbar.untrack_all()
        self._entity_hover_panel.hide()
        self._editors.clear()
        self._save_timers.clear()
        self._scene_widgets.clear()
        self._highlighters.clear()
        self._click_handlers.clear()
        self._hover_handlers.clear()
        self._suggestion_banners.clear()
        self._context_hint_banners.clear()
        self._energy_gutters.clear()
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

    def _add_chapter_header(self, chapter: str) -> None:
        label = QLabel(chapter)
        label.setObjectName("writingChapterHeader")
        label.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self._inner_layout.addSpacing(32)
        self._inner_layout.addWidget(label)
        self._inner_layout.addSpacing(16)
        self._scene_widgets.append(label)

    def _add_scene_block(self, scene, *, is_first: bool = False) -> None:
        if not is_first:
            self._inner_layout.addSpacing(56)

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
        editor.setMarkdown(scene.content or "")
        editor.slash_pressed = self._on_slash_pressed
        editor.set_focus_fade(self._focus_fade, theme.BG_DARK)
        editor._on_nav_next = lambda e=editor: self._navigate_next_editor(e)
        editor._on_nav_prev = lambda e=editor: self._navigate_prev_editor(e)
        editor._on_new_block = self._on_new_block_created
        editor._on_tab_cycle = self._on_tab_cycle_element
        editor._on_psyke_context_action = self._handle_psyke_context
        editor._smart_quotes = self._smart_quotes
        editor._grammar_enabled = self._grammar_checking
        editor._style_hints_enabled = self._style_hints_checking
        editor._voice_hints_enabled = self._voice_hints_checking
        editor.textChanged.connect(
            lambda sid=scene.id: self._schedule_save(sid)
        )
        editor.cursorPositionChanged.connect(
            lambda e=editor: self._on_editor_cursor_moved(e),
        )

        gutter = _EnergyGutter(editor)
        row = QWidget()
        row.setObjectName("writingEditorRow")
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(0)
        row_layout.addWidget(gutter)
        row_layout.addWidget(editor)
        self._inner_layout.addWidget(row)
        self._scene_widgets.append(row)
        self._energy_gutters[scene.id] = gutter
        ctx = build_story_context(self._db, self._project_id, scene.id)
        gutter.set_story_context(ctx)
        editor._style_context = build_style_context(
            self._db, self._project_id, scene.id,
        )
        char_ids = self._db.get_scene_character_ids(scene.id)
        scene_char_states = self._db.get_scene_character_states(scene.id)
        state_by_char = {cid: st for cid, st in scene_char_states}
        for cid in char_ids:
            vdata = self._db.get_voice_profile_data(cid)
            if vdata is not None:
                editor._voice_profile_data = vdata
                editor._voice_state_text = state_by_char.get(cid, "")
                break
        gutter.set_sensitivity(self._energy_sensitivity)
        gutter.set_enabled(self._energy_enabled)

        highlighter = PsykeHighlighter(editor.document())
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

        hint_banner = ContextHintBanner()
        hint_banner.accepted.connect(self._on_context_hint_accepted)
        hint_banner.dismissed.connect(self._on_context_hint_dismissed)
        hint_banner.ignored.connect(self._on_context_hint_ignored)
        self._inner_layout.addWidget(hint_banner)
        self._context_hint_banners[scene.id] = hint_banner

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
        term_types: dict[str, str] = {}
        self._psyke_term_map.clear()
        self._psyke_entry_cache.clear()
        for e in entries:
            self._psyke_entry_cache[e.id] = e
            if e.name.strip():
                terms.append(e.name)
                self._psyke_term_map[e.name.lower()] = e.id
                term_types[e.name.lower()] = e.entry_type
            if e.aliases:
                for alias in e.aliases.split(","):
                    alias = alias.strip()
                    if alias:
                        terms.append(alias)
                        self._psyke_term_map[alias.lower()] = e.id
                        term_types[alias.lower()] = e.entry_type
        for highlighter in self._highlighters.values():
            highlighter.refresh_patterns(terms, term_types=term_types)
        for handler in self._click_handlers.values():
            handler.set_term_map(self._psyke_term_map)
        for handler in self._hover_handlers.values():
            handler.set_term_map(self._psyke_term_map)
        self._rebuild_energy_contexts()

    # -- Format / element system -----------------------------------------------

    def current_element_type(self) -> str:
        """The element type of the current cursor block (or the format default).

        Read-only; used by the host to carry the current screenplay element into
        LogosContext. Returns "" if there is no active editor.
        """
        try:
            editor = self._active_editor
            if editor is None:
                return ""
            data = editor.textCursor().block().userData()
            if isinstance(data, _BlockData) and data.element:
                return data.element
            return self._format.default_element
        except Exception:
            return ""

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

    def _open_project_settings(self) -> None:
        """Open the Project Settings dialog and refresh on change."""
        from storyplanner.ui.project_settings_dialog import ProjectSettingsDialog
        dlg = ProjectSettingsDialog(self._db, self._project_id, parent=self)
        if dlg.exec():
            self.reload_project_format()

    def reload_project_format(self) -> None:
        """Re-read the project's writing format and rebuild block grammar.

        Called when Project Settings changes the engine/format so the editor
        adapts to the new defaults without re-instantiating the view.
        """
        from storyplanner.project_compat import (
            ENGINE_LABELS,
            FORMAT_LABELS,
            get_project_narrative_engine,
            get_project_writing_format,
        )
        project = self._db.get_project_by_id(self._project_id)
        fmt_name = get_project_writing_format(project)
        self._format = ALL_FORMATS.get(fmt_name, ALL_FORMATS["novel"])
        if hasattr(self, "_format_badge"):
            engine_label = ENGINE_LABELS.get(
                get_project_narrative_engine(project), "Novel",
            )
            format_label = FORMAT_LABELS.get(fmt_name, "Prose")
            self._format_badge.setText(f"{engine_label} · {format_label}")
        self._populate_element_combo()
        self._setup_element_shortcuts()
        self._apply_format_to_all_blocks()
        if self._on_content_saved:
            self._on_content_saved()

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

    def _build_element_formats(self, elem, *, preserve_inline: bool = False):
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
        # Optional subtle background band (e.g. boxed panel descriptions,
        # stylized SFX). Always set explicitly so re-applying a format
        # clears any previous band rather than leaving it stale. Resolved
        # live from the theme so palette changes are honored.
        bg = _element_bg_color(getattr(elem, "background_key", "") or "")
        bfmt.setBackground(
            QBrush(QColor(bg)) if bg else QBrush(Qt.GlobalColor.transparent)
        )
        lh = elem.line_height
        if self._focus_mode:
            lh = max(lh, _FOCUS_LINE_HEIGHT)
        bfmt.setLineHeight(
            lh * 100,
            QTextBlockFormat.LineHeightTypes.ProportionalHeight.value,
        )
        indent = elem.first_line_indent
        if self._first_line_indent and elem.font_size == _BODY_FONT_SIZE:
            indent = max(indent, 28)
        bfmt.setTextIndent(indent)

        families = _FONT_PRESETS.get(self._font_family_key, _FONT_PRESETS["sans"])

        cfmt = QTextCharFormat()
        cfmt.setFontFamilies(families)
        font_size = elem.font_size
        if elem.font_size == _BODY_FONT_SIZE:
            font_size = self._font_size
        cfmt.setProperty(QTextCharFormat.Property.FontPixelSize, font_size)
        if preserve_inline:
            if elem.bold:
                cfmt.setFontWeight(QFont.Weight.Bold)
            if elem.italic:
                cfmt.setFontItalic(True)
            if elem.all_caps:
                cfmt.setFontCapitalization(QFont.Capitalization.AllUppercase)
        else:
            cfmt.setFontWeight(
                QFont.Weight.Bold if elem.bold else QFont.Weight.Normal,
            )
            cfmt.setFontItalic(elem.italic)
            if elem.all_caps:
                cfmt.setFontCapitalization(QFont.Capitalization.AllUppercase)
            else:
                cfmt.setFontCapitalization(QFont.Capitalization.MixedCase)
        color = _element_text_color(elem.color_key)
        if color:
            cfmt.setForeground(QColor(color))
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
                    bfmt, cfmt = self._build_element_formats(
                        elem, preserve_inline=True,
                    )
                    cursor = QTextCursor(block)
                    cursor.movePosition(
                        QTextCursor.MoveOperation.EndOfBlock,
                        QTextCursor.MoveMode.KeepAnchor,
                    )
                    cursor.mergeBlockFormat(bfmt)
                    cursor.mergeCharFormat(cfmt)
                block = block.next()

    def _on_editor_cursor_moved(self, editor: _SceneEditor) -> None:
        if editor.hasFocus():
            if self._active_editor is not editor:
                self._active_editor = editor
                if editor._scene_id is not None:
                    self._hint_rate_limiter.on_scene_changed(editor._scene_id)
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
        self._session_save_timer.start()

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

    def _on_tab_cycle_element(
        self, editor: _SceneEditor, forward: bool = True,
    ) -> None:
        data = editor.textCursor().block().userData()
        current = (
            data.element
            if isinstance(data, _BlockData) and data.element
            else self._format.default_element
        )
        names = [e.name for e in self._format.elements]
        if not names:
            return
        try:
            idx = names.index(current)
        except ValueError:
            idx = 0
        idx = (idx + (1 if forward else -1)) % len(names)
        next_elem = names[idx]
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

        analysis = self._structural_cache.get(
            self._db, self._project_id, self._temporal_graph,
        )
        if analysis.issues:
            sep2 = QFrame()
            sep2.setFrameShape(QFrame.Shape.HLine)
            sep2.setStyleSheet(f"color: {theme.BORDER};")
            lay.addWidget(sep2)
            struct_label = QLabel(f"Structure ({len(analysis.issues)})")
            struct_label.setObjectName("reviewOverlayTitle")
            lay.addWidget(struct_label)
            for issue in analysis.issues[:3]:
                msg = QLabel(f"  {issue.message}")
                msg.setWordWrap(True)
                lay.addWidget(msg)
                if issue.suggestion:
                    sug = QLabel(f"    → {issue.suggestion}")
                    sug.setWordWrap(True)
                    sug.setStyleSheet(f"color: {theme.TEXT_MUTED}; font-size: 10px;")
                    lay.addWidget(sug)

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

        if self._on_content_saved:
            self._on_content_saved()
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
        if self._context_assistant_enabled:
            self._context_assist_timer.start()
        self._lang_detect_timer.start()
        if self._grammar_checking:
            self._grammar_timer.start()
        if self._style_hints_checking:
            self._style_hint_timer.start()
        if self._voice_hints_checking:
            self._voice_hint_timer.start()
        self._update_word_count()

    def _save_scene(self, scene_id: int) -> None:
        editor = self._editors.get(scene_id)
        if editor is None:
            return
        self._db.update_scene_content(scene_id, editor.toMarkdown().rstrip())
        self._structural_cache.mark_dirty()
        if self._on_content_saved:
            self._on_content_saved()

    # -- Command palette ------------------------------------------------------

    def _ensure_command_palette(self) -> CommandPalette:
        if self._command_palette is None:
            # Parent the popup to this view so it is transient-for the main
            # window — correct stacking, auto-dismiss, and screen placement
            # (a parentless Qt.Popup can render as a stray top-level window).
            self._command_palette = CommandPalette(self)
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
        elif key == "style_improve":
            if editor is not None:
                cursor_rect = editor.cursorRect()
                gpos = editor.mapToGlobal(cursor_rect.bottomLeft())
                editor._show_style_suggestions(gpos)
        elif key == "voice_rewrite":
            if editor is not None:
                cursor_rect = editor.cursorRect()
                gpos = editor.mapToGlobal(cursor_rect.bottomLeft())
                editor._show_voice_rewrites(gpos)
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
        families = _FONT_PRESETS.get(self._font_family_key, _FONT_PRESETS["sans"])
        family = ", ".join(f"'{f}'" if " " in f else f for f in families)
        lh = _FOCUS_LINE_HEIGHT if self._focus_mode else _BODY_LINE_HEIGHT
        font_size = self._font_size
        line_spacing_px = int(font_size * lh)

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
            f"  font-size: {font_size}px;"
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

        _combo_ids = (
            "#writingFormatCombo, #writingElementCombo,"
            " #writingFontCombo, #writingSizeCombo"
        )
        combo_style = (
            f"{_combo_ids} {{"
            f"  background: transparent;"
            f"  color: {theme.TEXT_MUTED};"
            f"  border: 1px solid {theme.BORDER};"
            f"  border-radius: 4px;"
            f"  padding: 2px 8px;"
            f"  font-size: 11px;"
            f"}}"
            f"{_combo_ids.replace(',', ':hover,')}:hover {{"
            f"  color: {theme.TEXT_PRIMARY};"
            f"  border-color: {theme.TEXT_MUTED};"
            f"}}"
            f"#writingFormatCombo QAbstractItemView,"
            f"#writingElementCombo QAbstractItemView,"
            f"#writingFontCombo QAbstractItemView,"
            f"#writingSizeCombo QAbstractItemView {{"
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

    def _on_font_family_changed(self, index: int) -> None:
        key = self._font_combo.itemData(index)
        if key and key in _FONT_PRESETS:
            self._font_family_key = key
            self._persist_font_settings()
            self._apply_typography()

    def _on_font_size_changed(self, index: int) -> None:
        size = self._size_combo.itemData(index)
        if size and size in _FONT_SIZE_OPTIONS:
            self._font_size = size
            self._persist_font_settings()
            self._apply_typography()

    # -- A-P menu (text + paragraph) -------------------------------------------

    def _show_ap_menu(self) -> None:
        menu = QMenu(self._ap_btn)

        bold = QAction("Bold", menu)
        bold.triggered.connect(self._toggle_bold)
        menu.addAction(bold)
        italic = QAction("Italic", menu)
        italic.triggered.connect(self._toggle_italic)
        menu.addAction(italic)
        underline = QAction("Underline", menu)
        underline.triggered.connect(self._toggle_underline)
        menu.addAction(underline)
        strike = QAction("Strikethrough", menu)
        strike.triggered.connect(self._toggle_strikethrough)
        menu.addAction(strike)

        menu.addSeparator()

        for label, alignment in (
            ("Align Left", Qt.AlignmentFlag.AlignLeft),
            ("Align Center", Qt.AlignmentFlag.AlignHCenter),
            ("Align Right", Qt.AlignmentFlag.AlignRight),
            ("Justify", Qt.AlignmentFlag.AlignJustify),
        ):
            act = QAction(label, menu)
            act.triggered.connect(
                lambda _checked=False, a=alignment: self._apply_alignment(a)
            )
            menu.addAction(act)

        menu.addSeparator()

        inc = QAction("Increase Indent", menu)
        inc.triggered.connect(lambda: self._change_block_indent(1))
        menu.addAction(inc)
        dec = QAction("Decrease Indent", menu)
        dec.triggered.connect(lambda: self._change_block_indent(-1))
        menu.addAction(dec)

        menu.addSeparator()

        bullet = QAction("Bullet List", menu)
        bullet.triggered.connect(
            lambda: self._toggle_list(QTextListFormat.Style.ListDisc)
        )
        menu.addAction(bullet)
        numbered = QAction("Numbered List", menu)
        numbered.triggered.connect(
            lambda: self._toggle_list(QTextListFormat.Style.ListDecimal)
        )
        menu.addAction(numbered)

        pos = self._ap_btn.mapToGlobal(self._ap_btn.rect().bottomLeft())
        menu.exec(pos)

    def _toggle_bold(self) -> None:
        editor = self._target_editor()
        if editor is None:
            return
        cursor = editor.textCursor()
        fmt = cursor.charFormat()
        new_fmt = QTextCharFormat()
        weight = QFont.Weight.Normal if fmt.fontWeight() >= QFont.Weight.Bold else QFont.Weight.Bold
        new_fmt.setFontWeight(weight)
        cursor.mergeCharFormat(new_fmt)
        editor.setTextCursor(cursor)

    def _toggle_italic(self) -> None:
        editor = self._target_editor()
        if editor is None:
            return
        cursor = editor.textCursor()
        new_fmt = QTextCharFormat()
        new_fmt.setFontItalic(not cursor.charFormat().fontItalic())
        cursor.mergeCharFormat(new_fmt)
        editor.setTextCursor(cursor)

    def _toggle_underline(self) -> None:
        editor = self._target_editor()
        if editor is None:
            return
        cursor = editor.textCursor()
        new_fmt = QTextCharFormat()
        new_fmt.setFontUnderline(not cursor.charFormat().fontUnderline())
        cursor.mergeCharFormat(new_fmt)
        editor.setTextCursor(cursor)

    def _toggle_strikethrough(self) -> None:
        editor = self._target_editor()
        if editor is None:
            return
        cursor = editor.textCursor()
        new_fmt = QTextCharFormat()
        new_fmt.setFontStrikeOut(not cursor.charFormat().fontStrikeOut())
        cursor.mergeCharFormat(new_fmt)
        editor.setTextCursor(cursor)

    # -- Review menu -----------------------------------------------------------

    def _show_review_menu(self) -> None:
        menu = QMenu(self._review_btn)

        review_act = QAction(
            "Close Review" if self._review_mode else "Review Metrics", menu,
        )
        review_act.triggered.connect(self.toggle_review_mode)
        menu.addAction(review_act)

        grammar_act = QAction("Grammar Check", menu)
        grammar_act.setCheckable(True)
        grammar_act.setChecked(self._grammar_checking)
        grammar_act.triggered.connect(lambda checked: self._toggle_grammar())
        menu.addAction(grammar_act)

        style_act = QAction("Style Feedback", menu)
        style_act.setCheckable(True)
        style_act.setChecked(self._style_hints_checking)
        style_act.triggered.connect(lambda checked: self._toggle_style_hints())
        menu.addAction(style_act)

        style_sens_sub = menu.addMenu("Style Sensitivity")
        for level in STYLE_SENSITIVITY_LEVELS:
            act = QAction(level.capitalize(), style_sens_sub)
            act.setCheckable(True)
            act.setChecked(level == self._style_sensitivity)
            act.triggered.connect(
                lambda _c=False, lv=level: self._set_style_sensitivity(lv),
            )
            style_sens_sub.addAction(act)

        voice_act = QAction("Voice Consistency", menu)
        voice_act.setCheckable(True)
        voice_act.setChecked(self._voice_hints_checking)
        voice_act.triggered.connect(lambda checked: self._toggle_voice_hints())
        menu.addAction(voice_act)

        voice_sens_sub = menu.addMenu("Voice Sensitivity")
        for level in VOICE_SENSITIVITY_LEVELS:
            act = QAction(level.capitalize(), voice_sens_sub)
            act.setCheckable(True)
            act.setChecked(level == self._voice_sensitivity)
            act.triggered.connect(
                lambda _c=False, lv=level: self._set_voice_sensitivity(lv),
            )
            voice_sens_sub.addAction(act)

        menu.addSeparator()

        energy_act = QAction("Energy View", menu)
        energy_act.setCheckable(True)
        energy_act.setChecked(self._energy_enabled)
        energy_act.triggered.connect(lambda checked: self._toggle_energy())
        menu.addAction(energy_act)

        sens_sub = menu.addMenu("Energy Sensitivity")
        for level in SENSITIVITY_LEVELS:
            act = QAction(level.capitalize(), sens_sub)
            act.setCheckable(True)
            act.setChecked(level == self._energy_sensitivity)
            act.triggered.connect(
                lambda _c=False, lv=level: self._set_energy_sensitivity(lv),
            )
            sens_sub.addAction(act)

        pos = self._review_btn.mapToGlobal(self._review_btn.rect().bottomLeft())
        menu.exec(pos)

    # -- Text/Bg menu ----------------------------------------------------------

    def _show_text_bg_menu(self) -> None:
        menu = QMenu(self._textbg_btn)

        font_sub = menu.addMenu("Font Family")
        for key in _FONT_PRESET_ORDER:
            act = QAction(_FONT_PRESET_LABELS[key], font_sub)
            act.setCheckable(True)
            act.setChecked(key == self._font_family_key)
            act.triggered.connect(
                lambda _c=False, k=key: self._set_font_family(k)
            )
            font_sub.addAction(act)

        size_sub = menu.addMenu("Font Size")
        for sz in _FONT_SIZE_OPTIONS:
            act = QAction(str(sz), size_sub)
            act.setCheckable(True)
            act.setChecked(sz == self._font_size)
            act.triggered.connect(
                lambda _c=False, s=sz: self._set_font_size(s)
            )
            size_sub.addAction(act)

        menu.addSeparator()

        color_sub = menu.addMenu("Text Color")
        for label, hex_color in _TEXT_COLOR_PALETTE:
            act = QAction(f"●  {label}" if hex_color else label, color_sub)
            act.triggered.connect(
                lambda _c=False, c=hex_color: self._apply_text_color(c)
            )
            color_sub.addAction(act)

        bg_sub = menu.addMenu("Background Color")
        for label, hex_color in _BG_COLOR_PALETTE:
            act = QAction(f"●  {label}" if hex_color else label, bg_sub)
            act.setCheckable(True)
            act.setChecked(hex_color == self._current_bg_color)
            act.triggered.connect(
                lambda _c=False, c=hex_color: self._apply_bg_color(c)
            )
            bg_sub.addAction(act)

        menu.addSeparator()

        indent_act = QAction("First-line Indent", menu)
        indent_act.setCheckable(True)
        indent_act.setChecked(self._first_line_indent)
        indent_act.triggered.connect(lambda: self._toggle_indent())
        menu.addAction(indent_act)

        sq_act = QAction("Smart Quotes", menu)
        sq_act.setCheckable(True)
        sq_act.setChecked(self._smart_quotes)
        sq_act.triggered.connect(lambda: self._toggle_smart_quotes())
        menu.addAction(sq_act)

        pos = self._textbg_btn.mapToGlobal(self._textbg_btn.rect().bottomLeft())
        menu.exec(pos)

    def _set_font_family(self, key: str) -> None:
        if key not in _FONT_PRESETS:
            return
        idx = _FONT_PRESET_ORDER.index(key)
        self._font_combo.setCurrentIndex(idx)

    def _set_font_size(self, size: int) -> None:
        if size not in _FONT_SIZE_OPTIONS:
            return
        idx = _FONT_SIZE_OPTIONS.index(size)
        self._size_combo.setCurrentIndex(idx)

    def _apply_text_color(self, hex_color: str) -> None:
        self._current_text_color = hex_color
        editor = self._active_editor
        if editor is None:
            for ed in self._editors.values():
                if ed.hasFocus():
                    editor = ed
                    break
        if editor is None and self._editors:
            editor = next(iter(self._editors.values()))
        if editor is None:
            return
        cursor = editor.textCursor()
        fmt = QTextCharFormat()
        if hex_color:
            fmt.setForeground(QColor(hex_color))
        else:
            fmt.setForeground(QColor(theme.TEXT_PRIMARY))
        cursor.mergeCharFormat(fmt)
        editor.mergeCurrentCharFormat(fmt)

    def _apply_bg_color(self, hex_color: str) -> None:
        self._current_bg_color = hex_color
        bg = hex_color or theme.BG_DARK
        self._canvas.setStyleSheet(
            f"#writingCanvas {{ background-color: {bg}; }}"
        )
        for editor in self._editors.values():
            editor._fade_bg = bg
            editor.viewport().update()

    def _target_editor(self) -> QTextEdit | None:
        editor = self._active_editor
        if editor is None:
            for ed in self._editors.values():
                if ed.hasFocus():
                    editor = ed
                    break
        if editor is None and self._editors:
            editor = next(iter(self._editors.values()))
        return editor

    def _apply_alignment(self, alignment: Qt.AlignmentFlag) -> None:
        editor = self._target_editor()
        if editor is None:
            return
        cursor = editor.textCursor()
        bfmt = QTextBlockFormat()
        bfmt.setAlignment(alignment)
        cursor.mergeBlockFormat(bfmt)
        editor.setTextCursor(cursor)

    def _change_block_indent(self, delta: int) -> None:
        editor = self._target_editor()
        if editor is None:
            return
        cursor = editor.textCursor()
        bfmt = cursor.blockFormat()
        new_indent = max(0, bfmt.indent() + delta)
        bfmt.setIndent(new_indent)
        cursor.mergeBlockFormat(bfmt)
        editor.setTextCursor(cursor)

    def _toggle_list(self, style: QTextListFormat.Style) -> None:
        editor = self._target_editor()
        if editor is None:
            return
        cursor = editor.textCursor()
        current_list = cursor.currentList()
        if current_list is not None and current_list.format().style() == style:
            block = cursor.block()
            current_list.remove(block)
            bfmt = QTextBlockFormat()
            bfmt.setIndent(0)
            cursor.setBlockFormat(bfmt)
        else:
            list_fmt = QTextListFormat()
            list_fmt.setStyle(style)
            cursor.createList(list_fmt)
        editor.setTextCursor(cursor)

    def _toggle_indent(self) -> None:
        self._first_line_indent = not self._first_line_indent
        self._persist_font_settings()
        self._apply_format_to_all_blocks()

    def _toggle_smart_quotes(self) -> None:
        self._smart_quotes = not self._smart_quotes
        for editor in self._editors.values():
            editor._smart_quotes = self._smart_quotes
        self._persist_font_settings()

    def _persist_font_settings(self) -> None:
        settings = self._db.get_project_settings(self._project_id)
        settings["font_family"] = self._font_family_key
        settings["font_size"] = self._font_size
        settings["first_line_indent"] = self._first_line_indent
        settings["smart_quotes"] = self._smart_quotes
        settings["grammar_checking"] = self._grammar_checking
        settings["style_hints"] = self._style_hints_checking
        settings["style_sensitivity"] = self._style_sensitivity
        settings["energy_enabled"] = self._energy_enabled
        settings["energy_sensitivity"] = self._energy_sensitivity
        settings["voice_hints"] = self._voice_hints_checking
        settings["voice_sensitivity"] = self._voice_sensitivity
        settings["language_override"] = self._language_override
        self._db.save_project_settings(self._project_id, settings)

    def _persist_session_state(self) -> None:
        settings = self._db.get_project_settings(self._project_id)
        settings["focus_mode"] = self._focus_mode
        settings["typewriter_mode"] = self._typewriter_mode
        settings["scroll_pos"] = self._scroll.verticalScrollBar().value()
        settings["current_language"] = self._current_language
        editor = self._active_editor
        if editor and editor._scene_id is not None:
            settings["cursor_scene_id"] = editor._scene_id
            settings["cursor_pos"] = editor.textCursor().position()
        self._db.save_project_settings(self._project_id, settings)

    def _restore_session_state(self) -> None:
        if self._pending_focus:
            self._pending_focus = False
            self.toggle_focus_mode()

        if self._pending_typewriter:
            self._pending_typewriter = False
            self.toggle_typewriter_mode()

        scene_id = self._pending_cursor_scene
        if scene_id and scene_id in self._editors:
            editor = self._editors[scene_id]
            cursor = editor.textCursor()
            pos = min(self._pending_cursor_pos, editor.document().characterCount() - 1)
            cursor.setPosition(max(0, pos))
            editor.setTextCursor(cursor)
            self._active_editor = editor

        scroll_val = self._pending_scroll
        if scroll_val:
            QTimer.singleShot(50, lambda: self._scroll.verticalScrollBar().setValue(scroll_val))

    # -- Focus mode -----------------------------------------------------------

    def toggle_focus_mode(self) -> None:
        self._focus_mode = not self._focus_mode
        self._top_bar.setVisible(not self._focus_mode)
        self._focus_bar.setVisible(self._focus_mode)
        if not self._focus_mode:
            self._topbar_opacity.setOpacity(1.0)

        para_alpha = 90 if self._focus_mode else _FADE_ALPHA_PARA
        scene_alpha = 130 if self._focus_mode else _FADE_ALPHA_SCENE

        if self._focus_mode:
            self._canvas_layout.setContentsMargins(0, 64, 0, 160)
            self._inner.setMaximumWidth(_CANVAS_MAX_WIDTH - 40)
        else:
            self._canvas_layout.setContentsMargins(0, 48, 0, 120)
            self._inner.setMaximumWidth(_CANVAS_MAX_WIDTH)

        for editor in self._editors.values():
            editor._fade_alpha_para = para_alpha
            editor._fade_alpha_scene = scene_alpha
            editor.viewport().update()

        self._apply_typography()
        self._update_word_count()

        self._session_save_timer.start()

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

    # -- Language detection ---------------------------------------------------

    @property
    def current_language(self) -> str:
        return self._current_language

    @property
    def language_override(self) -> str:
        return self._language_override

    def _on_language_changed(self, code: str) -> None:
        if code == self._language_override:
            return
        self._language_override = code
        if code == "auto":
            self._run_language_detection()
        else:
            self._current_language = code
            self._session_save_timer.start()
        self._persist_font_settings()

    def _run_language_detection(self) -> None:
        if self._language_override != "auto":
            return
        sample = self._collect_text_sample()
        if len(sample.strip()) < 50:
            return
        detected = detect_language(sample)
        if detected != self._current_language:
            self._current_language = detected
            self._session_save_timer.start()

    def _collect_text_sample(self) -> str:
        parts: list[str] = []
        total = 0
        for editor in self._editors.values():
            text = editor.toPlainText()
            parts.append(text)
            total += len(text)
            if total >= 2000:
                break
        return " ".join(parts)[:2000]

    # -- Grammar checking -----------------------------------------------------

    @property
    def is_grammar_checking(self) -> bool:
        return self._grammar_checking

    def _toggle_grammar(self) -> None:
        self._grammar_checking = not self._grammar_checking
        for editor in self._editors.values():
            editor._grammar_enabled = self._grammar_checking
            if not self._grammar_checking:
                editor._grammar_issues = []
                editor.apply_grammar_underlines()
        if self._grammar_checking:
            self._start_grammar_worker()
        else:
            self._grammar_timer.stop()
            self._cancel_grammar_worker()
        self._persist_font_settings()

    def _toggle_energy(self) -> None:
        self._energy_enabled = not self._energy_enabled
        for gutter in self._energy_gutters.values():
            gutter.set_enabled(self._energy_enabled)
        self._persist_font_settings()

    def _set_energy_sensitivity(self, level: str) -> None:
        self._energy_sensitivity = level
        for gutter in self._energy_gutters.values():
            gutter.set_sensitivity(level)
        self._persist_font_settings()

    def _set_style_sensitivity(self, level: str) -> None:
        self._style_sensitivity = level
        self._persist_font_settings()
        if self._style_hints_checking:
            self._start_style_hint_worker()

    def _rebuild_energy_contexts(self) -> None:
        for scene_id, gutter in self._energy_gutters.items():
            ctx = build_story_context(self._db, self._project_id, scene_id)
            gutter.set_story_context(ctx)
            editor = self._editors.get(scene_id)
            if editor is not None:
                editor._style_context = build_style_context(
                    self._db, self._project_id, scene_id,
                )

    def _run_grammar_check(self) -> None:
        if not self._grammar_checking:
            return
        self._start_grammar_worker()

    def _cancel_grammar_worker(self) -> None:
        if self._grammar_worker is not None:
            self._grammar_worker.cancel()
            if self._grammar_worker.isRunning():
                self._grammar_worker.wait()
            self._grammar_worker = None

    def _start_grammar_worker(self) -> None:
        self._grammar_generation += 1
        if self._grammar_worker is not None:
            self._grammar_worker.cancel()
            if self._grammar_worker.isRunning():
                self._grammar_worker.wait()
        scenes: dict[int, str] = {}
        for sid, editor in self._editors.items():
            scenes[sid] = editor.toPlainText()
        worker = _GrammarWorker(self._grammar_generation, scenes)
        worker.finished.connect(self._on_grammar_results)
        self._grammar_worker = worker
        worker.start()

    def _on_grammar_results(
        self, generation: int, results: dict[int, list[GrammarIssue]],
    ) -> None:
        if generation != self._grammar_generation:
            return
        if not self._grammar_checking:
            return
        for sid, issues in results.items():
            editor = self._editors.get(sid)
            if editor is None:
                continue
            editor._grammar_issues = issues
            editor.apply_grammar_underlines()
        self._grammar_worker = None

    def _check_editor_grammar(self, editor: _SceneEditor) -> None:
        self._start_grammar_worker()

    @property
    def grammar_issues(self) -> dict[int, list[GrammarIssue]]:
        return {
            sid: editor._grammar_issues
            for sid, editor in self._editors.items()
            if editor._grammar_issues
        }

    # -- Style hints -----------------------------------------------------------

    def _toggle_style_hints(self) -> None:
        self._style_hints_checking = not self._style_hints_checking
        for editor in self._editors.values():
            editor._style_hints_enabled = self._style_hints_checking
            if not self._style_hints_checking:
                editor._style_hints = []
                editor.apply_grammar_underlines()
        if self._style_hints_checking:
            self._start_style_hint_worker()
        else:
            self._style_hint_timer.stop()
            self._cancel_style_hint_worker()
        self._persist_font_settings()

    def _run_style_hints(self) -> None:
        if not self._style_hints_checking:
            return
        self._start_style_hint_worker()

    def _cancel_style_hint_worker(self) -> None:
        if self._style_hint_worker is not None:
            self._style_hint_worker.cancel()
            if self._style_hint_worker.isRunning():
                self._style_hint_worker.wait()
            self._style_hint_worker = None

    def _start_style_hint_worker(self) -> None:
        self._style_hint_generation += 1
        if self._style_hint_worker is not None:
            self._style_hint_worker.cancel()
            if self._style_hint_worker.isRunning():
                self._style_hint_worker.wait()
        scenes: dict[int, str] = {}
        for sid, editor in self._editors.items():
            scenes[sid] = editor.toPlainText()
        worker = _StyleHintWorker(
            self._style_hint_generation, scenes, self._style_sensitivity,
        )
        worker.finished.connect(self._on_style_hint_results)
        self._style_hint_worker = worker
        worker.start()

    def _on_style_hint_results(
        self, generation: int, results: dict[int, list[StyleHint]],
    ) -> None:
        if generation != self._style_hint_generation:
            return
        if not self._style_hints_checking:
            return
        for sid, hints in results.items():
            editor = self._editors.get(sid)
            if editor is None:
                continue
            editor._style_hints = hints
            editor.apply_grammar_underlines()
        self._style_hint_worker = None

    # -- Voice consistency hints -----------------------------------------------

    def _toggle_voice_hints(self) -> None:
        self._voice_hints_checking = not self._voice_hints_checking
        for editor in self._editors.values():
            editor._voice_hints_enabled = self._voice_hints_checking
            if not self._voice_hints_checking:
                editor._voice_deviations = []
                editor.apply_grammar_underlines()
        if self._voice_hints_checking:
            self._start_voice_hint_worker()
        else:
            self._voice_hint_timer.stop()
            self._cancel_voice_hint_worker()
        self._persist_font_settings()

    def _set_voice_sensitivity(self, level: str) -> None:
        self._voice_sensitivity = level
        self._persist_font_settings()
        if self._voice_hints_checking:
            self._start_voice_hint_worker()

    def _run_voice_hints(self) -> None:
        if not self._voice_hints_checking:
            return
        self._start_voice_hint_worker()

    def _cancel_voice_hint_worker(self) -> None:
        if self._voice_hint_worker is not None:
            self._voice_hint_worker.cancel()
            if self._voice_hint_worker.isRunning():
                self._voice_hint_worker.wait()
            self._voice_hint_worker = None

    def _start_voice_hint_worker(self) -> None:
        self._voice_hint_generation += 1
        if self._voice_hint_worker is not None:
            self._voice_hint_worker.cancel()
            if self._voice_hint_worker.isRunning():
                self._voice_hint_worker.wait()
        scenes: dict[int, str] = {}
        scene_states: dict[int, list[tuple[int, str]]] = {}
        for sid, editor in self._editors.items():
            scenes[sid] = editor.toPlainText()
            scene_states[sid] = self._db.get_scene_character_states(sid)
        characters = self._db.get_all_characters(self._project_id)
        profiles: dict[int, dict] = {}
        for ch in characters:
            data = self._db.get_voice_profile_data(ch.id)
            if data is not None:
                profiles[ch.id] = data
        worker = _VoiceConsistencyWorker(
            self._voice_hint_generation, scenes, characters, profiles,
            scene_states=scene_states,
            threshold=sensitivity_threshold(self._voice_sensitivity),
        )
        worker.finished.connect(self._on_voice_hint_results)
        self._voice_hint_worker = worker
        worker.start()

    def _on_voice_hint_results(
        self, generation: int, results: dict[int, list[VoiceDeviation]],
    ) -> None:
        if generation != self._voice_hint_generation:
            return
        if not self._voice_hints_checking:
            return
        for sid, deviations in results.items():
            editor = self._editors.get(sid)
            if editor is None:
                continue
            editor._voice_deviations = deviations
            editor.apply_grammar_underlines()
        self._voice_hint_worker = None

    # -- Typewriter mode ------------------------------------------------------

    def toggle_typewriter_mode(self) -> None:
        self._typewriter_mode = not self._typewriter_mode
        self._session_save_timer.start()

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
        self._session_save_timer.start()

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

    def _handle_psyke_context(self, action: str, *args):
        if action == "resolve":
            text, col = args[0], args[1]
            return self._resolve_term_at(text, col)
        if action == "open":
            entry_id = args[0]
            self._on_psyke_jump(entry_id)
        return None

    def _resolve_term_at(self, text: str, col: int) -> int | None:
        hl = next(iter(self._highlighters.values()), None)
        if hl is None or hl._pattern is None:
            return None
        for m in hl._pattern.finditer(text):
            if m.start() <= col <= m.end():
                return self._psyke_term_map.get(m.group().lower())
        return None

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

    # -- Context assistant -----------------------------------------------------

    def _run_context_analysis(self) -> None:
        if not self._context_assistant_enabled:
            return
        if not self._context_hint_banners:
            return

        active_scene_id: int | None = None
        if self._active_editor and self._active_editor._scene_id:
            active_scene_id = self._active_editor._scene_id

        ignored = self._get_context_ignored_keys()

        structural_hints = self._get_structural_hints()

        for scene_id, banner in self._context_hint_banners.items():
            if active_scene_id is not None and scene_id != active_scene_id:
                continue

            hints = self._context_assistant.analyze_scene(
                scene_id, temporal_graph=self._temporal_graph,
            )

            hints.extend(structural_hints)
            hints = [h for h in hints if h.dedup_key not in ignored]

            chosen = self._hint_rate_limiter.filter(hints)
            if chosen is not None:
                self._hint_rate_limiter.mark_shown(chosen)
                banner.show_hint(chosen)

    def _get_structural_hints(self) -> list[ContextHint]:
        analysis = self._structural_cache.get(
            self._db, self._project_id, self._temporal_graph,
        )
        hints: list[ContextHint] = []
        for issue in analysis.issues[:2]:
            hints.append(ContextHint(
                hint_type=f"structure_{issue.issue_type}",
                message=issue.message,
                priority=2 if issue.severity >= 0.5 else 3,
                scene_id=0,
                data={"_dedup": f"struct_{issue.issue_type}", **issue.data},
            ))
        return hints

    def _on_context_hint_accepted(self, hint: ContextHint) -> None:
        if hint.action == "open_progression":
            entry_id = hint.data.get("entry_id")
            if entry_id is not None and self._on_open_psyke_entry:
                self._on_open_psyke_entry(entry_id)
        elif hint.action == "focus_conflict":
            pass

        self._close_hint_banner_for(hint)

    def _on_context_hint_dismissed(self, hint: ContextHint) -> None:
        self._close_hint_banner_for(hint)

    def _on_context_hint_ignored(self, hint: ContextHint) -> None:
        self._persist_context_ignored_key(hint.dedup_key)
        self._close_hint_banner_for(hint)

    def _close_hint_banner_for(self, hint: ContextHint) -> None:
        for banner in self._context_hint_banners.values():
            if banner.current is hint:
                banner.clear()

    def _get_context_ignored_keys(self) -> set[str]:
        raw = get_settings().get("context_assistant_ignored")
        if isinstance(raw, list):
            return set(raw)
        return set()

    def _persist_context_ignored_key(self, key: str) -> None:
        keys = list(self._get_context_ignored_keys())
        if key in keys:
            return
        keys.append(key)
        get_settings().set("context_assistant_ignored", keys)

    # -- Public API -----------------------------------------------------------

    def scroll_to_scene(self, scene_id: int) -> None:
        editor = self._editors.get(scene_id)
        if editor:
            self._scroll.ensureWidgetVisible(editor, 50, 50)
            editor.setFocus()
