"""Scenes management view — list, create, edit, with chapter/plotline grouping."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from storyplanner.db import Database

USER_ROLE = Qt.ItemDataRole.UserRole
FILTER_ALL = "All"


class ScenesView(QWidget):
    def __init__(self, db: Database, project_id: int) -> None:
        super().__init__()
        self._db = db
        self._project_id = project_id
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

        right.addWidget(QLabel("Summary"))
        self._summary_input = QPlainTextEdit()
        self._summary_input.setMaximumHeight(80)
        right.addWidget(self._summary_input)

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

        right.addStretch()
        root.addLayout(right)

        self._load_characters()
        self._load_places()
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
        self._summary_input.setPlainText(scene.summary)

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
        chapter = self._chapter_input.text().strip()
        plotline = self._plotline_input.text().strip()
        char_ids = self._get_checked_ids(self._char_list)
        place_ids = self._get_checked_ids(self._place_list)

        if self._selected_scene_id is not None:
            self._db.update_scene(
                scene_id=self._selected_scene_id,
                title=title,
                summary=summary,
                chapter=chapter,
                plotline=plotline,
                character_ids=char_ids,
                place_ids=place_ids,
            )
        else:
            self._db.create_scene(
                project_id=self._project_id,
                title=title,
                summary=summary,
                chapter=chapter,
                plotline=plotline,
                character_ids=char_ids,
                place_ids=place_ids,
            )

        self._clear_form()
        self._refresh_filters()
        self._refresh_list()

    # -- Delete --------------------------------------------------------------

    def _on_delete(self) -> None:
        if self._selected_scene_id is None:
            return
        self._db.delete_scene(self._selected_scene_id)
        self._clear_form()
        self._refresh_filters()
        self._refresh_list()

    # -- Reorder -------------------------------------------------------------

    def _on_move_up(self) -> None:
        if self._selected_scene_id is None:
            return
        self._db.move_scene_up(self._selected_scene_id)
        self._refresh_list()
        self._reselect(self._selected_scene_id)

    def _on_move_down(self) -> None:
        if self._selected_scene_id is None:
            return
        self._db.move_scene_down(self._selected_scene_id)
        self._refresh_list()
        self._reselect(self._selected_scene_id)

    def select_scene(self, scene_id: int) -> None:
        """Programmatically select a scene by ID (used by Timeline navigation)."""
        self._reselect(scene_id)

    def _reselect(self, scene_id: int) -> None:
        for i in range(self._list.count()):
            if self._list.item(i).data(USER_ROLE) == scene_id:
                self._list.setCurrentRow(i)
                return

    # -- Helpers -------------------------------------------------------------

    def _clear_form(self) -> None:
        self._selected_scene_id = None
        self._form_label.setText("New Scene")
        self._delete_btn.setEnabled(False)
        self._move_up_btn.setEnabled(False)
        self._move_down_btn.setEnabled(False)
        self._title_input.clear()
        self._chapter_input.clear()
        self._plotline_input.clear()
        self._summary_input.clear()
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
