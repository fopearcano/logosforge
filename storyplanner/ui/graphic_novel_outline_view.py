"""Graphic Novel Outline — Page/Panel navigator + editor (Alpha Page/Panel surface).

Mounted as the **Outline** for Graphic Novel projects (the standalone Pages section
is disabled for Alpha). Two synchronized views over the *same* shared `Scene.content`
body (via :mod:`graphic_novel_outline`):

* **Scenes** tab — ``Act → Chapter → Scene → Page → Panel`` (editable).
* **Pages** tab — ``Act → Chapter → chapter Page N → Panel (Scene X)`` (a
  cross-reference grouping panels across a chapter's scenes by page number).

A selected-item editor on the right shows the selected Panel's fields (Visual /
Caption / Dialogue / SFX / Notes), a Page's title/notes, or the empty-state ladder.
Editing/add/delete/move mutate only the shared body; selection never mutates.
Double-clicking a Scene or Panel opens the Manuscript. The Outline and the
Manuscript mirror the same body. Child-widget-only: no separate route, no top-level
window, no dialog on mount — fullscreen-safe. No image / prompt / ComfyUI fields.
"""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QTabWidget,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from storyplanner import graphic_novel_outline as gno
from storyplanner import story_structure as ss
from storyplanner.ui import safe_dialogs

_ROLE = Qt.ItemDataRole.UserRole
_PANEL_FIELDS = (
    ("visual_description", "Visual", True),
    ("caption", "Caption", False),
    ("dialogue", "Dialogue", True),
    ("sfx", "SFX", False),
    ("notes", "Notes", True),
)


class _FocusPlainText(QPlainTextEdit):
    committed = Signal()

    def focusOutEvent(self, event) -> None:  # noqa: N802 (Qt signature)
        super().focusOutEvent(event)
        self.committed.emit()


class GraphicNovelOutlineView(QWidget):
    """GN-aware Outline: Scene/Page navigator + Panel editor over the shared body."""

    def __init__(
        self, db, project_id: int, *,
        on_data_changed: Callable[[], None] | None = None,
        on_open_manuscript: Callable[[int], None] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("graphicNovelOutlineView")
        self._db = db
        self._project_id = project_id
        self._on_data_changed = on_data_changed
        self._on_open_manuscript = on_open_manuscript
        self._sel: dict = {}

        root = QHBoxLayout(self)
        root.setContentsMargins(10, 8, 10, 8)
        root.setSpacing(10)

        # -- Left: toolbar + tabs (Scenes / Pages) --
        left = QVBoxLayout()
        left.setSpacing(4)
        head = QLabel("Graphic Novel Outline")
        head.setObjectName("gnOutlineHeading")
        head.setStyleSheet("font-size: 14px; font-weight: bold;")
        left.addWidget(head)

        bar = QHBoxLayout()
        for label, slot, name in (
            ("+ Scene", self._add_scene, "gnOutlineAddScene"),
            ("+ Page", self._add_page, "gnOutlineAddPage"),
            ("+ Panel", self._add_panel, "gnOutlineAddPanel"),
            ("▲", self._move_up, "gnOutlineMoveUp"),
            ("▼", self._move_down, "gnOutlineMoveDown"),
            ("Delete", self._delete_selected, "gnOutlineDelete"),
        ):
            b = QPushButton(label)
            b.setObjectName(name)
            b.clicked.connect(slot)
            bar.addWidget(b)
        left.addLayout(bar)

        self._tabs = QTabWidget()
        self._tabs.setObjectName("gnOutlineTabs")
        self._tabs.setMaximumWidth(360)
        self._scene_tree = self._make_tree("gnOutlineSceneTree")
        self._page_tree = self._make_tree("gnOutlinePageTree")
        self._tabs.addTab(self._scene_tree, "Scenes")
        self._tabs.addTab(self._page_tree, "Pages")
        left.addWidget(self._tabs, stretch=1)
        root.addLayout(left)

        # -- Right: selected-item editor --
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._detail_host = QWidget()
        self._detail_layout = QVBoxLayout(self._detail_host)
        self._detail_layout.setContentsMargins(4, 4, 4, 4)
        self._detail_layout.setSpacing(6)
        self._scroll.setWidget(self._detail_host)
        root.addWidget(self._scroll, stretch=1)

        self.refresh()

    def _make_tree(self, name: str) -> QTreeWidget:
        tree = QTreeWidget()
        tree.setObjectName(name)
        tree.setHeaderHidden(True)
        tree.currentItemChanged.connect(lambda cur, _p: self._on_select(cur))
        tree.itemDoubleClicked.connect(lambda it, _c: self._activate(it))
        return tree

    # -------------------------------------------------------------- build trees
    def refresh(self) -> None:
        keep = dict(self._sel)
        for tree in (self._scene_tree, self._page_tree):
            tree.blockSignals(True)
            tree.clear()
        view = gno.scene_view(self._db, self._project_id)
        self._build_scene_tree(view)
        self._build_page_tree(view)
        for tree in (self._scene_tree, self._page_tree):
            tree.blockSignals(False)
        # Restore selection in the active tree (or render the empty state).
        active = self._tabs.currentWidget()
        target = self._find_item(active, keep) if active is not None else None
        if target is not None:
            active.setCurrentItem(target)
        else:
            self._render_detail()

    def _build_scene_tree(self, view) -> None:
        for act, chapters in view:
            a_item = QTreeWidgetItem([act])
            a_item.setData(0, _ROLE, {"kind": "act", "act": act})
            self._scene_tree.addTopLevelItem(a_item)
            for chapter, sc_out in chapters:
                c_item = QTreeWidgetItem([chapter])
                c_item.setData(0, _ROLE, {"kind": "chapter", "act": act,
                                          "chapter": chapter})
                a_item.addChild(c_item)
                for s, script in sc_out:
                    s_title = (getattr(s, "title", "") or "Untitled").strip()
                    s_item = QTreeWidgetItem([f"Scene — {s_title or 'Untitled'}"])
                    s_item.setData(0, _ROLE, {"kind": "scene", "act": act,
                                              "chapter": chapter, "scene_id": s.id})
                    c_item.addChild(s_item)
                    for pi, page in enumerate(script.pages):
                        p_item = QTreeWidgetItem([
                            f"Page {page.number}"
                            + (f" — {page.title}" if (page.title or "").strip() else "")
                            + f"  ({len(page.panels)} panel(s))"])
                        p_item.setData(0, _ROLE, {"kind": "page", "act": act,
                                                  "chapter": chapter, "scene_id": s.id,
                                                  "page": pi})
                        s_item.addChild(p_item)
                        for ci, panel in enumerate(page.panels):
                            pn = QTreeWidgetItem([
                                f"Panel {panel.number} — {gno.panel_snippet(panel)}"])
                            pn.setData(0, _ROLE, {"kind": "panel", "act": act,
                                                  "chapter": chapter, "scene_id": s.id,
                                                  "page": pi, "panel": ci})
                            p_item.addChild(pn)
                        p_item.setExpanded(True)
                    s_item.setExpanded(True)
                c_item.setExpanded(True)
            a_item.setExpanded(True)

    def _build_page_tree(self, view) -> None:
        for act, chapters in view:
            a_item = QTreeWidgetItem([act])
            a_item.setData(0, _ROLE, {"kind": "act", "act": act})
            self._page_tree.addTopLevelItem(a_item)
            for chapter, sc_out in chapters:
                c_item = QTreeWidgetItem([chapter])
                c_item.setData(0, _ROLE, {"kind": "chapter", "act": act,
                                          "chapter": chapter})
                a_item.addChild(c_item)
                scenes = [s for s, _ in sc_out]
                for page_num, entries in gno.chapter_page_view(self._db, scenes):
                    pg_item = QTreeWidgetItem([f"Page {page_num}"])
                    pg_item.setData(0, _ROLE, {"kind": "chapter_page", "act": act,
                                               "chapter": chapter, "page_num": page_num})
                    c_item.addChild(pg_item)
                    for s, pi, ci, panel in entries:
                        s_title = (getattr(s, "title", "") or "Untitled").strip()
                        pn = QTreeWidgetItem([
                            f"Panel {panel.number} — Scene {s_title} — "
                            f"{gno.panel_snippet(panel)}"])
                        pn.setData(0, _ROLE, {"kind": "panel", "act": act,
                                              "chapter": chapter, "scene_id": s.id,
                                              "page": pi, "panel": ci})
                        pg_item.addChild(pn)
                    pg_item.setExpanded(True)
                c_item.setExpanded(True)
            a_item.setExpanded(True)

    def _find_item(self, tree, sel: dict):
        if not sel or tree is None:
            return None

        def walk(item):
            if item.data(0, _ROLE) == sel:
                return item
            for i in range(item.childCount()):
                f = walk(item.child(i))
                if f is not None:
                    return f
            return None
        for i in range(tree.topLevelItemCount()):
            f = walk(tree.topLevelItem(i))
            if f is not None:
                return f
        return None

    # -------------------------------------------------------------- selection
    def _on_select(self, item) -> None:
        data = item.data(0, _ROLE) if item is not None else None
        self._sel = dict(data) if isinstance(data, dict) else {}
        self._render_detail()

    def _activate(self, item) -> None:
        data = item.data(0, _ROLE) if item is not None else None
        if not isinstance(data, dict):
            return
        if data.get("kind") in ("scene", "panel") and self._on_open_manuscript:
            self._on_open_manuscript(int(data["scene_id"]))

    def select_scene(self, scene_id: int) -> None:
        # Find and select a scene node in the Scenes tab.
        def walk(it):
            d = it.data(0, _ROLE)
            if isinstance(d, dict) and d.get("kind") == "scene" \
                    and d.get("scene_id") == scene_id:
                return it
            for i in range(it.childCount()):
                f = walk(it.child(i))
                if f is not None:
                    return f
            return None
        for i in range(self._scene_tree.topLevelItemCount()):
            found = walk(self._scene_tree.topLevelItem(i))
            if found is not None:
                self._tabs.setCurrentWidget(self._scene_tree)
                self._scene_tree.setCurrentItem(found)
                return

    # -------------------------------------------------------------- detail
    def _clear_detail(self) -> None:
        while self._detail_layout.count():
            it = self._detail_layout.takeAt(0)
            w = it.widget()
            if w is not None:
                w.deleteLater()

    def _render_detail(self) -> None:
        self._clear_detail()
        kind = self._sel.get("kind")
        if kind == "panel":
            self._render_panel_detail()
        elif kind == "page":
            self._render_page_detail()
        elif kind == "scene":
            self._render_scene_detail()
        elif kind == "chapter":
            self._render_chapter_detail()
        else:
            self._detail_layout.addWidget(QLabel(
                "Select an Act, Chapter, Scene, Page or Panel on the left. "
                "Graphic Novel pages and panels are edited here and mirror the "
                "Manuscript."))
        self._detail_layout.addStretch()

    def _title_label(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet("font-size: 13px; font-weight: bold;")
        return lbl

    def _render_chapter_detail(self) -> None:
        self._detail_layout.addWidget(self._title_label(self._sel.get("chapter", "")))
        self._detail_layout.addWidget(QLabel(
            "Add a Scene to this chapter, then add Pages and Panels."))
        btn = QPushButton("+ Add Scene")
        btn.setObjectName("gnOutlineDetailAddScene")
        btn.clicked.connect(self._add_scene)
        self._detail_layout.addWidget(btn)

    def _render_scene_detail(self) -> None:
        sid = self._sel.get("scene_id")
        scene = self._db.get_scene_by_id(sid) if sid is not None else None
        title = (getattr(scene, "title", "") or "Untitled") if scene else "Scene"
        self._detail_layout.addWidget(self._title_label(f"Scene — {title}"))
        self._detail_layout.addWidget(QLabel(
            "Begin building this scene's pages and panels."))
        btn = QPushButton("+ Add Page")
        btn.setObjectName("gnOutlineDetailAddPage")
        btn.clicked.connect(self._add_page)
        self._detail_layout.addWidget(btn)

    def _render_page_detail(self) -> None:
        sid, pi = self._sel.get("scene_id"), self._sel.get("page")
        script = gno.gnb.load_scene_script(self._db, sid)
        try:
            page = script.pages[pi]
        except (IndexError, TypeError):
            return
        self._detail_layout.addWidget(self._title_label(f"Page {page.number}"))
        self._detail_layout.addWidget(QLabel("Title"))
        title_edit = QLineEdit(page.title or "")
        title_edit.setObjectName("gnOutlinePageTitle")
        title_edit.editingFinished.connect(
            lambda e=title_edit: self._commit_page(sid, pi, "title", e.text()))
        self._detail_layout.addWidget(title_edit)
        self._detail_layout.addWidget(QLabel("Page notes"))
        notes = _FocusPlainText()
        notes.setObjectName("gnOutlinePageSummary")
        notes.setPlainText(page.summary or "")
        notes.setFixedHeight(60)
        notes.committed.connect(
            lambda e=notes: self._commit_page(sid, pi, "summary", e.toPlainText()))
        self._detail_layout.addWidget(notes)
        btn = QPushButton("+ Add Panel")
        btn.setObjectName("gnOutlineDetailAddPanel")
        btn.clicked.connect(self._add_panel)
        self._detail_layout.addWidget(btn)

    def _render_panel_detail(self) -> None:
        sid, pi, ci = (self._sel.get("scene_id"), self._sel.get("page"),
                       self._sel.get("panel"))
        script = gno.gnb.load_scene_script(self._db, sid)
        try:
            page = script.pages[pi]
            panel = page.panels[ci]
        except (IndexError, TypeError):
            return
        scene = self._db.get_scene_by_id(sid)
        s_title = (getattr(scene, "title", "") or "Untitled") if scene else "Scene"
        self._detail_layout.addWidget(self._title_label(
            f"Panel {panel.number}  ·  Page {page.number}  ·  Scene {s_title}"))
        for key, label, multiline in _PANEL_FIELDS:
            self._detail_layout.addWidget(QLabel(label))
            if multiline:
                ed = _FocusPlainText()
                ed.setPlainText(getattr(panel, key, "") or "")
                ed.setFixedHeight(56)
                ed.committed.connect(
                    lambda e=ed, k=key: self._commit_panel(sid, pi, ci, k,
                                                           e.toPlainText()))
            else:
                ed = QLineEdit(getattr(panel, key, "") or "")
                ed.editingFinished.connect(
                    lambda e=ed, k=key: self._commit_panel(sid, pi, ci, k, e.text()))
            ed.setObjectName(f"gnOutlinePanelField_{key}")
            self._detail_layout.addWidget(ed)
        # Move-to-page control (assign panel to a different page in the scene).
        if len(script.pages) > 1:
            row = QHBoxLayout()
            row.addWidget(QLabel("Move panel to page:"))
            for to_idx, pg in enumerate(script.pages):
                if to_idx == pi:
                    continue
                b = QPushButton(f"Page {pg.number}")
                b.clicked.connect(
                    lambda _=False, t=to_idx: self._assign_panel_to_page(sid, pi, ci, t))
                row.addWidget(b)
            row.addStretch()
            holder = QWidget()
            holder.setLayout(row)
            self._detail_layout.addWidget(holder)

    # -------------------------------------------------------------- mutations
    def _notify(self) -> None:
        self.refresh()
        if self._on_data_changed:
            self._on_data_changed()

    def _commit_panel(self, sid, pi, ci, field, value) -> None:
        if gno.set_panel_field(self._db, sid, pi, ci, field, value):
            self._notify()

    def _commit_page(self, sid, pi, field, value) -> None:
        if gno.set_page_field(self._db, sid, pi, field, value):
            self._notify()

    def _current_chapter(self):
        return self._sel.get("act"), self._sel.get("chapter")

    def _add_scene(self) -> None:
        act, chapter = self._current_chapter()
        scene = ss.create_scene(self._db, self._project_id, act=act,
                                chapter=chapter, title="Untitled Scene")
        self._sel = {"kind": "scene", "act": scene.act, "chapter": scene.chapter,
                     "scene_id": scene.id}
        self._notify()

    def _add_page(self) -> None:
        sid = self._sel.get("scene_id")
        if sid is None:
            return
        idx = gno.add_page(self._db, sid)
        self._sel = {"kind": "page", "act": self._sel.get("act"),
                     "chapter": self._sel.get("chapter"), "scene_id": sid,
                     "page": idx}
        self._notify()

    def _add_panel(self) -> None:
        sid = self._sel.get("scene_id")
        if sid is None:
            return
        page_idx = self._sel.get("page")
        gno.add_panel(self._db, sid, page_idx)
        self._notify()

    def _assign_panel_to_page(self, sid, from_idx, panel_idx, to_idx) -> None:
        if gno.move_panel_to_page(self._db, sid, from_idx, panel_idx, to_idx):
            self._sel = {"kind": "scene", "act": self._sel.get("act"),
                         "chapter": self._sel.get("chapter"), "scene_id": sid}
            self._notify()

    def _move_up(self) -> None:
        self._move(-1)

    def _move_down(self) -> None:
        self._move(+1)

    def _move(self, delta: int) -> None:
        if self._sel.get("kind") != "panel":
            return
        sid, pi, ci = (self._sel.get("scene_id"), self._sel.get("page"),
                       self._sel.get("panel"))
        if gno.move_panel(self._db, sid, pi, ci, delta):
            self._sel = {**self._sel, "panel": ci + delta}
            self._notify()

    def _delete_selected(self) -> None:
        kind = self._sel.get("kind")
        sid = self._sel.get("scene_id")
        if kind == "panel":
            if not safe_dialogs.question(self, "Delete Panel", "Delete this panel?"):
                return
            gno.delete_panel(self._db, sid, self._sel.get("page"),
                             self._sel.get("panel"))
            self._sel = {"kind": "scene", "act": self._sel.get("act"),
                         "chapter": self._sel.get("chapter"), "scene_id": sid}
            self._notify()
        elif kind == "page":
            if not safe_dialogs.question(self, "Delete Page",
                                         "Delete this page and its panels?"):
                return
            gno.delete_page(self._db, sid, self._sel.get("page"))
            self._sel = {"kind": "scene", "act": self._sel.get("act"),
                         "chapter": self._sel.get("chapter"), "scene_id": sid}
            self._notify()
        elif kind == "scene":
            if not safe_dialogs.question(
                    self, "Delete Scene",
                    "Delete this scene and its pages/panels? This removes its body."):
                return
            self._db.delete_scene(sid)
            self._sel = {}
            self._notify()
