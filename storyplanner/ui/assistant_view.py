"""Writing Assistant view — local LM Studio integration for scene writing help."""

from collections.abc import Callable

from PySide6.QtCore import QThread, Signal, Qt
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
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
    build_outline_context,
    build_scene_context,
    chat_completion,
)
from storyplanner.db import Database


class _AssistantWorker(QThread):
    completed = Signal(str)
    failed = Signal(str)

    def __init__(
        self, messages: list[dict], base_url: str, model: str,
    ) -> None:
        super().__init__()
        self._messages = messages
        self._base_url = base_url
        self._model = model

    def run(self) -> None:
        try:
            result = chat_completion(
                self._messages, self._base_url, self._model,
            )
            self.completed.emit(result)
        except Exception as e:
            self.failed.emit(str(e))


class AssistantView(QWidget):
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

        layout = QVBoxLayout(self)

        layout.addWidget(QLabel("Writing Assistant"))

        # Scene selector
        scene_row = QHBoxLayout()
        scene_row.addWidget(QLabel("Scene:"))
        self._scene_combo = QComboBox()
        scene_row.addWidget(self._scene_combo, stretch=1)
        layout.addLayout(scene_row)

        # Quick action buttons
        actions_label = QLabel("Quick Actions")
        actions_label.setStyleSheet("color: #9aa0a6; margin-top: 6px;")
        layout.addWidget(actions_label)

        self._preset_buttons: list[QPushButton] = []

        btn_row1 = QHBoxLayout()
        for key in ("Rewrite", "Expand", "Summarize", "Alternatives"):
            btn = QPushButton(key)
            btn.clicked.connect(lambda checked, k=key: self._send_preset(k))
            btn_row1.addWidget(btn)
            self._preset_buttons.append(btn)
        layout.addLayout(btn_row1)

        btn_row2 = QHBoxLayout()
        for key in ("Dialogue", "Pacing", "Next Beat"):
            btn = QPushButton(key)
            btn.clicked.connect(lambda checked, k=key: self._send_preset(k))
            btn_row2.addWidget(btn)
            self._preset_buttons.append(btn)
        btn_row2.addStretch()
        layout.addLayout(btn_row2)

        # Include outline checkbox
        self._outline_check = QCheckBox("Include story outline as context")
        layout.addWidget(self._outline_check)

        # Custom prompt
        layout.addWidget(QLabel("Additional instructions"))
        self._prompt_input = QPlainTextEdit()
        self._prompt_input.setMaximumHeight(80)
        self._prompt_input.setPlaceholderText(
            "Add specific instructions or ask a question about the scene..."
        )
        layout.addWidget(self._prompt_input)

        send_row = QHBoxLayout()
        send_row.addStretch()
        self._send_btn = QPushButton("Send Custom Prompt")
        self._send_btn.clicked.connect(self._send_custom)
        send_row.addWidget(self._send_btn)
        layout.addLayout(send_row)

        # Response area
        response_label = QLabel("Response")
        response_label.setStyleSheet("color: #9aa0a6; margin-top: 6px;")
        layout.addWidget(response_label)

        self._response_output = QPlainTextEdit()
        self._response_output.setReadOnly(True)
        self._response_output.setPlaceholderText(
            "Assistant response will appear here..."
        )
        self._response_output.setStyleSheet(
            "QPlainTextEdit {"
            "  background-color: #12151a;"
            "  color: #d4d4d4;"
            "  border: 1px solid #2a2f36;"
            "  border-radius: 4px;"
            "  padding: 12px;"
            "}"
        )
        layout.addWidget(self._response_output, stretch=1)

        # Apply actions
        apply_label = QLabel("Apply to Scene")
        apply_label.setStyleSheet("color: #9aa0a6; margin-top: 6px;")
        layout.addWidget(apply_label)

        apply_row = QHBoxLayout()
        self._replace_content_btn = QPushButton("Replace Content")
        self._replace_content_btn.clicked.connect(self._apply_replace_content)
        apply_row.addWidget(self._replace_content_btn)

        self._append_content_btn = QPushButton("Append to Content")
        self._append_content_btn.clicked.connect(self._apply_append_content)
        apply_row.addWidget(self._append_content_btn)

        self._as_synopsis_btn = QPushButton("As Synopsis")
        self._as_synopsis_btn.clicked.connect(self._apply_as_synopsis)
        apply_row.addWidget(self._as_synopsis_btn)

        self._as_summary_btn = QPushButton("As Summary")
        self._as_summary_btn.clicked.connect(self._apply_as_summary)
        apply_row.addWidget(self._as_summary_btn)

        self._insert_cursor_btn = QPushButton("Insert at Cursor")
        self._insert_cursor_btn.clicked.connect(self._apply_insert_at_cursor)
        apply_row.addWidget(self._insert_cursor_btn)
        layout.addLayout(apply_row)

        self._apply_buttons = [
            self._replace_content_btn,
            self._append_content_btn,
            self._as_synopsis_btn,
            self._as_summary_btn,
            self._insert_cursor_btn,
        ]

        copy_row = QHBoxLayout()
        copy_row.addStretch()
        self._copy_btn = QPushButton("Copy Response")
        self._copy_btn.clicked.connect(self._copy_response)
        copy_row.addWidget(self._copy_btn)
        layout.addLayout(copy_row)

        # Settings
        settings_label = QLabel("Settings")
        settings_label.setStyleSheet("color: #6b7280; margin-top: 8px;")
        layout.addWidget(settings_label)

        url_row = QHBoxLayout()
        url_row.addWidget(QLabel("LM Studio URL:"))
        self._url_input = QLineEdit()
        self._url_input.setText(DEFAULT_BASE_URL)
        url_row.addWidget(self._url_input)
        layout.addLayout(url_row)

        model_row = QHBoxLayout()
        model_row.addWidget(QLabel("Model:"))
        self._model_input = QLineEdit()
        self._model_input.setPlaceholderText("leave empty for default")
        model_row.addWidget(self._model_input)
        layout.addLayout(model_row)

        self._load_scenes()

    # -- Data loading --------------------------------------------------------

    def _load_scenes(self) -> None:
        self._scene_combo.clear()
        scenes = self._db.get_all_scenes(self._project_id)
        for scene in scenes:
            label = scene.title
            if scene.chapter:
                label = f"[{scene.chapter}] {label}"
            self._scene_combo.addItem(label, userData=scene.id)

    def _gather_scene_data(self, scene_id: int) -> dict:
        scene = self._db.get_scene_by_id(scene_id)
        if scene is None:
            return {}

        char_map = {
            c.id: c for c in self._db.get_all_characters(self._project_id)
        }
        place_map = {
            p.id: p for p in self._db.get_all_places(self._project_id)
        }

        char_ids = self._db.get_scene_character_ids(scene_id)
        place_ids = self._db.get_scene_place_ids(scene_id)
        states = self._db.get_scene_character_states(scene_id)

        return {
            "title": scene.title,
            "summary": scene.summary,
            "synopsis": scene.synopsis,
            "content": scene.content,
            "goal": scene.goal,
            "conflict": scene.conflict,
            "outcome": scene.outcome,
            "beat": scene.beat,
            "act": scene.act,
            "chapter": scene.chapter,
            "plotline": scene.plotline,
            "characters": [
                char_map[cid].name for cid in char_ids if cid in char_map
            ],
            "places": [
                place_map[pid].name for pid in place_ids if pid in place_map
            ],
            "character_states": [
                (char_map[cid].name, state)
                for cid, state in states
                if cid in char_map
            ],
        }

    def _gather_outline(self) -> list[dict]:
        scenes = self._db.get_all_scenes(self._project_id)
        return [
            {"title": s.title, "chapter": s.chapter, "summary": s.summary}
            for s in scenes
        ]

    # -- Sending requests ----------------------------------------------------

    def _send_preset(self, action_key: str) -> None:
        if self._worker is not None:
            return
        scene_id = self._scene_combo.currentData()
        if scene_id is None:
            self._response_output.setPlainText("No scene selected.")
            return

        scene_data = self._gather_scene_data(scene_id)
        if not scene_data:
            self._response_output.setPlainText("Could not load scene data.")
            return

        scene_ctx = build_scene_context(scene_data)
        outline_ctx = ""
        if self._outline_check.isChecked():
            outline_ctx = build_outline_context(self._gather_outline())

        user_note = self._prompt_input.toPlainText().strip()
        action_prompt = PRESET_ACTIONS[action_key]

        messages = build_messages(
            action_prompt, scene_ctx, outline_ctx, user_note,
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

        scene_data = self._gather_scene_data(scene_id)
        if not scene_data:
            self._response_output.setPlainText("Could not load scene data.")
            return

        scene_ctx = build_scene_context(scene_data)
        outline_ctx = ""
        if self._outline_check.isChecked():
            outline_ctx = build_outline_context(self._gather_outline())

        messages = build_messages(prompt, scene_ctx, outline_ctx)
        self._start_request(messages)

    def _start_request(self, messages: list[dict]) -> None:
        self._set_busy(True)
        self._response_output.setPlainText("Thinking...")

        base_url = self._url_input.text().strip() or DEFAULT_BASE_URL
        model = self._model_input.text().strip()

        self._worker = _AssistantWorker(messages, base_url, model)
        self._worker.completed.connect(self._on_response)
        self._worker.failed.connect(self._on_error)
        self._worker.start()

    # -- Response handling ---------------------------------------------------

    def _on_response(self, text: str) -> None:
        self._response_output.setPlainText(text)
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

    # -- Apply to scene ------------------------------------------------------

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
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
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
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
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
