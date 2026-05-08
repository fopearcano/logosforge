"""Plan view — hierarchical Acts → Chapters → Scenes outline.

Acts and Chapters are derived from Scene.act and Scene.chapter string fields.
Renaming an act/chapter updates all scenes that share that label.
Summaries for acts and chapters live in the project's settings_json under
`act_summaries` and `chapter_summaries` keyed by the act/chapter name.
Scene summaries live on Scene.summary.
"""

from collections.abc import Callable

from PySide6.QtCore import Qt, QMimeData, QSize
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QAbstractItemView,
    QButtonGroup,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QListView,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from storyplanner.db import Database
from storyplanner.quantum_outliner.state import OutlineMode, get_outline_mode
from storyplanner.ui import theme


_UNTITLED_ACT = "Untitled Act"
_UNTITLED_CHAPTER = "Untitled Chapter"


def _act_key(name: str) -> str:
    return "" if name == _UNTITLED_ACT else name


def _chapter_key(name: str) -> str:
    return "" if name == _UNTITLED_CHAPTER else name


def _act_summaries(db: Database, project_id: int) -> dict[str, str]:
    settings = db.get_project_settings(project_id)
    raw = settings.get("act_summaries", {})
    return raw if isinstance(raw, dict) else {}


def _chapter_summaries(db: Database, project_id: int) -> dict[str, str]:
    settings = db.get_project_settings(project_id)
    raw = settings.get("chapter_summaries", {})
    return raw if isinstance(raw, dict) else {}


def _save_act_summary(db: Database, project_id: int, act: str, summary: str) -> None:
    settings = db.get_project_settings(project_id)
    summaries = dict(settings.get("act_summaries", {}) or {})
    if summary:
        summaries[act] = summary
    else:
        summaries.pop(act, None)
    settings["act_summaries"] = summaries
    db.save_project_settings(project_id, settings)


def _save_chapter_summary(
    db: Database, project_id: int, chapter: str, summary: str,
) -> None:
    settings = db.get_project_settings(project_id)
    summaries = dict(settings.get("chapter_summaries", {}) or {})
    if summary:
        summaries[chapter] = summary
    else:
        summaries.pop(chapter, None)
    settings["chapter_summaries"] = summaries
    db.save_project_settings(project_id, settings)


def _rename_act(db: Database, project_id: int, old: str, new: str) -> None:
    if old == new or not new:
        return
    for scene in db.get_all_scenes(project_id):
        if scene.act == old:
            db.update_scene(
                scene_id=scene.id,
                title=scene.title,
                summary=scene.summary,
                synopsis=scene.synopsis,
                goal=scene.goal,
                conflict=scene.conflict,
                outcome=scene.outcome,
                beat=scene.beat,
                tags=scene.tags,
                act=new,
                content=scene.content,
                chapter=scene.chapter,
                plotline=scene.plotline,
            )
    settings = db.get_project_settings(project_id)
    summaries = dict(settings.get("act_summaries", {}) or {})
    if old in summaries:
        summaries[new] = summaries.pop(old)
        settings["act_summaries"] = summaries
        db.save_project_settings(project_id, settings)


def _rename_chapter(db: Database, project_id: int, old: str, new: str) -> None:
    if old == new or not new:
        return
    for scene in db.get_all_scenes(project_id):
        if scene.chapter == old:
            db.update_scene(
                scene_id=scene.id,
                title=scene.title,
                summary=scene.summary,
                synopsis=scene.synopsis,
                goal=scene.goal,
                conflict=scene.conflict,
                outcome=scene.outcome,
                beat=scene.beat,
                tags=scene.tags,
                act=scene.act,
                content=scene.content,
                chapter=new,
                plotline=scene.plotline,
            )
    settings = db.get_project_settings(project_id)
    summaries = dict(settings.get("chapter_summaries", {}) or {})
    if old in summaries:
        summaries[new] = summaries.pop(old)
        settings["chapter_summaries"] = summaries
        db.save_project_settings(project_id, settings)


def _delete_act(db: Database, project_id: int, act: str) -> None:
    """Clear the act label from all scenes with this act and remove summary."""
    for scene in db.get_all_scenes(project_id):
        if scene.act == act:
            db.update_scene(
                scene_id=scene.id,
                title=scene.title,
                summary=scene.summary,
                synopsis=scene.synopsis,
                goal=scene.goal,
                conflict=scene.conflict,
                outcome=scene.outcome,
                beat=scene.beat,
                tags=scene.tags,
                act="",
                content=scene.content,
                chapter=scene.chapter,
                plotline=scene.plotline,
            )
    settings = db.get_project_settings(project_id)
    summaries = dict(settings.get("act_summaries", {}) or {})
    summaries.pop(act, None)
    settings["act_summaries"] = summaries
    db.save_project_settings(project_id, settings)


def _delete_chapter(db: Database, project_id: int, chapter: str) -> None:
    for scene in db.get_all_scenes(project_id):
        if scene.chapter == chapter:
            db.update_scene(
                scene_id=scene.id,
                title=scene.title,
                summary=scene.summary,
                synopsis=scene.synopsis,
                goal=scene.goal,
                conflict=scene.conflict,
                outcome=scene.outcome,
                beat=scene.beat,
                tags=scene.tags,
                act=scene.act,
                content=scene.content,
                chapter="",
                plotline=scene.plotline,
            )
    settings = db.get_project_settings(project_id)
    summaries = dict(settings.get("chapter_summaries", {}) or {})
    summaries.pop(chapter, None)
    settings["chapter_summaries"] = summaries
    db.save_project_settings(project_id, settings)


def build_plan_tree(
    db: Database, project_id: int,
) -> list[tuple[str, list[tuple[str, list]]]]:
    """Return [(act_name, [(chapter_name, [scene, ...]), ...]), ...].

    Acts and chapters preserve their first-seen order in scene sort_order.
    Scenes without an act fall under _UNTITLED_ACT, similarly for chapter.
    """
    scenes = db.get_all_scenes(project_id)
    act_order: list[str] = []
    chapter_order: dict[str, list[str]] = {}
    grouped: dict[str, dict[str, list]] = {}

    for scene in scenes:
        act = scene.act or _UNTITLED_ACT
        chapter = scene.chapter or _UNTITLED_CHAPTER
        if act not in grouped:
            grouped[act] = {}
            act_order.append(act)
            chapter_order[act] = []
        if chapter not in grouped[act]:
            grouped[act][chapter] = []
            chapter_order[act].append(chapter)
        grouped[act][chapter].append(scene)

    return [
        (
            act,
            [(ch, grouped[act][ch]) for ch in chapter_order[act]],
        )
        for act in act_order
    ]


class _SummaryEditor(QPlainTextEdit):
    """Compact summary text box that auto-saves on focus-out."""

    def __init__(
        self,
        text: str,
        on_commit: Callable[[str], None],
        placeholder: str = "Add a summary…",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setPlainText(text)
        self.setPlaceholderText(placeholder)
        self.setFixedHeight(56)
        self.setStyleSheet(
            f"QPlainTextEdit {{ background: {theme.BG_INPUT}; "
            f"color: {theme.TEXT_PRIMARY}; border: 1px solid {theme.BORDER}; "
            "border-radius: 4px; padding: 4px 6px; font-size: 11px; }}"
        )
        self._on_commit = on_commit
        self._initial = text

    def focusOutEvent(self, event) -> None:
        super().focusOutEvent(event)
        new_text = self.toPlainText().strip()
        if new_text != self._initial.strip():
            self._initial = new_text
            self._on_commit(new_text)


class _SceneGrid(QListWidget):
    """Flat 4-column grid of scene cards with drag-to-reorder.

    Scenes are displayed as squared blocks in IconMode with wrapping enabled,
    flowing left-to-right and wrapping after 4 cards per row. Internal drag
    reorders the items; the new order is persisted via on_reorder.
    """

    def __init__(
        self,
        scenes: list,
        on_reorder,
        on_open_scene,
        on_scene_menu,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._on_reorder = on_reorder
        self._on_open_scene = on_open_scene
        self._on_scene_menu = on_scene_menu
        self._suppress_reorder = True

        self.setViewMode(QListView.ViewMode.IconMode)
        self.setFlow(QListView.Flow.LeftToRight)
        self.setWrapping(True)
        self.setResizeMode(QListView.ResizeMode.Adjust)
        self.setMovement(QListView.Movement.Snap)
        self.setSpacing(8)
        self.setUniformItemSizes(True)
        self.setGridSize(QSize(160, 160))
        self.setIconSize(QSize(140, 140))
        self.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setWordWrap(True)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.setStyleSheet(
            f"QListWidget {{ background: transparent; border: none;"
            f" color: {theme.TEXT_PRIMARY}; }}"
            f"QListWidget::item {{ background: {theme.BG_PANEL};"
            f" color: {theme.TEXT_PRIMARY};"
            f" border: 1px solid {theme.BORDER}; border-radius: 6px;"
            " padding: 8px; font-size: 11px;"
            " text-align: center; }"
            f"QListWidget::item:selected {{ border-color: {theme.ACCENT};"
            f" background: {theme.BG_HOVER}; }}"
            f"QListWidget::item:hover {{ border-color: {theme.ACCENT}; }}"
        )

        for scene in scenes:
            item = QListWidgetItem(self._format_label(scene))
            item.setData(Qt.ItemDataRole.UserRole, scene.id)
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            tooltip = scene.summary or scene.title or "Untitled"
            item.setToolTip(tooltip)
            self.addItem(item)

        self.itemDoubleClicked.connect(self._open_card)
        self.customContextMenuRequested.connect(self._on_context_menu)
        self.model().rowsMoved.connect(self._on_rows_moved)
        self._suppress_reorder = False

    @staticmethod
    def _format_label(scene) -> str:
        title = scene.title or "Untitled"
        location: list[str] = []
        if scene.act:
            location.append(scene.act)
        if scene.chapter:
            location.append(scene.chapter)
        if location:
            return f"{title}\n\n{' · '.join(location)}"
        return title

    def _open_card(self, item: QListWidgetItem) -> None:
        if self._on_open_scene is not None:
            self._on_open_scene(item.data(Qt.ItemDataRole.UserRole))

    def _on_context_menu(self, pos) -> None:
        item = self.itemAt(pos)
        if item is None or self._on_scene_menu is None:
            return
        scene_id = item.data(Qt.ItemDataRole.UserRole)
        self._on_scene_menu(self, scene_id, self.mapToGlobal(pos))

    def _on_rows_moved(self, *_args) -> None:
        if self._suppress_reorder or self._on_reorder is None:
            return
        ordered_ids = [
            self.item(i).data(Qt.ItemDataRole.UserRole)
            for i in range(self.count())
        ]
        self._on_reorder(ordered_ids)


class PlanView(QWidget):
    """Hierarchical Acts → Chapters → Scenes plan view."""

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
        self._view_mode = "list"

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 12, 16, 12)
        root.setSpacing(8)

        header_row = QHBoxLayout()
        title = QLabel("Outline")
        title.setStyleSheet(
            f"font-size: 18px; font-weight: bold; color: {theme.TEXT_PRIMARY};"
        )
        header_row.addWidget(title)

        self._mode_badge = QLabel("")
        self._mode_badge.setObjectName("planModeBadge")
        header_row.addWidget(self._mode_badge)
        self._refresh_mode_badge()

        header_row.addSpacing(16)
        self._mode_group = QButtonGroup(self)
        self._mode_group.setExclusive(True)
        for mode_key, label in (("list", "List"), ("grid", "Grid"), ("matrix", "Matrix")):
            btn = QPushButton(label)
            btn.setCheckable(True)
            btn.setChecked(mode_key == self._view_mode)
            btn.setStyleSheet(
                f"QPushButton {{ padding: 4px 12px; font-size: 11px;"
                f" border: 1px solid {theme.BORDER}; background: transparent;"
                f" color: {theme.TEXT_MUTED}; }}"
                f"QPushButton:checked {{ background: {theme.ACCENT};"
                f" color: #ffffff; border-color: {theme.ACCENT}; }}"
            )
            btn.clicked.connect(lambda _c=False, k=mode_key: self._set_view_mode(k))
            self._mode_group.addButton(btn)
            header_row.addWidget(btn)

        header_row.addStretch()

        add_act_btn = QPushButton("+ Add Act")
        add_act_btn.clicked.connect(self._add_act)
        header_row.addWidget(add_act_btn)
        root.addLayout(header_row)

        self._stack = QStackedWidget()
        root.addWidget(self._stack, stretch=1)

        # List view (existing scrollable hierarchy)
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff,
        )
        self._scroll.setStyleSheet("QScrollArea { border: none; }")
        self._content = QWidget()
        self._content_layout = QVBoxLayout(self._content)
        self._content_layout.setContentsMargins(0, 0, 0, 0)
        self._content_layout.setSpacing(12)
        self._scroll.setWidget(self._content)
        self._stack.addWidget(self._scroll)

        # Grid view (flat 4-column scene grid with drag reorder)
        self._grid_canvas = QWidget()
        self._grid_layout = QVBoxLayout(self._grid_canvas)
        self._grid_layout.setContentsMargins(0, 0, 0, 0)
        self._grid_layout.setSpacing(0)
        self._grid_widget: _SceneGrid | None = None
        self._stack.addWidget(self._grid_canvas)

        # Matrix view (acts × chapters)
        self._matrix_scroll = QScrollArea()
        self._matrix_scroll.setWidgetResizable(True)
        self._matrix_scroll.setStyleSheet("QScrollArea { border: none; }")
        self._matrix_canvas = QWidget()
        self._matrix_layout = QGridLayout(self._matrix_canvas)
        self._matrix_layout.setContentsMargins(0, 0, 0, 0)
        self._matrix_layout.setHorizontalSpacing(8)
        self._matrix_layout.setVerticalSpacing(8)
        self._matrix_scroll.setWidget(self._matrix_canvas)
        self._stack.addWidget(self._matrix_scroll)

        self.refresh()

    def _set_view_mode(self, mode: str) -> None:
        if mode not in ("list", "grid", "matrix") or mode == self._view_mode:
            return
        self._view_mode = mode
        idx = {"list": 0, "grid": 1, "matrix": 2}[mode]
        self._stack.setCurrentIndex(idx)
        self.refresh()

    def refresh(self) -> None:
        self._refresh_mode_badge()
        if self._view_mode == "list":
            self._refresh_list()
        elif self._view_mode == "grid":
            self._refresh_grid()
        else:
            self._refresh_matrix()

    def _refresh_mode_badge(self) -> None:
        mode = get_outline_mode(self._project_id)
        if mode is OutlineMode.LAMBDA:
            self._mode_badge.setText("λ Lambda")
            self._mode_badge.setStyleSheet(
                f"color: {theme.ACCENT}; font-size: 10px;"
                f" font-weight: bold; background: transparent;"
                f" border: 1px solid {theme.ACCENT}; border-radius: 3px;"
                " padding: 2px 6px; margin-left: 8px;"
            )
        else:
            self._mode_badge.setText("Classical")
            self._mode_badge.setStyleSheet(
                f"color: {theme.TEXT_MUTED}; font-size: 10px;"
                f" background: transparent;"
                f" border: 1px solid {theme.BORDER}; border-radius: 3px;"
                " padding: 2px 6px; margin-left: 8px;"
            )

    def _refresh_list(self) -> None:
        while self._content_layout.count():
            item = self._content_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

        tree = build_plan_tree(self._db, self._project_id)
        act_summaries = _act_summaries(self._db, self._project_id)
        chapter_summaries = _chapter_summaries(self._db, self._project_id)

        if not tree:
            empty = QLabel(
                "No scenes yet. Add an act to start planning your story."
            )
            empty.setStyleSheet(
                f"color: {theme.TEXT_MUTED}; padding: 24px;"
            )
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._content_layout.addWidget(empty)
            self._content_layout.addStretch()
            return

        for act_name, chapters in tree:
            self._content_layout.addWidget(
                self._build_act_section(
                    act_name,
                    act_summaries.get(_act_key(act_name), ""),
                    chapters,
                    chapter_summaries,
                )
            )

        self._content_layout.addStretch()

    # -- Act section ----------------------------------------------------------

    def _build_act_section(
        self,
        act_name: str,
        act_summary: str,
        chapters: list[tuple[str, list]],
        chapter_summaries: dict[str, str],
    ) -> QWidget:
        section = QWidget()
        section.setStyleSheet(
            f"QWidget#planAct {{ background: {theme.BG_PANEL}; "
            f"border: 1px solid {theme.BORDER}; border-radius: 6px; }}"
        )
        section.setObjectName("planAct")

        layout = QVBoxLayout(section)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(6)

        head_row = QHBoxLayout()
        head_row.setSpacing(6)
        act_label = QLabel(f"Act — {act_name}")
        act_label.setStyleSheet(
            f"font-size: 14px; font-weight: bold; color: {theme.TEXT_PRIMARY};"
        )
        head_row.addWidget(act_label)
        head_row.addStretch()

        add_chap = QPushButton("+ Add Chapter")
        add_chap.clicked.connect(lambda: self._add_chapter(act_name))
        head_row.addWidget(add_chap)

        more = QPushButton("⋯")
        more.setFixedWidth(28)
        more.setToolTip("Edit Act")
        more.clicked.connect(lambda: self._show_act_menu(more, act_name))
        head_row.addWidget(more)

        layout.addLayout(head_row)

        summary_box = _SummaryEditor(
            act_summary,
            lambda text, a=act_name: self._save_act_summary(a, text),
            placeholder="Act summary…",
        )
        layout.addWidget(summary_box)

        for chapter_name, scenes in chapters:
            layout.addWidget(
                self._build_chapter_section(
                    act_name,
                    chapter_name,
                    chapter_summaries.get(_chapter_key(chapter_name), ""),
                    scenes,
                )
            )

        return section

    # -- Chapter section ------------------------------------------------------

    def _build_chapter_section(
        self,
        act_name: str,
        chapter_name: str,
        chapter_summary: str,
        scenes: list,
    ) -> QWidget:
        section = QWidget()
        section.setStyleSheet(
            f"QWidget#planChapter {{ background: {theme.BG_DARK}; "
            f"border: 1px solid {theme.BORDER}; border-radius: 4px; }}"
        )
        section.setObjectName("planChapter")

        layout = QVBoxLayout(section)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(4)

        head_row = QHBoxLayout()
        head_row.setSpacing(6)
        ch_label = QLabel(f"Chapter — {chapter_name}")
        ch_label.setStyleSheet(
            f"font-size: 12px; font-weight: bold; color: {theme.TEXT_PRIMARY};"
        )
        head_row.addWidget(ch_label)
        head_row.addStretch()

        add_scene = QPushButton("+ Add Scene")
        add_scene.clicked.connect(
            lambda: self._add_scene(act_name, chapter_name)
        )
        head_row.addWidget(add_scene)

        more = QPushButton("⋯")
        more.setFixedWidth(28)
        more.setToolTip("Edit Chapter")
        more.clicked.connect(
            lambda: self._show_chapter_menu(more, chapter_name)
        )
        head_row.addWidget(more)

        layout.addLayout(head_row)

        summary_box = _SummaryEditor(
            chapter_summary,
            lambda text, c=chapter_name: self._save_chapter_summary(c, text),
            placeholder="Chapter summary…",
        )
        layout.addWidget(summary_box)

        for scene in scenes:
            layout.addWidget(self._build_scene_row(scene))

        return section

    # -- Scene row ------------------------------------------------------------

    def _build_scene_row(self, scene) -> QWidget:
        row = QWidget()
        row.setStyleSheet(
            "QWidget#planScene { background: transparent; "
            f"border-left: 2px solid {theme.BORDER}; }}"
        )
        row.setObjectName("planScene")
        layout = QVBoxLayout(row)
        layout.setContentsMargins(8, 4, 4, 4)
        layout.setSpacing(2)

        head_row = QHBoxLayout()
        head_row.setSpacing(6)
        title = QLabel(scene.title or "Untitled Scene")
        title.setStyleSheet(
            f"font-size: 11px; color: {theme.TEXT_PRIMARY};"
        )
        head_row.addWidget(title)
        head_row.addStretch()

        more = QPushButton("⋯")
        more.setFixedWidth(24)
        more.setToolTip("Edit Scene")
        more.clicked.connect(lambda: self._show_scene_menu(more, scene.id))
        head_row.addWidget(more)

        layout.addLayout(head_row)

        summary_box = _SummaryEditor(
            scene.summary or "",
            lambda text, sid=scene.id: self._save_scene_summary(sid, text),
            placeholder="Scene summary…",
        )
        layout.addWidget(summary_box)

        return row

    # -- Grid view (flat 4-column movable scene blocks) -----------------------

    def _refresh_grid(self) -> None:
        while self._grid_layout.count():
            item = self._grid_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

        scenes = self._db.get_all_scenes(self._project_id)
        if not scenes:
            empty = QLabel("No scenes yet — add an act to begin.")
            empty.setStyleSheet(f"color: {theme.TEXT_MUTED}; padding: 24px;")
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._grid_layout.addWidget(empty)
            return

        self._grid_widget = _SceneGrid(
            scenes,
            on_reorder=self._on_grid_reordered,
            on_open_scene=self._on_open_scene,
            on_scene_menu=self._on_grid_card_menu,
        )
        self._grid_layout.addWidget(self._grid_widget)

    def _on_grid_reordered(self, ordered_scene_ids: list[int]) -> None:
        for new_index, scene_id in enumerate(ordered_scene_ids):
            self._db.reorder_scene(scene_id, new_index)
        self._notify()

    def _on_grid_card_menu(self, anchor: QWidget, scene_id: int, global_pos) -> None:
        menu = QMenu(anchor)
        if self._on_open_scene is not None:
            open_act = QAction("Open in Manuscript", menu)
            open_act.triggered.connect(
                lambda: self._on_open_scene(scene_id)
            )
            menu.addAction(open_act)
        rename = QAction("Rename Scene", menu)
        rename.triggered.connect(lambda: self._rename_scene_dialog(scene_id))
        menu.addAction(rename)
        delete = QAction("Delete Scene", menu)
        delete.triggered.connect(lambda: self._delete_scene_dialog(scene_id))
        menu.addAction(delete)
        menu.exec(global_pos)

    # -- Matrix view (acts × chapters) ----------------------------------------

    def _refresh_matrix(self) -> None:
        while self._matrix_layout.count():
            item = self._matrix_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

        tree = build_plan_tree(self._db, self._project_id)
        if not tree:
            empty = QLabel("No scenes yet — add an act to begin.")
            empty.setStyleSheet(f"color: {theme.TEXT_MUTED}; padding: 24px;")
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._matrix_layout.addWidget(empty, 0, 0)
            return

        all_chapters: list[str] = []
        seen: set[str] = set()
        for _act, chapters in tree:
            for chapter_name, _scenes in chapters:
                if chapter_name not in seen:
                    seen.add(chapter_name)
                    all_chapters.append(chapter_name)

        corner = QLabel("Acts ↓ / Chapters →")
        corner.setStyleSheet(
            f"color: {theme.TEXT_MUTED}; font-size: 10px;"
            " text-transform: uppercase; letter-spacing: 1px;"
        )
        self._matrix_layout.addWidget(corner, 0, 0)

        for col_idx, chapter_name in enumerate(all_chapters, start=1):
            header = QLabel(chapter_name)
            header.setStyleSheet(
                f"color: {theme.TEXT_PRIMARY}; font-size: 11px;"
                f" font-weight: bold; padding: 4px 8px;"
                f" background: {theme.BG_PANEL};"
                f" border: 1px solid {theme.BORDER}; border-radius: 4px;"
            )
            header.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._matrix_layout.addWidget(header, 0, col_idx)

        for row_idx, (act_name, chapters) in enumerate(tree, start=1):
            row_label = QLabel(act_name)
            row_label.setStyleSheet(
                f"color: {theme.TEXT_PRIMARY}; font-size: 11px;"
                f" font-weight: bold; padding: 4px 8px;"
                f" background: {theme.BG_PANEL};"
                f" border: 1px solid {theme.BORDER}; border-radius: 4px;"
            )
            self._matrix_layout.addWidget(row_label, row_idx, 0)

            chapters_for_act = {ch: scenes for ch, scenes in chapters}
            for col_idx, chapter_name in enumerate(all_chapters, start=1):
                scenes_in_cell = chapters_for_act.get(chapter_name, [])
                self._matrix_layout.addWidget(
                    self._build_matrix_cell(act_name, chapter_name, scenes_in_cell),
                    row_idx,
                    col_idx,
                )

    def _build_matrix_cell(
        self, act_name: str, chapter_name: str, scenes: list,
    ) -> QWidget:
        cell = QFrame()
        cell.setObjectName("planMatrixCell")
        cell.setStyleSheet(
            f"QFrame#planMatrixCell {{ background: {theme.BG_DARK};"
            f" border: 1px solid {theme.BORDER}; border-radius: 4px; }}"
        )
        cell.setMinimumSize(160, 80)
        lay = QVBoxLayout(cell)
        lay.setContentsMargins(6, 6, 6, 6)
        lay.setSpacing(2)

        if scenes:
            for scene in scenes:
                card = QPushButton(scene.title or "Untitled")
                card.setStyleSheet(
                    f"QPushButton {{ text-align: left; padding: 3px 6px;"
                    f" background: {theme.BG_PANEL}; color: {theme.TEXT_PRIMARY};"
                    f" border: 1px solid {theme.BORDER}; border-radius: 3px;"
                    " font-size: 10px; }"
                    f"QPushButton:hover {{ border-color: {theme.ACCENT}; }}"
                )
                card.clicked.connect(
                    lambda _c=False, sid=scene.id: self._open_scene_card(sid)
                )
                lay.addWidget(card)
        else:
            lay.addStretch()

        add_btn = QPushButton("+")
        add_btn.setFixedHeight(20)
        add_btn.setStyleSheet(
            f"QPushButton {{ background: transparent; color: {theme.TEXT_MUTED};"
            f" border: 1px dashed {theme.BORDER}; border-radius: 3px;"
            " font-size: 10px; }"
            f"QPushButton:hover {{ color: {theme.TEXT_PRIMARY}; }}"
        )
        add_btn.clicked.connect(
            lambda: self._add_scene(act_name, chapter_name)
        )
        lay.addWidget(add_btn)
        return cell

    def _open_scene_card(self, scene_id: int) -> None:
        if self._on_open_scene is not None:
            self._on_open_scene(scene_id)

    # -- Add operations -------------------------------------------------------

    def _add_act(self) -> None:
        name, ok = QInputDialog.getText(
            self, "Add Act", "Act name:", text="New Act",
        )
        if not ok or not name.strip():
            return
        name = name.strip()
        # Acts are created implicitly by adding a scene under them.
        # Create a placeholder scene so the act becomes visible.
        self._db.create_scene(
            self._project_id,
            title="Untitled Scene",
            act=name,
        )
        self._notify()
        self.refresh()

    def _add_chapter(self, act_name: str) -> None:
        name, ok = QInputDialog.getText(
            self, "Add Chapter", "Chapter name:", text="New Chapter",
        )
        if not ok or not name.strip():
            return
        actual_act = "" if act_name == _UNTITLED_ACT else act_name
        self._db.create_scene(
            self._project_id,
            title="Untitled Scene",
            act=actual_act,
            chapter=name.strip(),
        )
        self._notify()
        self.refresh()

    def _add_scene(self, act_name: str, chapter_name: str) -> None:
        title, ok = QInputDialog.getText(
            self, "Add Scene", "Scene title:", text="Untitled Scene",
        )
        if not ok:
            return
        title = title.strip() or "Untitled Scene"
        actual_act = "" if act_name == _UNTITLED_ACT else act_name
        actual_chapter = "" if chapter_name == _UNTITLED_CHAPTER else chapter_name
        self._db.create_scene(
            self._project_id,
            title=title,
            act=actual_act,
            chapter=actual_chapter,
        )
        self._notify()
        self.refresh()

    # -- Edit menus -----------------------------------------------------------

    def _show_act_menu(self, anchor: QWidget, act_name: str) -> None:
        menu = QMenu(anchor)
        rename_act = QAction("Rename Act", menu)
        rename_act.triggered.connect(lambda: self._rename_act_dialog(act_name))
        menu.addAction(rename_act)

        if act_name != _UNTITLED_ACT:
            delete_act = QAction("Delete Act (clear label from scenes)", menu)
            delete_act.triggered.connect(
                lambda: self._delete_act_dialog(act_name)
            )
            menu.addAction(delete_act)

        menu.exec(anchor.mapToGlobal(anchor.rect().bottomLeft()))

    def _show_chapter_menu(self, anchor: QWidget, chapter_name: str) -> None:
        menu = QMenu(anchor)
        rename = QAction("Rename Chapter", menu)
        rename.triggered.connect(
            lambda: self._rename_chapter_dialog(chapter_name)
        )
        menu.addAction(rename)

        if chapter_name != _UNTITLED_CHAPTER:
            delete = QAction("Delete Chapter (clear label from scenes)", menu)
            delete.triggered.connect(
                lambda: self._delete_chapter_dialog(chapter_name)
            )
            menu.addAction(delete)

        menu.exec(anchor.mapToGlobal(anchor.rect().bottomLeft()))

    def _show_scene_menu(self, anchor: QWidget, scene_id: int) -> None:
        menu = QMenu(anchor)

        if self._on_open_scene is not None:
            open_act = QAction("Open in Manuscript", menu)
            open_act.triggered.connect(
                lambda: self._on_open_scene(scene_id)
            )
            menu.addAction(open_act)

        rename = QAction("Rename Scene", menu)
        rename.triggered.connect(lambda: self._rename_scene_dialog(scene_id))
        menu.addAction(rename)

        delete = QAction("Delete Scene", menu)
        delete.triggered.connect(lambda: self._delete_scene_dialog(scene_id))
        menu.addAction(delete)

        menu.exec(anchor.mapToGlobal(anchor.rect().bottomLeft()))

    def _rename_act_dialog(self, act_name: str) -> None:
        new, ok = QInputDialog.getText(
            self, "Rename Act", "New name:", text=act_name,
        )
        if not ok or not new.strip() or new.strip() == act_name:
            return
        _rename_act(
            self._db, self._project_id, _act_key(act_name), new.strip(),
        )
        self._notify()
        self.refresh()

    def _rename_chapter_dialog(self, chapter_name: str) -> None:
        new, ok = QInputDialog.getText(
            self, "Rename Chapter", "New name:", text=chapter_name,
        )
        if not ok or not new.strip() or new.strip() == chapter_name:
            return
        _rename_chapter(
            self._db, self._project_id, _chapter_key(chapter_name), new.strip(),
        )
        self._notify()
        self.refresh()

    def _rename_scene_dialog(self, scene_id: int) -> None:
        scene = self._db.get_scene_by_id(scene_id)
        if scene is None:
            return
        new, ok = QInputDialog.getText(
            self, "Rename Scene", "New title:", text=scene.title,
        )
        if not ok or not new.strip():
            return
        self._db.update_scene(
            scene_id=scene.id,
            title=new.strip(),
            summary=scene.summary,
            synopsis=scene.synopsis,
            goal=scene.goal,
            conflict=scene.conflict,
            outcome=scene.outcome,
            beat=scene.beat,
            tags=scene.tags,
            act=scene.act,
            content=scene.content,
            chapter=scene.chapter,
            plotline=scene.plotline,
        )
        self._notify()
        self.refresh()

    def _delete_act_dialog(self, act_name: str) -> None:
        confirm = QMessageBox.question(
            self,
            "Delete Act",
            f"Remove the act label '{act_name}' from all its scenes?\n"
            "Scenes will not be deleted.",
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return
        _delete_act(self._db, self._project_id, _act_key(act_name))
        self._notify()
        self.refresh()

    def _delete_chapter_dialog(self, chapter_name: str) -> None:
        confirm = QMessageBox.question(
            self,
            "Delete Chapter",
            f"Remove the chapter label '{chapter_name}' from all its scenes?\n"
            "Scenes will not be deleted.",
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return
        _delete_chapter(self._db, self._project_id, _chapter_key(chapter_name))
        self._notify()
        self.refresh()

    def _delete_scene_dialog(self, scene_id: int) -> None:
        scene = self._db.get_scene_by_id(scene_id)
        if scene is None:
            return
        confirm = QMessageBox.question(
            self,
            "Delete Scene",
            f"Delete scene '{scene.title}'?\nThis cannot be undone.",
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return
        self._db.delete_scene(scene_id)
        self._notify()
        self.refresh()

    # -- Summary saves --------------------------------------------------------

    def _save_act_summary(self, act_name: str, summary: str) -> None:
        _save_act_summary(self._db, self._project_id, _act_key(act_name), summary)

    def _save_chapter_summary(self, chapter_name: str, summary: str) -> None:
        _save_chapter_summary(
            self._db, self._project_id, _chapter_key(chapter_name), summary,
        )

    def _save_scene_summary(self, scene_id: int, summary: str) -> None:
        self._db.update_scene_summary(scene_id, summary)
        self._notify()

    def _notify(self) -> None:
        if self._on_data_changed is not None:
            self._on_data_changed()
