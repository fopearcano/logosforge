"""Graphic Novel Manuscript — embedded Page/Panel Navigator + detail editor.

The Alpha-safe Graphic Novel writing surface. It is mounted as the **Manuscript**
content for Graphic Novel projects (the standalone left-panel Pages route is
disabled for Alpha because it was fullscreen-hostile). It is a single embedded
child widget — no separate Pages route, no top-level window, no dock, no dialog on
mount — so it cannot trigger the macOS fullscreen minimize.

Layout::

    [ Scene → Page → Panel navigator ]   [ selected Page/Panel editor ]

* **Navigator** (left): a tree of Scene → Page → Panel with compact snippets and
  collapsible groups; selecting a node shows it on the right.
* **Editor** (right): the selected Panel's fields (Visual / Caption / Dialogue /
  SFX / Notes), or a selected Page's title/notes, or the empty-state ladder
  (Create Scene → Add Page → Add Panel).

Single source of truth: everything reads/writes the shared
``Scene.content`` body via :mod:`storyplanner.graphic_novel_blocks`. There is no
separate Pages storage. The navigator is the intended future anchor point for
visual-production integrations, but **no image generation / prompt / ComfyUI**
fields exist today — these are writing/script structure only.
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
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from storyplanner import graphic_novel_blocks as gnb
from storyplanner.ui import safe_dialogs

_ROLE = Qt.ItemDataRole.UserRole
# (field key, label, multiline?)
_PANEL_FIELDS = (
    ("visual_description", "Visual", True),
    ("caption", "Caption", False),
    ("dialogue", "Dialogue", True),
    ("sfx", "SFX", False),
    ("notes", "Notes", True),
)


class _FocusPlainText(QPlainTextEdit):
    """Multi-line edit that commits (emits) when it loses focus."""

    committed = Signal()

    def focusOutEvent(self, event) -> None:  # noqa: N802 (Qt signature)
        super().focusOutEvent(event)
        self.committed.emit()


class GraphicNovelManuscriptView(QWidget):
    """Embedded Page/Panel navigator + detail editor over the shared GN body."""

    def __init__(
        self, db, project_id: int, *,
        on_data_changed: Callable[[], None] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("graphicNovelManuscriptView")
        self._db = db
        self._project_id = project_id
        self._on_data_changed = on_data_changed
        # Selection: kind in {"scene","page","panel"} + identifying indices.
        self._sel: dict = {}
        # Cache of the currently-selected scene's script (for fast field commits).
        self._scene_id: int | None = None
        self._script = gnb.GraphicNovelScript()

        root = QHBoxLayout(self)
        root.setContentsMargins(10, 8, 10, 8)
        root.setSpacing(10)

        # -- Left: navigator --
        left = QVBoxLayout()
        left.setSpacing(4)
        head = QLabel("Pages & Panels")
        head.setObjectName("gnNavHeading")
        head.setStyleSheet("font-size: 14px; font-weight: bold;")
        left.addWidget(head)

        bar = QHBoxLayout()
        for label, slot, name in (
            ("+ Scene", self._add_scene, "gnNavAddScene"),
            ("+ Page", self._add_page, "gnNavAddPage"),
            ("+ Panel", self._add_panel, "gnNavAddPanel"),
            ("▲", self._move_up, "gnNavMoveUp"),
            ("▼", self._move_down, "gnNavMoveDown"),
            ("Delete", self._delete_selected, "gnNavDelete"),
        ):
            b = QPushButton(label)
            b.setObjectName(name)
            b.clicked.connect(slot)
            bar.addWidget(b)
        left.addLayout(bar)

        self._tree = QTreeWidget()
        self._tree.setObjectName("gnNavTree")
        self._tree.setHeaderHidden(True)
        self._tree.setMaximumWidth(320)
        self._tree.currentItemChanged.connect(
            lambda cur, _prev: self._on_select(cur))
        left.addWidget(self._tree, stretch=1)
        root.addLayout(left)

        # -- Right: selected Page/Panel editor (scrollable) --
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._detail_host = QWidget()
        self._detail_layout = QVBoxLayout(self._detail_host)
        self._detail_layout.setContentsMargins(4, 4, 4, 4)
        self._detail_layout.setSpacing(6)
        self._scroll.setWidget(self._detail_host)
        root.addWidget(self._scroll, stretch=1)

        self.refresh()

    # ----------------------------------------------------------------- scenes
    def _gn_scenes(self) -> list:
        from storyplanner import story_structure as ss
        try:
            order = ss.canonical_scene_order(self._db, self._project_id)
            by_id = {s.id: s for s in self._db.get_all_scenes(self._project_id)}
            return [by_id[s] for s in order if s in by_id]
        except Exception:
            try:
                return list(self._db.get_all_scenes(self._project_id) or [])
            except Exception:
                return []

    def _load(self, scene_id: int) -> gnb.GraphicNovelScript:
        return gnb.load_scene_script(self._db, scene_id)

    # --------------------------------------------------------------- navigator
    def refresh(self) -> None:
        """Rebuild the navigator tree from the shared body and re-render detail."""
        keep = dict(self._sel)
        self._tree.blockSignals(True)
        self._tree.clear()
        scenes = self._gn_scenes()
        for sc in scenes:
            s_item = QTreeWidgetItem([self._scene_label(sc)])
            s_item.setData(0, _ROLE, {"kind": "scene", "scene_id": sc.id})
            self._tree.addTopLevelItem(s_item)
            script = self._load(sc.id)
            for pi, page in enumerate(script.pages):
                p_item = QTreeWidgetItem([self._page_label(page)])
                p_item.setData(0, _ROLE, {"kind": "page", "scene_id": sc.id,
                                          "page": pi})
                s_item.addChild(p_item)
                for ci, panel in enumerate(page.panels):
                    c_item = QTreeWidgetItem([self._panel_label(panel)])
                    c_item.setData(0, _ROLE, {"kind": "panel", "scene_id": sc.id,
                                              "page": pi, "panel": ci})
                    p_item.addChild(c_item)
                p_item.setExpanded(True)
            s_item.setExpanded(True)
        self._tree.blockSignals(False)

        if not scenes:
            self._sel = {}
            self._scene_id = None
            self._render_detail()
            return
        # Restore selection (or default to the first scene).
        target = self._find_item(keep) or self._tree.topLevelItem(0)
        if target is not None:
            self._tree.setCurrentItem(target)
        else:
            self._on_select(None)

    def _find_item(self, sel: dict):
        if not sel:
            return None

        def walk(item):
            data = item.data(0, _ROLE)
            if isinstance(data, dict) and data == sel:
                return item
            for i in range(item.childCount()):
                found = walk(item.child(i))
                if found is not None:
                    return found
            return None
        for i in range(self._tree.topLevelItemCount()):
            found = walk(self._tree.topLevelItem(i))
            if found is not None:
                return found
        return None

    def _scene_label(self, scene) -> str:
        title = (getattr(scene, "title", "") or "Untitled").strip() or "Untitled"
        return f"Scene — {title}"

    def _page_label(self, page: gnb.Page) -> str:
        title = (page.title or "").strip()
        head = f"Page {page.number}" + (f" — {title}" if title else "")
        return f"{head}  ({len(page.panels)} panel(s))"

    def _panel_label(self, panel: gnb.Panel) -> str:
        vis = (panel.visual_description or "").strip().replace("\n", " ")
        snippet = (vis[:40] + "…") if len(vis) > 40 else (vis or "(empty)")
        flags = []
        if (panel.dialogue or "").strip():
            flags.append("💬")
        if (panel.caption or "").strip():
            flags.append("▤")
        if (panel.sfx or "").strip():
            flags.append("✺")
        tag = ("  " + " ".join(flags)) if flags else ""
        return f"Panel {panel.number} — {snippet}{tag}"

    def select_scene(self, scene_id: int) -> None:
        """Select a scene's node in the navigator (used when navigating in)."""
        item = self._find_item({"kind": "scene", "scene_id": scene_id})
        if item is not None:
            self._tree.setCurrentItem(item)

    def _on_select(self, item) -> None:
        data = item.data(0, _ROLE) if item is not None else None
        self._sel = dict(data) if isinstance(data, dict) else {}
        sid = self._sel.get("scene_id")
        if sid is not None and sid != self._scene_id:
            self._scene_id = sid
            self._script = self._load(sid)
        elif sid is not None:
            # Same scene — keep the cached script (already in sync via commits).
            pass
        self._render_detail()

    # ------------------------------------------------------------------ detail
    def _clear_detail(self) -> None:
        while self._detail_layout.count():
            it = self._detail_layout.takeAt(0)
            w = it.widget()
            if w is not None:
                w.deleteLater()

    def _render_detail(self) -> None:
        self._clear_detail()
        if not self._gn_scenes():
            self._detail_layout.addWidget(QLabel(
                "No scene yet. Begin building your Graphic Novel scene."))
            btn = QPushButton("Create Scene")
            btn.setObjectName("gnDetailCreateScene")
            btn.clicked.connect(self._add_scene)
            self._detail_layout.addWidget(btn)
            self._detail_layout.addStretch()
            return

        kind = self._sel.get("kind")
        if kind == "panel":
            self._render_panel_detail()
        elif kind == "page":
            self._render_page_detail()
        else:
            self._render_scene_detail()
        self._detail_layout.addStretch()

    def _render_scene_detail(self) -> None:
        sid = self._sel.get("scene_id")
        scene = self._db.get_scene_by_id(sid) if sid is not None else None
        title = (getattr(scene, "title", "") or "Untitled") if scene else "Scene"
        self._detail_layout.addWidget(self._title_label(f"{title}"))
        if not self._script.pages:
            self._detail_layout.addWidget(QLabel(
                "Begin building your Graphic Novel scene. Add a Page to start "
                "structuring panels."))
            btn = QPushButton("+ Add Page")
            btn.setObjectName("gnDetailAddPage")
            btn.clicked.connect(self._add_page)
            self._detail_layout.addWidget(btn)
        else:
            self._detail_layout.addWidget(QLabel(
                "Select a Page or Panel on the left to edit it."))

    def _render_page_detail(self) -> None:
        pi = self._sel.get("page")
        try:
            page = self._script.pages[pi]
        except (IndexError, TypeError):
            return
        self._detail_layout.addWidget(self._title_label(f"Page {page.number}"))

        self._detail_layout.addWidget(QLabel("Title"))
        title_edit = QLineEdit(page.title or "")
        title_edit.setObjectName("gnPageTitle")
        title_edit.editingFinished.connect(
            lambda e=title_edit, p=pi: self._commit_page_field(p, "title", e.text()))
        self._detail_layout.addWidget(title_edit)

        self._detail_layout.addWidget(QLabel("Page notes"))
        notes = _FocusPlainText()
        notes.setObjectName("gnPageSummary")
        notes.setPlainText(page.summary or "")
        notes.setFixedHeight(60)
        notes.committed.connect(
            lambda e=notes, p=pi: self._commit_page_field(p, "summary",
                                                          e.toPlainText()))
        self._detail_layout.addWidget(notes)

        if not page.panels:
            self._detail_layout.addWidget(QLabel("No panels yet."))
        btn = QPushButton("+ Add Panel")
        btn.setObjectName("gnDetailAddPanel")
        btn.clicked.connect(self._add_panel)
        self._detail_layout.addWidget(btn)

    def _render_panel_detail(self) -> None:
        pi, ci = self._sel.get("page"), self._sel.get("panel")
        try:
            panel = self._script.pages[pi].panels[ci]
        except (IndexError, TypeError):
            return
        self._detail_layout.addWidget(self._title_label(
            f"Page {self._script.pages[pi].number} · Panel {panel.number}"))
        for key, label, multiline in _PANEL_FIELDS:
            self._detail_layout.addWidget(QLabel(label))
            if multiline:
                ed = _FocusPlainText()
                ed.setPlainText(getattr(panel, key, "") or "")
                ed.setFixedHeight(60)
                ed.committed.connect(
                    lambda e=ed, k=key, p=pi, c=ci:
                    self._commit_panel_field(p, c, k, e.toPlainText()))
            else:
                ed = QLineEdit(getattr(panel, key, "") or "")
                ed.editingFinished.connect(
                    lambda e=ed, k=key, p=pi, c=ci:
                    self._commit_panel_field(p, c, k, e.text()))
            ed.setObjectName(f"gnPanelField_{key}")
            self._detail_layout.addWidget(ed)

    def _title_label(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet("font-size: 13px; font-weight: bold;")
        return lbl

    # ------------------------------------------------------------- mutations
    def _save(self) -> None:
        if self._scene_id is None:
            return
        gnb.save_scene_script(self._db, self._scene_id, self._script)
        if self._on_data_changed:
            self._on_data_changed()

    def _commit_panel_field(self, page_idx, panel_idx, field, value) -> None:
        try:
            panel = self._script.pages[page_idx].panels[panel_idx]
        except (IndexError, TypeError):
            return
        if getattr(panel, field, None) == value:
            return
        setattr(panel, field, value)
        self._save()
        # Update just the affected tree label (keep focus / avoid full rebuild).
        item = self._find_item({"kind": "panel", "scene_id": self._scene_id,
                                "page": page_idx, "panel": panel_idx})
        if item is not None:
            item.setText(0, self._panel_label(panel))

    def _commit_page_field(self, page_idx, field, value) -> None:
        try:
            page = self._script.pages[page_idx]
        except (IndexError, TypeError):
            return
        if getattr(page, field, None) == value:
            return
        setattr(page, field, value)
        self._save()
        item = self._find_item({"kind": "page", "scene_id": self._scene_id,
                                "page": page_idx})
        if item is not None:
            item.setText(0, self._page_label(page))

    def _add_scene(self) -> None:
        from storyplanner import story_structure as ss
        scene = ss.create_scene(self._db, self._project_id,
                                title="Untitled Scene")
        self._sel = {"kind": "scene", "scene_id": scene.id}
        self._scene_id = scene.id
        self._script = self._load(scene.id)
        self.refresh()
        if self._on_data_changed:
            self._on_data_changed()

    def _ensure_scene(self) -> int | None:
        if self._scene_id is not None:
            return self._scene_id
        scenes = self._gn_scenes()
        if scenes:
            self._scene_id = scenes[0].id
            self._script = self._load(self._scene_id)
            return self._scene_id
        return None

    def _add_page(self) -> None:
        sid = self._ensure_scene()
        if sid is None:
            return
        gnb.add_page(self._script, title="")
        self._save()
        self._sel = {"kind": "page", "scene_id": sid,
                     "page": len(self._script.pages) - 1}
        self.refresh()

    def _add_panel(self) -> None:
        sid = self._ensure_scene()
        if sid is None:
            return
        page_idx = self._sel.get("page")
        if page_idx is None or page_idx >= len(self._script.pages):
            if not self._script.pages:
                gnb.add_page(self._script, title="")
            page_idx = len(self._script.pages) - 1
        gnb.add_panel(self._script.pages[page_idx])
        gnb._renumber(self._script)
        self._save()
        self._sel = {"kind": "panel", "scene_id": sid, "page": page_idx,
                     "panel": len(self._script.pages[page_idx].panels) - 1}
        self.refresh()

    def _move_up(self) -> None:
        self._move(-1)

    def _move_down(self) -> None:
        self._move(+1)

    def _move(self, delta: int) -> None:
        kind = self._sel.get("kind")
        if kind == "panel":
            pi, ci = self._sel.get("page"), self._sel.get("panel")
            try:
                gnb.move_panel(self._script.pages[pi], ci, delta)
            except (IndexError, TypeError):
                return
            new_ci = max(0, min(ci + delta, len(self._script.pages[pi].panels) - 1))
            self._save()
            self._sel = {"kind": "panel", "scene_id": self._scene_id,
                         "page": pi, "panel": new_ci}
            self.refresh()
        elif kind == "page":
            pi = self._sel.get("page")
            pages = self._script.pages
            j = pi + delta
            if pi is None or j < 0 or j >= len(pages):
                return
            pages[pi], pages[j] = pages[j], pages[pi]
            gnb._renumber(self._script)
            self._save()
            self._sel = {"kind": "page", "scene_id": self._scene_id, "page": j}
            self.refresh()

    def _delete_selected(self) -> None:
        kind = self._sel.get("kind")
        if kind == "panel":
            if not safe_dialogs.question(self, "Delete Panel",
                                         "Delete this panel?"):
                return
            pi, ci = self._sel.get("page"), self._sel.get("panel")
            try:
                gnb.delete_panel(self._script.pages[pi], ci)
            except (IndexError, TypeError):
                return
            self._save()
            self._sel = {"kind": "page", "scene_id": self._scene_id, "page": pi}
            self.refresh()
        elif kind == "page":
            if not safe_dialogs.question(self, "Delete Page",
                                         "Delete this page and its panels?"):
                return
            pi = self._sel.get("page")
            try:
                gnb.delete_page(self._script, pi)
            except (IndexError, TypeError):
                return
            self._save()
            self._sel = {"kind": "scene", "scene_id": self._scene_id}
            self.refresh()
        elif kind == "scene":
            if not safe_dialogs.question(
                    self, "Delete Scene",
                    "Delete this scene and its pages/panels? This removes its body."):
                return
            sid = self._sel.get("scene_id")
            self._db.delete_scene(sid)
            self._sel = {}
            self._scene_id = None
            self.refresh()
            if self._on_data_changed:
                self._on_data_changed()
