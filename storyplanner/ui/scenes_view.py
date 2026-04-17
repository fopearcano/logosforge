"""Scenes management view — list, create, edit, with chapter/plotline grouping."""

from collections.abc import Callable

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QTextBlockFormat, QTextCursor
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from storyplanner.db import Database
from storyplanner.ui.link_preview import BacklinksWidget, create_link_browser, render_linked_text

USER_ROLE = Qt.ItemDataRole.UserRole
FILTER_ALL = "All"
BEAT_OPTIONS = [
    "",
    "Opening Image",
    "Setup",
    "Catalyst",
    "Debate",
    "Break into Two",
    "Midpoint",
    "Bad Guys Close In",
    "All Is Lost",
    "Break into Three",
    "Finale",
    "Final Image",
]


class ScenesView(QWidget):
    def __init__(
        self,
        db: Database,
        project_id: int,
        on_data_changed: Callable[[], None] | None = None,
        on_link_clicked: Callable[[str, int], None] | None = None,
    ) -> None:
        super().__init__()
        self._db = db
        self._project_id = project_id
        self._on_data_changed = on_data_changed
        self._on_link_clicked = on_link_clicked
        self._selected_scene_id: int | None = None

        root = QHBoxLayout(self)

        # -- Left: scene list ------------------------------------------------
        left = QVBoxLayout()
        left.addWidget(QLabel("Scenes"))

        # Chapter filter
        left.addWidget(QLabel("Chapter filter"))
        self._chapter_filter = QComboBox()
        self._chapter_filter.currentTextChanged.connect(self._on_filter_changed)
        left.addWidget(self._chapter_filter)

        # Plotline filter
        left.addWidget(QLabel("Plotline filter"))
        self._plotline_filter = QComboBox()
        self._plotline_filter.currentTextChanged.connect(self._on_filter_changed)
        left.addWidget(self._plotline_filter)

        # Tag filter
        left.addWidget(QLabel("Tag filter"))
        self._tag_filter = QComboBox()
        self._tag_filter.currentTextChanged.connect(self._on_filter_changed)
        left.addWidget(self._tag_filter)

        self._list = QListWidget()
        self._list.currentItemChanged.connect(self._on_scene_selected)
        left.addWidget(self._list)

        # Reorder buttons
        self._move_up_btn = QPushButton("Move Up")
        self._move_up_btn.setEnabled(False)
        self._move_up_btn.clicked.connect(self._on_move_up)
        left.addWidget(self._move_up_btn)

        self._move_down_btn = QPushButton("Move Down")
        self._move_down_btn.setEnabled(False)
        self._move_down_btn.clicked.connect(self._on_move_down)
        left.addWidget(self._move_down_btn)

        root.addLayout(left)

        # -- Right: form -----------------------------------------------------
        right = QVBoxLayout()

        self._form_label = QLabel("New Scene")
        right.addWidget(self._form_label)

        right.addWidget(QLabel("Title"))
        self._title_input = QLineEdit()
        right.addWidget(self._title_input)

        right.addWidget(QLabel("Chapter"))
        self._chapter_input = QLineEdit()
        self._chapter_input.setPlaceholderText("e.g. Chapter 1")
        right.addWidget(self._chapter_input)

        right.addWidget(QLabel("Plotline"))
        self._plotline_input = QLineEdit()
        self._plotline_input.setPlaceholderText("e.g. Main Plot")
        right.addWidget(self._plotline_input)

        right.addWidget(QLabel("Act"))
        self._act_input = QComboBox()
        self._act_input.addItems(["", "Act I", "Act II", "Act III"])
        right.addWidget(self._act_input)

        right.addWidget(QLabel("Beat"))
        self._beat_input = QComboBox()
        self._beat_input.setEditable(True)
        self._beat_input.addItems(BEAT_OPTIONS)
        self._beat_input.lineEdit().setPlaceholderText("e.g. Catalyst")
        right.addWidget(self._beat_input)

        right.addWidget(QLabel("Tags"))
        self._tags_input = QLineEdit()
        self._tags_input.setPlaceholderText("e.g. love, betrayal, redemption")
        right.addWidget(self._tags_input)

        right.addWidget(QLabel("Summary"))
        self._summary_input = QPlainTextEdit()
        self._summary_input.setMaximumHeight(60)
        right.addWidget(self._summary_input)

        right.addWidget(QLabel("Synopsis"))
        self._synopsis_input = QPlainTextEdit()
        self._synopsis_input.setMaximumHeight(60)
        right.addWidget(self._synopsis_input)

        right.addWidget(QLabel("Goal"))
        self._goal_input = QPlainTextEdit()
        self._goal_input.setMaximumHeight(40)
        right.addWidget(self._goal_input)

        right.addWidget(QLabel("Conflict"))
        self._conflict_input = QPlainTextEdit()
        self._conflict_input.setMaximumHeight(40)
        right.addWidget(self._conflict_input)

        right.addWidget(QLabel("Outcome"))
        self._outcome_input = QPlainTextEdit()
        self._outcome_input.setMaximumHeight(40)
        right.addWidget(self._outcome_input)

        content_label = QLabel("Content")
        content_label.setStyleSheet(
            "font-weight: bold; font-size: 15px; margin-top: 12px;"
            " color: #9aa0a6;"
        )
        right.addWidget(content_label)

        writing_col = QHBoxLayout()
        writing_col.addStretch()
        self._content_input = QPlainTextEdit()
        self._content_input.setMinimumHeight(400)
        self._content_input.setMaximumWidth(720)
        self._content_input.setPlaceholderText("Write the full scene content here...")
        writing_font = QFont()
        writing_font.setPointSize(14)
        self._content_input.setFont(writing_font)
        self._content_input.setStyleSheet(
            "QPlainTextEdit {"
            "  background-color: #12151a;"
            "  color: #d4d4d4;"
            "  border: none;"
            "  border-radius: 4px;"
            "  padding: 20px 28px;"
            "  selection-background-color: #1a3a2a;"
            "  selection-color: #00ff9c;"
            "}"
        )
        self._content_input.setTabStopDistance(40.0)
        self._apply_line_spacing(self._content_input)
        writing_col.addWidget(self._content_input)
        writing_col.addStretch()
        right.addLayout(writing_col)

        # Link preview
        right.addWidget(QLabel("Link Preview"))
        self._link_preview = create_link_browser(self._on_link_name_clicked)
        right.addWidget(self._link_preview)

        # Checkable character list
        right.addWidget(QLabel("Characters"))
        self._char_list = QListWidget()
        self._char_list.setMaximumHeight(100)
        right.addWidget(self._char_list)

        # Checkable place list
        right.addWidget(QLabel("Places"))
        self._place_list = QListWidget()
        self._place_list.setMaximumHeight(100)
        right.addWidget(self._place_list)

        # Character states
        right.addWidget(QLabel("Character States"))
        state_row = QHBoxLayout()
        self._state_char_combo = QComboBox()
        state_row.addWidget(self._state_char_combo)
        self._state_text_input = QLineEdit()
        self._state_text_input.setPlaceholderText("e.g. conflicted, hopeful")
        state_row.addWidget(self._state_text_input)
        self._add_state_btn = QPushButton("Add")
        self._add_state_btn.clicked.connect(self._on_add_state)
        state_row.addWidget(self._add_state_btn)
        right.addLayout(state_row)

        self._state_list = QListWidget()
        self._state_list.setMaximumHeight(80)
        right.addWidget(self._state_list)

        self._remove_state_btn = QPushButton("Remove State")
        self._remove_state_btn.clicked.connect(self._on_remove_state)
        right.addWidget(self._remove_state_btn)

        self._save_btn = QPushButton("Save")
        self._save_btn.clicked.connect(self._on_save)
        right.addWidget(self._save_btn)

        self._delete_btn = QPushButton("Delete")
        self._delete_btn.setEnabled(False)
        self._delete_btn.clicked.connect(self._on_delete)
        right.addWidget(self._delete_btn)

        new_btn = QPushButton("New Scene")
        new_btn.clicked.connect(self._clear_form)
        right.addWidget(new_btn)

        self._backlinks = BacklinksWidget(
            db, project_id, on_backlink_clicked=on_link_clicked,
        )
        right.addWidget(self._backlinks)

        right.addStretch()

        right_widget = QWidget()
        right_widget.setLayout(right)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(right_widget)
        root.addWidget(scroll, stretch=1)

        self._load_characters()
        self._load_places()
        self._load_state_combo()
        self._refresh_filters()
        self._refresh_list()

    # -- Populate checkable lists --------------------------------------------

    def _load_characters(self) -> None:
        self._char_list.clear()
        for char in self._db.get_all_characters(self._project_id):
            item = QListWidgetItem(char.name)
            item.setData(USER_ROLE, char.id)
            item.setCheckState(Qt.CheckState.Unchecked)
            self._char_list.addItem(item)

    def _load_places(self) -> None:
        self._place_list.clear()
        for place in self._db.get_all_places(self._project_id):
            item = QListWidgetItem(place.name)
            item.setData(USER_ROLE, place.id)
            item.setCheckState(Qt.CheckState.Unchecked)
            self._place_list.addItem(item)

    def _load_state_combo(self) -> None:
        self._state_char_combo.clear()
        self._char_id_by_name: dict[str, int] = {}
        self._char_name_by_id: dict[int, str] = {}
        for char in self._db.get_all_characters(self._project_id):
            self._state_char_combo.addItem(char.name)
            self._char_id_by_name[char.name] = char.id
            self._char_name_by_id[char.id] = char.name

    def _on_add_state(self) -> None:
        name = self._state_char_combo.currentText()
        state = self._state_text_input.text().strip()
        if not name or not state:
            return
        char_id = self._char_id_by_name.get(name)
        if char_id is None:
            return
        item = QListWidgetItem(f"{name}: {state}")
        item.setData(USER_ROLE, (char_id, state))
        self._state_list.addItem(item)
        self._state_text_input.clear()

    def _on_remove_state(self) -> None:
        row = self._state_list.currentRow()
        if row >= 0:
            self._state_list.takeItem(row)

    def _get_character_states(self) -> list[tuple[int, str]]:
        states = []
        for i in range(self._state_list.count()):
            data = self._state_list.item(i).data(USER_ROLE)
            if data:
                states.append(data)
        return states

    def _load_character_states(self, scene_id: int) -> None:
        self._state_list.clear()
        for char_id, state in self._db.get_scene_character_states(scene_id):
            name = self._char_name_by_id.get(char_id, f"Character {char_id}")
            item = QListWidgetItem(f"{name}: {state}")
            item.setData(USER_ROLE, (char_id, state))
            self._state_list.addItem(item)

    # -- Filters -------------------------------------------------------------

    def _refresh_filters(self) -> None:
        self._refresh_combo(
            self._chapter_filter,
            self._db.get_scene_chapters(self._project_id),
        )
        self._refresh_combo(
            self._plotline_filter,
            self._db.get_scene_plotlines(self._project_id),
        )
        self._refresh_combo(
            self._tag_filter,
            self._db.get_scene_tags(self._project_id),
        )

    def _refresh_combo(self, combo: QComboBox, values: list[str]) -> None:
        combo.blockSignals(True)
        current = combo.currentText()
        combo.clear()
        combo.addItem(FILTER_ALL)
        for val in values:
            combo.addItem(val)
        idx = combo.findText(current)
        combo.setCurrentIndex(idx if idx >= 0 else 0)
        combo.blockSignals(False)

    def _get_filter_value(self, combo: QComboBox) -> str | None:
        text = combo.currentText()
        return None if text == FILTER_ALL else text

    def _on_filter_changed(self) -> None:
        self._clear_form()
        self._refresh_list()

    # -- Scene list ----------------------------------------------------------

    def _refresh_list(self) -> None:
        self._list.blockSignals(True)
        self._list.clear()
        scenes = self._db.get_all_scenes(
            self._project_id,
            chapter=self._get_filter_value(self._chapter_filter),
            plotline=self._get_filter_value(self._plotline_filter),
            tag=self._get_filter_value(self._tag_filter),
        )
        for scene in scenes:
            label = self._format_scene_label(scene)
            item = QListWidgetItem(label)
            item.setData(USER_ROLE, scene.id)
            self._list.addItem(item)
        self._list.blockSignals(False)

    def _format_scene_label(self, scene) -> str:
        tags = []
        if scene.chapter:
            tags.append(scene.chapter)
        if scene.plotline:
            tags.append(scene.plotline)
        if scene.beat:
            tags.append(scene.beat)
        if tags:
            return f"[{' | '.join(tags)}] {scene.title}"
        return scene.title

    # -- Selection -----------------------------------------------------------

    def _on_scene_selected(self, current: QListWidgetItem | None) -> None:
        if current is None:
            return

        scene_id = current.data(USER_ROLE)
        scene = self._db.get_scene_by_id(scene_id)
        if scene is None:
            return

        self._selected_scene_id = scene.id
        self._form_label.setText("Edit Scene")
        self._delete_btn.setEnabled(True)
        self._move_up_btn.setEnabled(True)
        self._move_down_btn.setEnabled(True)
        self._title_input.setText(scene.title)
        self._chapter_input.setText(scene.chapter)
        self._plotline_input.setText(scene.plotline)
        idx = self._act_input.findText(scene.act)
        self._act_input.setCurrentIndex(idx if idx >= 0 else 0)
        self._beat_input.setCurrentText(scene.beat)
        self._tags_input.setText(scene.tags)
        self._summary_input.setPlainText(scene.summary)
        self._synopsis_input.setPlainText(scene.synopsis)
        self._goal_input.setPlainText(scene.goal)
        self._conflict_input.setPlainText(scene.conflict)
        self._outcome_input.setPlainText(scene.outcome)
        self._content_input.setPlainText(scene.content)
        self._apply_line_spacing(self._content_input)
        self._update_link_preview(scene.summary, scene.synopsis)
        self._backlinks.load(scene.title)
        self._load_character_states(scene_id)

        # Check linked characters
        linked_char_ids = set(self._db.get_scene_character_ids(scene_id))
        for i in range(self._char_list.count()):
            item = self._char_list.item(i)
            checked = item.data(USER_ROLE) in linked_char_ids
            item.setCheckState(
                Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked
            )

        # Check linked places
        linked_place_ids = set(self._db.get_scene_place_ids(scene_id))
        for i in range(self._place_list.count()):
            item = self._place_list.item(i)
            checked = item.data(USER_ROLE) in linked_place_ids
            item.setCheckState(
                Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked
            )

    # -- Save (create or update) ---------------------------------------------

    def _on_save(self) -> None:
        title = self._title_input.text().strip()
        if not title:
            return

        summary = self._summary_input.toPlainText().strip()
        synopsis = self._synopsis_input.toPlainText().strip()
        goal = self._goal_input.toPlainText().strip()
        conflict = self._conflict_input.toPlainText().strip()
        outcome = self._outcome_input.toPlainText().strip()
        content = self._content_input.toPlainText()
        beat = self._beat_input.currentText().strip()
        tags = ", ".join(
            t for t in (t.strip() for t in self._tags_input.text().split(",")) if t
        )
        act = self._act_input.currentText()
        chapter = self._chapter_input.text().strip()
        plotline = self._plotline_input.text().strip()
        char_ids = self._get_checked_ids(self._char_list)
        place_ids = self._get_checked_ids(self._place_list)
        char_states = self._get_character_states()

        if self._selected_scene_id is not None:
            self._db.update_scene(
                scene_id=self._selected_scene_id,
                title=title,
                summary=summary,
                synopsis=synopsis,
                goal=goal,
                conflict=conflict,
                outcome=outcome,
                beat=beat,
                tags=tags,
                act=act,
                content=content,
                chapter=chapter,
                plotline=plotline,
                character_ids=char_ids,
                place_ids=place_ids,
                character_states=char_states,
            )
        else:
            self._db.create_scene(
                project_id=self._project_id,
                title=title,
                summary=summary,
                synopsis=synopsis,
                goal=goal,
                conflict=conflict,
                outcome=outcome,
                beat=beat,
                tags=tags,
                act=act,
                content=content,
                chapter=chapter,
                plotline=plotline,
                character_ids=char_ids,
                place_ids=place_ids,
                character_states=char_states,
            )

        self._clear_form()
        self._refresh_filters()
        self._refresh_list()
        if self._on_data_changed:
            self._on_data_changed()

    # -- Delete --------------------------------------------------------------

    def _on_delete(self) -> None:
        if self._selected_scene_id is None:
            return
        self._db.delete_scene(self._selected_scene_id)
        self._clear_form()
        self._refresh_filters()
        self._refresh_list()
        if self._on_data_changed:
            self._on_data_changed()

    # -- Reorder -------------------------------------------------------------

    def _on_move_up(self) -> None:
        if self._selected_scene_id is None:
            return
        self._db.move_scene_up(self._selected_scene_id)
        self._refresh_list()
        self._reselect(self._selected_scene_id)
        if self._on_data_changed:
            self._on_data_changed()

    def _on_move_down(self) -> None:
        if self._selected_scene_id is None:
            return
        self._db.move_scene_down(self._selected_scene_id)
        self._refresh_list()
        self._reselect(self._selected_scene_id)
        if self._on_data_changed:
            self._on_data_changed()

    def select_scene(self, scene_id: int) -> None:
        """Programmatically select a scene by ID (used by Timeline navigation)."""
        self._reselect(scene_id)

    def _reselect(self, scene_id: int) -> None:
        for i in range(self._list.count()):
            if self._list.item(i).data(USER_ROLE) == scene_id:
                self._list.setCurrentRow(i)
                return

    # -- Helpers -------------------------------------------------------------

    @staticmethod
    def _apply_line_spacing(editor: QPlainTextEdit) -> None:
        fmt = QTextBlockFormat()
        fmt.setLineHeight(155, 1)  # 1 = ProportionalHeight
        cursor = editor.textCursor()
        cursor.select(QTextCursor.SelectionType.Document)
        cursor.mergeBlockFormat(fmt)
        cursor.clearSelection()
        editor.setTextCursor(cursor)

    def _clear_form(self) -> None:
        self._selected_scene_id = None
        self._form_label.setText("New Scene")
        self._delete_btn.setEnabled(False)
        self._move_up_btn.setEnabled(False)
        self._move_down_btn.setEnabled(False)
        self._title_input.clear()
        self._chapter_input.clear()
        self._plotline_input.clear()
        self._act_input.setCurrentIndex(0)
        self._beat_input.setCurrentIndex(0)
        self._tags_input.clear()
        self._summary_input.clear()
        self._synopsis_input.clear()
        self._goal_input.clear()
        self._conflict_input.clear()
        self._outcome_input.clear()
        self._content_input.clear()
        self._apply_line_spacing(self._content_input)
        self._link_preview.clear()
        self._backlinks.clear_backlinks()
        self._state_list.clear()
        self._state_text_input.clear()
        self._uncheck_all(self._char_list)
        self._uncheck_all(self._place_list)
        self._list.clearSelection()

    def _get_checked_ids(self, list_widget: QListWidget) -> list[int]:
        ids = []
        for i in range(list_widget.count()):
            item = list_widget.item(i)
            if item.checkState() == Qt.CheckState.Checked:
                ids.append(item.data(USER_ROLE))
        return ids

    def _uncheck_all(self, list_widget: QListWidget) -> None:
        for i in range(list_widget.count()):
            list_widget.item(i).setCheckState(Qt.CheckState.Unchecked)

    def _update_link_preview(self, summary: str, synopsis: str) -> None:
        parts: list[str] = []
        if summary:
            parts.append(render_linked_text(summary))
        if synopsis:
            if parts:
                parts.append("<hr>")
            parts.append(render_linked_text(synopsis))
        self._link_preview.setHtml("".join(parts) if parts else "")

    def _on_link_name_clicked(self, name: str) -> None:
        result = self._db.resolve_link(self._project_id, name)
        if result is None:
            return
        entity_type, entity_id = result
        if self._on_link_clicked:
            self._on_link_clicked(entity_type, entity_id)
