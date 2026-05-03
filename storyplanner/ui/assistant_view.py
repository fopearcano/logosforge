"""Global assistant side panel — compact AI writing assistant."""

from collections.abc import Callable

from PySide6.QtCore import QThread, QTimer, Signal, Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMenu,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from storyplanner.assistant import (
    PRESET_ACTIONS,
    build_messages,
    chat_completion,
)
from storyplanner.counterpart import (
    DIALOGIC_MODES,
    build_counterpart_messages,
)
from storyplanner.adaptive_mode import (
    AIMode,
    HealthState,
    ModeResult,
    StoryStage,
    _MODE_DESCRIPTIONS,
    compute_mode,
    mode_context_block,
)
from storyplanner.context_builder import (
    gather_graph_context,
    gather_outline_context,
    gather_psyke_context,
    gather_scene_context,
    gather_story_memory,
)
from storyplanner.irrational import build_irrational_context, reroll_seed
from storyplanner.structural_intelligence import gather_structural_context
from storyplanner.db import Database
from storyplanner.memory_context import gather_memory_context
from storyplanner.narrative_suggestions import (
    build_suggestion_messages,
    format_suggestion_debug,
)
from storyplanner.orchestration import (
    format_orchestration_debug,
    orchestrate_psyke_context,
    resolve_mode,
)
from storyplanner.providers import ProviderConfig
from storyplanner.quantum_outliner import (
    collapse_branch as quantum_collapse_branch,
    detect_weak_scenes as quantum_detect_weak_scenes,
    generate_branches as quantum_generate_branches,
    generate_outline as quantum_generate_outline,
    list_active_wavefunctions as quantum_list_active,
    load_state as quantum_load_state,
    reframe as quantum_reframe,
    save_state as quantum_save_state,
)
from storyplanner.settings import get_manager as get_settings
from storyplanner.ui import theme
from storyplanner.ui.mode_strip import ModeStrip
from storyplanner.ui.provider_settings import ProviderSettingsWidget


SECTION_SYSTEM_PROMPTS: dict[str, str] = {
    "Manuscript": (
        "You are a skilled fiction writer. "
        "The user is writing their manuscript. "
        "ALWAYS generate pure prose — narrative text, dialogue, "
        "action, description, and inner thought. Write directly "
        "in the voice of the story as if writing a novel. "
        "NEVER output outlines, bullet points, headers, scene "
        "breakdowns, or structural analysis. Just write the story."
    ),
    "Outline": (
        "You are a story planning assistant. "
        "The user is building the story outline. Generate a structured outline: "
        "numbered scenes or chapters with brief descriptions of key events, "
        "turning points, and character arcs."
    ),
    "Scenes": (
        "You are a fiction writing assistant. "
        "Help the user develop individual scenes. When asked to write "
        "a scene, generate prose — narrative text with action, "
        "dialogue, and description. When asked to plan a scene, "
        "describe setting, characters, beats, and conflict."
    ),
    "Characters": (
        "You are a character development assistant. "
        "Help the user flesh out characters: personality traits, backstory, "
        "motivations, relationships, speech patterns, and arc."
    ),
    "Plot": (
        "You are a plot development assistant. "
        "Help the user structure the plot. Focus on cause and effect, "
        "escalation, stakes, subplots, and story beats."
    ),
    "Acts": (
        "You are a story structure assistant. "
        "Help the user organize the story into acts. Analyze structure, "
        "identify act breaks, midpoints, climax placement, and pacing."
    ),
    "Beats": (
        "You are a narrative beat analyst. "
        "Help the user plan and refine story beats: emotional shifts, "
        "revelations, reversals, and micro-tensions within scenes."
    ),
    "Dialogue": (
        "You are a dialogue specialist. "
        "Help the user write natural, character-appropriate dialogue "
        "with subtext, rhythm, and distinct voices."
    ),
    "Notes": (
        "You are a creative writing assistant. "
        "The user is taking notes. Help organize ideas, brainstorm, "
        "and develop raw concepts into structured story material."
    ),
    "Places": (
        "You are a worldbuilding assistant. "
        "Help the user develop locations: atmosphere, sensory details, "
        "history, significance to the plot, and mood."
    ),
    "Pacing": (
        "You are a pacing analyst. "
        "Analyze and suggest improvements to narrative pacing: rhythm, "
        "scene length, tension curves, and breathing room."
    ),
    "PSYKE": (
        "You are a story bible assistant. "
        "Help the user develop and organize their story bible: rules, "
        "lore, character facts, world details, and continuity notes."
    ),
}

SECTION_PLACEHOLDERS: dict[str, str] = {
    "Manuscript": "Describe what to write: a scene, continuation, dialogue...",
    "Outline": "Describe your story idea or ask to structure the plot...",
    "Scenes": "Describe the scene you want to develop...",
    "Characters": "Describe a character to develop or ask for suggestions...",
    "Plot": "Ask about plot structure, stakes, subplots...",
    "Acts": "Ask about act structure, turning points...",
    "Beats": "Ask about beats, emotional shifts, revelations...",
    "Notes": "Brainstorm, develop ideas, or ask questions...",
    "Places": "Describe a location to develop or ask for details...",
    "Pacing": "Ask about pacing, rhythm, scene lengths...",
    "PSYKE": "Ask about story rules, lore, continuity...",
}

_ACTION_ALIASES: dict[str, str] = {k.lower(): k for k in PRESET_ACTIONS}


def _normalize_action(key: str) -> str | None:
    """Map a user-typed action name to the canonical PRESET_ACTIONS key."""
    return _ACTION_ALIASES.get(key.lower())


class _AssistantWorker(QThread):
    completed = Signal(str, bool)
    failed = Signal(str)

    def __init__(
        self, messages: list[dict], provider: ProviderConfig,
    ) -> None:
        super().__init__()
        self._messages = messages
        self._provider = provider

    def run(self) -> None:
        try:
            result, from_cache = chat_completion(
                self._messages, provider=self._provider,
            )
            self.completed.emit(result, from_cache)
        except Exception as e:
            self.failed.emit(str(e))


class _QuantumWorker(QThread):
    completed = Signal(object)
    failed = Signal(str)

    def __init__(self, fn, *args, **kwargs) -> None:
        super().__init__()
        self._fn = fn
        self._args = args
        self._kwargs = kwargs

    def run(self) -> None:
        try:
            result = self._fn(*self._args, **self._kwargs)
            self.completed.emit(result)
        except Exception as e:
            self.failed.emit(str(e))


class AssistantPanel(QWidget):
    """Compact AI writing assistant — docks as a right-side panel."""

    panel_closed = Signal()

    def __init__(
        self,
        db: Database,
        project_id: int,
        on_data_changed: Callable[[], None] | None = None,
        on_open_scene: Callable[[int], None] | None = None,
        get_active_scene_id: Callable[[], int | None] | None = None,
        get_selected_text: Callable[[], str] | None = None,
        get_active_editor: Callable[[], object | None] | None = None,
    ) -> None:
        super().__init__()
        self._db = db
        self._project_id = project_id
        self._on_data_changed = on_data_changed
        self._on_open_scene = on_open_scene
        self._get_active_scene_id = get_active_scene_id
        self._get_selected_text = get_selected_text
        self._get_active_editor = get_active_editor
        self._active_section: str = "Dashboard"
        self._worker: _AssistantWorker | None = None
        self._quantum_worker: _QuantumWorker | None = None
        self._pending_messages: list[dict] | None = None

        quantum_load_state(db, project_id)

        self._debounce_timer = QTimer()
        self._debounce_timer.setSingleShot(True)
        self._debounce_timer.setInterval(120)
        self._debounce_timer.timeout.connect(self._fire_request)

        self._overlay_mode = False
        self._typing_dimmed = False

        self.setMinimumWidth(220)
        self.setMaximumWidth(360)
        self.setObjectName("assistantPanel")

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        outer.addWidget(scroll)

        container = QWidget()
        self._layout = QVBoxLayout(container)
        self._layout.setContentsMargins(8, 6, 8, 8)
        self._layout.setSpacing(6)
        scroll.setWidget(container)

        self._build_ui()

    # -- Layout ----------------------------------------------------------------

    def _build_ui(self) -> None:
        # Header
        header = QHBoxLayout()
        header.setSpacing(4)
        title = QLabel("Assistant")
        title_font = QFont()
        title_font.setBold(True)
        title_font.setPointSize(title_font.pointSize() + 1)
        title.setFont(title_font)
        title.setStyleSheet(f"color: {theme.TEXT_PRIMARY};")
        header.addWidget(title)
        header.addStretch()

        self._overlay_btn = QPushButton("\u29c9")
        self._overlay_btn.setFixedSize(24, 24)
        self._overlay_btn.setFlat(True)
        self._overlay_btn.setToolTip("Toggle overlay mode")
        self._overlay_btn.setStyleSheet(
            f"QPushButton {{ color: {theme.TEXT_MUTED}; border: none; }}"
            f"QPushButton:hover {{ color: {theme.TEXT_PRIMARY}; }}"
        )
        self._overlay_btn.clicked.connect(self._toggle_overlay)
        header.addWidget(self._overlay_btn)

        close_btn = QPushButton("\u2715")
        close_btn.setFixedSize(24, 24)
        close_btn.setFlat(True)
        close_btn.setStyleSheet(
            f"QPushButton {{ color: {theme.TEXT_MUTED}; border: none; }}"
            f"QPushButton:hover {{ color: {theme.TEXT_PRIMARY}; }}"
        )
        close_btn.clicked.connect(self.panel_closed.emit)
        header.addWidget(close_btn)
        self._layout.addLayout(header)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"color: {theme.BORDER};")
        self._layout.addWidget(sep)

        # Panel mode selector: Assistant | Counterpart | Quantum
        self._panel_mode = "assistant"
        panel_mode_row = QHBoxLayout()
        panel_mode_row.setSpacing(4)
        self._assistant_mode_btn = QPushButton("Assistant")
        self._counterpart_mode_btn = QPushButton("Counterpart")
        self._quantum_mode_btn = QPushButton("Quantum")
        for btn, mode in (
            (self._assistant_mode_btn, "assistant"),
            (self._counterpart_mode_btn, "counterpart"),
            (self._quantum_mode_btn, "quantum"),
        ):
            btn.setCheckable(True)
            btn.clicked.connect(lambda _, m=mode: self._set_panel_mode(m))
        self._assistant_mode_btn.setChecked(True)
        self._assistant_mode_btn.setStyleSheet(self._seg_btn_style(active=True))
        self._counterpart_mode_btn.setStyleSheet(self._seg_btn_style(active=False))
        self._quantum_mode_btn.setStyleSheet(self._seg_btn_style(active=False))
        panel_mode_row.addWidget(self._assistant_mode_btn)
        panel_mode_row.addWidget(self._counterpart_mode_btn)
        panel_mode_row.addWidget(self._quantum_mode_btn)
        panel_mode_row.addStretch()
        self._layout.addLayout(panel_mode_row)

        # Mode strip
        self._mode_strip = ModeStrip(
            self._db, self._project_id,
            on_mode_changed=self._on_mode_override,
        )
        self._layout.addWidget(self._mode_strip)

        # Context source selector + Generate
        ctx_row = QHBoxLayout()
        ctx_row.setSpacing(4)
        self._ctx_source_combo = QComboBox()
        self._ctx_source_combo.addItem("Selection", userData="selection")
        self._ctx_source_combo.addItem("Current scene", userData="scene")
        self._ctx_source_combo.addItem("Outline", userData="outline")
        self._ctx_source_combo.addItem("Acts", userData="acts")
        self._ctx_source_combo.addItem("Whole project", userData="project")
        self._ctx_source_combo.setCurrentIndex(1)
        ctx_row.addWidget(self._ctx_source_combo, stretch=1)
        self._send_btn = QPushButton("Generate")
        self._send_btn.setStyleSheet(theme.primary_btn())
        self._send_btn.clicked.connect(self._send_custom)
        ctx_row.addWidget(self._send_btn)
        self._layout.addLayout(ctx_row)

        # Core actions (grid for wrapping on narrow panels)
        action_grid = QGridLayout()
        action_grid.setSpacing(4)
        action_grid.setContentsMargins(0, 0, 0, 0)
        self._preset_buttons: list[QPushButton] = []
        for col, action in enumerate(("Rewrite", "Expand", "Dialogue")):
            btn = QPushButton(action)
            btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            btn.clicked.connect(
                lambda _, a=action: self._send_preset(a)
            )
            action_grid.addWidget(btn, 0, col)
            self._preset_buttons.append(btn)

        self._suggest_btn = QPushButton("Suggest")
        self._suggest_btn.setToolTip(
            "Structured narrative direction suggestions"
        )
        self._suggest_btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._suggest_btn.clicked.connect(self._on_suggest_beats)
        action_grid.addWidget(self._suggest_btn, 1, 0, 1, 2)
        self._preset_buttons.append(self._suggest_btn)

        self._more_btn = QPushButton("More \u25be")
        more_menu = QMenu(self)
        for action in (
            "Summarize", "Tension", "Pacing", "Next Beat", "Alternatives",
        ):
            more_menu.addAction(
                action, lambda a=action: self._send_preset(a)
            )
        self._more_btn.setMenu(more_menu)
        self._more_btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        action_grid.addWidget(self._more_btn, 1, 2)
        self._preset_buttons.append(self._more_btn)
        self._layout.addLayout(action_grid)

        # Counterpart actions (hidden by default)
        self._counterpart_row = QWidget()
        cp_grid = QGridLayout(self._counterpart_row)
        cp_grid.setContentsMargins(0, 0, 0, 0)
        cp_grid.setSpacing(4)
        self._counterpart_buttons: list[QPushButton] = []
        for col, mode_name in enumerate(("Feedback", "Critique", "Interpret")):
            btn = QPushButton(mode_name)
            btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            btn.clicked.connect(
                lambda _, m=mode_name: self._send_counterpart(m)
            )
            cp_grid.addWidget(btn, 0, col)
            self._counterpart_buttons.append(btn)
        cp_more_btn = QPushButton("More ▾")
        cp_more_menu = QMenu(self)
        for mode_name in ("Ask Back", "Compare"):
            cp_more_menu.addAction(
                mode_name, lambda m=mode_name: self._send_counterpart(m)
            )
        cp_more_btn.setMenu(cp_more_menu)
        cp_more_btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        cp_grid.addWidget(cp_more_btn, 1, 0, 1, 3)
        self._counterpart_buttons.append(cp_more_btn)
        self._counterpart_row.setVisible(False)
        self._layout.addWidget(self._counterpart_row)

        # Quantum actions (hidden by default)
        self._quantum_row = QWidget()
        q_grid = QGridLayout(self._quantum_row)
        q_grid.setContentsMargins(0, 0, 0, 0)
        q_grid.setSpacing(4)
        self._quantum_buttons: list[QPushButton] = []

        outline_btn = QPushButton("Outline")
        outline_btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        outline_btn.setToolTip("Generate opening branches from a premise")
        outline_btn.clicked.connect(self._on_quantum_outline)
        q_grid.addWidget(outline_btn, 0, 0)
        self._quantum_buttons.append(outline_btn)

        possibilities_btn = QPushButton("Possibilities")
        possibilities_btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        possibilities_btn.setToolTip("Generate next-move branches for the prompt")
        possibilities_btn.clicked.connect(self._on_quantum_possibilities)
        q_grid.addWidget(possibilities_btn, 0, 1)
        self._quantum_buttons.append(possibilities_btn)

        reframe_btn = QPushButton("Reframe")
        reframe_btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        reframe_btn.setToolTip("Reread the active scene from a different POV")
        reframe_btn.clicked.connect(self._on_quantum_reframe)
        q_grid.addWidget(reframe_btn, 1, 0)
        self._quantum_buttons.append(reframe_btn)

        weak_btn = QPushButton("Uncertainty")
        weak_btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        weak_btn.setToolTip("Find weak/predictable scenes")
        weak_btn.clicked.connect(self._on_quantum_uncertainty)
        q_grid.addWidget(weak_btn, 1, 1)
        self._quantum_buttons.append(weak_btn)

        collapse_btn = QPushButton("Collapse ▾")
        collapse_btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        collapse_btn.setToolTip("Commit a branch — updates PSYKE")
        self._collapse_menu = QMenu(self)
        collapse_btn.setMenu(self._collapse_menu)
        self._collapse_menu.aboutToShow.connect(self._refresh_collapse_menu)
        q_grid.addWidget(collapse_btn, 2, 0, 1, 2)
        self._quantum_buttons.append(collapse_btn)

        self._quantum_row.setVisible(False)
        self._layout.addWidget(self._quantum_row)

        # Custom prompt
        self._prompt_input = QPlainTextEdit()
        self._prompt_input.setPlaceholderText(
            "Instructions or questions about the scene..."
        )
        self._prompt_input.setMaximumHeight(48)
        self._prompt_input.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)
        self._layout.addWidget(self._prompt_input)

        # Collapsible settings
        self._settings_btn = QPushButton("\u25b6 Settings")
        self._settings_btn.setFlat(True)
        self._settings_btn.setStyleSheet(
            f"QPushButton {{ color: {theme.TEXT_SECONDARY}; border: none;"
            f" text-align: left; padding: 2px 0; font-size: 11px; }}"
            f"QPushButton:hover {{ color: {theme.TEXT_PRIMARY}; }}"
        )
        self._settings_btn.clicked.connect(self._toggle_settings)
        self._layout.addWidget(self._settings_btn)

        self._settings_container = QWidget()
        settings_layout = QVBoxLayout(self._settings_container)
        settings_layout.setContentsMargins(0, 0, 0, 0)
        settings_layout.setSpacing(4)
        self._outline_check = QCheckBox("Include story outline")
        self._story_memory_check = QCheckBox("Include story memory")
        self._psyke_check = QCheckBox("PSYKE")
        settings_layout.addWidget(self._outline_check)
        settings_layout.addWidget(self._story_memory_check)
        settings_layout.addWidget(self._psyke_check)

        self._irrational_check = QCheckBox("Go Irrational")
        self._irrational_check.setToolTip(
            "Disrupt PSYKE rules: temporal displacement, entity blending, surreal prompts"
        )
        self._irrational_check.setStyleSheet(
            f"QCheckBox {{ color: {theme.TEXT_SECONDARY}; }}"
            f"QCheckBox::indicator:checked {{ background: #a855f7; border: 1px solid #7c3aed; }}"
        )
        settings_layout.addWidget(self._irrational_check)
        self._irrational_iteration = 0

        self._ctx_toggle = QCheckBox("Show context sent to model")
        self._ctx_toggle.toggled.connect(self._on_ctx_toggle)
        settings_layout.addWidget(self._ctx_toggle)

        self._ctx_viewer = QPlainTextEdit()
        self._ctx_viewer.setReadOnly(True)
        self._ctx_viewer.setMaximumHeight(140)
        self._ctx_viewer.setPlaceholderText(
            "Context will appear here after a request..."
        )
        self._ctx_viewer.setStyleSheet(
            f"QPlainTextEdit {{"
            f"  background-color: {theme.BG_PANEL};"
            f"  color: {theme.TEXT_SECONDARY};"
            f"  border: 1px solid {theme.BORDER};"
            f"  font-size: 10px; padding: 4px;"
            f"}}"
        )
        self._ctx_viewer.setVisible(False)
        settings_layout.addWidget(self._ctx_viewer)

        self._provider_widget = ProviderSettingsWidget(compact=True)
        self._restore_provider_settings()
        settings_layout.addWidget(self._provider_widget)
        self._settings_container.setVisible(False)
        self._layout.addWidget(self._settings_container)

        # Response area
        resp_header = QHBoxLayout()
        resp_header.setSpacing(4)
        resp_label = QLabel("Response")
        resp_label.setStyleSheet(
            f"color: {theme.TEXT_SECONDARY}; font-size: 11px;"
        )
        resp_header.addWidget(resp_label)
        self._cache_label = QLabel("cached")
        self._cache_label.setStyleSheet(
            f"color: {theme.ACCENT}; font-size: 10px; font-style: italic;"
        )
        self._cache_label.setVisible(False)
        resp_header.addWidget(self._cache_label)
        resp_header.addStretch()
        self._layout.addLayout(resp_header)

        self._response_output = QPlainTextEdit()
        self._response_output.setReadOnly(True)
        self._response_output.setPlaceholderText(
            "AI response will appear here..."
        )
        self._response_output.setMinimumHeight(80)
        self._response_output.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)
        self._response_output.setStyleSheet(
            f"QPlainTextEdit {{"
            f"  background-color: {theme.BG_PANEL};"
            f"  color: {theme.TEXT_PRIMARY};"
            f"  border: 1px solid {theme.BORDER};"
            f"  border-radius: 4px; padding: 6px;"
            f"}}"
        )
        self._layout.addWidget(self._response_output, stretch=1)

        # Apply actions: Copy | Replace | Insert | Append
        apply_row = QHBoxLayout()
        apply_row.setSpacing(4)

        self._copy_btn = QPushButton("Copy")
        self._copy_btn.clicked.connect(self._copy_response)
        apply_row.addWidget(self._copy_btn)

        self._replace_content_btn = QPushButton("Replace")
        self._replace_content_btn.clicked.connect(self._apply_replace)
        apply_row.addWidget(self._replace_content_btn)

        self._insert_cursor_btn = QPushButton("Insert")
        self._insert_cursor_btn.clicked.connect(self._apply_insert)
        apply_row.addWidget(self._insert_cursor_btn)

        self._append_btn = QPushButton("Append")
        self._append_btn.clicked.connect(self._apply_append)
        apply_row.addWidget(self._append_btn)

        self._apply_buttons = [
            self._copy_btn,
            self._replace_content_btn,
            self._insert_cursor_btn,
            self._append_btn,
        ]
        self._layout.addLayout(apply_row)

        self._mode_strip.refresh()
        self._restore_panel_settings()

    # -- Mode override ---------------------------------------------------------

    def _on_mode_override(self, mode: AIMode | None) -> None:
        pass  # Mode is read from strip at context-build time

    # -- Panel mode (Assistant / Counterpart) ----------------------------------

    def _seg_btn_style(self, active: bool) -> str:
        if active:
            return (
                f"QPushButton {{ background-color: {theme.ACCENT};"
                f" color: #ffffff; border: none; border-radius: 4px;"
                f" padding: 3px 10px; font-size: 11px; font-weight: bold; }}"
            )
        return (
            f"QPushButton {{ background-color: transparent;"
            f" color: {theme.TEXT_MUTED}; border: 1px solid {theme.BORDER};"
            f" border-radius: 4px; padding: 3px 10px; font-size: 11px; }}"
            f"QPushButton:hover {{ color: {theme.TEXT_PRIMARY}; }}"
        )

    def _set_panel_mode(self, mode: str) -> None:
        if mode not in ("assistant", "counterpart", "quantum"):
            mode = "assistant"
        self._panel_mode = mode
        is_assistant = mode == "assistant"
        is_counterpart = mode == "counterpart"
        is_quantum = mode == "quantum"

        self._assistant_mode_btn.setChecked(is_assistant)
        self._counterpart_mode_btn.setChecked(is_counterpart)
        self._quantum_mode_btn.setChecked(is_quantum)
        self._assistant_mode_btn.setStyleSheet(self._seg_btn_style(is_assistant))
        self._counterpart_mode_btn.setStyleSheet(self._seg_btn_style(is_counterpart))
        self._quantum_mode_btn.setStyleSheet(self._seg_btn_style(is_quantum))

        # Toggle action rows
        for btn in self._preset_buttons:
            btn.setVisible(is_assistant)
        self._counterpart_row.setVisible(is_counterpart)
        self._quantum_row.setVisible(is_quantum)

        # Apply buttons mutate scene content — only Assistant uses them
        self._replace_content_btn.setVisible(is_assistant)
        self._insert_cursor_btn.setVisible(is_assistant)
        self._append_btn.setVisible(is_assistant)

        # Mode strip only relevant for assistant
        self._mode_strip.setVisible(is_assistant)

        if is_assistant:
            placeholder = SECTION_PLACEHOLDERS.get(
                self._active_section,
                "Instructions or questions about your story...",
            )
            self._prompt_input.setPlaceholderText(placeholder)
        elif is_counterpart:
            self._prompt_input.setPlaceholderText(
                "Ask about your scene, request feedback, or reflect..."
            )
        else:
            self._prompt_input.setPlaceholderText(
                "Premise, situation, or POV name (used by Quantum actions)..."
            )

    # -- Settings toggle -------------------------------------------------------

    def _restore_provider_settings(self) -> None:
        mgr = get_settings()
        saved_provider = str(mgr.get("ai_provider"))
        idx = self._provider_widget._provider_combo.findText(saved_provider)
        if idx >= 0:
            self._provider_widget._provider_combo.setCurrentIndex(idx)
        saved_model = str(mgr.get("ai_model"))
        if saved_model:
            self._provider_widget._model_combo.setCurrentText(saved_model)
        saved_key = str(mgr.get("ai_api_key"))
        if saved_key:
            self._provider_widget._key_input.setText(saved_key)
        saved_url = str(mgr.get("ai_base_url"))
        if saved_url:
            self._provider_widget._url_input.setText(saved_url)

    def _restore_panel_settings(self) -> None:
        mgr = get_settings()
        mode = str(mgr.get("assistant_panel_mode") or "assistant")
        if mode in ("assistant", "counterpart", "quantum"):
            self._set_panel_mode(mode)
        self._outline_check.setChecked(bool(mgr.get("assistant_include_outline")))
        self._story_memory_check.setChecked(bool(mgr.get("assistant_include_memory")))
        self._psyke_check.setChecked(bool(mgr.get("assistant_include_bible")))
        self._irrational_check.setChecked(bool(mgr.get("assistant_irrational")))

    def save_settings(self) -> None:
        mgr = get_settings()
        pw = self._provider_widget
        mgr.set("ai_provider", pw._provider_combo.currentText())
        mgr.set("ai_model", pw._model_combo.currentText())
        mgr.set("ai_api_key", pw._key_input.text())
        mgr.set("ai_base_url", pw._url_input.text())
        mgr.set("assistant_panel_mode", self._panel_mode)
        mgr.set("assistant_include_outline", self._outline_check.isChecked())
        mgr.set("assistant_include_memory", self._story_memory_check.isChecked())
        mgr.set("assistant_include_bible", self._psyke_check.isChecked())
        mgr.set("assistant_irrational", self._irrational_check.isChecked())

    def _toggle_settings(self) -> None:
        visible = not self._settings_container.isVisible()
        self._settings_container.setVisible(visible)
        self._settings_btn.setText(
            "\u25bc Settings" if visible else "\u25b6 Settings"
        )

    def _on_ctx_toggle(self, checked: bool) -> None:
        self._ctx_viewer.setVisible(checked)

    # -- Context source --------------------------------------------------------

    def _get_context_source(self) -> str:
        return self._ctx_source_combo.currentData() or "scene"

    def _get_auto_scene_id(self) -> int | None:
        if self._get_active_scene_id:
            sid = self._get_active_scene_id()
            if sid is not None:
                return sid
        scenes = self._db.get_all_scenes(self._project_id)
        if len(scenes) == 1:
            return scenes[0].id
        return None

    def _get_selected_text_content(self) -> str:
        if self._get_selected_text:
            text = self._get_selected_text()
            if text:
                return text
        return ""

    def set_active_scene(self, scene_id: int) -> None:
        pass

    def refresh_scenes(self) -> None:
        self._mode_strip.refresh()

    def set_active_section_name(self, name: str) -> None:
        self._active_section = name
        placeholder = SECTION_PLACEHOLDERS.get(
            name, "Instructions or questions about your story..."
        )
        if self._panel_mode == "assistant":
            self._prompt_input.setPlaceholderText(placeholder)
        self.refresh_scenes()

    def run_action(self, action_key: str, selected_text: str = "") -> bool:
        """Trigger a preset AI action programmatically. Returns False if busy."""
        if self._worker is not None:
            return False
        canonical = _normalize_action(action_key)
        if canonical is None:
            return False

        scene_ctx = ""
        if selected_text:
            scene_ctx = f"[Selected Text]\n{selected_text}"
        else:
            scene_id = self._get_auto_scene_id()
            if scene_id is not None:
                scene_ctx = gather_scene_context(
                    self._db, self._project_id, scene_id,
                )

        if not scene_ctx:
            self._response_output.setPlainText("No text selected and no active scene.")
            return False

        action_prompt = PRESET_ACTIONS[canonical]
        messages = build_messages(
            action_prompt, scene_ctx,
            structural_context=gather_structural_context(self._db, self._project_id),
            system_prompt=self._get_section_system_prompt(),
        )

        if not self.isVisible():
            self.setVisible(True)
        self._response_output.setPlainText("")
        self._start_request(messages)
        return True

    def _get_section_system_prompt(self) -> str:
        return SECTION_SYSTEM_PROMPTS.get(self._active_section, "")

    # -- Sending requests ------------------------------------------------------

    def _build_context(
        self, action_key: str = "",
    ) -> tuple[str, str, str, str, str, str, str, str, str]:
        source = self._get_context_source()
        scene_id = self._get_auto_scene_id()

        scene_ctx = ""
        if source == "selection":
            selected = self._get_selected_text_content()
            if selected:
                scene_ctx = f"[Selected Text]\n{selected}"
            elif scene_id is not None:
                scene_ctx = gather_scene_context(
                    self._db, self._project_id, scene_id,
                )
        elif source == "scene" and scene_id is not None:
            scene_ctx = gather_scene_context(
                self._db, self._project_id, scene_id,
            )

        outline_ctx = ""
        if source in ("outline", "project", "acts") or self._outline_check.isChecked():
            outline_ctx = gather_outline_context(self._db, self._project_id)

        story_memory_ctx = ""
        if self._story_memory_check.isChecked():
            global_mem = gather_story_memory(self._db, self._project_id)
            scene_mem = ""
            if scene_id is not None:
                scene_mem = gather_memory_context(
                    self._db, self._project_id, scene_id=scene_id,
                )
            story_memory_ctx = "\n\n".join(
                part for part in [global_mem, scene_mem] if part
            )

        psyke_ctx = ""
        orchestration_debug = ""
        if self._psyke_check.isChecked():
            prompt_query = self._prompt_input.toPlainText().strip()
            selected_text = self._get_selected_text_content()
            query_text = "\n".join(t for t in (prompt_query, selected_text) if t)
            if action_key and scene_id is not None:
                mode = resolve_mode(action_key)
                result = orchestrate_psyke_context(
                    self._db, self._project_id, scene_id, mode,
                    selected_text=query_text,
                )
                psyke_ctx = result.psyke_context
                orchestration_debug = format_orchestration_debug(result)
            else:
                psyke_ctx = gather_psyke_context(
                    self._db, self._project_id, scene_id,
                    query_text=query_text,
                )

        graph_ctx = ""
        if scene_id is not None and source in ("scene", "selection"):
            graph_ctx = gather_graph_context(self._db, self._project_id, scene_id)

        structural_ctx = gather_structural_context(self._db, self._project_id)

        irrational_ctx = ""
        if self._irrational_check.isChecked() and scene_id is not None:
            seed = reroll_seed(scene_id, self._irrational_iteration)
            irrational_ctx = build_irrational_context(
                self._db, self._project_id, scene_id, seed=seed,
            )

        self._mode_strip.refresh()
        mode_result = self._mode_strip.get_mode_result()
        if self._mode_strip.is_overridden():
            effective = self._mode_strip.get_effective_mode()
            mode_result = ModeResult(
                mode=effective,
                stage=mode_result.stage if mode_result else StoryStage.EARLY,
                health=mode_result.health if mode_result else HealthState.FRAGMENTED,
                description=_MODE_DESCRIPTIONS[effective],
            )
        mode_ctx = mode_context_block(mode_result) if mode_result else ""
        return scene_ctx, outline_ctx, story_memory_ctx, psyke_ctx, orchestration_debug, graph_ctx, mode_ctx, structural_ctx, irrational_ctx

    def _send_preset(self, action_key: str) -> None:
        if self._worker is not None:
            return

        scene_ctx, outline_ctx, story_memory_ctx, psyke_ctx, orch_debug, graph_ctx, mode_ctx, struct_ctx, irr_ctx = (
            self._build_context(action_key=action_key)
        )
        if not scene_ctx and not outline_ctx and not struct_ctx:
            self._response_output.setPlainText("No context available. Add scenes or project data first.")
            return

        user_note = self._prompt_input.toPlainText().strip()
        action_prompt = PRESET_ACTIONS[action_key]

        messages = build_messages(
            action_prompt, scene_ctx,
            outline_context=outline_ctx,
            story_memory_context=story_memory_ctx,
            psyke_context=psyke_ctx,
            graph_context=graph_ctx,
            mode_context=mode_ctx,
            user_note=user_note,
            structural_context=struct_ctx,
            irrational_context=irr_ctx,
            system_prompt=self._get_section_system_prompt(),
        )
        self._update_ctx_viewer(
            scene_ctx, outline_ctx, story_memory_ctx, psyke_ctx, action_prompt,
            orch_debug, graph_ctx, mode_ctx,
        )
        self._start_request(messages)

    def _send_custom(self) -> None:
        if self._panel_mode == "counterpart":
            return self._send_counterpart_custom()
        if self._worker is not None:
            return
        prompt = self._prompt_input.toPlainText().strip()
        if not prompt:
            self._response_output.setPlainText("Enter a prompt first.")
            return

        scene_ctx, outline_ctx, story_memory_ctx, psyke_ctx, orch_debug, graph_ctx, mode_ctx, struct_ctx, irr_ctx = (
            self._build_context()
        )

        messages = build_messages(
            prompt, scene_ctx,
            outline_context=outline_ctx,
            story_memory_context=story_memory_ctx,
            psyke_context=psyke_ctx,
            graph_context=graph_ctx,
            mode_context=mode_ctx,
            structural_context=struct_ctx,
            irrational_context=irr_ctx,
            system_prompt=self._get_section_system_prompt(),
        )
        self._update_ctx_viewer(
            scene_ctx, outline_ctx, story_memory_ctx, psyke_ctx, prompt,
            orch_debug, graph_ctx, mode_ctx,
        )
        self._start_request(messages)

    def _send_counterpart(self, mode_key: str) -> None:
        if self._worker is not None:
            return

        scene_ctx, outline_ctx, story_memory_ctx, psyke_ctx, orch_debug, graph_ctx, _mode_ctx, _struct_ctx, _irr_ctx = (
            self._build_context()
        )
        if not scene_ctx and not outline_ctx:
            self._response_output.setPlainText("No context available. Add scenes or project data first.")
            return

        mode_prompt = DIALOGIC_MODES[mode_key]
        user_note = self._prompt_input.toPlainText().strip()

        messages = build_counterpart_messages(
            mode_prompt, scene_ctx,
            outline_context=outline_ctx,
            story_memory_context=story_memory_ctx,
            psyke_context=psyke_ctx,
            graph_context=graph_ctx,
            user_note=user_note,
        )
        self._update_ctx_viewer(
            scene_ctx, outline_ctx, story_memory_ctx, psyke_ctx,
            f"[COUNTERPART: {mode_key}] {mode_prompt}",
            orch_debug, graph_ctx,
        )
        self._start_request(messages)

    def _send_counterpart_custom(self) -> None:
        if self._worker is not None:
            return
        prompt = self._prompt_input.toPlainText().strip()
        if not prompt:
            self._response_output.setPlainText("Enter a prompt first.")
            return

        scene_ctx, outline_ctx, story_memory_ctx, psyke_ctx, orch_debug, graph_ctx, _mode_ctx, _struct_ctx, _irr_ctx = (
            self._build_context()
        )

        messages = build_counterpart_messages(
            prompt, scene_ctx,
            outline_context=outline_ctx,
            story_memory_context=story_memory_ctx,
            psyke_context=psyke_ctx,
            graph_context=graph_ctx,
        )
        self._update_ctx_viewer(
            scene_ctx, outline_ctx, story_memory_ctx, psyke_ctx,
            f"[COUNTERPART: Custom] {prompt}",
            orch_debug, graph_ctx,
        )
        self._start_request(messages)

    # -- Quantum Outliner handlers ---------------------------------------------

    def _quantum_prompt(self) -> str:
        return self._prompt_input.toPlainText().strip()

    def _show_quantum_result(self, result) -> None:
        body = f"[QUANTUM · {result.title}]\n\n{result.body}"
        self._response_output.setPlainText(body)

    def _start_quantum(self, fn, *args, loading_msg: str = "Working…", **kwargs) -> bool:
        if self._quantum_worker is not None:
            return False
        self._set_quantum_busy(True)
        self._response_output.setPlainText(loading_msg)
        self._quantum_worker = _QuantumWorker(fn, *args, **kwargs)
        self._quantum_worker.completed.connect(self._on_quantum_done)
        self._quantum_worker.failed.connect(self._on_quantum_error)
        self._quantum_worker.start()
        return True

    def _on_quantum_done(self, result) -> None:
        self._show_quantum_result(result)
        self._set_quantum_busy(False)
        if result.kind in ("possibilities", "collapse"):
            quantum_save_state(self._db, self._project_id)
        if result.kind == "collapse" and self._on_data_changed:
            self._on_data_changed()
        self._quantum_worker = None

    def _on_quantum_error(self, error: str) -> None:
        self._response_output.setPlainText(f"Error:\n\n{error}")
        self._set_quantum_busy(False)
        self._quantum_worker = None

    def _set_quantum_busy(self, busy: bool) -> None:
        for btn in self._quantum_buttons:
            btn.setEnabled(not busy)

    def _on_quantum_outline(self) -> None:
        premise = self._quantum_prompt()
        if not premise:
            self._response_output.setPlainText(
                "Type a story premise above, then click Outline."
            )
            return
        self._start_quantum(
            quantum_generate_outline, self._db, self._project_id, premise,
            loading_msg="Generating wavefunction…",
        )

    def _on_quantum_possibilities(self) -> None:
        situation = self._quantum_prompt()
        if not situation:
            scene_id = self._get_auto_scene_id()
            if scene_id is not None:
                situation = f"Continue from active scene #{scene_id}"
            else:
                self._response_output.setPlainText(
                    "Type a situation (e.g. 'Hero meets enemy') and click Possibilities."
                )
                return
        self._start_quantum(
            quantum_generate_branches, self._db, self._project_id, situation,
            loading_msg="Generating possibilities…",
        )

    def _on_quantum_reframe(self) -> None:
        pov = self._quantum_prompt() or "neutral"
        scene_text = self._get_selected_text_content()
        if not scene_text:
            scene_id = self._get_auto_scene_id()
            if scene_id is not None:
                scene = self._db.get_scene_by_id(scene_id)
                if scene:
                    scene_text = scene.content or ""
        if not scene_text:
            self._response_output.setPlainText(
                "Select text or open a scene to reframe."
            )
            return
        self._start_quantum(
            quantum_reframe, scene_text, pov, self._db, self._project_id,
            loading_msg=f"Reframing from {pov}…",
        )

    def _on_quantum_uncertainty(self) -> None:
        result = quantum_detect_weak_scenes(self._db, self._project_id)
        self._show_quantum_result(result)

    def _refresh_collapse_menu(self) -> None:
        self._collapse_menu.clear()
        active = quantum_list_active(self._project_id)
        if not active:
            action = self._collapse_menu.addAction("(no active wavefunctions)")
            action.setEnabled(False)
            return
        for wf in active:
            sub = self._collapse_menu.addMenu(f"{wf['anchor'][:40]}")
            for branch in wf["branches"]:
                label = f"{branch['title']} [{branch['id']}]"
                sub.addAction(
                    label,
                    lambda wf_id=wf["wavefunction_id"], b_id=branch["id"]:
                        self._on_quantum_collapse(wf_id, b_id),
                )

    def _on_quantum_collapse(self, wf_id: str, branch_id: str) -> None:
        self._start_quantum(
            quantum_collapse_branch, self._db, self._project_id, wf_id, branch_id,
            loading_msg="Collapsing branch…",
        )

    def _on_suggest_beats(self) -> None:
        if self._worker is not None:
            return
        scene_id = self._get_auto_scene_id()
        if scene_id is None:
            self._response_output.setPlainText("Select a scene to get beat suggestions.")
            return

        messages, ctx = build_suggestion_messages(
            self._db, self._project_id, scene_id,
        )
        if not messages:
            self._response_output.setPlainText(
                "Could not build suggestion context."
            )
            return

        if ctx:
            self._update_ctx_viewer(
                "", "", "", ctx.psyke_context,
                "Narrative Beat Suggestions",
                format_suggestion_debug(ctx),
            )

        self._start_request(messages)

    def _update_ctx_viewer(
        self, scene_ctx: str, outline_ctx: str,
        story_memory_ctx: str, psyke_ctx: str, action: str,
        orchestration_debug: str = "", graph_ctx: str = "",
        mode_ctx: str = "",
    ) -> None:
        parts = []
        if mode_ctx:
            parts.append(f"--- AI Mode ---\n{mode_ctx}")
        parts.append(f"--- Scene Context ---\n{scene_ctx}")
        if outline_ctx:
            parts.append(f"--- Outline ---\n{outline_ctx}")
        if story_memory_ctx:
            parts.append(f"--- Story Memory ---\n{story_memory_ctx}")
        if psyke_ctx:
            parts.append(f"--- Story Bible ---\n{psyke_ctx}")
        if graph_ctx:
            parts.append(f"--- Graph Context ---\n{graph_ctx}")
        if orchestration_debug:
            parts.append(orchestration_debug)
        parts.append(f"--- Action ---\n{action}")
        self._ctx_viewer.setPlainText("\n\n".join(parts))

    def _start_request(self, messages: list[dict]) -> None:
        error = self._provider_widget.validate()
        if error:
            self._response_output.setPlainText(error)
            return
        self._pending_messages = messages
        self._debounce_timer.start()

    def _fire_request(self) -> None:
        if self._pending_messages is None:
            return
        messages = self._pending_messages
        self._pending_messages = None
        self._set_busy(True)
        self._cache_label.setVisible(False)
        self._response_output.setPlainText("Thinking...")

        provider = self._provider_widget.get_provider_config()
        self._worker = _AssistantWorker(messages, provider)
        self._worker.completed.connect(self._on_response)
        self._worker.failed.connect(self._on_error)
        self._worker.start()

    # -- Response handling -----------------------------------------------------

    def _on_response(self, text: str, from_cache: bool) -> None:
        self._response_output.setPlainText(text)
        self._cache_label.setVisible(from_cache)
        self._set_busy(False)
        self._worker = None

    def _on_error(self, error: str) -> None:
        self._response_output.setPlainText(f"Error:\n\n{error}")
        self._set_busy(False)
        self._worker = None

    def _set_busy(self, busy: bool) -> None:
        self._send_btn.setEnabled(not busy)
        self._ctx_source_combo.setEnabled(not busy)
        for btn in self._preset_buttons:
            btn.setEnabled(not busy)
        for btn in self._apply_buttons:
            btn.setEnabled(not busy)

    def _copy_response(self) -> None:
        text = self._response_output.toPlainText()
        if text:
            QApplication.clipboard().setText(text)

    # -- Apply to editor / scene -----------------------------------------------

    def _get_response_text(self) -> str | None:
        text = self._response_output.toPlainText().strip()
        if not text or text == "Thinking..." or text.startswith("Error:"):
            return None
        return text

    def _notify_data_changed(self) -> None:
        if self._on_data_changed:
            self._on_data_changed()

    def _active_editor(self) -> object | None:
        if self._get_active_editor:
            return self._get_active_editor()
        return None

    def _apply_replace(self) -> None:
        text = self._get_response_text()
        if text is None:
            return

        editor = self._active_editor()
        if editor and hasattr(editor, "textCursor"):
            cursor = editor.textCursor()
            has_selection = cursor.hasSelection()
            what = "the selected text" if has_selection else "all text in the editor"
            answer = QMessageBox.question(
                self, "Replace",
                f"Replace {what} with the AI response?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
            if not has_selection:
                cursor.select(cursor.SelectionType.Document)
            cursor.insertText(text)
            editor.setTextCursor(cursor)
            self._notify_data_changed()
            return

        scene_id = self._get_auto_scene_id()
        if scene_id is not None:
            answer = QMessageBox.question(
                self, "Replace Scene Content",
                "Replace the entire scene content?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
            self._db.update_scene_content(scene_id, text)
            self._notify_data_changed()
            return

        QApplication.clipboard().setText(text)

    def _apply_insert(self) -> None:
        text = self._get_response_text()
        if text is None:
            return

        editor = self._active_editor()
        if editor and hasattr(editor, "textCursor"):
            answer = QMessageBox.question(
                self, "Insert Text",
                "Insert the AI response at the cursor position?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
            cursor = editor.textCursor()
            cursor.insertText(text)
            editor.setTextCursor(cursor)
            self._notify_data_changed()
            return

        QApplication.clipboard().setText(text)

    def _apply_append(self) -> None:
        text = self._get_response_text()
        if text is None:
            return

        editor = self._active_editor()
        if editor and hasattr(editor, "textCursor"):
            cursor = editor.textCursor()
            if cursor.hasSelection():
                end = max(cursor.position(), cursor.anchor())
                cursor.setPosition(end)
            else:
                cursor.movePosition(cursor.MoveOperation.End)
            cursor.insertText("\n\n" + text)
            editor.setTextCursor(cursor)
            self._notify_data_changed()
            return

        scene_id = self._get_auto_scene_id()
        if scene_id is not None:
            scene = self._db.get_scene_by_id(scene_id)
            if scene is not None:
                existing = scene.content or ""
                new_content = (existing + "\n\n" + text) if existing else text
                self._db.update_scene_content(scene_id, new_content)
                self._notify_data_changed()
                return

        QApplication.clipboard().setText(text)

    # -- Overlay mode ----------------------------------------------------------

    overlay_toggled = Signal(bool)

    def _toggle_overlay(self) -> None:
        self._overlay_mode = not self._overlay_mode
        self.overlay_toggled.emit(self._overlay_mode)
        self.refresh_style()

    def is_overlay(self) -> bool:
        return self._overlay_mode

    # -- Contextual dimming ----------------------------------------------------

    def dim_for_typing(self) -> None:
        if not self._typing_dimmed:
            self._typing_dimmed = True
            self.setWindowOpacity(0.7) if self._overlay_mode else None
            self.setStyleSheet(self._build_style(dimmed=True))

    def undim(self) -> None:
        if self._typing_dimmed:
            self._typing_dimmed = False
            self.setWindowOpacity(1.0) if self._overlay_mode else None
            self.setStyleSheet(self._build_style(dimmed=False))

    def refresh_style(self) -> None:
        self.setStyleSheet(self._build_style(dimmed=self._typing_dimmed))

    def _build_style(self, dimmed: bool = False) -> str:
        opacity_rule = "opacity: 0.65;" if dimmed and not self._overlay_mode else ""
        if self._overlay_mode:
            return (
                f"#assistantPanel {{"
                f"  border-left: none;"
                f"  border: 1px solid {theme.BORDER};"
                f"  border-radius: 10px;"
                f"  background-color: {theme.BG_PANEL};"
                f"  {opacity_rule}"
                f"}}"
            )
        return (
            f"#assistantPanel {{"
            f"  border-left: 1px solid {theme.BORDER};"
            f"  background-color: {theme.BG_PANEL};"
            f"  {opacity_rule}"
            f"}}"
        )
