"""Graphic Novel Manuscript — a comics SCRIPT editor (Pages → Panels inline).

The Graphic Novel writing surface, mounted as the **Manuscript** content for
Graphic Novel projects. It is a *script editor*, not an outliner: the page is
the writing surface. The whole scene script is rendered inline as a vertical
flow of PAGE blocks, each containing Panel cards whose five fields
(Visual / Caption / Dialogue / SFX / Notes) are always visible and editable in
place — exactly like writing a comics script top to bottom. There is no
structure tree here; structural navigation/management is the **Outline**'s job
(`GraphicNovelOutlineView`), which mirrors this view over the same body.

Layout::

    [ scene selector ▾ ]  [+ Scene] [+ Page]
    ┌──────────────────────────────────────────────┐
    │ PAGE 1   (title) ............... [+ Panel] x │
    │   page notes                                 │
    │   ┌ Panel 1 ──────────────────── ▲ ▼ Delete ┐│
    │   │ Visual   [..............................]││
    │   │ Caption  [..............................]││
    │   │ Dialogue [..............................]││
    │   │ SFX      [..............................]││
    │   │ Notes    [..............................]││
    │   └─────────────────────────────────────────┘│
    │ PAGE 2 ...                                   │
    │ [+ Add Page]                                 │
    └──────────────────────────────────────────────┘

Empty-state ladder: no scene → *Create Scene*; scene without pages → *Add
Page*; page without panels → *Add Panel*; otherwise the full script.

Single source of truth: everything reads/writes the shared ``Scene.content``
body via :mod:`storyplanner.graphic_novel_blocks` — the same body the GN
Outline manages — so the two surfaces mirror automatically on refresh. There is
no separate Pages storage. The standalone Pages route stays disabled (it was
fullscreen-hostile); this view is a single embedded child widget — no top-level
window, no dock, no dialog on mount. **No image generation / prompt / ComfyUI**
fields exist — this is writing/script structure only.
"""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from storyplanner import graphic_novel_blocks as gnb
from storyplanner.ui import safe_dialogs

# (field key, label, multiline?, height)
_PANEL_FIELDS = (
    ("visual_description", "Visual", True, 64),
    ("caption", "Caption", False, 0),
    ("dialogue", "Dialogue", True, 64),
    ("sfx", "SFX", False, 0),
    ("notes", "Notes", True, 44),
)

_PAGE_STYLE = (
    "QFrame#gnPageBlock { border: 1px solid palette(mid);"
    " border-radius: 6px; background: palette(base); }")
_PANEL_STYLE = (
    "QFrame#gnPanelCard { border: 1px solid palette(midlight);"
    " border-left: 3px solid palette(highlight); border-radius: 4px; }")


class _FocusPlainText(QPlainTextEdit):
    """Multi-line edit that commits (emits) when it loses focus."""

    committed = Signal()

    def __init__(self, *a, **k) -> None:
        super().__init__(*a, **k)
        self.setTabChangesFocus(True)   # Tab walks the script like a form

    def focusOutEvent(self, event) -> None:  # noqa: N802 (Qt signature)
        super().focusOutEvent(event)
        self.committed.emit()


class GraphicNovelManuscriptView(QWidget):
    """Inline comics-script editor over the shared GN ``Scene.content`` body."""

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

        self._scene_id: int | None = None
        self._script = gnb.GraphicNovelScript()
        # Logical location -> live editor widget (for focus restore/navigation).
        # Keys: ("panel", page_idx, panel_idx, field) / ("page", page_idx, field)
        self._field_editors: dict[tuple, QWidget] = {}
        # Fingerprint of what is currently rendered; refresh() skips the
        # rebuild when the data has not actually changed (keeps focus/clicks
        # alive through the app-wide refresh that follows every save).
        self._rendered_fp: tuple | None = None
        self._scenes_sig: tuple = ()

        root = QVBoxLayout(self)
        root.setContentsMargins(10, 8, 10, 8)
        root.setSpacing(8)

        # -- Header bar: scene selector + create actions --
        bar = QHBoxLayout()
        bar.setSpacing(6)
        heading = QLabel("Comics Script")
        heading.setObjectName("gnScriptHeading")
        heading.setStyleSheet("font-size: 14px; font-weight: bold;")
        bar.addWidget(heading)

        self._scene_combo = QComboBox()
        self._scene_combo.setObjectName("gnScriptSceneSelect")
        self._scene_combo.setMinimumWidth(220)
        self._scene_combo.currentIndexChanged.connect(self._on_scene_combo)
        bar.addWidget(self._scene_combo, stretch=1)

        for label, slot, name in (
            ("+ Scene", self._add_scene, "gnScriptAddScene"),
            ("+ Page", self._add_page, "gnScriptAddPage"),
        ):
            b = QPushButton(label)
            b.setObjectName(name)
            b.clicked.connect(slot)
            bar.addWidget(b)
        root.addLayout(bar)

        # -- Script surface: the whole scene script, inline --
        self._scroll = QScrollArea()
        self._scroll.setObjectName("gnScriptScroll")
        self._scroll.setWidgetResizable(True)
        self._host = QWidget()
        self._host.setObjectName("gnScriptHost")
        self._script_layout = QVBoxLayout(self._host)
        self._script_layout.setContentsMargins(4, 4, 4, 4)
        self._script_layout.setSpacing(10)
        self._scroll.setWidget(self._host)
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

    def _scene_label(self, scene) -> str:
        title = (getattr(scene, "title", "") or "Untitled").strip() or "Untitled"
        act = (getattr(scene, "act", "") or "").strip()
        chapter = (getattr(scene, "chapter", "") or "").strip()
        prefix = " · ".join(p for p in (act, chapter) if p)
        return f"{prefix} · {title}" if prefix else title

    # ---------------------------------------------------------------- refresh
    def refresh(self) -> None:
        """Re-read the shared body; rebuild only if it actually changed."""
        scenes = self._gn_scenes()
        scenes_sig = tuple((sc.id, self._scene_label(sc)) for sc in scenes)
        ids = [sc.id for sc in scenes]
        if self._scene_id not in ids:
            self._scene_id = ids[0] if ids else None
        fresh = (gnb.load_scene_script(self._db, self._scene_id)
                 if self._scene_id is not None else gnb.GraphicNovelScript())
        fp = (scenes_sig, self._scene_id,
              gnb.serialize_graphic_novel_script(fresh))
        if fp == self._rendered_fp:
            return                       # rendered UI already matches the data
        focus_loc = self._focused_location()
        self._script = fresh
        self._scenes_sig = scenes_sig
        self._rebuild_combo(scenes_sig)
        self._rebuild_script(have_scenes=bool(scenes))
        self._rendered_fp = fp
        if focus_loc is not None:
            self._restore_focus(focus_loc)

    def _mark_rendered_current(self) -> None:
        """After an in-place field commit the visible editors already show the
        new value, so record the new state as rendered — the app-wide refresh
        that follows the save can then skip the rebuild and the user's focus,
        cursor and pending clicks survive."""
        self._rendered_fp = (self._scenes_sig, self._scene_id,
                             gnb.serialize_graphic_novel_script(self._script))

    def _rebuild_combo(self, scenes_sig: tuple) -> None:
        self._scene_combo.blockSignals(True)
        self._scene_combo.clear()
        for sid, label in scenes_sig:
            self._scene_combo.addItem(label, sid)
        idx = next((i for i, (sid, _) in enumerate(scenes_sig)
                    if sid == self._scene_id), -1)
        self._scene_combo.setCurrentIndex(idx)
        self._scene_combo.setEnabled(bool(scenes_sig))
        self._scene_combo.blockSignals(False)

    def _on_scene_combo(self, index: int) -> None:
        sid = self._scene_combo.itemData(index)
        if sid is None or sid == self._scene_id:
            return
        self._scene_id = int(sid)
        self._rendered_fp = None         # force the rebuild for the new scene
        self.refresh()

    # ------------------------------------------------------ focus preservation
    def _focused_location(self) -> tuple | None:
        w = QApplication.focusWidget()
        if w is None or not self.isAncestorOf(w):
            return None
        loc = getattr(w, "_gn_loc", None)
        if loc is None:
            return None
        if isinstance(w, QPlainTextEdit):
            pos = w.textCursor().position()
        elif isinstance(w, QLineEdit):
            pos = w.cursorPosition()
        else:
            pos = 0
        return (loc, pos)

    def _restore_focus(self, focus_loc: tuple) -> None:
        loc, pos = focus_loc
        editor = self._field_editors.get(loc)
        if editor is None:
            return
        editor.setFocus()
        if isinstance(editor, QPlainTextEdit):
            cur = editor.textCursor()
            cur.setPosition(min(pos, len(editor.toPlainText())))
            editor.setTextCursor(cur)
        elif isinstance(editor, QLineEdit):
            editor.setCursorPosition(min(pos, len(editor.text())))

    # ------------------------------------------------------------- navigation
    def select_scene(self, scene_id: int) -> None:
        """Show *scene_id*'s script (used when navigating in from the Outline)."""
        if scene_id == self._scene_id:
            return
        self._scene_id = scene_id
        self._rendered_fp = None
        self.refresh()

    def select_page(self, page_idx: int) -> None:
        """Scroll to / focus a page's title field (optional deep-link)."""
        editor = self._field_editors.get(("page", page_idx, "title"))
        if editor is not None:
            self._scroll.ensureWidgetVisible(editor)
            editor.setFocus()

    def select_panel(self, page_idx: int, panel_idx: int) -> None:
        """Scroll to / focus a panel's Visual field (optional deep-link)."""
        editor = self._field_editors.get(
            ("panel", page_idx, panel_idx, "visual_description"))
        if editor is not None:
            self._scroll.ensureWidgetVisible(editor)
            editor.setFocus()

    # ------------------------------------------------------------ script area
    def _clear_script(self) -> None:
        self._field_editors = {}
        while self._script_layout.count():
            it = self._script_layout.takeAt(0)
            w = it.widget()
            if w is not None:
                w.setParent(None)        # drop from the child tree right away
                w.deleteLater()

    def _rebuild_script(self, *, have_scenes: bool) -> None:
        self._clear_script()
        if not have_scenes:
            # Empty state A: no scene in the project yet.
            msg = QLabel("No scene yet. Begin building your Graphic Novel "
                         "scene.")
            msg.setObjectName("gnScriptEmpty")
            self._script_layout.addWidget(msg)
            btn = QPushButton("Create Scene")
            btn.setObjectName("gnDetailCreateScene")
            btn.clicked.connect(self._add_scene)
            self._script_layout.addWidget(btn)
            self._script_layout.addStretch()
            return

        if not self._script.pages:
            # Empty state B: a scene with no pages yet.
            msg = QLabel("This scene has no pages yet. Add a Page to start "
                         "writing your comics script.")
            msg.setObjectName("gnScriptEmpty")
            self._script_layout.addWidget(msg)
            btn = QPushButton("+ Add Page")
            btn.setObjectName("gnDetailAddPage")
            btn.clicked.connect(self._add_page)
            self._script_layout.addWidget(btn)
            self._script_layout.addStretch()
            return

        for pi, page in enumerate(self._script.pages):
            self._script_layout.addWidget(self._build_page_block(pi, page))
        more = QPushButton("+ Add Page")
        more.setObjectName("gnScriptAddPageBottom")
        more.clicked.connect(self._add_page)
        self._script_layout.addWidget(more)
        self._script_layout.addStretch()

    def _build_page_block(self, pi: int, page: gnb.Page) -> QFrame:
        box = QFrame()
        box.setObjectName("gnPageBlock")
        box.setStyleSheet(_PAGE_STYLE)
        v = QVBoxLayout(box)
        v.setContentsMargins(10, 8, 10, 8)
        v.setSpacing(6)

        head = QHBoxLayout()
        head.setSpacing(6)
        lbl = QLabel(f"PAGE {page.number}")
        lbl.setObjectName("gnPageHeader")
        lbl.setStyleSheet("font-size: 15px; font-weight: bold;")
        head.addWidget(lbl)

        title = QLineEdit(page.title or "")
        title.setObjectName("gnPageTitle")
        title.setPlaceholderText("Page title (optional)")
        title._gn_loc = ("page", pi, "title")
        title.editingFinished.connect(
            lambda e=title, p=pi: self._commit_page_field(p, "title", e.text()))
        self._field_editors[("page", pi, "title")] = title
        head.addWidget(title, stretch=1)

        add_panel = QPushButton("+ Panel")
        add_panel.setObjectName("gnDetailAddPanel")
        add_panel.clicked.connect(lambda _=False, p=pi: self._add_panel(p))
        head.addWidget(add_panel)
        del_page = QPushButton("Delete Page")
        del_page.setObjectName("gnPageDelete")
        del_page.clicked.connect(lambda _=False, p=pi: self._delete_page(p))
        head.addWidget(del_page)
        v.addLayout(head)

        notes = _FocusPlainText()
        notes.setObjectName("gnPageSummary")
        notes.setPlaceholderText("Page notes (optional)")
        notes.setPlainText(page.summary or "")
        notes.setFixedHeight(40)
        notes._gn_loc = ("page", pi, "summary")
        notes.committed.connect(
            lambda e=notes, p=pi:
            self._commit_page_field(p, "summary", e.toPlainText()))
        self._field_editors[("page", pi, "summary")] = notes
        v.addWidget(notes)

        if not page.panels:
            # Empty state C: a page with no panels yet.
            empty = QLabel("No panels yet. Add a Panel to write this page.")
            empty.setObjectName("gnPageNoPanels")
            v.addWidget(empty)
        for ci, panel in enumerate(page.panels):
            v.addWidget(self._build_panel_card(pi, ci, panel))
        return box

    def _build_panel_card(self, pi: int, ci: int, panel: gnb.Panel) -> QFrame:
        card = QFrame()
        card.setObjectName("gnPanelCard")
        card.setStyleSheet(_PANEL_STYLE)
        v = QVBoxLayout(card)
        v.setContentsMargins(8, 6, 8, 8)
        v.setSpacing(3)

        head = QHBoxLayout()
        head.setSpacing(4)
        lbl = QLabel(f"Panel {panel.number}")
        lbl.setObjectName("gnPanelHeader")
        lbl.setStyleSheet("font-weight: bold;")
        head.addWidget(lbl)
        head.addStretch()
        for text, delta, name in (("▲", -1, "gnPanelMoveUp"),
                                  ("▼", +1, "gnPanelMoveDown")):
            b = QPushButton(text)
            b.setObjectName(name)
            b.setFixedWidth(28)
            b.clicked.connect(
                lambda _=False, p=pi, c=ci, d=delta: self._move_panel(p, c, d))
            head.addWidget(b)
        delb = QPushButton("Delete")
        delb.setObjectName("gnPanelDelete")
        delb.clicked.connect(
            lambda _=False, p=pi, c=ci: self._delete_panel(p, c))
        head.addWidget(delb)
        v.addLayout(head)

        for key, label, multiline, height in _PANEL_FIELDS:
            cap = QLabel(label)
            cap.setObjectName("gnFieldLabel")
            cap.setStyleSheet("font-size: 11px; font-weight: bold;")
            v.addWidget(cap)
            if multiline:
                ed = _FocusPlainText()
                ed.setPlainText(getattr(panel, key, "") or "")
                ed.setFixedHeight(height)
                ed.committed.connect(
                    lambda e=ed, k=key, p=pi, c=ci:
                    self._commit_panel_field(p, c, k, e.toPlainText()))
            else:
                ed = QLineEdit(getattr(panel, key, "") or "")
                ed.editingFinished.connect(
                    lambda e=ed, k=key, p=pi, c=ci:
                    self._commit_panel_field(p, c, k, e.text()))
            ed.setObjectName(f"gnPanelField_{key}")
            ed._gn_loc = ("panel", pi, ci, key)
            self._field_editors[("panel", pi, ci, key)] = ed
            v.addWidget(ed)
        return card

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
        self._mark_rendered_current()    # editors already show the new value
        self._save()

    def _commit_page_field(self, page_idx, field, value) -> None:
        try:
            page = self._script.pages[page_idx]
        except (IndexError, TypeError):
            return
        if getattr(page, field, None) == value:
            return
        setattr(page, field, value)
        self._mark_rendered_current()
        self._save()

    def _add_scene(self) -> None:
        from storyplanner import story_structure as ss
        scene = ss.create_scene(self._db, self._project_id,
                                title="Untitled Scene")
        self._scene_id = scene.id
        self._rendered_fp = None
        self.refresh()
        if self._on_data_changed:
            self._on_data_changed()

    def _ensure_scene(self) -> int | None:
        if self._scene_id is not None:
            return self._scene_id
        scenes = self._gn_scenes()
        if scenes:
            self._scene_id = scenes[0].id
            self._script = gnb.load_scene_script(self._db, self._scene_id)
            return self._scene_id
        return None

    def _add_page(self) -> None:
        if self._ensure_scene() is None:
            return
        gnb.add_page(self._script, title="")
        self._save()
        self.refresh()
        self.select_page(len(self._script.pages) - 1)

    def _add_panel(self, page_idx: int | None = None) -> None:
        if self._ensure_scene() is None:
            return
        if not self._script.pages:
            gnb.add_page(self._script, title="")
        if page_idx is None or not (0 <= page_idx < len(self._script.pages)):
            page_idx = len(self._script.pages) - 1
        gnb.add_panel(self._script.pages[page_idx])
        gnb._renumber(self._script)
        self._save()
        self.refresh()
        self.select_panel(page_idx, len(self._script.pages[page_idx].panels) - 1)

    def _move_panel(self, page_idx: int, panel_idx: int, delta: int) -> None:
        try:
            page = self._script.pages[page_idx]
        except (IndexError, TypeError):
            return
        if not (0 <= panel_idx < len(page.panels)):
            return
        gnb.move_panel(page, panel_idx, delta)
        self._save()
        self.refresh()

    def _delete_panel(self, page_idx: int, panel_idx: int) -> None:
        if not safe_dialogs.question(self, "Delete Panel",
                                     "Delete this panel?"):
            return
        try:
            gnb.delete_panel(self._script.pages[page_idx], panel_idx)
        except (IndexError, TypeError):
            return
        self._save()
        self.refresh()

    def _delete_page(self, page_idx: int) -> None:
        if not safe_dialogs.question(self, "Delete Page",
                                     "Delete this page and its panels?"):
            return
        try:
            gnb.delete_page(self._script, page_idx)
        except (IndexError, TypeError):
            return
        self._save()
        self.refresh()
