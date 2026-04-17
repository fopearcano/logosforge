"""Character Arc view — ordered list of a character's states across scenes."""

from collections.abc import Callable
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
    QWidget,
)

from storyplanner.db import Database

USER_ROLE = Qt.ItemDataRole.UserRole


class CharacterArcView(QWidget):
    def __init__(
        self,
        db: Database,
        project_id: int,
        on_scene_selected: Optional[Callable[[int], None]] = None,
    ) -> None:
        super().__init__()
        self._db = db
        self._project_id = project_id
        self._on_scene_selected = on_scene_selected

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Character Arc"))

        self._char_combo = QComboBox()
        self._char_combo.currentIndexChanged.connect(self._on_character_changed)
        layout.addWidget(self._char_combo)

        self._arc_list = QListWidget()
        self._arc_list.itemDoubleClicked.connect(self._on_item_double_clicked)
        layout.addWidget(self._arc_list)

        self._empty_label = QLabel("Select a character to view their arc.")
        self._empty_label.setWordWrap(True)
        layout.addWidget(self._empty_label)

        self._load_characters()

    def _load_characters(self) -> None:
        self._char_combo.blockSignals(True)
        self._char_combo.clear()
        self._char_combo.addItem("-- Select Character --", None)
        for char in self._db.get_all_characters(self._project_id):
            self._char_combo.addItem(char.name, char.id)
        self._char_combo.blockSignals(False)
        self._char_combo.setCurrentIndex(0)
        self._arc_list.clear()
        self._empty_label.setText("Select a character to view their arc.")
        self._empty_label.setVisible(True)

    def _on_character_changed(self, index: int) -> None:
        char_id = self._char_combo.currentData()
        if char_id is None:
            self._arc_list.clear()
            self._empty_label.setText("Select a character to view their arc.")
            self._empty_label.setVisible(True)
            return

        arc = self._db.get_character_arc(self._project_id, char_id)
        self._arc_list.clear()

        if not arc:
            self._empty_label.setText(
                "No scene states found for this character.\n"
                "Add character states in the Scenes editor."
            )
            self._empty_label.setVisible(True)
            return

        self._empty_label.setVisible(False)
        for scene_id, title, order_index, state in arc:
            text = f"[{order_index}] {title}  \u2192  \"{state}\""
            item = QListWidgetItem(text)
            item.setData(USER_ROLE, scene_id)
            self._arc_list.addItem(item)

    def _on_item_double_clicked(self, item: QListWidgetItem) -> None:
        scene_id = item.data(USER_ROLE)
        if scene_id is not None and self._on_scene_selected:
            self._on_scene_selected(scene_id)
