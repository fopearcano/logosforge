"""Global assistant side panel — compact AI writing assistant."""

from collections.abc import Callable

from PySide6.QtCore import QThread, QTimer, Signal, Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMenu,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from storyplanner.assistant import (
    PRESET_ACTIONS,
    build_messages,
    chat_completion,
)
from storyplanner.context_builder import (
    gather_graph_context,
    gather_outline_context,
    gather_psyke_context,
    gather_scene_context,
    gather_story_memory,
)
from storyplanner.db import Database
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
from storyplanner.ui import theme
from storyplanner.ui.provider_settings import ProviderSettingsWidget


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


class AssistantPanel(QWidget):
    """Compact AI writing assistant — docks as a right-side panel."""

    panel_closed = Signal()

    def __init__(
        self,
        db: Database,
        project_id: int,
        on_data_changed: Callable[[], None] | None = None,
        on_open_scene: Callable[[int], None] | None = None,
    ) -> None:
        super().__init__()
        self._db = db
        self._project_id = project_id
        self._on_data_changed = on_data_changed
        self._on_open_scene = on_open_scene
        self._worker: _AssistantWorker | None = None
        self._pending_messages: list[dict] | None = None

        self._debounce_timer = QTimer()
        self._debounce_timer.setSingleShot(True)
        self._debounce_timer.setInterval(120)
        self._debounce_timer.timeout.connect(self._fire_request)

        self._overlay_mode = False
        self._typing_dimmed = False

        self.setMinimumWidth(260)
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

        # Scene selector + Generate
        scene_row = QHBoxLayout()
        scene_row.setSpacing(4)
        self._scene_combo = QComboBox()
        scene_row.addWidget(self._scene_combo, stretch=1)
        self._send_btn = QPushButton("Generate")
        self._send_btn.setStyleSheet(theme.primary_btn())
        self._send_btn.clicked.connect(self._send_custom)
        scene_row.addWidget(self._send_btn)
        self._layout.addLayout(scene_row)

        # Core actions
        action_row = QHBoxLayout()
        action_row.setSpacing(4)
        self._preset_buttons: list[QPushButton] = []
        for action in ("Rewrite", "Expand", "Dialogue"):
            btn = QPushButton(action)
            btn.clicked.connect(
                lambda _, a=action: self._send_preset(a)
            )
            action_row.addWidget(btn)
            self._preset_buttons.append(btn)

        self._suggest_btn = QPushButton("Suggest Beats")
        self._suggest_btn.setToolTip(
            "Structured narrative direction suggestions"
        )
        self._suggest_btn.clicked.connect(self._on_suggest_beats)
        action_row.addWidget(self._suggest_btn)
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
        action_row.addWidget(self._more_btn)
        self._preset_buttons.append(self._more_btn)
        self._layout.addLayout(action_row)

        # Custom prompt
        self._prompt_input = QPlainTextEdit()
        self._prompt_input.setPlaceholderText(
            "Instructions or questions about the scene..."
        )
        self._prompt_input.setMaximumHeight(48)
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
        self._psyke_check = QCheckBox("Include Story Bible")
        settings_layout.addWidget(self._outline_check)
        settings_layout.addWidget(self._story_memory_check)
        settings_layout.addWidget(self._psyke_check)

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
        self._response_output.setStyleSheet(
            f"QPlainTextEdit {{"
            f"  background-color: {theme.BG_PANEL};"
            f"  color: {theme.TEXT_PRIMARY};"
            f"  border: 1px solid {theme.BORDER};"
            f"  border-radius: 4px; padding: 6px;"
            f"}}"
        )
        self._layout.addWidget(self._response_output, stretch=1)

        # Apply actions: Replace | Insert at Cursor | More▾
        apply_row = QHBoxLayout()
        apply_row.setSpacing(4)

        self._replace_content_btn = QPushButton("Replace")
        self._replace_content_btn.clicked.connect(
            self._apply_replace_content
        )
        apply_row.addWidget(self._replace_content_btn)

        self._insert_cursor_btn = QPushButton("Insert")
        self._insert_cursor_btn.clicked.connect(
            self._apply_insert_at_cursor
        )
        apply_row.addWidget(self._insert_cursor_btn)

        self._apply_more_btn = QPushButton("\u25be")
        self._apply_more_btn.setFixedWidth(28)
        apply_more_menu = QMenu(self)
        apply_more_menu.addAction("Append", self._apply_append_content)
        apply_more_menu.addAction("As Synopsis", self._apply_as_synopsis)
        apply_more_menu.addAction("As Summary", self._apply_as_summary)
        apply_more_menu.addSeparator()
        apply_more_menu.addAction("Copy", self._copy_response)
        self._apply_more_btn.setMenu(apply_more_menu)
        apply_row.addWidget(self._apply_more_btn)

        self._apply_buttons = [
            self._replace_content_btn,
            self._insert_cursor_btn,
            self._apply_more_btn,
        ]
        self._layout.addLayout(apply_row)

        self._load_scenes()

    # -- Settings toggle -------------------------------------------------------

    def _toggle_settings(self) -> None:
        visible = not self._settings_container.isVisible()
        self._settings_container.setVisible(visible)
        self._settings_btn.setText(
            "\u25bc Settings" if visible else "\u25b6 Settings"
        )

    def _on_ctx_toggle(self, checked: bool) -> None:
        self._ctx_viewer.setVisible(checked)

    # -- Scene loading ---------------------------------------------------------

    def _load_scenes(self) -> None:
        self._scene_combo.clear()
        scenes = self._db.get_all_scenes(self._project_id)
        for scene in scenes:
            label = scene.title
            if scene.chapter:
                label = f"[{scene.chapter}] {label}"
            self._scene_combo.addItem(label, userData=scene.id)

    def set_active_scene(self, scene_id: int) -> None:
        for i in range(self._scene_combo.count()):
            if self._scene_combo.itemData(i) == scene_id:
                self._scene_combo.setCurrentIndex(i)
                return

    def refresh_scenes(self) -> None:
        current = self._scene_combo.currentData()
        self._load_scenes()
        if current is not None:
            self.set_active_scene(current)

    # -- Sending requests ------------------------------------------------------

    def _build_context(
        self, scene_id: int, action_key: str = "",
    ) -> tuple[str, str, str, str, str, str]:
        scene_ctx = gather_scene_context(
            self._db, self._project_id, scene_id,
        )
        outline_ctx = ""
        if self._outline_check.isChecked():
            outline_ctx = gather_outline_context(
                self._db, self._project_id,
            )
        story_memory_ctx = ""
        if self._story_memory_check.isChecked():
            story_memory_ctx = gather_story_memory(
                self._db, self._project_id,
            )
        psyke_ctx = ""
        orchestration_debug = ""
        if self._psyke_check.isChecked():
            if action_key:
                mode = resolve_mode(action_key)
                result = orchestrate_psyke_context(
                    self._db, self._project_id, scene_id, mode,
                )
                psyke_ctx = result.psyke_context
                orchestration_debug = format_orchestration_debug(result)
            else:
                psyke_ctx = gather_psyke_context(
                    self._db, self._project_id, scene_id,
                )
        graph_ctx = gather_graph_context(self._db, self._project_id, scene_id)
        return scene_ctx, outline_ctx, story_memory_ctx, psyke_ctx, orchestration_debug, graph_ctx

    def _send_preset(self, action_key: str) -> None:
        if self._worker is not None:
            return
        scene_id = self._scene_combo.currentData()
        if scene_id is None:
            self._response_output.setPlainText("No scene selected.")
            return

        scene_ctx, outline_ctx, story_memory_ctx, psyke_ctx, orch_debug, graph_ctx = (
            self._build_context(scene_id, action_key=action_key)
        )
        if not scene_ctx:
            self._response_output.setPlainText("Could not load scene data.")
            return

        user_note = self._prompt_input.toPlainText().strip()
        action_prompt = PRESET_ACTIONS[action_key]

        messages = build_messages(
            action_prompt, scene_ctx,
            outline_context=outline_ctx,
            story_memory_context=story_memory_ctx,
            psyke_context=psyke_ctx,
            graph_context=graph_ctx,
            user_note=user_note,
        )
        self._update_ctx_viewer(
            scene_ctx, outline_ctx, story_memory_ctx, psyke_ctx, action_prompt,
            orch_debug, graph_ctx,
        )
        self._start_request(messages)

    def _send_custom(self) -> None:
        if self._worker is not None:
            return
        prompt = self._prompt_input.toPlainText().strip()
        if not prompt:
            self._response_output.setPlainText("Enter a prompt first.")
            return

        scene_id = self._scene_combo.currentData()
        if scene_id is None:
            self._response_output.setPlainText("No scene selected.")
            return

        scene_ctx, outline_ctx, story_memory_ctx, psyke_ctx, orch_debug, graph_ctx = (
            self._build_context(scene_id)
        )
        if not scene_ctx:
            self._response_output.setPlainText("Could not load scene data.")
            return

        messages = build_messages(
            prompt, scene_ctx,
            outline_context=outline_ctx,
            story_memory_context=story_memory_ctx,
            psyke_context=psyke_ctx,
            graph_context=graph_ctx,
        )
        self._update_ctx_viewer(
            scene_ctx, outline_ctx, story_memory_ctx, psyke_ctx, prompt,
            orch_debug, graph_ctx,
        )
        self._start_request(messages)

    def _on_suggest_beats(self) -> None:
        if self._worker is not None:
            return
        scene_id = self._scene_combo.currentData()
        if scene_id is None:
            self._response_output.setPlainText("No scene selected.")
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
    ) -> None:
        parts = [f"--- Scene Context ---\n{scene_ctx}"]
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
        self._scene_combo.setEnabled(not busy)
        for btn in self._preset_buttons:
            btn.setEnabled(not busy)
        for btn in self._apply_buttons:
            btn.setEnabled(not busy)

    def _copy_response(self) -> None:
        text = self._response_output.toPlainText()
        if text:
            QApplication.clipboard().setText(text)

    # -- Apply to scene --------------------------------------------------------

    def _get_response_text(self) -> str | None:
        text = self._response_output.toPlainText().strip()
        if not text or text == "Thinking..." or text.startswith("Error:"):
            return None
        return text

    def _get_selected_scene_id(self) -> int | None:
        return self._scene_combo.currentData()

    def _notify_data_changed(self) -> None:
        if self._on_data_changed:
            self._on_data_changed()

    def _apply_replace_content(self) -> None:
        text = self._get_response_text()
        scene_id = self._get_selected_scene_id()
        if text is None or scene_id is None:
            return

        answer = QMessageBox.question(
            self,
            "Replace Content",
            "This will replace the entire scene content.\n\n"
            "Are you sure?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return

        self._db.update_scene_content(scene_id, text)
        self._notify_data_changed()

    def _apply_append_content(self) -> None:
        text = self._get_response_text()
        scene_id = self._get_selected_scene_id()
        if text is None or scene_id is None:
            return

        scene = self._db.get_scene_by_id(scene_id)
        if scene is None:
            return

        existing = scene.content or ""
        if existing:
            new_content = existing + "\n\n" + text
        else:
            new_content = text

        self._db.update_scene_content(scene_id, new_content)
        self._notify_data_changed()

    def _apply_as_synopsis(self) -> None:
        text = self._get_response_text()
        scene_id = self._get_selected_scene_id()
        if text is None or scene_id is None:
            return

        scene = self._db.get_scene_by_id(scene_id)
        if scene and scene.synopsis:
            answer = QMessageBox.question(
                self,
                "Replace Synopsis",
                "This will replace the existing synopsis.\n\n"
                "Are you sure?",
                QMessageBox.StandardButton.Yes
                | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                return

        self._db.update_scene_synopsis(scene_id, text)
        self._notify_data_changed()

    def _apply_as_summary(self) -> None:
        text = self._get_response_text()
        scene_id = self._get_selected_scene_id()
        if text is None or scene_id is None:
            return

        scene = self._db.get_scene_by_id(scene_id)
        if scene and scene.summary:
            answer = QMessageBox.question(
                self,
                "Replace Summary",
                "This will replace the existing summary.\n\n"
                "Are you sure?",
                QMessageBox.StandardButton.Yes
                | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                return

        self._db.update_scene_summary(scene_id, text)
        self._notify_data_changed()

    def _apply_insert_at_cursor(self) -> None:
        text = self._get_response_text()
        scene_id = self._get_selected_scene_id()
        if text is None or scene_id is None:
            return

        QApplication.clipboard().setText(text)
        QMessageBox.information(
            self,
            "Insert at Cursor",
            "Text copied to clipboard.\n\n"
            "Position your cursor in the scene editor and paste (Ctrl+V).",
        )
        if self._on_open_scene:
            self._on_open_scene(scene_id)

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
