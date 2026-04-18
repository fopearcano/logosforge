"""Inline AI assistant panel embedded in the scene editor."""

from collections.abc import Callable

from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from storyplanner.assistant import (
    DEFAULT_BASE_URL,
    build_messages,
    chat_completion,
)
from storyplanner.context_builder import gather_scene_context
from storyplanner.db import Database


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
        self._db = db
        self._project_id = project_id
        self._get_scene_id = get_scene_id
        self._on_data_changed = on_data_changed
        self._worker: _Worker | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 8, 0, 0)

        header = QLabel("AI Assist")
        header.setStyleSheet("font-weight: bold; color: #9aa0a6;")
        layout.addWidget(header)

        # Selection actions
        sel_row = QHBoxLayout()
        self._rewrite_btn = QPushButton("Rewrite Selection")
        self._rewrite_btn.clicked.connect(self._on_rewrite_selection)
        sel_row.addWidget(self._rewrite_btn)

        self._expand_btn = QPushButton("Expand Selection")
        self._expand_btn.clicked.connect(self._on_expand_selection)
        sel_row.addWidget(self._expand_btn)
        sel_row.addStretch()
        layout.addLayout(sel_row)

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

        # Response
        self._response = QPlainTextEdit()
        self._response.setReadOnly(True)
        self._response.setMaximumHeight(200)
        self._response.setPlaceholderText("Response...")
        self._response.setStyleSheet(
            "QPlainTextEdit {"
            "  background-color: #12151a;"
            "  color: #d4d4d4;"
            "  border: 1px solid #2a2f36;"
            "  border-radius: 4px;"
            "  padding: 8px;"
            "}"
        )
        layout.addWidget(self._response)

        # Apply actions
        action_row = QHBoxLayout()
        self._insert_btn = QPushButton("Insert at Cursor")
        self._insert_btn.clicked.connect(self._insert_at_cursor)
        action_row.addWidget(self._insert_btn)

        self._copy_btn = QPushButton("Copy")
        self._copy_btn.clicked.connect(self._copy_response)
        action_row.addWidget(self._copy_btn)
        action_row.addStretch()
        layout.addLayout(action_row)

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
        settings_row.addStretch()
        layout.addLayout(settings_row)

        self._interactive_buttons = [
            self._rewrite_btn, self._expand_btn,
            self._send_btn, self._preview_btn, self._insert_btn,
        ]

    # -- Scene context -------------------------------------------------------

    def _get_scene_context(self) -> str:
        scene_id = self._get_scene_id()
        if scene_id is None:
            return ""
        return gather_scene_context(self._db, self._project_id, scene_id)

    # -- Selection actions ---------------------------------------------------

    def _get_selection(self) -> str:
        return self._editor.textCursor().selectedText().replace("\u2029", "\n")

    def _on_rewrite_selection(self) -> None:
        selected = self._get_selection()
        if not selected.strip():
            self._response.setPlainText("Select text in the editor first.")
            return
        prompt = (
            "Rewrite the following text, improving clarity, flow, and "
            "prose quality while preserving the original meaning.\n\n"
            f"Text to rewrite:\n{selected}"
        )
        self._send_request(prompt)

    def _on_expand_selection(self) -> None:
        selected = self._get_selection()
        if not selected.strip():
            self._response.setPlainText("Select text in the editor first.")
            return
        prompt = (
            "Expand the following text with more detail, sensory "
            "description, and emotional depth.\n\n"
            f"Text to expand:\n{selected}"
        )
        self._send_request(prompt)

    def _on_send(self) -> None:
        prompt = self._prompt.toPlainText().strip()
        if not prompt:
            self._response.setPlainText("Enter a prompt first.")
            return
        self._send_request(prompt)

    def _on_preview(self) -> None:
        scene_ctx = self._get_scene_context()
        if not scene_ctx:
            self._response.setPlainText("No scene selected.")
            return
        self._response.setPlainText(
            "=== Context sent to the model ===\n\n" + scene_ctx
        )

    # -- LM Studio communication ---------------------------------------------

    def _send_request(self, action_prompt: str) -> None:
        if self._worker is not None:
            return
        scene_ctx = self._get_scene_context()
        if not scene_ctx:
            self._response.setPlainText("No scene selected.")
            return

        messages = build_messages(action_prompt, scene_ctx)
        self._set_busy(True)
        self._response.setPlainText("Thinking...")

        base_url = self._url.text().strip() or DEFAULT_BASE_URL
        model = self._model_input.text().strip()

        self._worker = _Worker(messages, base_url, model)
        self._worker.completed.connect(self._on_completed)
        self._worker.failed.connect(self._on_failed)
        self._worker.start()

    def _on_completed(self, text: str) -> None:
        self._response.setPlainText(text)
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
        if text.startswith("=== Context sent to the model ==="):
            return None
        return text

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

        scene_id = self._get_scene_id()
        if scene_id is not None:
            self._db.update_scene_content(scene_id, self._editor.toPlainText())
            if self._on_data_changed:
                self._on_data_changed()

    def _copy_response(self) -> None:
        text = self._get_response_text()
        if text:
            QApplication.clipboard().setText(text)
