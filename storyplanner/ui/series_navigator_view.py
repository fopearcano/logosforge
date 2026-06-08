"""Series Navigator — a read-only left-panel tree for the serial structure.

Series mode interprets the canonical Act -> Chapter -> Scene as
Season/Arc -> Episode -> Scene. This navigator presents that structure for quick
navigation; it is **not** a new storage system and never mutates data:

* Act node  -> "Season / Arc N"  (canonical Act number)
* Chapter   -> "Episode N.M"     (canonical Chapter number; Chapter shown as Episode)
* Scene     -> "Scene N.M.K"     (canonical Scene number)
* A/B/C     -> read-only buckets derived from the Episode Beat Plan's a/b/c story
              fields (Phase 2 ``series_pipeline``). No per-scene thread storage.

Clicking a node navigates (Season/Episode -> Outline, Scene -> Manuscript) via
injected callbacks. The navigator builds from the canonical
``story_structure`` tree, so it stays in lock-step with Outline / Timeline /
Export. No Qt mutation of project data, no LLM, no image generation.
"""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

_ROLE = Qt.ItemDataRole.UserRole

_EMPTY_PROJECT = ("No Series structure yet. Create an Act/Season, Episode, and "
                  "Scene in Outline.")
_NO_PLAN = "No A/B/C story plan yet. Generate or edit Episode Beat Plan."
_NO_SCENES = "No scenes in this episode."


class SeriesNavigatorView(QWidget):
    """Read-only Season/Arc -> Episode -> Scene navigator for Series projects."""

    def __init__(
        self, db, project_id: int, *,
        on_open_outline: Callable[[int], None] | None = None,
        on_open_manuscript: Callable[[int], None] | None = None,
        on_open_timeline: Callable[[int], None] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("seriesNavigatorView")
        self._db = db
        self._project_id = project_id
        self._on_open_outline = on_open_outline
        self._on_open_manuscript = on_open_manuscript
        self._on_open_timeline = on_open_timeline

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(8)

        heading = QLabel("Series Navigator")
        heading.setObjectName("seriesNavigatorHeading")
        heading.setStyleSheet("font-size: 14px; font-weight: bold;")
        layout.addWidget(heading)

        controls = QHBoxLayout()
        controls.addStretch()
        for label, slot in (("Open in Outline", self._open_outline),
                            ("Open in Manuscript", self._open_manuscript),
                            ("Open in Timeline", self._open_timeline)):
            btn = QPushButton(label)
            btn.clicked.connect(slot)
            controls.addWidget(btn)
        refresh_btn = QPushButton("Refresh")
        refresh_btn.setObjectName("seriesNavigatorRefresh")
        refresh_btn.clicked.connect(self.refresh)
        controls.addWidget(refresh_btn)
        layout.addLayout(controls)

        self._tree = QTreeWidget()
        self._tree.setObjectName("seriesNavigatorTree")
        self._tree.setHeaderHidden(True)
        self._tree.itemDoubleClicked.connect(lambda it, _c: self._activate(it))
        layout.addWidget(self._tree, stretch=1)

        self.refresh()

    # -- Build (read-only) ---------------------------------------------------

    def refresh(self) -> None:
        self._tree.clear()
        from storyplanner import story_structure as ss
        from storyplanner import series_blocks as sbk  # noqa: F401 (parity/labels)
        try:
            tree = ss.build_structure_tree(self._db, self._project_id)
            numbers = ss.compute_structural_numbers(
                tree, ss.is_novel_project(self._db, self._project_id))
        except Exception:
            tree, numbers = [], {"acts": {}, "chapters": {}, "scenes": {}}

        named = [(a, chs) for a, chs in tree if a != ss.UNASSIGNED_ACT]
        if not named and not tree:
            self._tree.addTopLevelItem(QTreeWidgetItem([_EMPTY_PROJECT]))
            return
        if not any(chs for _a, chs in tree):
            self._tree.addTopLevelItem(QTreeWidgetItem([_EMPTY_PROJECT]))
            return

        acts_n = numbers.get("acts", {})
        chaps_n = numbers.get("chapters", {})
        scenes_n = numbers.get("scenes", {})

        for act, chapters in tree:
            anum = acts_n.get(act, "")
            atext = (f"Season / Arc {anum} — {act}" if act != ss.UNASSIGNED_ACT
                     else "Unassigned")
            act_item = QTreeWidgetItem([atext])
            act_item.setData(0, _ROLE, {"kind": "season", "act": act})
            self._tree.addTopLevelItem(act_item)

            for chapter, scenes in chapters:
                if chapter == ss.UNASSIGNED_CHAPTER:
                    ep_text = "Unassigned"
                else:
                    cnum = chaps_n.get((act, chapter), "")
                    ep_text = (f"Episode {cnum} — {chapter}" if cnum
                               else f"Episode — {chapter}")
                ep_item = QTreeWidgetItem([ep_text])
                ep_item.setData(0, _ROLE, {"kind": "episode", "act": act,
                                           "chapter": chapter})
                act_item.addChild(ep_item)
                self._add_episode_children(ep_item, chapter, scenes, scenes_n)
            act_item.setExpanded(True)

    def _add_episode_children(self, ep_item, chapter, scenes, scenes_n) -> None:
        from storyplanner import series_pipeline as spp
        # A/B/C story buckets, derived read-only from the Episode Beat Plan.
        plan = None
        try:
            plan = spp.get_episode_plan(self._db, self._project_id, chapter)
        except Exception:
            plan = None
        threads = []
        if plan is not None and not plan.is_empty():
            for label, val in (("A-Story", plan.a_story), ("B-Story", plan.b_story),
                               ("C-Story", plan.c_story)):
                if (val or "").strip():
                    threads.append((label, val.strip()))
        if threads:
            for label, val in threads:
                t_item = QTreeWidgetItem([f"{label}: {val[:80]}"])
                t_item.setData(0, _ROLE, {"kind": "abc", "chapter": chapter,
                                          "thread": label[0]})
                ep_item.addChild(t_item)
                # No per-scene thread metadata exists yet — read-only bucket.
                t_item.addChild(QTreeWidgetItem(["No linked scenes yet"]))
        else:
            ep_item.addChild(QTreeWidgetItem([_NO_PLAN]))

        all_scenes = QTreeWidgetItem(["All Scenes"])
        ep_item.addChild(all_scenes)
        if not scenes:
            all_scenes.addChild(QTreeWidgetItem([_NO_SCENES]))
        for sc in scenes:
            snum = scenes_n.get(sc.id, "")
            title = (getattr(sc, "title", "") or "Untitled").strip() or "Untitled"
            label = f"Scene {snum} — {title}" if snum else f"Scene — {title}"
            s_item = QTreeWidgetItem([label])
            s_item.setData(0, _ROLE, {"kind": "scene", "scene_id": sc.id})
            all_scenes.addChild(s_item)
        all_scenes.setExpanded(True)

    # -- Navigation (no mutation) --------------------------------------------

    def _activate(self, item) -> None:
        """Double-click: Scene -> Manuscript; Season/Episode -> Outline."""
        data = item.data(0, _ROLE) if item is not None else None
        if not isinstance(data, dict):
            return
        kind = data.get("kind")
        if kind == "scene" and self._on_open_manuscript:
            self._on_open_manuscript(int(data["scene_id"]))
        elif kind in ("season", "episode") and self._on_open_outline:
            self._on_open_outline(0)

    def _selected_data(self) -> dict | None:
        item = self._tree.currentItem()
        data = item.data(0, _ROLE) if item is not None else None
        return data if isinstance(data, dict) else None

    def _open_outline(self) -> None:
        if self._on_open_outline:
            self._on_open_outline(0)

    def _open_manuscript(self) -> None:
        data = self._selected_data()
        if data and data.get("kind") == "scene" and self._on_open_manuscript:
            self._on_open_manuscript(int(data["scene_id"]))

    def _open_timeline(self) -> None:
        data = self._selected_data()
        if data and data.get("kind") == "scene" and self._on_open_timeline:
            self._on_open_timeline(int(data["scene_id"]))
