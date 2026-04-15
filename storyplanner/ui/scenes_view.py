"""Scenes management view — list + create form with character/place links."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
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


class ScenesView(QWidget):
    def __init__(self, db: Database, project_id: int) -> None:
        super().__init__()
        self._db = db
        self._project_id = project_id

        root = QHBoxLayout(self)

        # -- Left: scene list ------------------------------------------------
        left = QVBoxLayout()
        left.addWidget(QLabel("Scenes"))
        self._list = QListWidget()
        self._list.currentItemChanged.connect(self._on_scene_selected)
        left.addWidget(self._list)
        root.addLayout(left)

        # -- Right: form -----------------------------------------------------
        right = QVBoxLayout()
        right.addWidget(QLabel("New Scene"))

        right.addWidget(QLabel("Title"))
        self._title_input = QLineEdit()
        right.addWidget(self._title_input)

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

        save_btn = QPushButton("Save")
        save_btn.clicked.connect(self._on_save)
        right.addWidget(save_btn)

        right.addStretch()
        root.addLayout(right)

        self._load_characters()
        self._load_places()
        self._refresh_list()

    def _load_characters(self) -> None:
        """Populate the checkable character list."""
        self._char_list.clear()
        for char in self._db.get_all_characters(self._project_id):
            item = QListWidgetItem(char.name)
            item.setData(USER_ROLE, char.id)
            item.setCheckState(Qt.CheckState.Unchecked)
            self._char_list.addItem(item)

    def _load_places(self) -> None:
        """Populate the checkable place list."""
        self._place_list.clear()
        for place in self._db.get_all_places(self._project_id):
            item = QListWidgetItem(place.name)
            item.setData(USER_ROLE, place.id)
            item.setCheckState(Qt.CheckState.Unchecked)
            self._place_list.addItem(item)

    def _refresh_list(self) -> None:
        self._list.clear()
        for scene in self._db.get_all_scenes(self._project_id):
            item = QListWidgetItem(scene.title)
            item.setData(USER_ROLE, scene.id)
            self._list.addItem(item)

    def _on_scene_selected(self, current: QListWidgetItem | None) -> None:
        """When a scene is clicked, show its data and linked items."""
        if current is None:
            return

        scene_id = current.data(USER_ROLE)

        # Load scene details
        scenes = self._db.get_all_scenes(self._project_id)
        scene = next((s for s in scenes if s.id == scene_id), None)
        if scene is None:
            return

        self._title_input.setText(scene.title)
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

    def _get_checked_ids(self, list_widget: QListWidget) -> list[int]:
        """Return the IDs of all checked items in a list widget."""
        ids = []
        for i in range(list_widget.count()):
            item = list_widget.item(i)
            if item.checkState() == Qt.CheckState.Checked:
                ids.append(item.data(USER_ROLE))
        return ids

    def _on_save(self) -> None:
        title = self._title_input.text().strip()
        if not title:
            return

        self._db.create_scene(
            project_id=self._project_id,
            title=title,
            summary=self._summary_input.toPlainText().strip(),
            character_ids=self._get_checked_ids(self._char_list),
            place_ids=self._get_checked_ids(self._place_list),
        )

        self._title_input.clear()
        self._summary_input.clear()
        self._uncheck_all(self._char_list)
        self._uncheck_all(self._place_list)
        self._refresh_list()

    def _uncheck_all(self, list_widget: QListWidget) -> None:
        for i in range(list_widget.count()):
            list_widget.item(i).setCheckState(Qt.CheckState.Unchecked)
