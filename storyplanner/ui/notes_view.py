"""Notes management view — a simple note list + editor with a compact
"Linked to" section that links each note to Outline structure (Act / Chapter /
Scene) and, optionally, PSYKE entries.

Acts/Chapters are string labels (NoteStructureLink, keyed by name); Scenes use
NoteSceneLink; PSYKE uses NotePsykeLink. All are shown together as removable
chips. Everything is project-bound and reloads on project switch.
"""

from collections.abc import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from storyplanner.db import Database
from storyplanner.ui import theme

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

        # -- Left: compact note list -----------------------------------------
        left = QVBoxLayout()
        left.addWidget(QLabel("Notes"))
        self._list = QListWidget()
        self._list.setMaximumWidth(240)
        self._list.currentItemChanged.connect(self._on_selected)
        left.addWidget(self._list)
        new_btn = QPushButton("+ New Note")
        new_btn.clicked.connect(self._clear_form)
        left.addWidget(new_btn)
        root.addLayout(left)

        # -- Right: editor + compact link area -------------------------------
        right = QVBoxLayout()

        self._form_label = QLabel("New Note")
        self._form_label.setStyleSheet("font-weight: bold;")
        right.addWidget(self._form_label)

        right.addWidget(QLabel("Title"))
        self._title_input = QLineEdit()
        right.addWidget(self._title_input)

        right.addWidget(QLabel("Content"))
        self._content_input = QPlainTextEdit()
        right.addWidget(self._content_input, stretch=1)

        right.addWidget(QLabel("Tags (comma-separated)"))
        self._tags_input = QLineEdit()
        self._tags_input.setPlaceholderText("e.g. worldbuilding, magic, backstory")
        right.addWidget(self._tags_input)

        self._pinned_check = QCheckBox(
            "Pinned (always include in Assistant context)"
        )
        right.addWidget(self._pinned_check)

        # -- "Linked to" — compact, removable chips --------------------------
        link_header = QHBoxLayout()
        lk = QLabel("Linked to")
        lk.setStyleSheet(f"color: {theme.TEXT_MUTED}; font-weight: bold;")
        link_header.addWidget(lk)
        link_header.addStretch()
        self._link_btn = QPushButton("Link to…")
        self._link_btn.clicked.connect(self._on_link_to)
        link_header.addWidget(self._link_btn)
        right.addLayout(link_header)

        self._links_list = QListWidget()
        self._links_list.setObjectName("noteLinksList")
        self._links_list.setFlow(QListWidget.Flow.LeftToRight)
        self._links_list.setWrapping(True)
        self._links_list.setResizeMode(QListWidget.ResizeMode.Adjust)
        self._links_list.setSpacing(4)
        self._links_list.setMaximumHeight(96)
        self._links_list.setSelectionMode(
            QListWidget.SelectionMode.NoSelection,
        )
        self._links_list.setStyleSheet(
            "QListWidget#noteLinksList { background: transparent; border: none; }"
        )
        self._empty_links = QLabel("No links yet — use “Link to…”.")
        self._empty_links.setStyleSheet(
            f"color: {theme.TEXT_MUTED}; font-style: italic; font-size: 11px;"
        )
        right.addWidget(self._empty_links)
        right.addWidget(self._links_list)

        # -- Controls --------------------------------------------------------
        controls = QHBoxLayout()
        save_btn = QPushButton("Save")
        save_btn.clicked.connect(self._on_save)
        controls.addWidget(save_btn)
        self._delete_btn = QPushButton("Delete")
        self._delete_btn.setEnabled(False)
        self._delete_btn.clicked.connect(self._on_delete)
        controls.addWidget(self._delete_btn)
        controls.addStretch()
        right.addLayout(controls)

        root.addLayout(right, stretch=1)

        self._refresh_list()
        self._refresh_links()

    # -- List ----------------------------------------------------------------

    def _refresh_list(self) -> None:
        self._list.blockSignals(True)
        self._list.clear()
        for note in self._db.get_all_notes(self._project_id):
            label = note.title or "Untitled"
            if note.pinned:
                label = f"📌 {label}"
            item = QListWidgetItem(label)
            item.setData(USER_ROLE, note.id)
            self._list.addItem(item)
        self._list.blockSignals(False)

    def refresh(self) -> None:
        self._refresh_list()
        self._refresh_links()

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
        self._refresh_links()

    # -- Save / Delete -------------------------------------------------------

    def _on_save(self) -> None:
        title = self._title_input.text().strip()
        if not title:
            return
        content = self._content_input.toPlainText().strip()
        tags = self._tags_input.text().strip()
        pinned = self._pinned_check.isChecked()

        if self._selected_id is not None:
            self._db.update_note(
                self._selected_id, title, content, tags=tags, pinned=pinned,
            )
        else:
            note = self._db.create_note(
                self._project_id, title, content, tags=tags, pinned=pinned,
            )
            self._selected_id = note.id

        # Keep the saved note selected so it can be linked immediately.
        self._form_label.setText("Edit Note")
        self._delete_btn.setEnabled(True)
        self._refresh_list()
        self.select_note(self._selected_id)
        if self._on_data_changed:
            self._on_data_changed()

    def _on_delete(self) -> None:
        if self._selected_id is None:
            return
        note = self._db.get_note_by_id(self._selected_id)
        name = note.title if note else "this note"
        if QMessageBox.question(
            self, "Delete Note", f"Delete “{name}”? This cannot be undone.",
        ) != QMessageBox.StandardButton.Yes:
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
        self._list.clearSelection()
        self._refresh_links()

    # -- Linked-to chips -----------------------------------------------------

    def _collect_links(self) -> list[dict]:
        """Aggregate a note's links (act/chapter/scene/psyke) into uniform chip
        descriptors; targets that no longer exist are flagged ``missing``."""
        if self._selected_id is None:
            return []
        from storyplanner.story_structure import note_link_label
        out: list[dict] = []
        for ttype, ref in self._db.get_note_structure_links(self._selected_id):
            label, missing = note_link_label(
                self._db, self._project_id, ttype, ref)
            out.append({"kind": ttype, "ref": ref,
                        "label": label, "missing": missing})
        for sid in self._db.get_note_scene_links(self._selected_id):
            label, missing = note_link_label(
                self._db, self._project_id, "scene", sid)
            out.append({"kind": "scene", "ref": sid,
                        "label": label, "missing": missing})
        for eid in self._db.get_note_psyke_links(self._selected_id):
            entry = self._db.get_psyke_entry_by_id(eid)
            out.append({
                "kind": "psyke", "ref": eid,
                "label": f"PSYKE: {entry.name}" if entry else "PSYKE: (missing)",
                "missing": entry is None,
            })
        return out

    def _refresh_links(self) -> None:
        self._links_list.clear()
        links = self._collect_links()
        has = bool(links)
        self._empty_links.setVisible(not has and self._selected_id is not None)
        self._link_btn.setEnabled(self._selected_id is not None)
        for link in links:
            text = link["label"] + ("  (missing)" if link["missing"] else "")
            chip = QPushButton(f"{text}   ✕")
            chip.setCursor(Qt.CursorShape.PointingHandCursor)
            chip.setToolTip("Remove link")
            border = theme.TEXT_MUTED if link["missing"] else theme.BORDER
            chip.setStyleSheet(
                f"QPushButton {{ color: {theme.TEXT_PRIMARY}; font-size: 11px;"
                f" border: 1px solid {border}; border-radius: 10px;"
                f" padding: 2px 8px; background: {theme.BG_PANEL}; }}"
                f"QPushButton:hover {{ border-color: {theme.ACCENT}; }}"
            )
            chip.clicked.connect(
                lambda _=False, ln=link: self._remove_link(ln),
            )
            item = QListWidgetItem()
            item.setSizeHint(chip.sizeHint())
            self._links_list.addItem(item)
            self._links_list.setItemWidget(item, chip)

    def _remove_link(self, link: dict) -> None:
        if self._selected_id is None:
            return
        kind, ref = link["kind"], link["ref"]
        if kind in ("act", "chapter"):
            self._db.remove_note_structure_link(self._selected_id, kind, ref)
        elif kind == "scene":
            self._db.unlink_note_from_scene(self._selected_id, ref)
        elif kind == "psyke":
            self._db.unlink_note_from_psyke(self._selected_id, ref)
        self._refresh_links()
        if self._on_data_changed:
            self._on_data_changed()

    # -- "Link to…" menu -----------------------------------------------------

    def _on_link_to(self) -> None:
        if self._selected_id is None:
            QMessageBox.information(
                self, "Link to…", "Save the note first, then add links.",
            )
            return
        menu = QMenu(self)

        acts = self._db.get_scene_acts(self._project_id)
        act_menu = menu.addMenu("Act")
        act_menu.setEnabled(bool(acts))
        for act in acts:
            act_menu.addAction(
                act, lambda a=act: self._add_structure("act", a),
            )

        chapters = self._db.get_scene_chapters(self._project_id)
        chap_menu = menu.addMenu("Chapter")
        chap_menu.setEnabled(bool(chapters))
        for ch in chapters:
            chap_menu.addAction(
                ch, lambda c=ch: self._add_structure("chapter", c),
            )

        scenes = self._db.get_all_scenes(self._project_id)
        scene_menu = menu.addMenu("Scene")
        scene_menu.setEnabled(bool(scenes))
        for scene in scenes:
            scene_menu.addAction(
                scene.title or "Untitled",
                lambda s=scene.id: self._add_scene(s),
            )

        entries = self._db.get_all_psyke_entries(self._project_id)
        psyke_menu = menu.addMenu("PSYKE")
        psyke_menu.setEnabled(bool(entries))
        for entry in entries:
            psyke_menu.addAction(
                f"{entry.name} ({entry.entry_type})",
                lambda e=entry.id: self._add_psyke(e),
            )

        menu.exec(self._link_btn.mapToGlobal(
            self._link_btn.rect().bottomLeft(),
        ))

    def _add_structure(self, ttype: str, ref: str) -> None:
        if self._selected_id is None:
            return
        self._db.add_note_structure_link(
            self._selected_id, self._project_id, ttype, ref,
        )
        self._after_link()

    def _add_scene(self, scene_id: int) -> None:
        if self._selected_id is None:
            return
        self._db.link_note_to_scene(self._selected_id, scene_id)
        self._after_link()

    def _add_psyke(self, entry_id: int) -> None:
        if self._selected_id is None:
            return
        self._db.link_note_to_psyke(self._selected_id, entry_id)
        self._after_link()

    def _after_link(self) -> None:
        self._refresh_links()
        if self._on_data_changed:
            self._on_data_changed()
