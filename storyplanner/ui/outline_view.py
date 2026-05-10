"""Outline view — editable story structure with template presets."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from storyplanner.db import Database
from storyplanner.outline_templates import OUTLINE_TEMPLATES, list_templates
from storyplanner.ui import theme

_NODE_ID_ROLE = Qt.ItemDataRole.UserRole


class OutlineView(QWidget):
    def __init__(
        self,
        db: Database,
        project_id: int,
        on_data_changed: Callable[[], None] | None = None,
    ) -> None:
        super().__init__()
        self._db = db
        self._project_id = project_id
        self._on_data_changed = on_data_changed
        self._current_node_id: int | None = None
        self._suppress = False

        self._save_timer = QTimer()
        self._save_timer.setSingleShot(True)
        self._save_timer.setInterval(300)
        self._save_timer.timeout.connect(self._flush_description)

        self._build_ui()
        self._load_outline()

    # -- Layout ----------------------------------------------------------------

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # -- Toolbar -----------------------------------------------------------
        toolbar = QWidget()
        toolbar.setObjectName("outlineToolbar")
        tb = QHBoxLayout(toolbar)
        tb.setContentsMargins(12, 8, 12, 8)
        tb.setSpacing(8)

        tb.addWidget(QLabel("Template:"))
        self._template_combo = QComboBox()
        self._template_combo.addItem("Choose a template…", userData="")
        for key, name, desc in list_templates():
            self._template_combo.addItem(name, userData=key)
            self._template_combo.setItemData(
                self._template_combo.count() - 1, desc, Qt.ItemDataRole.ToolTipRole,
            )
        tb.addWidget(self._template_combo)

        apply_btn = QPushButton("Apply")
        apply_btn.setToolTip("Replace outline with the selected template")
        apply_btn.clicked.connect(self._apply_template)
        tb.addWidget(apply_btn)

        tb.addSpacing(16)

        add_section_btn = QPushButton("+ Section")
        add_section_btn.setToolTip("Add a top-level section (act / part)")
        add_section_btn.clicked.connect(self._add_section)
        tb.addWidget(add_section_btn)

        add_beat_btn = QPushButton("+ Beat")
        add_beat_btn.setToolTip("Add a beat under the selected section")
        add_beat_btn.clicked.connect(self._add_beat)
        tb.addWidget(add_beat_btn)

        delete_btn = QPushButton("Delete")
        delete_btn.clicked.connect(self._delete_node)
        tb.addWidget(delete_btn)

        tb.addSpacing(8)

        up_btn = QPushButton("▲")
        up_btn.setFixedWidth(28)
        up_btn.setToolTip("Move up")
        up_btn.clicked.connect(self._move_up)
        tb.addWidget(up_btn)

        down_btn = QPushButton("▼")
        down_btn.setFixedWidth(28)
        down_btn.setToolTip("Move down")
        down_btn.clicked.connect(self._move_down)
        tb.addWidget(down_btn)

        tb.addStretch()

        export_btn = QPushButton("Export")
        export_btn.clicked.connect(self._export_outline)
        tb.addWidget(export_btn)

        root.addWidget(toolbar)

        # -- Splitter: tree + editor -------------------------------------------
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left: tree
        self._tree = QTreeWidget()
        self._tree.setHeaderHidden(True)
        self._tree.setIndentation(20)
        self._tree.setMinimumWidth(200)
        self._tree.currentItemChanged.connect(self._on_item_selected)
        self._tree.setStyleSheet(
            f"QTreeWidget {{ border: none; background: {theme.BG_DARK}; }}"
            f"QTreeWidget::item {{ padding: 4px 6px; }}"
            f"QTreeWidget::item:selected {{"
            f"  background: {theme.ACCENT}; color: #ffffff;"
            f"}}"
        )
        splitter.addWidget(self._tree)

        # Right: editor
        editor = QWidget()
        editor.setMinimumWidth(300)
        ed = QVBoxLayout(editor)
        ed.setContentsMargins(16, 16, 16, 16)
        ed.setSpacing(10)

        self._editor_label = QLabel("Select or create a section to begin")
        label_font = QFont()
        label_font.setBold(True)
        self._editor_label.setFont(label_font)
        self._editor_label.setStyleSheet(f"color: {theme.TEXT_SECONDARY};")
        ed.addWidget(self._editor_label)

        title_label = QLabel("Title")
        title_label.setStyleSheet(f"color: {theme.TEXT_SECONDARY}; font-size: 11px;")
        ed.addWidget(title_label)

        self._title_input = QLineEdit()
        self._title_input.setPlaceholderText("Beat title")
        self._title_input.textChanged.connect(self._on_title_changed)
        ed.addWidget(self._title_input)

        desc_label = QLabel("Description")
        desc_label.setStyleSheet(f"color: {theme.TEXT_SECONDARY}; font-size: 11px;")
        ed.addWidget(desc_label)

        self._desc_input = QPlainTextEdit()
        self._desc_input.setPlaceholderText(
            "Write your outline notes, scene ideas, or structure plan…"
        )
        self._desc_input.textChanged.connect(self._on_desc_changed)
        self._desc_input.setStyleSheet(
            f"QPlainTextEdit {{"
            f"  background-color: {theme.BG_PANEL};"
            f"  color: {theme.TEXT_PRIMARY};"
            f"  border: 1px solid {theme.BORDER};"
            f"  border-radius: 4px; padding: 8px;"
            f"}}"
        )
        ed.addWidget(self._desc_input, stretch=1)

        splitter.addWidget(editor)
        splitter.setSizes([280, 520])
        root.addWidget(splitter, stretch=1)

        self._set_editor_enabled(False)

    # -- Tree operations -------------------------------------------------------

    def refresh(self) -> None:
        self._load_outline()

    def _load_outline(self) -> None:
        self._tree.clear()
        nodes = self._db.get_outline_nodes(self._project_id)

        children_map: dict[int | None, list] = {}
        for node in nodes:
            children_map.setdefault(node.parent_id, []).append(node)

        self._populate_tree(None, children_map, None)
        self._tree.expandAll()

        if self._tree.topLevelItemCount() == 0:
            self._current_node_id = None
            self._set_editor_enabled(False)

    def _populate_tree(
        self,
        parent_id: int | None,
        children_map: dict[int | None, list],
        parent_item: QTreeWidgetItem | None,
    ) -> None:
        children = children_map.get(parent_id, [])
        children.sort(key=lambda n: (n.sort_order, n.id))

        for node in children:
            item = QTreeWidgetItem()
            item.setText(0, node.title)
            item.setData(0, _NODE_ID_ROLE, node.id)

            if parent_id is None:
                font = item.font(0)
                font.setBold(True)
                item.setFont(0, font)

            if parent_item is None:
                self._tree.addTopLevelItem(item)
            else:
                parent_item.addChild(item)

            self._populate_tree(node.id, children_map, item)

    def _find_tree_item(self, node_id: int) -> QTreeWidgetItem | None:
        def _search(parent_item: QTreeWidgetItem | None) -> QTreeWidgetItem | None:
            count = (
                parent_item.childCount()
                if parent_item
                else self._tree.topLevelItemCount()
            )
            for i in range(count):
                child = (
                    parent_item.child(i)
                    if parent_item
                    else self._tree.topLevelItem(i)
                )
                if child.data(0, _NODE_ID_ROLE) == node_id:
                    return child
                found = _search(child)
                if found:
                    return found
            return None

        return _search(None)

    def _select_node(self, node_id: int) -> None:
        item = self._find_tree_item(node_id)
        if item:
            self._tree.setCurrentItem(item)

    # -- Editor ----------------------------------------------------------------

    def _set_editor_enabled(self, enabled: bool) -> None:
        self._title_input.setEnabled(enabled)
        self._desc_input.setEnabled(enabled)
        if not enabled:
            self._suppress = True
            self._title_input.clear()
            self._desc_input.clear()
            self._editor_label.setText("Select or create a section to begin")
            self._suppress = False

    def _on_item_selected(
        self, current: QTreeWidgetItem | None, _prev: QTreeWidgetItem | None,
    ) -> None:
        if current is None:
            self._current_node_id = None
            self._set_editor_enabled(False)
            return

        node_id = current.data(0, _NODE_ID_ROLE)
        self._current_node_id = node_id
        node = self._db.get_outline_node_by_id(node_id)
        if node is None:
            self._set_editor_enabled(False)
            return

        self._suppress = True
        self._set_editor_enabled(True)
        self._title_input.setText(node.title)
        self._desc_input.setPlainText(node.description)
        is_section = current.parent() is None
        self._editor_label.setText("Section" if is_section else "Beat")
        self._suppress = False

    def _on_title_changed(self, text: str) -> None:
        if self._suppress or self._current_node_id is None:
            return
        self._db.update_outline_node(self._current_node_id, title=text)
        current = self._tree.currentItem()
        if current:
            current.setText(0, text)
        self._notify()

    def _on_desc_changed(self) -> None:
        if self._suppress or self._current_node_id is None:
            return
        self._save_timer.start()

    def _flush_description(self) -> None:
        if self._current_node_id is None:
            return
        self._db.update_outline_node(
            self._current_node_id,
            description=self._desc_input.toPlainText(),
        )
        self._notify()

    # -- Add / delete ----------------------------------------------------------

    def _add_section(self) -> None:
        siblings = self._db.get_outline_children(self._project_id, None)
        node = self._db.create_outline_node(
            self._project_id, "New Section",
            parent_id=None, sort_order=len(siblings),
        )
        self._load_outline()
        self._select_node(node.id)
        self._title_input.selectAll()
        self._title_input.setFocus()
        self._notify()

    def _add_beat(self) -> None:
        current = self._tree.currentItem()
        if current is None:
            self._add_section()
            return

        section_item = current
        while section_item.parent() is not None:
            section_item = section_item.parent()
        parent_id = section_item.data(0, _NODE_ID_ROLE)

        siblings = self._db.get_outline_children(self._project_id, parent_id)
        node = self._db.create_outline_node(
            self._project_id, "New Beat",
            parent_id=parent_id, sort_order=len(siblings),
        )
        self._load_outline()
        self._select_node(node.id)
        self._title_input.selectAll()
        self._title_input.setFocus()
        self._notify()

    def _delete_node(self) -> None:
        current = self._tree.currentItem()
        if current is None:
            return
        node_id = current.data(0, _NODE_ID_ROLE)
        has_children = current.childCount() > 0
        msg = (
            "Delete this section and all its beats?"
            if has_children
            else "Delete this item?"
        )
        answer = QMessageBox.question(
            self, "Delete", msg,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return

        self._db.delete_outline_node(node_id)
        self._current_node_id = None
        self._load_outline()
        self._set_editor_enabled(False)
        self._notify()

    # -- Reorder ---------------------------------------------------------------

    def _move_up(self) -> None:
        self._swap_sibling(-1)

    def _move_down(self) -> None:
        self._swap_sibling(1)

    def _swap_sibling(self, direction: int) -> None:
        current = self._tree.currentItem()
        if current is None:
            return
        node_id = current.data(0, _NODE_ID_ROLE)
        node = self._db.get_outline_node_by_id(node_id)
        if node is None:
            return

        siblings = self._db.get_outline_children(self._project_id, node.parent_id)
        siblings.sort(key=lambda n: (n.sort_order, n.id))
        idx = next((i for i, n in enumerate(siblings) if n.id == node_id), -1)
        target = idx + direction
        if idx < 0 or target < 0 or target >= len(siblings):
            return

        other = siblings[target]
        self._db.update_outline_node(node_id, sort_order=other.sort_order)
        self._db.update_outline_node(other.id, sort_order=node.sort_order)
        if node.sort_order == other.sort_order:
            self._db.update_outline_node(node_id, sort_order=target)
            self._db.update_outline_node(other.id, sort_order=idx)
        self._load_outline()
        self._select_node(node_id)
        self._notify()

    # -- Templates -------------------------------------------------------------

    def _apply_template(self) -> None:
        key = self._template_combo.currentData()
        if not key:
            return
        template = OUTLINE_TEMPLATES.get(key)
        if not template:
            return

        existing = self._db.get_outline_nodes(self._project_id)
        if existing:
            answer = QMessageBox.question(
                self,
                "Apply Template",
                f"Apply “{template.name}” template?\n\n"
                "This will replace the current outline structure.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                return

        self._db.delete_all_outline_nodes(self._project_id)

        def create_beats(beats, parent_id: int | None) -> None:
            for i, beat in enumerate(beats):
                node = self._db.create_outline_node(
                    self._project_id, beat.title, beat.description,
                    parent_id=parent_id, sort_order=i,
                )
                if beat.children:
                    create_beats(beat.children, node.id)

        create_beats(template.beats, None)

        self._load_outline()
        self._template_combo.setCurrentIndex(0)
        self._notify()

    # -- Export ----------------------------------------------------------------

    def _export_outline(self) -> None:
        nodes = self._db.get_outline_nodes(self._project_id)
        if not nodes:
            QMessageBox.information(self, "Export", "No outline to export.")
            return

        path, selected = QFileDialog.getSaveFileName(
            self, "Export Outline", "",
            "Markdown (*.md);;Text (*.txt)",
        )
        if not path:
            return

        is_md = "Markdown" in selected or path.endswith(".md")
        if not path.endswith((".md", ".txt")):
            path += ".md" if is_md else ".txt"

        children_map: dict[int | None, list] = {}
        for node in nodes:
            children_map.setdefault(node.parent_id, []).append(node)

        project = self._db.get_project_by_id(self._project_id)
        title = project.title if project else "Untitled"

        lines: list[str] = []
        if is_md:
            lines.append(f"# {title} — Story Outline")
        else:
            header = f"{title} — Story Outline"
            lines.append(header)
            lines.append("=" * len(header))
        lines.append("")

        def write_nodes(parent_id: int | None, depth: int) -> None:
            children = children_map.get(parent_id, [])
            children.sort(key=lambda n: (n.sort_order, n.id))
            for node in children:
                if is_md:
                    prefix = "#" * (depth + 2)
                    lines.append(f"{prefix} {node.title}")
                else:
                    indent = "  " * depth
                    lines.append(f"{indent}{node.title}")
                if node.description:
                    lines.append("")
                    if is_md:
                        lines.append(node.description)
                    else:
                        pad = "  " * (depth + 1)
                        for line in node.description.split("\n"):
                            lines.append(f"{pad}{line}")
                lines.append("")
                write_nodes(node.id, depth + 1)

        write_nodes(None, 0)

        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        QMessageBox.information(self, "Export", f"Outline exported to {path}")

    # -- Helpers ---------------------------------------------------------------

    def _notify(self) -> None:
        if self._on_data_changed:
            self._on_data_changed()
