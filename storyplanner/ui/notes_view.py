"""Notes management view — list, create, edit, delete."""

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


class NotesView(QWidget):
    def __init__(self, db: Database, project_id: int) -> None:
        super().__init__()
        self._db = db
        self._project_id = project_id
        self._selected_id: int | None = None

        root = QHBoxLayout(self)

        # -- Left: note list -------------------------------------------------
        left = QVBoxLayout()
        left.addWidget(QLabel("Notes"))
        self._list = QListWidget()
        self._list.currentItemChanged.connect(self._on_selected)
        left.addWidget(self._list)
        root.addLayout(left)

        # -- Right: form -----------------------------------------------------
        right = QVBoxLayout()

        self._form_label = QLabel("New Note")
        right.addWidget(self._form_label)

        right.addWidget(QLabel("Title"))
        self._title_input = QLineEdit()
        right.addWidget(self._title_input)

        right.addWidget(QLabel("Content"))
        self._content_input = QPlainTextEdit()
        right.addWidget(self._content_input)

        save_btn = QPushButton("Save")
        save_btn.clicked.connect(self._on_save)
        right.addWidget(save_btn)

        self._delete_btn = QPushButton("Delete")
        self._delete_btn.setEnabled(False)
        self._delete_btn.clicked.connect(self._on_delete)
        right.addWidget(self._delete_btn)

        new_btn = QPushButton("New Note")
        new_btn.clicked.connect(self._clear_form)
        right.addWidget(new_btn)

        right.addStretch()
        root.addLayout(right)

        self._refresh_list()

    def _refresh_list(self) -> None:
        self._list.blockSignals(True)
        self._list.clear()
        for note in self._db.get_all_notes(self._project_id):
            item = QListWidgetItem(note.title)
            item.setData(USER_ROLE, note.id)
            self._list.addItem(item)
        self._list.blockSignals(False)

    def _on_selected(self, current: QListWidgetItem | None) -> None:
        if current is None:
            return
        note = self._db.get_note_by_id(current.data(USER_ROLE))
        if note is None:
            return
        self._selected_id = note.id
        self._form_label.setText("Edit Note")
        self._delete_btn.setEnabled(True)
        self._title_input.setText(note.title)
        self._content_input.setPlainText(note.content)

    def _on_save(self) -> None:
        title = self._title_input.text().strip()
        if not title:
            return
        content = self._content_input.toPlainText().strip()

        if self._selected_id is not None:
            self._db.update_note(self._selected_id, title, content)
        else:
            self._db.create_note(self._project_id, title, content)

        self._clear_form()
        self._refresh_list()

    def _on_delete(self) -> None:
        if self._selected_id is None:
            return
        self._db.delete_note(self._selected_id)
        self._clear_form()
        self._refresh_list()

    def _clear_form(self) -> None:
        self._selected_id = None
        self._form_label.setText("New Note")
        self._delete_btn.setEnabled(False)
        self._title_input.clear()
        self._content_input.clear()
        self._list.clearSelection()
