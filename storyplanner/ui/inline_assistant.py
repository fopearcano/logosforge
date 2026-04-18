"""Inline AI assistant panel embedded in the scene editor."""

from collections.abc import Callable

from PySide6.QtCore import QEvent, QThread, Signal
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from storyplanner.assistant import (
    DEFAULT_BASE_URL,
    PRESET_ACTIONS,
    build_messages,
    chat_completion,
)
from storyplanner.context_builder import gather_scene_context
from storyplanner.db import Database
from storyplanner.prompt_router import route_prompt

SELECTION_ACTIONS = {
    "Rewrite": (
        "Rewrite the following text, improving clarity, flow, and "
        "prose quality while preserving the original meaning."
    ),
    "Expand": (
        "Expand the following text with more detail, sensory "
        "description, and emotional depth."
    ),
    "Tighten": (
        "Tighten the following text. Remove unnecessary words, "
        "cut filler, and make every sentence count. Preserve meaning."
    ),
    "Dialogue": (
        "Improve the dialogue in the following text. Make it more "
        "natural, concise, and character-appropriate. Sharpen subtext."
    ),
    "Tension": (
        "Rewrite the following text to increase tension. Heighten "
        "conflict, add urgency, and raise emotional pressure."
    ),
}

SLASH_COMMANDS: dict[str, tuple[str, str]] = {
    "/rewrite": ("selection", "Rewrite"),
    "/expand": ("selection", "Expand"),
    "/tighten": ("selection", "Tighten"),
    "/dialogue": ("selection", "Dialogue"),
    "/tension": ("selection", "Tension"),
    "/summarize": ("scene", "Summarize"),
}


_ORIGINAL_STYLE = (
    "QPlainTextEdit {"
    "  background-color: #1a1215;"
    "  color: #d4a0a0;"
    "  border: 1px solid #3a2020;"
    "  border-radius: 4px;"
    "  padding: 8px;"
    "}"
)

_PROPOSED_STYLE = (
    "QPlainTextEdit {"
    "  background-color: #121a15;"
    "  color: #a0d4a0;"
    "  border: 1px solid #203a20;"
    "  border-radius: 4px;"
    "  padding: 8px;"
    "}"
)

_RESPONSE_STYLE = (
    "QPlainTextEdit {"
    "  background-color: #12151a;"
    "  color: #d4d4d4;"
    "  border: 1px solid #2a2f36;"
    "  border-radius: 4px;"
    "  padding: 8px;"
    "}"
)

SESSION_MEMORY_LIMIT = 3
SESSION_OUTPUT_PREVIEW_MAX = 100


class _Worker(QThread):
    completed = Signal(str)
    failed = Signal(str)

    def __init__(self, messages: list[dict], base_url: str, model: str) -> None:
        super().__init__()
        self._messages = messages
        self._base_url = base_url
        self._model = model

    def run(self) -> None:
        try:
            result = chat_completion(self._messages, self._base_url, self._model)
            self.completed.emit(result)
        except Exception as e:
            self.failed.emit(str(e))


class InlineAssistantPanel(QWidget):
    def __init__(
        self,
        content_editor: QPlainTextEdit,
        db: Database,
        project_id: int,
        get_scene_id: Callable[[], int | None],
        on_data_changed: Callable[[], None] | None = None,
    ) -> None:
        super().__init__()
        self._editor = content_editor
        self._editor.installEventFilter(self)
        self._db = db
        self._project_id = project_id
        self._get_scene_id = get_scene_id
        self._on_data_changed = on_data_changed
        self._worker: _Worker | None = None

        self._session_memory: list[dict] = []
        self._pending_action: str = ""

        self._sel_start: int | None = None
        self._sel_end: int | None = None
        self._sel_text: str | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 8, 0, 0)

        header = QLabel("AI Assist")
        header.setStyleSheet("font-weight: bold; color: #9aa0a6;")
        layout.addWidget(header)

        # Selection action row
        sel_row = QHBoxLayout()
        sel_row.addWidget(QLabel("Selection:"))
        self._sel_action_combo = QComboBox()
        for label in SELECTION_ACTIONS:
            self._sel_action_combo.addItem(label)
        sel_row.addWidget(self._sel_action_combo, stretch=1)
        self._sel_run_btn = QPushButton("Run on Selection")
        self._sel_run_btn.clicked.connect(self._on_run_selection_action)
        sel_row.addWidget(self._sel_run_btn)
        layout.addLayout(sel_row)

        # Template actions (whole scene)
        tpl_row = QHBoxLayout()
        tpl_row.addWidget(QLabel("Template:"))
        self._template_combo = QComboBox()
        for label in PRESET_ACTIONS:
            self._template_combo.addItem(label)
        tpl_row.addWidget(self._template_combo, stretch=1)
        self._run_template_btn = QPushButton("Run")
        self._run_template_btn.clicked.connect(self._on_run_template)
        tpl_row.addWidget(self._run_template_btn)
        layout.addLayout(tpl_row)

        # Prompt input
        self._prompt = QPlainTextEdit()
        self._prompt.setMaximumHeight(60)
        self._prompt.setPlaceholderText("Ask about this scene...")
        layout.addWidget(self._prompt)

        prompt_row = QHBoxLayout()
        prompt_row.addStretch()
        self._preview_btn = QPushButton("Preview")
        self._preview_btn.clicked.connect(self._on_preview)
        prompt_row.addWidget(self._preview_btn)
        self._send_btn = QPushButton("Send")
        self._send_btn.clicked.connect(self._on_send)
        prompt_row.addWidget(self._send_btn)
        layout.addLayout(prompt_row)

        # -- Response container (normal view) --------------------------------
        self._response_container = QWidget()
        rc_layout = QVBoxLayout(self._response_container)
        rc_layout.setContentsMargins(0, 0, 0, 0)

        self._response = QPlainTextEdit()
        self._response.setReadOnly(True)
        self._response.setMaximumHeight(200)
        self._response.setPlaceholderText("Response...")
        self._response.setStyleSheet(_RESPONSE_STYLE)
        rc_layout.addWidget(self._response)

        action_row = QHBoxLayout()
        self._replace_btn = QPushButton("Replace Selection")
        self._replace_btn.clicked.connect(self._replace_selection)
        action_row.addWidget(self._replace_btn)

        self._insert_btn = QPushButton("Insert at Cursor")
        self._insert_btn.clicked.connect(self._insert_at_cursor)
        action_row.addWidget(self._insert_btn)

        self._compare_btn = QPushButton("Compare")
        self._compare_btn.clicked.connect(self._show_diff)
        action_row.addWidget(self._compare_btn)

        self._copy_btn = QPushButton("Copy")
        self._copy_btn.clicked.connect(self._copy_response)
        action_row.addWidget(self._copy_btn)
        action_row.addStretch()
        rc_layout.addLayout(action_row)

        layout.addWidget(self._response_container)

        # -- Diff container (hidden by default) ------------------------------
        self._diff_container = QWidget()
        dc_layout = QVBoxLayout(self._diff_container)
        dc_layout.setContentsMargins(0, 0, 0, 0)

        orig_label = QLabel("Original")
        orig_label.setStyleSheet("font-weight: bold; color: #d4a0a0;")
        dc_layout.addWidget(orig_label)

        self._diff_original = QPlainTextEdit()
        self._diff_original.setReadOnly(True)
        self._diff_original.setMaximumHeight(140)
        self._diff_original.setStyleSheet(_ORIGINAL_STYLE)
        dc_layout.addWidget(self._diff_original)

        prop_label = QLabel("Proposed")
        prop_label.setStyleSheet("font-weight: bold; color: #a0d4a0;")
        dc_layout.addWidget(prop_label)

        self._diff_proposed = QPlainTextEdit()
        self._diff_proposed.setReadOnly(True)
        self._diff_proposed.setMaximumHeight(140)
        self._diff_proposed.setStyleSheet(_PROPOSED_STYLE)
        dc_layout.addWidget(self._diff_proposed)

        diff_action_row = QHBoxLayout()
        diff_replace_btn = QPushButton("Replace Selection")
        diff_replace_btn.clicked.connect(self._replace_selection)
        diff_action_row.addWidget(diff_replace_btn)

        diff_insert_btn = QPushButton("Insert at Cursor")
        diff_insert_btn.clicked.connect(self._insert_at_cursor)
        diff_action_row.addWidget(diff_insert_btn)

        diff_close_btn = QPushButton("Close")
        diff_close_btn.clicked.connect(self._close_diff)
        diff_action_row.addWidget(diff_close_btn)
        diff_action_row.addStretch()
        dc_layout.addLayout(diff_action_row)

        layout.addWidget(self._diff_container)
        self._diff_container.hide()

        # Settings (compact)
        settings_row = QHBoxLayout()
        settings_row.addWidget(QLabel("URL:"))
        self._url = QLineEdit()
        self._url.setText(DEFAULT_BASE_URL)
        self._url.setMaximumWidth(250)
        settings_row.addWidget(self._url)
        settings_row.addWidget(QLabel("Model:"))
        self._model_input = QLineEdit()
        self._model_input.setPlaceholderText("default")
        self._model_input.setMaximumWidth(150)
        settings_row.addWidget(self._model_input)
        self._clear_memory_btn = QPushButton("Clear Memory")
        self._clear_memory_btn.clicked.connect(self._clear_session_memory)
        settings_row.addWidget(self._clear_memory_btn)
        settings_row.addStretch()
        layout.addLayout(settings_row)

        self._interactive_buttons = [
            self._sel_run_btn, self._run_template_btn,
            self._send_btn, self._preview_btn,
            self._replace_btn, self._insert_btn, self._compare_btn,
        ]

    # -- Scene context -------------------------------------------------------

    def _get_scene_context(self) -> str:
        scene_id = self._get_scene_id()
        if scene_id is None:
            return ""
        return gather_scene_context(self._db, self._project_id, scene_id)

    # -- Session memory -------------------------------------------------------

    def _record_session_entry(self, action: str, output: str) -> None:
        preview = output[:SESSION_OUTPUT_PREVIEW_MAX]
        if len(output) > SESSION_OUTPUT_PREVIEW_MAX:
            preview += "..."
        self._session_memory.append({"action": action, "output": preview})
        if len(self._session_memory) > SESSION_MEMORY_LIMIT:
            self._session_memory = self._session_memory[-SESSION_MEMORY_LIMIT:]

    def _build_session_memory_context(self) -> str:
        if not self._session_memory:
            return ""
        lines = ["[Session Memory]"]
        for i, entry in enumerate(self._session_memory, 1):
            lines.append(f"{i}. Action: {entry['action']}")
            lines.append(f"   Output: {entry['output']}")
        return "\n".join(lines)

    def _clear_session_memory(self) -> None:
        self._session_memory.clear()
        self._response.setPlainText("Session memory cleared.")

    # -- Slash commands -------------------------------------------------------

    def eventFilter(self, obj, event):  # noqa: N802
        if obj is not self._editor:
            return super().eventFilter(obj, event)
        if event.type() != QEvent.Type.KeyPress:
            return super().eventFilter(obj, event)

        from PySide6.QtCore import Qt
        if event.key() not in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            return super().eventFilter(obj, event)

        cursor = self._editor.textCursor()
        cursor.select(cursor.SelectionType.LineUnderCursor)
        line = cursor.selectedText().strip().lower()

        if line not in SLASH_COMMANDS:
            return super().eventFilter(obj, event)

        cursor.removeSelectedText()
        doc = self._editor.toPlainText()
        new_cursor = self._editor.textCursor()
        pos = new_cursor.position()
        if pos > 0 and pos <= len(doc) and doc[pos - 1:pos] == "\n":
            new_cursor.deletePreviousChar()

        self._handle_slash_command(line)
        return True

    def _handle_slash_command(self, command: str) -> None:
        mode, key = SLASH_COMMANDS[command]

        if mode == "scene":
            prompt = PRESET_ACTIONS.get(key, "")
            if prompt:
                self._send_request(prompt)
            return

        instruction = SELECTION_ACTIONS.get(key, "")
        if not instruction:
            return

        cursor = self._editor.textCursor()
        selected = cursor.selectedText().replace("\u2029", "\n").strip()
        if selected:
            self._sel_start = cursor.selectionStart()
            self._sel_end = cursor.selectionEnd()
            self._sel_text = selected
            target_text = selected
        else:
            target_text = self._extract_preceding_paragraph()
            if not target_text:
                self._response.setPlainText(
                    "No text selected and no paragraph found above."
                )
                return
            self._sel_text = target_text
            self._sel_start = None
            self._sel_end = None

        prompt = f"{instruction}\n\nText:\n{target_text}"
        self._send_request(prompt)

    def _extract_preceding_paragraph(self) -> str:
        doc = self._editor.toPlainText()
        cursor = self._editor.textCursor()
        pos = cursor.position()
        text_before = doc[:pos].rstrip()
        if not text_before:
            return ""
        paragraphs = text_before.split("\n\n")
        last = paragraphs[-1].strip()
        return last

    # -- Selection snapshot ---------------------------------------------------

    def _snapshot_selection(self) -> str | None:
        cursor = self._editor.textCursor()
        text = cursor.selectedText().replace("\u2029", "\n")
        if not text.strip():
            self._response.setPlainText("Select text in the editor first.")
            self._sel_start = None
            self._sel_end = None
            self._sel_text = None
            return None
        self._sel_start = cursor.selectionStart()
        self._sel_end = cursor.selectionEnd()
        self._sel_text = text
        return text

    def _verify_selection(self) -> bool:
        if self._sel_start is None or self._sel_text is None:
            self._response.setPlainText(
                "No original selection recorded. "
                "Run a selection action first."
            )
            return False
        doc = self._editor.toPlainText()
        current = doc[self._sel_start:self._sel_end]
        if current != self._sel_text:
            self._response.setPlainText(
                "The original selection has changed or moved.\n"
                "Cannot replace safely.\n\n"
                "Use 'Insert at Cursor' or 'Copy' instead."
            )
            return False
        return True

    # -- Diff view -----------------------------------------------------------

    def _show_diff(self) -> None:
        proposed = self._get_response_text()
        if proposed is None:
            return
        if self._sel_text is None:
            self._response.setPlainText(
                "No original selection recorded. "
                "Run a selection action first to compare."
            )
            return

        self._diff_original.setPlainText(self._sel_text)
        self._diff_proposed.setPlainText(proposed)
        self._response_container.hide()
        self._diff_container.show()

    def _close_diff(self) -> None:
        self._diff_container.hide()
        self._response_container.show()

    # -- Selection actions ---------------------------------------------------

    def _on_run_selection_action(self) -> None:
        selected = self._snapshot_selection()
        if selected is None:
            return
        key = self._sel_action_combo.currentText()
        instruction = SELECTION_ACTIONS.get(key, "")
        if not instruction:
            return
        prompt = f"{instruction}\n\nText:\n{selected}"
        self._send_request(prompt)

    # -- Template actions (whole scene) --------------------------------------

    def _on_run_template(self) -> None:
        key = self._template_combo.currentText()
        prompt = PRESET_ACTIONS.get(key, "")
        if not prompt:
            return
        self._send_request(prompt)

    def _on_send(self) -> None:
        prompt = self._prompt.toPlainText().strip()
        if not prompt:
            self._response.setPlainText("Enter a prompt first.")
            return
        template_name, action_prompt = route_prompt(prompt)
        self._send_request(action_prompt, routed_to=template_name)

    def _on_preview(self) -> None:
        scene_ctx = self._get_scene_context()
        if not scene_ctx:
            self._response.setPlainText("No scene selected.")
            return
        self._response.setPlainText(
            "=== Context sent to the model ===\n\n" + scene_ctx
        )

    # -- LM Studio communication ---------------------------------------------

    def _send_request(
        self, action_prompt: str, routed_to: str = "",
    ) -> None:
        if self._worker is not None:
            return
        scene_ctx = self._get_scene_context()
        if not scene_ctx:
            self._response.setPlainText("No scene selected.")
            return

        self._close_diff()
        self._pending_action = action_prompt.split("\n")[0][:80]

        session_ctx = self._build_session_memory_context()
        messages = build_messages(
            action_prompt, scene_ctx, story_memory_context=session_ctx,
        )
        self._set_busy(True)
        if routed_to:
            self._response.setPlainText(
                f"Routed \u2192 {routed_to} | Thinking..."
            )
        else:
            self._response.setPlainText("Thinking...")

        base_url = self._url.text().strip() or DEFAULT_BASE_URL
        model = self._model_input.text().strip()

        self._worker = _Worker(messages, base_url, model)
        self._worker.completed.connect(self._on_completed)
        self._worker.failed.connect(self._on_failed)
        self._worker.start()

    def _on_completed(self, text: str) -> None:
        self._response.setPlainText(text)
        if self._pending_action:
            self._record_session_entry(self._pending_action, text)
            self._pending_action = ""
        self._set_busy(False)
        self._worker = None

    def _on_failed(self, error: str) -> None:
        self._response.setPlainText(f"Error:\n\n{error}")
        self._set_busy(False)
        self._worker = None

    def _set_busy(self, busy: bool) -> None:
        for btn in self._interactive_buttons:
            btn.setEnabled(not busy)

    # -- Apply actions -------------------------------------------------------

    def _get_response_text(self) -> str | None:
        text = self._response.toPlainText().strip()
        if not text or text == "Thinking..." or text.startswith("Error:"):
            return None
        if text.startswith("Routed \u2192"):
            return None
        if text.startswith("=== Context sent to the model ==="):
            return None
        if text.startswith("The original selection has changed"):
            return None
        if text.startswith("No original selection recorded"):
            return None
        if text.startswith("Select text in the editor first"):
            return None
        if text == "Session memory cleared.":
            return None
        return text

    def _replace_selection(self) -> None:
        text = self._get_response_text()
        if text is None:
            return
        if not self._verify_selection():
            self._close_diff()
            return

        answer = QMessageBox.question(
            self,
            "Replace Selection",
            "Replace the selected text with the assistant's output?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return

        cursor = self._editor.textCursor()
        cursor.setPosition(self._sel_start)
        cursor.setPosition(self._sel_end, cursor.MoveMode.KeepAnchor)
        cursor.insertText(text)
        self._editor.setTextCursor(cursor)
        self._editor.setFocus()

        self._sel_start = None
        self._sel_end = None
        self._sel_text = None

        self._close_diff()
        self._save_content()

    def _insert_at_cursor(self) -> None:
        text = self._get_response_text()
        if text is None:
            return

        cursor = self._editor.textCursor()
        pos = cursor.position()
        doc = self._editor.toPlainText()

        insert = text
        if pos > 0 and not doc[pos - 1].isspace():
            insert = "\n\n" + insert
        if pos < len(doc) and not doc[pos].isspace():
            insert = insert + "\n\n"

        cursor.insertText(insert)
        self._editor.setTextCursor(cursor)
        self._editor.setFocus()

        self._close_diff()
        self._save_content()

    def _copy_response(self) -> None:
        text = self._get_response_text()
        if text:
            QApplication.clipboard().setText(text)

    def _save_content(self) -> None:
        scene_id = self._get_scene_id()
        if scene_id is not None:
            self._db.update_scene_content(scene_id, self._editor.toPlainText())
            if self._on_data_changed:
                self._on_data_changed()
