"""ManuscriptNavigator — a compact, IDE-style document outline shown on the
right of the Manuscript writing area.

It is a *read/navigate* surface, not an Outline editor: it renders the canonical
Act → Chapter → Scene structure (from ``story_structure``) with structural
numbers, highlights the current unit, and opens a unit in the Manuscript editor
on click. It never edits structure or touches manuscript body text.
"""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QLabel,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from storyplanner import story_structure as ss
from storyplanner.db import Database
from storyplanner.ui import theme

_ROLE_KIND = Qt.ItemDataRole.UserRole
_ROLE_SCENE_ID = Qt.ItemDataRole.UserRole + 1
_ROLE_FIRST_SCENE = Qt.ItemDataRole.UserRole + 2


class ManuscriptNavigator(QWidget):
    """Narrow right-side navigator: canonical Act/Chapter/Scene tree.

    ``on_select(scene_id)`` is called when the writer picks a Chapter or Scene
    (Chapter opens its first Scene), so the host can open + focus that unit.
    """

    def __init__(
        self,
        db: Database,
        project_id: int,
        on_select: Callable[[int], None] | None = None,
    ) -> None:
        super().__init__()
        self.setObjectName("manuscriptNavigator")
        self._db = db
        self._project_id = project_id
        self._on_select = on_select
        self._current_scene_id: int | None = None
        self.setMinimumWidth(170)
        self.setMaximumWidth(240)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(6, 8, 6, 8)
        lay.setSpacing(4)

        header = QLabel("Navigator")
        header.setObjectName("navigatorHeader")
        header.setStyleSheet(
            f"color: {theme.TEXT_MUTED}; font-size: 11px; font-weight: bold;")
        lay.addWidget(header)

        self._tree = QTreeWidget()
        self._tree.setObjectName("navigatorTree")
        self._tree.setHeaderHidden(True)
        self._tree.setIndentation(12)
        self._tree.setFocusPolicy(Qt.FocusPolicy.NoFocus)  # never steal the caret
        self._tree.setStyleSheet(
            f"QTreeWidget#navigatorTree {{ background: {theme.BG_PANEL};"
            f" border: 1px solid {theme.BORDER}; border-radius: 6px;"
            f" color: {theme.TEXT_SECONDARY}; font-size: 11px; }}"
            f"QTreeWidget#navigatorTree::item {{ padding: 2px 2px; }}"
            f"QTreeWidget#navigatorTree::item:selected {{"
            f" background: {theme.SELECTION_BG}; color: {theme.TEXT_PRIMARY}; }}"
        )
        # A single click navigates; double-click/Enter also works (itemActivated).
        self._tree.itemClicked.connect(self._on_item_chosen)
        self._tree.itemActivated.connect(self._on_item_chosen)
        lay.addWidget(self._tree, stretch=1)

        self._empty = QLabel("No structure yet.")
        self._empty.setStyleSheet(
            f"color: {theme.TEXT_MUTED}; font-size: 10px; font-style: italic;")
        self._empty.setVisible(False)
        lay.addWidget(self._empty)

        self.refresh()

    # -- Build ---------------------------------------------------------------

    @staticmethod
    def _wc(text: str | None) -> int:
        return len((text or "").split())

    def refresh(self, current_scene_id: int | None = None) -> None:
        """Rebuild from canonical structure. Highlights *current_scene_id* (or
        the last-known current). Orphans are repaired upstream, so a Scene never
        appears before an Act."""
        if current_scene_id is not None:
            self._current_scene_id = current_scene_id
        self._tree.clear()
        tree = ss.build_structure_tree(self._db, self._project_id)
        numbers = ss.compute_structural_numbers(
            tree, ss.is_novel_project(self._db, self._project_id))
        current_item: QTreeWidgetItem | None = None

        for act_name, chapters in tree:
            an = numbers["acts"].get(act_name, "")
            act_item = QTreeWidgetItem(
                [f"Act {an}: {act_name}" if an else act_name])
            act_item.setData(0, _ROLE_KIND, "act")
            self._tree.addTopLevelItem(act_item)
            act_item.setExpanded(True)
            for ch_name, scenes in chapters:
                if ch_name == ss.UNASSIGNED_CHAPTER:
                    parent = act_item   # scenes sit directly under the Act
                else:
                    cn = numbers["chapters"].get((act_name, ch_name), "")
                    ch_item = QTreeWidgetItem(
                        [f"Chapter {cn}: {ch_name}" if cn else ch_name])
                    ch_item.setData(0, _ROLE_KIND, "chapter")
                    ch_item.setData(
                        0, _ROLE_FIRST_SCENE, scenes[0].id if scenes else None)
                    act_item.addChild(ch_item)
                    ch_item.setExpanded(True)
                    parent = ch_item
                for scene in scenes:
                    sn = numbers["scenes"].get(scene.id, "")
                    title = (scene.title or "Untitled").strip() or "Untitled"
                    label = f"{sn}: {title}" if sn else title
                    s_item = QTreeWidgetItem([label])
                    s_item.setData(0, _ROLE_KIND, "scene")
                    s_item.setData(0, _ROLE_SCENE_ID, scene.id)
                    summary = (scene.summary or "").strip()
                    wc = self._wc(scene.content)
                    tip = f"{label}\n{wc:,} words"
                    if summary:
                        tip += f"\n{summary[:200]}"
                    s_item.setToolTip(0, tip)
                    parent.addChild(s_item)
                    if scene.id == self._current_scene_id:
                        current_item = s_item

        has_any = self._tree.topLevelItemCount() > 0
        self._tree.setVisible(has_any)
        self._empty.setVisible(not has_any)
        if current_item is not None:
            self._tree.setCurrentItem(current_item)
            self._tree.scrollToItem(current_item)

    def set_current(self, scene_id: int | None) -> None:
        """Highlight a unit without a full rebuild (called when the writer opens
        a unit elsewhere)."""
        self._current_scene_id = scene_id
        self.refresh()

    # -- Interaction ---------------------------------------------------------

    @staticmethod
    def _first_scene_under(item: QTreeWidgetItem) -> int | None:
        if item.data(0, _ROLE_KIND) == "scene":
            return item.data(0, _ROLE_SCENE_ID)
        for i in range(item.childCount()):
            sid = ManuscriptNavigator._first_scene_under(item.child(i))
            if sid is not None:
                return sid
        return None

    def _on_item_chosen(self, item: QTreeWidgetItem, _col: int = 0) -> None:
        if item is None or self._on_select is None:
            return
        kind = item.data(0, _ROLE_KIND)
        scene_id: int | None
        if kind == "scene":
            scene_id = item.data(0, _ROLE_SCENE_ID)
        elif kind == "chapter":
            scene_id = item.data(0, _ROLE_FIRST_SCENE)
        else:  # act → open its first scene if any
            scene_id = self._first_scene_under(item)
        if scene_id is not None:
            self._current_scene_id = scene_id
            self._on_select(scene_id)
