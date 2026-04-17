"""Notes management view — list, create, edit, delete."""

from collections.abc import Callable

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
from storyplanner.ui.link_preview import BacklinksWidget, create_link_browser, render_linked_text

USER_ROLE = Qt.ItemDataRole.UserRole


class NotesView(QWidget):
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

        right.addWidget(QLabel("Link Preview"))
        self._link_preview = create_link_browser(self._on_link_name_clicked)
        right.addWidget(self._link_preview)

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

        self._backlinks = BacklinksWidget(
            db, project_id, on_backlink_clicked=on_link_clicked,
        )
        right.addWidget(self._backlinks)

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
        self._link_preview.setHtml(render_linked_text(note.content))
        self._backlinks.load(note.title)

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
        if self._on_data_changed:
            self._on_data_changed()

    def _on_delete(self) -> None:
        if self._selected_id is None:
            return
        self._db.delete_note(self._selected_id)
        self._clear_form()
        self._refresh_list()
        if self._on_data_changed:
            self._on_data_changed()

    def select_note(self, note_id: int) -> None:
        for i in range(self._list.count()):
            if self._list.item(i).data(USER_ROLE) == note_id:
                self._list.setCurrentRow(i)
                return

    def _clear_form(self) -> None:
        self._selected_id = None
        self._form_label.setText("New Note")
        self._delete_btn.setEnabled(False)
        self._title_input.clear()
        self._content_input.clear()
        self._link_preview.clear()
        self._backlinks.clear_backlinks()
        self._list.clearSelection()

    def _on_link_name_clicked(self, name: str) -> None:
        result = self._db.resolve_link(self._project_id, name)
        if result is None:
            return
        entity_type, entity_id = result
        if self._on_link_clicked:
            self._on_link_clicked(entity_type, entity_id)
