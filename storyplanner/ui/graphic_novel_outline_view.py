"""Graphic Novel Outline — canonical **Act → Page → Scene → Panel** navigator.

Mounted as the **Outline** for Graphic Novel projects (the standalone Pages
section stays disabled). One tree in physical, page-first order over the
act-wide page coordinates from :mod:`graphic_novel_structure`:

    Act 1
      Page 1
        Scene — A                ← the scene's first page on this act page
          Panel 1 — snippet
      Page 2
        Scene — A (continued)    ← the same scene spanning onto Page 2
        Scene — B                ← a second scene sharing Page 2
      Scene — D (no pages yet)   ← empty scenes stay visible under their Act

An Act owns its Pages and Scenes; a Panel belongs to one Scene and sits on one
act Page; a Scene can span several Pages; one Page can hold Panels from
several Scenes. **Chapters are hidden** in Graphic Novel mode (they remain
storage labels for cross-mode compatibility only).

The selected-item editor on the right edits a Panel's five fields (Visual /
Caption / Dialogue / SFX / Notes), a scene-page's title/notes, the Scene's
title (rename — PlanView is not mounted in GN mode), and a scene's act-wide
start page (pin / auto-chain). Selection never mutates; add/move/
delete go through the shared body (:mod:`graphic_novel_outline`) so the
Manuscript mirrors every edit. Double-click deep-links into the Manuscript.
Child-widget-only: no separate route, no top-level window, no dialog on
mount — fullscreen-safe. No image / prompt / ComfyUI fields.
"""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from storyplanner import graphic_novel_outline as gno
from storyplanner import graphic_novel_structure as gns
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

EMPTY_PROJECT_MESSAGE = "Create an Act to begin your Graphic Novel."


class _FocusPlainText(QPlainTextEdit):
    committed = Signal()

    def focusOutEvent(self, event) -> None:  # noqa: N802 (Qt signature)
        super().focusOutEvent(event)
        self.committed.emit()


class GraphicNovelOutlineView(QWidget):
    """Act → Page → Scene → Panel navigator + editor over the shared body."""

    def __init__(
        self, db, project_id: int, *,
        on_data_changed: Callable[[], None] | None = None,
        on_open_manuscript: Callable[[int], None] | None = None,
        on_open_panel: Callable[[int, int, int], None] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("graphicNovelOutlineView")
        self._db = db
        self._project_id = project_id
        self._on_data_changed = on_data_changed
        self._on_open_manuscript = on_open_manuscript
        # Optional deep-link: double-clicking a Panel focuses its script
        # block in the Manuscript (scene_id, local_page_idx, panel_idx).
        self._on_open_panel = on_open_panel
        self._sel: dict = {}

        root = QHBoxLayout(self)
        root.setContentsMargins(10, 8, 10, 8)
        root.setSpacing(10)

        # -- Left: toolbar + the canonical tree --
        left = QVBoxLayout()
        left.setSpacing(4)
        head = QLabel("Graphic Novel Outline")
        head.setObjectName("gnOutlineHeading")
        head.setStyleSheet("font-size: 14px; font-weight: bold;")
        left.addWidget(head)

        bar = QHBoxLayout()
        for label, slot, name in (
            ("+ Act", self._add_act, "gnOutlineAddAct"),
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

        self._tree = QTreeWidget()
        self._tree.setObjectName("gnOutlineTree")
        self._tree.setHeaderHidden(True)
        self._tree.setMaximumWidth(380)
        self._tree.currentItemChanged.connect(
            lambda cur, _p: self._on_select(cur))
        self._tree.itemDoubleClicked.connect(
            lambda it, _c: self._activate(it))
        left.addWidget(self._tree, stretch=1)
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

    # -------------------------------------------------------------- tree build
    def refresh(self) -> None:
        keep = dict(self._sel)
        self._tree.blockSignals(True)
        self._tree.clear()
        self._build_tree(gns.act_view(self._db, self._project_id))
        self._tree.blockSignals(False)
        target = self._find_item(keep)
        if target is not None:
            self._tree.setCurrentItem(target)
        else:
            self._render_detail()

    @staticmethod
    def _scene_title(scene) -> str:
        return (getattr(scene, "title", "") or "Untitled").strip() or "Untitled"

    def _build_tree(self, view) -> None:
        for act, pages, placements in view:
            a_item = QTreeWidgetItem([act])
            a_item.setData(0, _ROLE, {"kind": "act", "act": act})
            self._tree.addTopLevelItem(a_item)
            for page_no, slices in pages:
                pg_item = QTreeWidgetItem([f"Page {page_no}"])
                pg_item.setData(0, _ROLE, {"kind": "act_page", "act": act,
                                           "page_no": page_no})
                a_item.addChild(pg_item)
                for sl in slices:
                    scene = sl.placement.scene
                    label = f"Scene — {self._scene_title(scene)}"
                    if sl.continued:
                        label += " (continued)"
                    if (sl.page.title or "").strip():
                        label += f" · {sl.page.title.strip()}"
                    s_item = QTreeWidgetItem([label])
                    s_item.setData(0, _ROLE, {
                        "kind": "scene_page", "act": act,
                        "scene_id": scene.id, "page": sl.local_idx,
                        "page_no": page_no, "continued": sl.continued})
                    pg_item.addChild(s_item)
                    for ci, panel in enumerate(sl.page.panels):
                        pn = QTreeWidgetItem([
                            f"Panel {panel.number} — {gno.panel_snippet(panel)}"])
                        pn.setData(0, _ROLE, {
                            "kind": "panel", "act": act, "scene_id": scene.id,
                            "page": sl.local_idx, "panel": ci,
                            "page_no": page_no})
                        s_item.addChild(pn)
                    s_item.setExpanded(True)
                pg_item.setExpanded(True)
            # Scenes without pages stay visible directly under their Act.
            for placement in placements:
                if placement.page_count:
                    continue
                s_item = QTreeWidgetItem([
                    f"Scene — {self._scene_title(placement.scene)} "
                    f"(no pages yet)"])
                s_item.setData(0, _ROLE, {"kind": "scene", "act": act,
                                          "scene_id": placement.scene.id})
                a_item.addChild(s_item)
            a_item.setExpanded(True)

    def _find_item(self, sel: dict):
        if not sel:
            return None

        def walk(item):
            if item.data(0, _ROLE) == sel:
                return item
            for i in range(item.childCount()):
                f = walk(item.child(i))
                if f is not None:
                    return f
            return None
        for i in range(self._tree.topLevelItemCount()):
            f = walk(self._tree.topLevelItem(i))
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
        if data.get("kind") == "panel" and self._on_open_panel is not None:
            # Deep-link: focus the panel's script block in the Manuscript.
            self._on_open_panel(int(data["scene_id"]),
                                int(data["page"]), int(data["panel"]))
            return
        if data.get("kind") in ("scene", "scene_page", "panel") \
                and self._on_open_manuscript:
            self._on_open_manuscript(int(data["scene_id"]))

    def select_scene(self, scene_id: int) -> None:
        # Select a scene's first node (its first page slice, or the
        # no-pages entry) in the tree.
        def walk(it):
            d = it.data(0, _ROLE)
            if isinstance(d, dict) and d.get("kind") in ("scene_page", "scene") \
                    and d.get("scene_id") == scene_id:
                return it
            for i in range(it.childCount()):
                f = walk(it.child(i))
                if f is not None:
                    return f
            return None
        for i in range(self._tree.topLevelItemCount()):
            found = walk(self._tree.topLevelItem(i))
            if found is not None:
                self._tree.setCurrentItem(found)
                return

    def _select_scene_node(self, scene_id: int) -> None:
        """Point _sel at a scene's first node after a structural change."""
        act, placement = gns.find_placement(self._db, self._project_id,
                                            scene_id)
        if placement is None:
            self._sel = {}
        elif placement.page_count:
            self._sel = {"kind": "scene_page", "act": act,
                         "scene_id": scene_id, "page": 0,
                         "page_no": placement.start_page, "continued": False}
        else:
            self._sel = {"kind": "scene", "act": act, "scene_id": scene_id}

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
        elif kind == "scene_page":
            self._render_scene_page_detail()
        elif kind == "scene":
            self._render_scene_detail()
        elif kind == "act_page":
            self._render_act_page_detail()
        elif kind == "act":
            self._render_act_detail()
        elif self._tree.topLevelItemCount() == 0:
            # Empty state A: no Act yet.
            msg = QLabel(EMPTY_PROJECT_MESSAGE)
            msg.setObjectName("gnOutlineEmpty")
            self._detail_layout.addWidget(msg)
            btn = QPushButton("+ Act")
            btn.setObjectName("gnOutlineDetailAddAct")
            btn.clicked.connect(self._add_act)
            self._detail_layout.addWidget(btn)
        else:
            self._detail_layout.addWidget(QLabel(
                "Select an Act, Page, Scene or Panel on the left. The "
                "Outline is the canonical Act → Page → Scene → Panel "
                "structure; the Manuscript mirrors it."))
        self._detail_layout.addStretch()

    def _title_label(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet("font-size: 13px; font-weight: bold;")
        return lbl

    def _render_act_detail(self) -> None:
        act = self._sel.get("act", "")
        self._detail_layout.addWidget(self._title_label(act))
        self._detail_layout.addWidget(QLabel(
            "An Act owns its Pages and Scenes. Add a Scene, then Pages "
            "and Panels."))
        btn = QPushButton("+ Add Scene")
        btn.setObjectName("gnOutlineDetailAddScene")
        btn.clicked.connect(self._add_scene)
        self._detail_layout.addWidget(btn)
        btn = QPushButton("+ Add Page")
        btn.setObjectName("gnOutlineDetailAddPage")
        btn.clicked.connect(self._add_page)
        self._detail_layout.addWidget(btn)

    def _render_act_page_detail(self) -> None:
        act = self._sel.get("act")
        page_no = self._sel.get("page_no")
        self._detail_layout.addWidget(self._title_label(
            f"{act} · Page {page_no}"))
        slices = self._act_page_slices(act, page_no)
        if len(slices) > 1:
            self._detail_layout.addWidget(QLabel(
                "This page holds panels from more than one scene:"))
        for sl in slices:
            marker = " — continued" if sl.continued else ""
            self._detail_layout.addWidget(QLabel(
                f"• Scene {self._scene_title(sl.placement.scene)}{marker} "
                f"({len(sl.page.panels)} panel(s))"))
        self._detail_layout.addWidget(QLabel(
            "Select a Scene entry under this page to edit its page title, "
            "notes and panels."))

    def _act_page_slices(self, act, page_no):
        for a, pages, _placements in gns.act_view(self._db, self._project_id):
            if a != act:
                continue
            for no, slices in pages:
                if no == page_no:
                    return slices
        return []

    def _start_page_controls(self, scene_id: int) -> QWidget:
        """Pin / auto-chain a scene's act-wide start page (how a scene is
        placed onto a shared page)."""
        _act, placement = gns.find_placement(self._db, self._project_id,
                                             scene_id)
        holder = QWidget()
        row = QHBoxLayout(holder)
        row.setContentsMargins(0, 0, 0, 0)
        row.addWidget(QLabel("Scene starts on act page:"))
        spin = QSpinBox()
        spin.setObjectName("gnOutlineStartPage")
        spin.setRange(1, 9999)
        spin.setValue(placement.start_page if placement else 1)
        auto = QCheckBox("Auto (after previous scene)")
        auto.setObjectName("gnOutlineStartAuto")
        auto.setChecked(not (placement and placement.explicit))
        spin.setEnabled(not auto.isChecked())

        def commit_spin() -> None:
            if auto.isChecked():
                return
            if gns.set_scene_start_page(self._db, scene_id, spin.value()):
                self._select_scene_node(scene_id)
                self._notify()

        def toggled(checked: bool) -> None:
            spin.setEnabled(not checked)
            value = None if checked else spin.value()
            if gns.set_scene_start_page(self._db, scene_id, value):
                self._select_scene_node(scene_id)
                self._notify()

        spin.editingFinished.connect(commit_spin)
        auto.toggled.connect(toggled)
        row.addWidget(spin)
        row.addWidget(auto)
        row.addStretch()
        return holder

    def _scene_title_editor(self, scene_id: int) -> QLineEdit:
        """Rename the Scene from the Outline (the canonical GN structure
        surface — PlanView's rename is not mounted in Graphic Novel mode)."""
        scene = self._db.get_scene_by_id(scene_id)
        edit = QLineEdit((getattr(scene, "title", "") or "") if scene else "")
        edit.setObjectName("gnOutlineSceneTitle")
        edit.setPlaceholderText("Scene title")
        edit.editingFinished.connect(
            lambda e=edit, sid=scene_id: self._commit_scene_title(sid,
                                                                  e.text()))
        return edit

    def _commit_scene_title(self, sid: int, title: str) -> None:
        title = (title or "").strip()
        scene = self._db.get_scene_by_id(sid)
        # Empty titles are refused (never blank a scene by accident).
        if scene is None or not title or (scene.title or "") == title:
            return
        self._db.update_scene_title(sid, title)
        self._notify()

    def _render_scene_detail(self) -> None:
        sid = self._sel.get("scene_id")
        scene = self._db.get_scene_by_id(sid) if sid is not None else None
        title = self._scene_title(scene) if scene else "Scene"
        self._detail_layout.addWidget(self._title_label(f"Scene — {title}"))
        if sid is not None:
            self._detail_layout.addWidget(QLabel("Scene title"))
            self._detail_layout.addWidget(self._scene_title_editor(sid))
        self._detail_layout.addWidget(QLabel(
            "No pages yet — add a Page to place this scene's panels."))
        btn = QPushButton("+ Add Page")
        btn.setObjectName("gnOutlineDetailAddPage")
        btn.clicked.connect(self._add_page)
        self._detail_layout.addWidget(btn)
        if sid is not None:
            self._detail_layout.addWidget(self._start_page_controls(sid))

    def _render_scene_page_detail(self) -> None:
        sid, pi = self._sel.get("scene_id"), self._sel.get("page")
        page_no = self._sel.get("page_no")
        script = gno.gnb.load_scene_script(self._db, sid)
        try:
            page = script.pages[pi]
        except (IndexError, TypeError):
            return
        scene = self._db.get_scene_by_id(sid)
        title = self._scene_title(scene) if scene else "Scene"
        marker = " — continued" if self._sel.get("continued") else ""
        self._detail_layout.addWidget(self._title_label(
            f"Scene {title}{marker} · Act page {page_no} "
            f"(scene page {page.number} of {len(script.pages)})"))
        self._detail_layout.addWidget(QLabel("Scene title"))
        self._detail_layout.addWidget(self._scene_title_editor(sid))
        self._detail_layout.addWidget(QLabel("Page title"))
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
            lambda e=notes: self._commit_page(sid, pi, "summary",
                                              e.toPlainText()))
        self._detail_layout.addWidget(notes)
        btn = QPushButton("+ Add Panel")
        btn.setObjectName("gnOutlineDetailAddPanel")
        btn.clicked.connect(self._add_panel)
        self._detail_layout.addWidget(btn)
        self._detail_layout.addWidget(self._start_page_controls(sid))

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
        s_title = self._scene_title(scene) if scene else "Scene"
        page_no = self._sel.get("page_no")
        where = f"Act page {page_no}" if page_no else f"Page {page.number}"
        self._detail_layout.addWidget(self._title_label(
            f"Panel {panel.number}  ·  {where}  ·  Scene {s_title}"))
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
                    lambda e=ed, k=key: self._commit_panel(sid, pi, ci, k,
                                                           e.text()))
            ed.setObjectName(f"gnOutlinePanelField_{key}")
            self._detail_layout.addWidget(ed)
        # Move-to-page control (labels show ACT-wide page numbers).
        if len(script.pages) > 1:
            _act, placement = gns.find_placement(self._db, self._project_id,
                                                 sid)
            row = QHBoxLayout()
            row.addWidget(QLabel("Move panel to page:"))
            for to_idx in range(len(script.pages)):
                if to_idx == pi:
                    continue
                no = placement.global_page(to_idx) if placement else to_idx + 1
                b = QPushButton(f"Page {no}")
                b.clicked.connect(
                    lambda _=False, t=to_idx:
                    self._assign_panel_to_page(sid, pi, ci, t))
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

    def _selected_act(self) -> str | None:
        act = self._sel.get("act")
        if act:
            return act
        acts = [a for a, _s in gns.acts_with_scenes(self._db,
                                                    self._project_id)]
        return acts[-1] if acts else None

    def _add_act(self) -> None:
        scene = ss.create_act(self._db, self._project_id)
        self._select_scene_node(scene.id)
        self._notify()

    def _add_scene(self) -> None:
        act = self._selected_act()
        scene = ss.create_scene(self._db, self._project_id, act=act,
                                title="Untitled Scene")
        self._select_scene_node(scene.id)
        self._notify()

    def _scene_for_structure_ops(self) -> int | None:
        """The scene a '+ Page' acts on: the selected scene, else the
        selected Act's last scene (created if the Act is empty)."""
        sid = self._sel.get("scene_id")
        if sid is not None:
            return sid
        act = self._sel.get("act")
        if not act:
            return None
        for a, scenes in gns.acts_with_scenes(self._db, self._project_id):
            if a == act:
                if scenes:
                    return scenes[-1].id
                return ss.create_scene(self._db, self._project_id, act=act,
                                       title="Untitled Scene").id
        return None

    def _add_page(self) -> None:
        sid = self._scene_for_structure_ops()
        if sid is None:
            return
        idx = gno.add_page(self._db, sid)
        act, placement = gns.find_placement(self._db, self._project_id, sid)
        if placement is not None:
            self._sel = {"kind": "scene_page", "act": act, "scene_id": sid,
                         "page": idx, "page_no": placement.global_page(idx),
                         "continued": idx > 0}
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
            self._select_scene_node(sid)
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
            if not safe_dialogs.question(self, "Delete Panel",
                                         "Delete this panel?"):
                return
            gno.delete_panel(self._db, sid, self._sel.get("page"),
                             self._sel.get("panel"))
            self._select_scene_node(sid)
            self._notify()
        elif kind == "scene_page":
            if not safe_dialogs.question(self, "Delete Page",
                                         "Delete this page and its panels?"):
                return
            gno.delete_page(self._db, sid, self._sel.get("page"))
            self._select_scene_node(sid)
            self._notify()
        elif kind == "scene":
            if not safe_dialogs.question(
                    self, "Delete Scene",
                    "Delete this scene and its pages/panels? "
                    "This removes its body."):
                return
            self._db.delete_scene(sid)
            self._sel = {}
            self._notify()
