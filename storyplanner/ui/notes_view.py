"""Notes management view — list, create, edit, delete."""

from collections.abc import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFrame,
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

        right.addWidget(QLabel("Tags (comma-separated)"))
        self._tags_input = QLineEdit()
        self._tags_input.setPlaceholderText("e.g. worldbuilding, magic, backstory")
        right.addWidget(self._tags_input)

        self._pinned_check = QCheckBox("Pinned (always include in Assistant context)")
        right.addWidget(self._pinned_check)

        # -- PSYKE linking ---------------------------------------------------
        psyke_frame = QFrame()
        psyke_frame.setObjectName("noteLinkFrame")
        psyke_layout = QVBoxLayout(psyke_frame)
        psyke_layout.setContentsMargins(4, 4, 4, 4)
        psyke_layout.setSpacing(4)

        psyke_header = QHBoxLayout()
        psyke_header.addWidget(QLabel("Linked PSYKE Entries"))
        self._psyke_combo = QComboBox()
        self._psyke_combo.setMinimumWidth(120)
        psyke_header.addWidget(self._psyke_combo)
        link_psyke_btn = QPushButton("Link")
        link_psyke_btn.clicked.connect(self._on_link_psyke)
        psyke_header.addWidget(link_psyke_btn)
        psyke_header.addStretch()
        psyke_layout.addLayout(psyke_header)

        self._psyke_links_list = QListWidget()
        self._psyke_links_list.setMaximumHeight(80)
        psyke_layout.addWidget(self._psyke_links_list)

        unlink_psyke_btn = QPushButton("Unlink Selected")
        unlink_psyke_btn.clicked.connect(self._on_unlink_psyke)
        psyke_layout.addWidget(unlink_psyke_btn)
        right.addWidget(psyke_frame)

        # -- Scene linking ---------------------------------------------------
        scene_frame = QFrame()
        scene_frame.setObjectName("noteLinkFrame")
        scene_layout = QVBoxLayout(scene_frame)
        scene_layout.setContentsMargins(4, 4, 4, 4)
        scene_layout.setSpacing(4)

        scene_header = QHBoxLayout()
        scene_header.addWidget(QLabel("Linked Scenes"))
        self._scene_combo = QComboBox()
        self._scene_combo.setMinimumWidth(120)
        scene_header.addWidget(self._scene_combo)
        link_scene_btn = QPushButton("Link")
        link_scene_btn.clicked.connect(self._on_link_scene)
        scene_header.addWidget(link_scene_btn)
        scene_header.addStretch()
        scene_layout.addLayout(scene_header)

        self._scene_links_list = QListWidget()
        self._scene_links_list.setMaximumHeight(80)
        scene_layout.addWidget(self._scene_links_list)

        unlink_scene_btn = QPushButton("Unlink Selected")
        unlink_scene_btn.clicked.connect(self._on_unlink_scene)
        scene_layout.addWidget(unlink_scene_btn)
        right.addWidget(scene_frame)

        # -- Link preview / actions ------------------------------------------
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
        self._refresh_combos()

    # -- List ----------------------------------------------------------------

    def _refresh_list(self) -> None:
        self._list.blockSignals(True)
        self._list.clear()
        for note in self._db.get_all_notes(self._project_id):
            label = note.title
            if note.pinned:
                label = f"[pinned] {label}"
            item = QListWidgetItem(label)
            item.setData(USER_ROLE, note.id)
            self._list.addItem(item)
        self._list.blockSignals(False)

    def _refresh_combos(self) -> None:
        self._psyke_combo.clear()
        self._psyke_combo.addItem("-- select --", userData=None)
        for entry in self._db.get_all_psyke_entries(self._project_id):
            self._psyke_combo.addItem(f"{entry.name} ({entry.entry_type})", userData=entry.id)

        self._scene_combo.clear()
        self._scene_combo.addItem("-- select --", userData=None)
        for scene in self._db.get_all_scenes(self._project_id):
            self._scene_combo.addItem(scene.title, userData=scene.id)

    def refresh(self) -> None:
        self._refresh_list()
        self._refresh_combos()

    # -- Selection -----------------------------------------------------------

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
        self._tags_input.setText(note.tags)
        self._pinned_check.setChecked(note.pinned)
        self._link_preview.setHtml(render_linked_text(note.content))
        self._backlinks.load(note.title)
        self._refresh_psyke_links()
        self._refresh_scene_links()

    # -- Save / Delete -------------------------------------------------------

    def _on_save(self) -> None:
        title = self._title_input.text().strip()
        if not title:
            return
        content = self._content_input.toPlainText().strip()
        tags = self._tags_input.text().strip()
        pinned = self._pinned_check.isChecked()

        if self._selected_id is not None:
            self._db.update_note(self._selected_id, title, content, tags=tags, pinned=pinned)
        else:
            note = self._db.create_note(self._project_id, title, content, tags=tags, pinned=pinned)
            self._selected_id = note.id

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
        self._tags_input.clear()
        self._pinned_check.setChecked(False)
        self._link_preview.clear()
        self._backlinks.clear_backlinks()
        self._psyke_links_list.clear()
        self._scene_links_list.clear()
        self._list.clearSelection()

    # -- PSYKE linking -------------------------------------------------------

    def _refresh_psyke_links(self) -> None:
        self._psyke_links_list.clear()
        if self._selected_id is None:
            return
        linked_ids = self._db.get_note_psyke_links(self._selected_id)
        for eid in linked_ids:
            entry = self._db.get_psyke_entry_by_id(eid)
            if entry:
                item = QListWidgetItem(f"{entry.name} ({entry.entry_type})")
                item.setData(USER_ROLE, entry.id)
                self._psyke_links_list.addItem(item)

    def _on_link_psyke(self) -> None:
        if self._selected_id is None:
            return
        entry_id = self._psyke_combo.currentData()
        if entry_id is None:
            return
        self._db.link_note_to_psyke(self._selected_id, entry_id)
        self._refresh_psyke_links()
        if self._on_data_changed:
            self._on_data_changed()

    def _on_unlink_psyke(self) -> None:
        if self._selected_id is None:
            return
        current = self._psyke_links_list.currentItem()
        if current is None:
            return
        entry_id = current.data(USER_ROLE)
        self._db.unlink_note_from_psyke(self._selected_id, entry_id)
        self._refresh_psyke_links()
        if self._on_data_changed:
            self._on_data_changed()

    # -- Scene linking -------------------------------------------------------

    def _refresh_scene_links(self) -> None:
        self._scene_links_list.clear()
        if self._selected_id is None:
            return
        linked_ids = self._db.get_note_scene_links(self._selected_id)
        for sid in linked_ids:
            scene = self._db.get_scene_by_id(sid)
            if scene:
                item = QListWidgetItem(scene.title)
                item.setData(USER_ROLE, scene.id)
                self._scene_links_list.addItem(item)

    def _on_link_scene(self) -> None:
        if self._selected_id is None:
            return
        scene_id = self._scene_combo.currentData()
        if scene_id is None:
            return
        self._db.link_note_to_scene(self._selected_id, scene_id)
        self._refresh_scene_links()
        if self._on_data_changed:
            self._on_data_changed()

    def _on_unlink_scene(self) -> None:
        if self._selected_id is None:
            return
        current = self._scene_links_list.currentItem()
        if current is None:
            return
        scene_id = current.data(USER_ROLE)
        self._db.unlink_note_from_scene(self._selected_id, scene_id)
        self._refresh_scene_links()
        if self._on_data_changed:
            self._on_data_changed()

    # -- Wiki link click -----------------------------------------------------

    def _on_link_name_clicked(self, name: str) -> None:
        result = self._db.resolve_link(self._project_id, name)
        if result is None:
            return
        entity_type, entity_id = result
        if self._on_link_clicked:
            self._on_link_clicked(entity_type, entity_id)
