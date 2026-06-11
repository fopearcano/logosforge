"""Graphic Novel Manuscript — a comics SCRIPT editor (Superscript-style blocks).

The Graphic Novel writing surface, mounted as the **Manuscript** content for
Graphic Novel projects. It is a *script editor*, not an outliner and not a
form: the scene's script flows vertically like a document — PAGE headings,
then one **large free-typing script block per panel** in which the writer
types labeled sections (the Superscript-style, label-as-you-type syntax)::

    PAGE 1   (title)                                  [+ Panel] [Delete Page]
    ────────────────────────────────────────────────────────────────────────
      Panel 1                                                  ▲ ▼ Delete
      Visual:
      A tiny chapel buried under rain. The dog stands at the threshold.

      Caption:
      The road had forgotten his name.

      Dialogue:
      ZAMPANÒ: Woof.

      SFX:
      THOOM

    PAGE 2 …

Labels (Visual / Caption / Dialogue / SFX / Notes) are optional — unlabeled
leading text is the panel's Visual; speaker lines like ``NAME: …`` stay plain
content. Each block parses back into the canonical five-field Panel on
commit (focus-out) via :func:`graphic_novel_blocks.parse_panel_text`, so the
canonical model (**Act → Page → Scene → Panel**: an Act owns its Pages and
Scenes, a Panel belongs to one Scene and sits on one Page, a Scene can span
Pages and a Page can hold Panels from several Scenes) remains intact
underneath, page/panel numbers stay auto-numbered, and the **Outline** — the
canonical structure — is what this Manuscript derives from, mirroring every
edit over the same shared ``Scene.content`` body. PAGE headings show the
**act-wide** page numbers from :mod:`graphic_novel_structure`; chapters are
hidden in Graphic Novel mode (storage labels only). Line breaks inside a
field are preserved end-to-end.

Empty-state ladder: no Act → *"Create an Act to begin your Graphic Novel."*
with **+ Act**; Act/scene without pages → *Add Page*; page without panels →
*Add Panel*; otherwise the flowing script.

The standalone Pages route stays disabled (it was fullscreen-hostile); this
view is a single embedded child widget — no top-level window, no dock, no
dialog on mount. **No image generation / prompt / ComfyUI** fields exist —
this is writing/script structure only.
"""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import Qt, Signal
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
from storyplanner import graphic_novel_structure as gns
from storyplanner.ui import safe_dialogs

EMPTY_PROJECT_MESSAGE = "Create an Act to begin your Graphic Novel."

_SCRIPT_PLACEHOLDER = (
    "Visual:\n"
    "What we see in this panel…\n\n"
    "Dialogue:\n"
    "NAME: spoken line\n\n"
    "Labels (Visual / Caption / Dialogue / SFX / Notes) are optional — "
    "unlabeled text is the Visual."
)

_BORDERLESS_TEXT = (
    "QPlainTextEdit { border: none; background: transparent;"
    " font-size: 14px; }")
_BORDERLESS_LINE = (
    "QLineEdit { border: none; background: transparent; }")


class _FocusPlainText(QPlainTextEdit):
    """Multi-line edit that commits (emits) when it loses focus."""

    committed = Signal()

    def __init__(self, *a, **k) -> None:
        super().__init__(*a, **k)
        self.setTabChangesFocus(True)   # Tab walks the script like a document

    def focusOutEvent(self, event) -> None:  # noqa: N802 (Qt signature)
        super().focusOutEvent(event)
        self.committed.emit()


class _AutoGrowScript(_FocusPlainText):
    """A script block that grows with its text (no inner scrollbar), so the
    whole scene scrolls as ONE document — manuscript flow, not form fields."""

    focused = Signal()

    def focusInEvent(self, event) -> None:  # noqa: N802 (Qt signature)
        super().focusInEvent(event)
        self.focused.emit()

    def __init__(self, *, min_height: int = 120, parent=None) -> None:
        super().__init__(parent)
        self._min_height = min_height
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setStyleSheet(_BORDERLESS_TEXT)
        self.textChanged.connect(self._grow)
        self._grow()

    def _grow(self) -> None:
        # Block count gives a layout-independent height (the document's pixel
        # size is unreliable before the first paint in offscreen/headless).
        line_h = self.fontMetrics().lineSpacing()
        px = max(self._min_height,
                 self.document().blockCount() * (line_h + 2) + 24)
        self.setFixedHeight(px)

    def setPlainText(self, text: str) -> None:  # noqa: N802 (Qt signature)
        super().setPlainText(text)
        self._grow()


class GraphicNovelManuscriptView(QWidget):
    """Comics-script editor (script blocks) over the shared GN body."""

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
        # Act-wide placement of the current scene (the Outline is canonical;
        # PAGE headings show these act-wide numbers, not scene-local ones).
        self._page_start = 1
        self._scene_act = ""
        self._scene_pages_label = ""
        # Last panel whose script block had focus — (page_idx, panel_idx).
        # The Voice Commit Router reads this as "the selected Panel".
        self._last_panel_loc: tuple[int, int] | None = None
        # Logical location -> live editor widget (focus restore / navigation).
        # Keys: ("panel", page_idx, panel_idx) -> the panel's script block;
        #       ("page", page_idx, "title"|"summary") -> page header editors.
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

        # -- Script surface: the whole scene script, one flowing document --
        self._scroll = QScrollArea()
        self._scroll.setObjectName("gnScriptScroll")
        self._scroll.setWidgetResizable(True)
        self._host = QWidget()
        self._host.setObjectName("gnScriptHost")
        self._script_layout = QVBoxLayout(self._host)
        self._script_layout.setContentsMargins(16, 10, 16, 10)
        self._script_layout.setSpacing(8)
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
        # Chapters are hidden in Graphic Novel mode (storage labels only).
        title = (getattr(scene, "title", "") or "Untitled").strip() or "Untitled"
        act = (getattr(scene, "act", "") or "").strip()
        return f"{act} · {title}" if act else title

    def _scene_context_text(self) -> str:
        scene = (self._db.get_scene_by_id(self._scene_id)
                 if self._scene_id is not None else None)
        if scene is None:
            return ""
        title = (getattr(scene, "title", "") or "Untitled").strip() or "Untitled"
        parts = [p for p in (self._scene_act, self._scene_pages_label) if p]
        path = " · ".join(parts)
        return f"{path}  —  SCENE: {title}" if path else f"SCENE: {title}"

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
        # Act-wide placement (canonical Act → Page → Scene → Panel): another
        # scene's pages shift this scene's page numbers, so the start page is
        # part of the fingerprint.
        start, act_name, pages_label = 1, "", ""
        if self._scene_id is not None:
            act, placement = gns.find_placement(self._db, self._project_id,
                                                self._scene_id)
            if placement is not None:
                start = placement.start_page
                act_name = act or ""
                pages_label = gns.scene_page_range_label(placement)
        fp = (scenes_sig, self._scene_id, start,
              gnb.serialize_graphic_novel_script(fresh))
        if fp == self._rendered_fp:
            return                       # rendered UI already matches the data
        focus_loc = self._focused_location()
        self._script = fresh
        self._page_start = start
        self._scene_act = act_name
        self._scene_pages_label = pages_label
        self._scenes_sig = scenes_sig
        self._rebuild_combo(scenes_sig)
        self._rebuild_script(have_scenes=bool(scenes))
        self._rendered_fp = fp
        if focus_loc is not None:
            self._restore_focus(focus_loc)

    def _mark_rendered_current(self) -> None:
        """After an in-place commit the visible blocks already show the new
        text, so record the new state as rendered — the app-wide refresh that
        follows the save can then skip the rebuild and the user's focus,
        cursor and pending clicks survive."""
        self._rendered_fp = (self._scenes_sig, self._scene_id,
                             self._page_start,
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
        self._last_panel_loc = None      # panel selection is scene-scoped
        self._rendered_fp = None         # force the rebuild for the new scene
        self.refresh()

    def _note_panel_focus(self, page_idx: int, panel_idx: int) -> None:
        self._last_panel_loc = (page_idx, panel_idx)

    def current_panel_ref(self) -> tuple[int, int, int] | None:
        """The selected Panel for voice commits: (scene_id, page_idx,
        panel_idx) of the last-focused script block, validated against the
        live script — or ``None`` when nothing valid is selected."""
        if self._scene_id is None or self._last_panel_loc is None:
            return None
        page_idx, panel_idx = self._last_panel_loc
        if not (0 <= page_idx < len(self._script.pages)):
            return None
        if not (0 <= panel_idx < len(self._script.pages[page_idx].panels)):
            return None
        return (self._scene_id, page_idx, panel_idx)

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
        """Scroll to / focus a page's title (Outline deep-link)."""
        editor = self._field_editors.get(("page", page_idx, "title"))
        if editor is not None:
            self._scroll.ensureWidgetVisible(editor)
            editor.setFocus()

    def select_panel(self, page_idx: int, panel_idx: int) -> None:
        """Scroll to / focus a panel's script block (Outline deep-link)."""
        editor = self._field_editors.get(("panel", page_idx, panel_idx))
        if editor is not None:
            self._note_panel_focus(page_idx, panel_idx)
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

    def _muted(self, text: str, *, name: str = "") -> QLabel:
        lbl = QLabel(text)
        if name:
            lbl.setObjectName(name)
        lbl.setStyleSheet("color: palette(mid); font-size: 12px;")
        return lbl

    def _rebuild_script(self, *, have_scenes: bool) -> None:
        self._clear_script()
        if not have_scenes:
            # Empty state A: no Act in the project yet.
            msg = QLabel(EMPTY_PROJECT_MESSAGE)
            msg.setObjectName("gnScriptEmpty")
            self._script_layout.addWidget(msg)
            btn = QPushButton("+ Act")
            btn.setObjectName("gnScriptCreateAct")
            btn.clicked.connect(self._add_act)
            self._script_layout.addWidget(btn)
            self._script_layout.addStretch()
            return

        # Scene context — the script document's header line.
        context = QLabel(self._scene_context_text())
        context.setObjectName("gnScriptContext")
        context.setStyleSheet(
            "color: palette(mid); font-size: 12px; font-weight: bold;")
        self._script_layout.addWidget(context)

        if not self._script.pages:
            # Empty state B: a scene with no pages yet.
            msg = QLabel("Start the comics script for this scene.")
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
        v = QVBoxLayout(box)
        v.setContentsMargins(0, 10, 0, 4)
        v.setSpacing(4)

        head = QHBoxLayout()
        head.setSpacing(8)
        # Act-wide page number (the Outline's canonical coordinate).
        lbl = QLabel(f"PAGE {self._page_start + pi}")
        lbl.setObjectName("gnPageHeader")
        lbl.setStyleSheet("font-size: 16px; font-weight: bold;")
        head.addWidget(lbl)

        title = QLineEdit(page.title or "")
        title.setObjectName("gnPageTitle")
        title.setPlaceholderText("Page title (optional)")
        title.setStyleSheet(_BORDERLESS_LINE + " QLineEdit { font-size: 13px; }")
        title._gn_loc = ("page", pi, "title")
        title.editingFinished.connect(
            lambda e=title, p=pi: self._commit_page_field(p, "title", e.text()))
        self._field_editors[("page", pi, "title")] = title
        head.addWidget(title, stretch=1)

        add_panel = QPushButton("+ Panel")
        add_panel.setObjectName("gnDetailAddPanel")
        add_panel.setFlat(True)
        add_panel.clicked.connect(lambda _=False, p=pi: self._add_panel(p))
        head.addWidget(add_panel)
        del_page = QPushButton("Delete Page")
        del_page.setObjectName("gnPageDelete")
        del_page.setFlat(True)
        del_page.clicked.connect(lambda _=False, p=pi: self._delete_page(p))
        head.addWidget(del_page)
        v.addLayout(head)

        rule = QFrame()
        rule.setFrameShape(QFrame.Shape.HLine)
        rule.setObjectName("gnPageRule")
        v.addWidget(rule)

        notes = _FocusPlainText()
        notes.setObjectName("gnPageSummary")
        notes.setPlaceholderText("Page notes (optional)")
        notes.setPlainText(page.summary or "")
        notes.setFixedHeight(34)
        notes.setStyleSheet(_BORDERLESS_TEXT + " QPlainTextEdit {"
                            " font-size: 12px; font-style: italic; }")
        notes._gn_loc = ("page", pi, "summary")
        notes.committed.connect(
            lambda e=notes, p=pi:
            self._commit_page_field(p, "summary", e.toPlainText()))
        self._field_editors[("page", pi, "summary")] = notes
        v.addWidget(notes)

        if not page.panels:
            # Empty state C: a page with no panels yet.
            v.addWidget(self._muted("No panels yet. Add a Panel to write "
                                    "this page.", name="gnPageNoPanels"))
        for ci, panel in enumerate(page.panels):
            v.addWidget(self._build_panel_block(pi, ci, panel))
        return box

    def _build_panel_block(self, pi: int, ci: int, panel: gnb.Panel) -> QFrame:
        block = QFrame()
        block.setObjectName("gnPanelCard")
        block.setStyleSheet(
            "QFrame#gnPanelCard { border: none;"
            " border-left: 2px solid palette(midlight); }")
        v = QVBoxLayout(block)
        v.setContentsMargins(12, 2, 0, 6)
        v.setSpacing(2)

        head = QHBoxLayout()
        head.setSpacing(4)
        lbl = QLabel(f"Panel {panel.number}")
        lbl.setObjectName("gnPanelHeader")
        lbl.setStyleSheet("font-weight: bold; color: palette(mid);"
                          " font-size: 12px;")
        head.addWidget(lbl)
        head.addStretch()
        for text, delta, name in (("▲", -1, "gnPanelMoveUp"),
                                  ("▼", +1, "gnPanelMoveDown")):
            b = QPushButton(text)
            b.setObjectName(name)
            b.setFlat(True)
            b.setFixedWidth(26)
            b.clicked.connect(
                lambda _=False, p=pi, c=ci, d=delta: self._move_panel(p, c, d))
            head.addWidget(b)
        delb = QPushButton("Delete")
        delb.setObjectName("gnPanelDelete")
        delb.setFlat(True)
        delb.clicked.connect(
            lambda _=False, p=pi, c=ci: self._delete_panel(p, c))
        head.addWidget(delb)
        v.addLayout(head)

        ed = _AutoGrowScript(min_height=120)
        ed.setObjectName("gnPanelScript")
        ed.setPlaceholderText(_SCRIPT_PLACEHOLDER)
        ed.setPlainText(gnb.panel_script_text(panel))
        ed.focused.connect(
            lambda p=pi, c=ci: self._note_panel_focus(p, c))
        ed.committed.connect(
            lambda e=ed, p=pi, c=ci:
            self._commit_panel_script(p, c, e.toPlainText()))
        ed._gn_loc = ("panel", pi, ci)
        self._field_editors[("panel", pi, ci)] = ed
        v.addWidget(ed)
        return block

    # ------------------------------------------------------------- mutations
    def _save(self) -> None:
        if self._scene_id is None:
            return
        gnb.save_scene_script(self._db, self._scene_id, self._script)
        if self._on_data_changed:
            self._on_data_changed()

    def _commit_panel_script(self, page_idx, panel_idx, text) -> None:
        """Parse one panel's script block back into the five canonical fields."""
        try:
            panel = self._script.pages[page_idx].panels[panel_idx]
        except (IndexError, TypeError):
            return
        fields = gnb.parse_panel_text(text)
        if all(getattr(panel, key, "") == value
               for key, value in fields.items()):
            return
        for key, value in fields.items():
            setattr(panel, key, value)
        self._mark_rendered_current()    # the block already shows this text
        self._save()

    def _commit_panel_field(self, page_idx, panel_idx, field, value) -> None:
        """Set a single canonical field (programmatic/navigation path)."""
        try:
            panel = self._script.pages[page_idx].panels[panel_idx]
        except (IndexError, TypeError):
            return
        if getattr(panel, field, None) == value:
            return
        setattr(panel, field, value)
        editor = self._field_editors.get(("panel", page_idx, panel_idx))
        if editor is not None:
            editor.blockSignals(True)
            editor.setPlainText(gnb.panel_script_text(panel))
            editor.blockSignals(False)
        self._mark_rendered_current()
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

    def _add_act(self) -> None:
        """Empty state A: create the first Act (seeds its first scene)."""
        from storyplanner import story_structure as ss
        scene = ss.create_act(self._db, self._project_id)
        self._scene_id = scene.id
        self._rendered_fp = None
        self.refresh()
        if self._on_data_changed:
            self._on_data_changed()

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
