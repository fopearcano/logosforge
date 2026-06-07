"""Plan view — hierarchical Acts → Chapters → Scenes outline.

Acts and Chapters are derived from Scene.act and Scene.chapter string fields.
Renaming an act/chapter updates all scenes that share that label.
Summaries for acts and chapters live in the project's settings_json under
`act_summaries` and `chapter_summaries` keyed by the act/chapter name.
Scene summaries live on Scene.summary.
"""

from collections.abc import Callable

from PySide6.QtCore import QMimeData, QPoint, Qt
from PySide6.QtGui import QAction, QDrag
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMenu,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from storyplanner.db import Database
from storyplanner.quantum_outliner.state import OutlineMode, get_outline_mode
from storyplanner.story_structure import (
    UNASSIGNED_ACT as _UNTITLED_ACT,
    UNASSIGNED_CHAPTER as _UNTITLED_CHAPTER,
    act_key as _act_key,
    build_structure_tree as build_plan_tree,
    chapter_key as _chapter_key,
    compute_structural_numbers as compute_outline_numbering,
    flatten_tree_to_order as _flatten_tree_to_order,
)
from storyplanner.ui import theme
from storyplanner.ui.outline_ai import OutlineGenWorker, build_provider, outline_messages


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


def _is_placeholder_scene(scene) -> bool:
    """A scene is a *pure structural placeholder* when it has no written body,
    no planning summary, and only a default/empty title. Such scenes are safe to
    remove when clearing the outline; anything else is preserved."""
    has_body = bool((scene.content or "").strip())
    has_summary = bool((scene.summary or "").strip())
    title = (scene.title or "").strip().lower()
    is_default_title = title in ("", "untitled", "untitled scene")
    return not has_body and not has_summary and is_default_title


def clear_outline_structure(db: Database, project_id: int) -> dict:
    """Clear the whole Outline structure *safely*.

    - Pure structural placeholder scenes (no body, no summary, default title)
      are deleted — they only existed to scaffold Acts/Chapters.
    - Scenes that contain written text **or** a planning summary are PRESERVED;
      their Act/Chapter labels are cleared (detached to Unsorted) so no prose or
      planning is ever lost.
    - All Act/Chapter summaries are removed.

    Manuscript body text is never deleted. Returns ``{"deleted", "detached"}``.
    """
    deleted = 0
    detached = 0
    for scene in db.get_all_scenes(project_id):
        if _is_placeholder_scene(scene):
            db.delete_scene(scene.id)
            deleted += 1
        elif (scene.act or "") or (scene.chapter or ""):
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
                chapter="",
                plotline=scene.plotline,
            )
            detached += 1
    settings = db.get_project_settings(project_id)
    settings["act_summaries"] = {}
    settings["chapter_summaries"] = {}
    db.save_project_settings(project_id, settings)
    return {"deleted": deleted, "detached": detached}


# ---------------------------------------------------------------------------
# Status (stored as a ``status:<value>`` tag — no schema change)
# ---------------------------------------------------------------------------

# Compact planning-board statuses. Stored on Scene.tags as "status:<value>"
# so the existing tag system carries them with zero storage migration.
STATUS_VALUES = ["Draft", "Edited", "Needs Work", "Complete"]
_STATUS_PREFIX = "status:"


def _split_tags(raw: str) -> list[str]:
    return [t.strip() for t in (raw or "").split(",") if t.strip()]


def scene_status(scene) -> str:
    """Return the scene's planning status (from a ``status:`` tag) or ""."""
    for tag in _split_tags(getattr(scene, "tags", "") or ""):
        if tag.lower().startswith(_STATUS_PREFIX):
            return tag.split(":", 1)[1].strip()
    return ""


def _tags_without_status(raw: str) -> list[str]:
    return [t for t in _split_tags(raw)
            if not t.lower().startswith(_STATUS_PREFIX)]


def set_scene_status(db: Database, scene, value: str) -> None:
    """Set/clear the scene's status tag, preserving all other tags."""
    tags = _tags_without_status(getattr(scene, "tags", "") or "")
    if value:
        tags.append(f"{_STATUS_PREFIX}{value}")
    db.update_scene_tags(scene.id, ", ".join(tags))


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
            f"border-radius: 4px; padding: 4px 6px; font-size: 11px; }}"
        )
        self._on_commit = on_commit
        self._initial = text

    def focusOutEvent(self, event) -> None:
        super().focusOutEvent(event)
        new_text = self.toPlainText().strip()
        if new_text != self._initial.strip():
            self._initial = new_text
            self._on_commit(new_text)


# ---------------------------------------------------------------------------
# Draggable card widgets (move = drag/drop; the view holds the move logic)
# ---------------------------------------------------------------------------

_DRAG_THRESHOLD = 8
_CHAP_SEP = "\x1f"   # separates act/chapter in a chapter drag payload


class _SceneCard(QFrame):
    """Compact, draggable Scene card. Drag onto a chapter/scene to move it;
    double-click to open the scene in Manuscript. All move logic lives in the
    view, so the menu controls and drag/drop share one (tested) code path."""

    def __init__(self, view: "PlanView", scene) -> None:
        super().__init__()
        self._view = view
        self.scene_id = scene.id
        self._drag_start: QPoint | None = None
        self.setObjectName("planScene")
        self.setProperty("outlineRole", "scene_card")
        self.setAcceptDrops(True)
        self.setCursor(Qt.CursorShape.OpenHandCursor)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_start = event.pos()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        if self._drag_start is None:
            return
        if (event.pos() - self._drag_start).manhattanLength() < _DRAG_THRESHOLD:
            return
        drag = QDrag(self)
        mime = QMimeData()
        mime.setText(f"scene:{self.scene_id}")
        drag.setMimeData(mime)
        drag.setPixmap(self.grab())
        drag.exec(Qt.DropAction.MoveAction)
        self._drag_start = None

    def mouseDoubleClickEvent(self, event) -> None:
        self._view._open_in_manuscript(self.scene_id)

    def dragEnterEvent(self, event) -> None:
        t = event.mimeData().text()
        if t.startswith("scene:") and t != f"scene:{self.scene_id}":
            event.acceptProposedAction()

    def dragMoveEvent(self, event) -> None:
        if event.mimeData().text().startswith("scene:"):
            event.acceptProposedAction()

    def dropEvent(self, event) -> None:
        t = event.mimeData().text()
        if not t.startswith("scene:"):
            return
        try:
            src = int(t.split(":", 1)[1])
        except ValueError:
            return
        if src != self.scene_id:
            self._view._drop_scene_before(src, self.scene_id)
            event.acceptProposedAction()


class _ChapterColumn(QFrame):
    """Compact, draggable Chapter column. Drop a Scene to move it here; drag
    the column onto another column/Act to move/reorder the chapter."""

    def __init__(self, view: "PlanView", act_name: str, chapter_name: str) -> None:
        super().__init__()
        self._view = view
        self._act = act_name
        self._chapter = chapter_name
        self._drag_start: QPoint | None = None
        self.setObjectName("planChapter")
        self.setProperty("outlineRole", "chapter_card")
        self.setAcceptDrops(True)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_start = event.pos()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        if self._drag_start is None:
            return
        if (event.pos() - self._drag_start).manhattanLength() < _DRAG_THRESHOLD:
            return
        drag = QDrag(self)
        mime = QMimeData()
        mime.setText(f"chapter:{self._act}{_CHAP_SEP}{self._chapter}")
        drag.setMimeData(mime)
        drag.setPixmap(self.grab())
        drag.exec(Qt.DropAction.MoveAction)
        self._drag_start = None

    def mouseDoubleClickEvent(self, event) -> None:
        self._view._open_chapter_in_manuscript(self._act, self._chapter)

    def dragEnterEvent(self, event) -> None:
        t = event.mimeData().text()
        if t.startswith("scene:") or t.startswith("chapter:"):
            event.acceptProposedAction()

    def dragMoveEvent(self, event) -> None:
        t = event.mimeData().text()
        if t.startswith("scene:") or t.startswith("chapter:"):
            event.acceptProposedAction()

    def dropEvent(self, event) -> None:
        t = event.mimeData().text()
        if t.startswith("scene:"):
            try:
                src = int(t.split(":", 1)[1])
            except ValueError:
                return
            self._view._drop_scene_on_chapter(src, self._act, self._chapter)
            event.acceptProposedAction()
        elif t.startswith("chapter:"):
            act, _, chap = t.split(":", 1)[1].partition(_CHAP_SEP)
            if (act, chap) != (self._act, self._chapter):
                self._view._drop_chapter_before(
                    act, chap, self._act, self._chapter)
                event.acceptProposedAction()


class _ActSection(QFrame):
    """Act container. Accepts Chapter drops (move chapter into this Act) and,
    for non-Novel modes, Scene drops (scenes live directly under the Act)."""

    def __init__(self, view: "PlanView", act_name: str) -> None:
        super().__init__()
        self._view = view
        self._act = act_name
        self.setObjectName("planAct")
        self.setProperty("outlineRole", "act_container")
        self.setAcceptDrops(True)

    def dragEnterEvent(self, event) -> None:
        t = event.mimeData().text()
        if t.startswith("chapter:") or t.startswith("scene:"):
            event.acceptProposedAction()

    def dragMoveEvent(self, event) -> None:
        t = event.mimeData().text()
        if t.startswith("chapter:") or t.startswith("scene:"):
            event.acceptProposedAction()

    def dropEvent(self, event) -> None:
        t = event.mimeData().text()
        if t.startswith("chapter:"):
            act, _, chap = t.split(":", 1)[1].partition(_CHAP_SEP)
            if act != self._act:
                self._view._drop_chapter_on_act(act, chap, self._act)
                event.acceptProposedAction()
        elif t.startswith("scene:"):
            try:
                src = int(t.split(":", 1)[1])
            except ValueError:
                return
            self._view._drop_scene_on_chapter(src, self._act, _UNTITLED_CHAPTER)
            event.acceptProposedAction()


class PlanView(QWidget):
    """Hierarchical Acts → Chapters → Scenes plan view."""

    def __init__(
        self,
        db: Database,
        project_id: int,
        on_data_changed: Callable[[], None] | None = None,
        on_open_scene: Callable[[int], None] | None = None,
        on_logos_action: Callable[[dict, str], None] | None = None,
        on_open_in_manuscript: Callable[[int], None] | None = None,
    ) -> None:
        super().__init__()
        # Diagnostic marker: confirms the running app uses the block/card
        # Outline planner (Acts/Chapters/Scenes cards with type badges).
        self.setObjectName("outline_target_block_card_planner_view")
        from storyplanner.diagnostics import attach_dev_marker
        attach_dev_marker(self, "NEW OUTLINE VIEW")
        self._db = db
        self._project_id = project_id
        self._on_data_changed = on_data_changed
        self._on_open_scene = on_open_scene
        # Double-click / "Open in Manuscript" → open the unit in the Manuscript
        # writing surface (falls back to on_open_scene if not provided).
        self._on_open_in_manuscript = on_open_in_manuscript
        # Structural numbers, recomputed each refresh (Act 1 · Chapter 1.2 · …).
        self._numbers: dict = {"acts": {}, "chapters": {}, "scenes": {}}
        # Optional inline-Logos hook: (node_descriptor, action_name) -> None.
        self._on_logos_action = on_logos_action
        self._gen_worker: OutlineGenWorker | None = None
        self._pending_gen: tuple[str, str, str] = ("full", "", "")

        # The Outline section must stay usable when the Assistant panel is open
        # — keep a sensible minimum so the act cards never collapse to a sliver.
        self.setMinimumWidth(420)

        # Narrative engine drives the structural vocabulary used for AI prompts.
        try:
            from storyplanner.project_compat import get_project_narrative_engine
            project = self._db.get_project_by_id(self._project_id)
            self._engine = get_project_narrative_engine(project) or "novel"
        except Exception:
            self._engine = "novel"

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 12, 16, 12)
        root.setSpacing(8)

        header_row = QHBoxLayout()
        header_row.setSpacing(6)
        title = QLabel("Outline")
        title.setStyleSheet(
            f"font-size: 18px; font-weight: bold; color: {theme.TEXT_PRIMARY};"
        )
        header_row.addWidget(title)

        self._mode_badge = QLabel("")
        self._mode_badge.setObjectName("planModeBadge")
        header_row.addWidget(self._mode_badge)

        header_row.addStretch()

        # -- Template selector --------------------------------------------------
        self._template_combo = QComboBox()
        self._template_combo.setToolTip(
            "Structural template used when generating the outline",
        )
        self._template_combo.addItem("No template", userData="")
        from storyplanner.outline_templates import list_templates
        for key, name, desc in list_templates():
            self._template_combo.addItem(name, userData=key)
            self._template_combo.setItemData(
                self._template_combo.count() - 1, desc,
                Qt.ItemDataRole.ToolTipRole,
            )
        self._restore_selected_template()
        self._template_combo.currentIndexChanged.connect(self._on_template_changed)
        header_row.addWidget(QLabel("Template:"))
        header_row.addWidget(self._template_combo)

        # -- Generate / AI controls --------------------------------------------
        gen_btn = QPushButton("✨ Generate Outline")
        gen_btn.setToolTip("Generate a full outline using the selected template")
        gen_btn.clicked.connect(lambda: self._run_ai("full"))
        header_row.addWidget(gen_btn)

        ai_btn = QPushButton("✨ AI Generate ▾")
        ai_menu = QMenu(ai_btn)
        ai_menu.addAction("Full Outline", lambda: self._run_ai("full"))
        ai_menu.addAction("Act", lambda: self._run_ai("act"))
        ai_menu.addAction("Chapter", lambda: self._run_ai("chapter"))
        ai_menu.addAction("Scene", lambda: self._run_ai("scene"))
        ai_btn.setMenu(ai_menu)
        header_row.addWidget(ai_btn)

        self._ai_status = QLabel("")
        self._ai_status.setStyleSheet(
            f"color: {theme.TEXT_MUTED}; font-size: 11px;"
        )
        header_row.addWidget(self._ai_status)

        add_act_btn = QPushButton("+ Add Act")
        add_act_btn.clicked.connect(self._add_act)
        header_row.addWidget(add_act_btn)

        clear_btn = QPushButton("Clear Outline")
        clear_btn.setToolTip(
            "Remove the Act/Chapter structure. Written text is preserved.",
        )
        clear_btn.clicked.connect(self._clear_outline_dialog)
        header_row.addWidget(clear_btn)
        root.addLayout(header_row)
        self._refresh_mode_badge()

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
        root.addWidget(self._scroll, stretch=1)

        self.refresh()

    def refresh(self) -> None:
        self._refresh_mode_badge()
        self._refresh_list()

    def _refresh_mode_badge(self) -> None:
        """Show the outline *structure mode* and the selected template.

        "Classical" / "λ Lambda" is the structure mode (stable linear vs
        quantum superposition) from :func:`get_outline_mode`. The template name
        is appended so the badge is never ambiguous — picking "Save the Cat"
        shows "Classical · Save the Cat", not just "Classical".
        """
        mode = get_outline_mode(self._project_id)
        template_name = self._selected_template_name()
        if mode is OutlineMode.LAMBDA:
            label = "λ Lambda"
            tip = "Outline structure mode: Lambda (quantum superposition)."
            self._mode_badge.setStyleSheet(
                f"color: {theme.ACCENT}; font-size: 10px;"
                f" font-weight: bold; background: transparent;"
                f" border: 1px solid {theme.ACCENT}; border-radius: 3px;"
                " padding: 2px 6px; margin-left: 8px;"
            )
        else:
            label = "Classical"
            tip = "Outline structure mode: Classical (stable, linear)."
            self._mode_badge.setStyleSheet(
                f"color: {theme.TEXT_MUTED}; font-size: 10px;"
                f" background: transparent;"
                f" border: 1px solid {theme.BORDER}; border-radius: 3px;"
                " padding: 2px 6px; margin-left: 8px;"
            )
        if template_name:
            label = f"{label} · {template_name}"
            tip += f"  Template: {template_name}."
        else:
            tip += "  No template selected."
        self._mode_badge.setText(label)
        self._mode_badge.setToolTip(tip)

    # -- Template selection ---------------------------------------------------

    def _selected_template_name(self) -> str:
        if not hasattr(self, "_template_combo"):
            return ""
        key = self._template_combo.currentData()
        if not key:
            return ""
        from storyplanner.outline_templates import get_template
        tmpl = get_template(key)
        return tmpl.name if tmpl else ""

    def _restore_selected_template(self) -> None:
        settings = self._db.get_project_settings(self._project_id)
        key = settings.get("outline_template", "")
        if not key:
            return
        idx = self._template_combo.findData(key)
        if idx >= 0:
            self._template_combo.blockSignals(True)
            self._template_combo.setCurrentIndex(idx)
            self._template_combo.blockSignals(False)

    def _on_template_changed(self) -> None:
        key = self._template_combo.currentData() or ""
        settings = self._db.get_project_settings(self._project_id)
        settings["outline_template"] = key
        self._db.save_project_settings(self._project_id, settings)
        self._refresh_mode_badge()

    def _refresh_list(self) -> None:
        while self._content_layout.count():
            item = self._content_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

        tree = build_plan_tree(self._db, self._project_id)
        act_summaries = _act_summaries(self._db, self._project_id)
        chapter_summaries = _chapter_summaries(self._db, self._project_id)
        # Structural numbers (Act 1 · Chapter 1.2 · Scene 1.2.3) are recomputed
        # from the current tree on every refresh, so a move always retracks.
        self._numbers = compute_outline_numbering(tree, self._is_novel())

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

        n_acts = len(tree)
        for idx, (act_name, chapters) in enumerate(tree):
            self._content_layout.addWidget(
                self._build_act_section(
                    act_name,
                    act_summaries.get(_act_key(act_name), ""),
                    chapters,
                    chapter_summaries,
                    act_index=idx,
                    act_count=n_acts,
                )
            )

        self._content_layout.addStretch()

    def outline_numbering(self) -> dict:
        """Public: current {acts, chapters, scenes} structural numbers."""
        return compute_outline_numbering(
            build_plan_tree(self._db, self._project_id), self._is_novel(),
        )

    # -- Block type badges ----------------------------------------------------

    _BADGE_COLORS = {
        "ACT": theme.ACCENT,
        "CHAPTER": theme.TEXT_PRIMARY,
        "SCENE": theme.TEXT_MUTED,
    }

    def _note_indicator(self, count: int) -> QLabel | None:
        """Compact '📝 N' marker shown on a block that has linked notes."""
        if count <= 0:
            return None
        lbl = QLabel(f"📝 {count}")
        lbl.setObjectName("planNoteIndicator")
        lbl.setToolTip(f"{count} linked note(s)")
        lbl.setStyleSheet(
            f"color: {theme.TEXT_MUTED}; font-size: 10px;"
            f" border: 1px solid {theme.BORDER}; border-radius: 3px;"
            f" padding: 0px 4px; background: transparent;"
        )
        return lbl

    def _is_novel(self) -> bool:
        """Novel uses Act → Chapter → Scene; other modes use Act → Scene
        (the empty Chapter layer is flattened so scenes sit directly in the Act)."""
        return (self._engine or "novel") == "novel"

    def _type_badge(self, kind: str) -> QLabel:
        """A small pill badge labelling a block's type: Act / Chapter / Scene."""
        badge = QLabel(kind)
        badge.setObjectName("planTypeBadge")
        color = self._BADGE_COLORS.get(kind, theme.TEXT_MUTED)
        badge.setStyleSheet(
            f"color: {color}; font-size: 9px; font-weight: bold;"
            f" border: 1px solid {theme.BORDER};"
            f" border-radius: 3px; padding: 1px 5px; background: transparent;"
        )
        return badge

    # -- Act section ----------------------------------------------------------

    def _build_act_section(
        self,
        act_name: str,
        act_summary: str,
        chapters: list[tuple[str, list]],
        chapter_summaries: dict[str, str],
        act_index: int = 0,
        act_count: int = 1,
    ) -> QWidget:
        section = _ActSection(self, act_name)
        section.setStyleSheet(
            f"QFrame#planAct {{ background: {theme.BG_PANEL}; "
            f"border: 1px solid {theme.BORDER}; border-radius: 6px; }}"
        )

        layout = QVBoxLayout(section)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(5)

        head_row = QHBoxLayout()
        head_row.setSpacing(6)
        head_row.addWidget(self._type_badge("ACT"))
        num = self._numbers.get("acts", {}).get(act_name, "")
        num_lbl = QLabel(num)
        num_lbl.setObjectName("planNumber")
        num_lbl.setStyleSheet(
            f"color: {theme.ACCENT}; font-size: 12px; font-weight: bold;")
        head_row.addWidget(num_lbl)
        act_label = QLabel(act_name)
        act_label.setStyleSheet(
            f"font-size: 14px; font-weight: bold; color: {theme.TEXT_PRIMARY};"
        )
        head_row.addWidget(act_label)
        act_notes = self._note_indicator(
            self._db.get_structure_note_count(
                self._project_id, "act", _act_key(act_name),
            )
        )
        if act_notes is not None:
            head_row.addWidget(act_notes)
        head_row.addStretch()

        # Mode-aware primary action: Novel adds Chapters, other modes add Scenes
        # directly under the Act.
        if self._is_novel():
            add_chap = QPushButton("+ New Chapter")
            add_chap.setObjectName("planAddChild")
            add_chap.clicked.connect(lambda: self._add_chapter(act_name))
            head_row.addWidget(add_chap)
        else:
            add_scene = QPushButton("+ New Scene")
            add_scene.setObjectName("planAddChild")
            add_scene.clicked.connect(
                lambda: self._add_scene(act_name, _UNTITLED_CHAPTER),
            )
            head_row.addWidget(add_scene)

        more = QPushButton("⋯")
        more.setFixedWidth(26)
        more.setToolTip("Edit / move Act")
        more.clicked.connect(
            lambda: self._show_act_menu(more, act_name, act_index, act_count))
        head_row.addWidget(more)

        layout.addLayout(head_row)

        # Compact one-line summary preview + word/chapter meta on one row.
        meta_row = QHBoxLayout()
        meta_row.setSpacing(8)
        meta_row.setContentsMargins(0, 0, 0, 0)
        if act_summary.strip():
            meta_row.addWidget(self._summary_preview(act_summary), stretch=1)
        else:
            meta_row.addStretch(1)
        n_ch = sum(1 for c, _ in chapters if c != _UNTITLED_CHAPTER)
        n_words = sum(self._word_count(s.content)
                      for _, scs in chapters for s in scs)
        meta = QLabel(f"{n_ch} ch · {n_words:,} w"
                      if self._is_novel() else f"{n_words:,} w")
        meta.setStyleSheet(f"color: {theme.TEXT_MUTED}; font-size: 10px;")
        meta_row.addWidget(meta)
        layout.addLayout(meta_row)

        # Horizontal board: Chapters as columns (Novel) or Scene cards directly
        # inside the Act (non-Novel). Scrolls horizontally when wide.
        board_scroll = QScrollArea()
        board_scroll.setWidgetResizable(False)
        board_scroll.setFixedHeight(360)
        board_scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        board_scroll.setStyleSheet("QScrollArea { border: none; }")
        board = QWidget()
        hbox = QHBoxLayout(board)
        hbox.setContentsMargins(0, 0, 0, 0)
        hbox.setSpacing(8)
        hbox.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        hbox.setSizeConstraint(hbox.SizeConstraint.SetMinAndMaxSize)
        for chapter_name, scenes in chapters:
            if not self._is_novel() and chapter_name == _UNTITLED_CHAPTER:
                for scene in scenes:
                    hbox.addWidget(self._build_scene_card(scene, fixed_width=232))
                continue
            hbox.addWidget(self._build_chapter_column(
                act_name, chapter_name,
                chapter_summaries.get(_chapter_key(chapter_name), ""), scenes,
            ))
        board_scroll.setWidget(board)
        layout.addWidget(board_scroll)
        return section

    # -- Helpers --------------------------------------------------------------

    @staticmethod
    def _word_count(text: str | None) -> int:
        return len((text or "").split())

    @staticmethod
    def _passthrough(widget: QWidget) -> QWidget:
        """Let mouse events fall through to the card (so drag + double-click
        work) while keeping the widget visible."""
        widget.setAttribute(
            Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        return widget

    def _summary_preview(self, text: str, max_chars: int = 120) -> QLabel:
        """Compact, truncated, read-only summary preview (edit via the menu)."""
        clean = " ".join((text or "").split())
        shown = clean if len(clean) <= max_chars else clean[:max_chars - 1] + "…"
        lbl = QLabel(shown)
        lbl.setObjectName("planSummaryPreview")
        lbl.setWordWrap(True)
        lbl.setToolTip(clean)
        lbl.setStyleSheet(
            f"color: {theme.TEXT_MUTED}; font-size: 11px; font-style: italic;")
        return self._passthrough(lbl)

    def _scene_chips(self, scene) -> list[QLabel]:
        """Compact chips: non-status tags + linked character names (Codex).
        The planning status has its own chip, so it is excluded here."""
        chips: list[QLabel] = []
        for tag in _tags_without_status(getattr(scene, "tags", "") or ""):
            chips.append(self._chip(tag))
        try:
            for cid in self._db.get_scene_character_ids(scene.id):
                ch = self._db.get_character_by_id(cid)
                if ch:
                    chips.append(self._chip(ch.name))
        except Exception:
            pass
        return chips

    _STATUS_CHIP_COLORS = {
        "Draft": theme.TEXT_MUTED,
        "Edited": theme.ACCENT,
        "Needs Work": "#d97706",
        "Complete": "#16a34a",
    }

    def _status_chip(self, status: str) -> QLabel:
        chip = QLabel(status)
        chip.setObjectName("planStatusChip")
        col = self._STATUS_CHIP_COLORS.get(status, theme.ACCENT)
        chip.setStyleSheet(
            f"color: {col}; font-size: 9px; font-weight: bold;"
            f" border: 1px solid {col}; border-radius: 8px;"
            f" padding: 0px 6px; background: transparent;"
        )
        return self._passthrough(chip)

    def _chip(self, text: str, accent: bool = False) -> QLabel:
        chip = QLabel(text)
        chip.setObjectName("planChip")
        border = theme.ACCENT if accent else theme.BORDER
        col = theme.ACCENT if accent else theme.TEXT_SECONDARY
        chip.setStyleSheet(
            f"color: {col}; font-size: 10px; border: 1px solid {border};"
            f" border-radius: 8px; padding: 1px 7px; background: transparent;"
        )
        return self._passthrough(chip)

    # -- Chapter column -------------------------------------------------------

    def _build_chapter_column(
        self,
        act_name: str,
        chapter_name: str,
        chapter_summary: str,
        scenes: list,
    ) -> QWidget:
        column = _ChapterColumn(self, act_name, chapter_name)
        column.setFixedWidth(240)
        column.setStyleSheet(
            f"QFrame#planChapter {{ background: {theme.BG_DARK};"
            f" border: 1px solid {theme.BORDER}; border-radius: 6px; }}"
        )
        layout = QVBoxLayout(column)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        head_row = QHBoxLayout()
        head_row.setSpacing(5)
        head_row.addWidget(self._passthrough(self._type_badge("CHAPTER")))
        num = self._numbers.get("chapters", {}).get((act_name, chapter_name), "")
        if num:
            n = QLabel(num)
            n.setObjectName("planNumber")
            n.setStyleSheet(
                f"color: {theme.ACCENT}; font-size: 11px; font-weight: bold;")
            head_row.addWidget(self._passthrough(n))
        ch_label = QLabel(chapter_name)
        ch_label.setStyleSheet(
            f"font-size: 12px; font-weight: bold; color: {theme.TEXT_PRIMARY};")
        head_row.addWidget(self._passthrough(ch_label))
        head_row.addStretch()
        wc = QLabel(f"{sum(self._word_count(s.content) for s in scenes):,} w")
        wc.setStyleSheet(f"color: {theme.TEXT_MUTED}; font-size: 10px;")
        head_row.addWidget(self._passthrough(wc))
        ch_notes = self._note_indicator(self._db.get_structure_note_count(
            self._project_id, "chapter", _chapter_key(chapter_name)))
        if ch_notes is not None:
            head_row.addWidget(self._passthrough(ch_notes))
        more = QPushButton("⋯")
        more.setFixedWidth(20)
        more.setToolTip("Edit / move Chapter")
        more.clicked.connect(
            lambda: self._show_chapter_menu(more, act_name, chapter_name))
        head_row.addWidget(more)
        layout.addLayout(head_row)

        if chapter_summary.strip():
            layout.addWidget(self._summary_preview(chapter_summary, max_chars=90))

        # Scene cards scroll vertically inside the column.
        cards_scroll = QScrollArea()
        cards_scroll.setWidgetResizable(True)
        cards_scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        cards_scroll.setStyleSheet("QScrollArea { border: none; }")
        holder = QWidget()
        vbox = QVBoxLayout(holder)
        vbox.setContentsMargins(0, 0, 0, 0)
        vbox.setSpacing(6)
        for scene in scenes:
            vbox.addWidget(self._build_scene_card(scene))
        vbox.addStretch()
        cards_scroll.setWidget(holder)
        layout.addWidget(cards_scroll, stretch=1)

        add_scene = QPushButton("+ New Scene")
        add_scene.setObjectName("planAddChild")
        add_scene.setFlat(True)
        add_scene.clicked.connect(
            lambda: self._add_scene(act_name, chapter_name))
        layout.addWidget(add_scene)
        return column

    # -- Scene card -----------------------------------------------------------

    def _build_scene_card(self, scene, fixed_width: int | None = None) -> QWidget:
        from storyplanner.ui.color_labels import color_hex
        accent = color_hex(getattr(scene, "color_label", "")) or theme.BORDER
        card = _SceneCard(self, scene)
        if fixed_width:
            card.setFixedWidth(fixed_width)
        card.setStyleSheet(
            f"QFrame#planScene {{ background: {theme.BG_PANEL};"
            f" border: 1px solid {theme.BORDER};"
            f" border-left: 3px solid {accent}; border-radius: 5px; }}"
            f"QFrame#planScene:hover {{ border-color: {theme.ACCENT}; }}"
        )
        card.setToolTip("Double-click to open in Manuscript · drag to move")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(8, 5, 8, 5)
        layout.setSpacing(3)

        head_row = QHBoxLayout()
        head_row.setSpacing(5)
        head_row.addWidget(self._passthrough(self._type_badge("SCENE")))
        num = self._numbers.get("scenes", {}).get(scene.id, "")
        if num:
            n = QLabel(num)
            n.setObjectName("planNumber")
            n.setStyleSheet(
                f"color: {theme.ACCENT}; font-size: 10px; font-weight: bold;")
            head_row.addWidget(self._passthrough(n))
        wcount = self._word_count(scene.content)
        title = QLabel(scene.title or "Untitled Scene")
        title.setStyleSheet(f"font-size: 11px; color: {theme.TEXT_PRIMARY};")
        head_row.addWidget(self._passthrough(title), stretch=1)
        wc = QLabel(f"{wcount:,} w")
        wc.setStyleSheet(f"color: {theme.TEXT_MUTED}; font-size: 9px;")
        head_row.addWidget(self._passthrough(wc))
        sc_notes = self._note_indicator(len(self._db.get_scene_note_links(scene.id)))
        if sc_notes is not None:
            head_row.addWidget(self._passthrough(sc_notes))
        more = QPushButton("⋯")
        more.setFixedWidth(20)
        more.setToolTip("Edit / move Scene")
        more.clicked.connect(lambda: self._show_scene_menu(more, scene.id))
        head_row.addWidget(more)
        layout.addLayout(head_row)

        summary = (scene.summary or "").strip()
        if summary:
            layout.addWidget(self._summary_preview(summary, max_chars=110))

        # Compact chips: status (own colour) + non-status tags + character chips.
        chips: list[QLabel] = []
        status = scene_status(scene)
        if status:
            chips.append(self._status_chip(status))
        chips.extend(self._scene_chips(scene))
        if chips:
            chip_row = QHBoxLayout()
            chip_row.setSpacing(4)
            chip_row.setContentsMargins(0, 0, 0, 0)
            for c in chips[:6]:
                chip_row.addWidget(c)
            chip_row.addStretch()
            wrap = QWidget()
            wrap.setLayout(chip_row)
            layout.addWidget(self._passthrough(wrap))
        return card

    # -- Add operations -------------------------------------------------------

    def _add_act(self) -> None:
        name, ok = QInputDialog.getText(
            self, "Add Act", "Act name:", text="New Act",
        )
        if not ok or not name.strip():
            return
        # An Act always seeds a valid Act → Chapter 1 → Scene chain (the
        # structure service guarantees no orphan Chapter is created).
        from storyplanner import story_structure
        story_structure.create_act(self._db, self._project_id, name.strip())
        self._notify()
        self.refresh()

    def _add_chapter(self, act_name: str) -> None:
        name, ok = QInputDialog.getText(
            self, "Add Chapter", "Chapter name:", text="New Chapter",
        )
        if not ok or not name.strip():
            return
        # A Chapter always lands under a valid Act (auto-created if needed).
        from storyplanner import story_structure
        story_structure.create_chapter(
            self._db, self._project_id, _act_key(act_name), name.strip())
        self._notify()
        self.refresh()

    def _add_scene(self, act_name: str, chapter_name: str) -> None:
        title, ok = QInputDialog.getText(
            self, "Add Scene", "Scene title:", text="Untitled Scene",
        )
        if not ok:
            return
        title = title.strip() or "Untitled Scene"
        # A Scene always lands under a valid Act + Chapter (the service fills a
        # default parent when the act-level "+ New Scene" passes no chapter).
        from storyplanner import story_structure
        story_structure.create_scene(
            self._db, self._project_id,
            act=_act_key(act_name), chapter=_chapter_key(chapter_name),
            title=title,
        )
        self._notify()
        self.refresh()

    # -- Edit menus -----------------------------------------------------------

    def _add_logos_submenu(self, menu: QMenu, descriptor: dict) -> None:
        """Add a compact, non-destructive 'Logos ▸' submenu for an outline node."""
        if self._on_logos_action is None:
            return
        from storyplanner.logos.actions import list_actions_for_section
        actions = list_actions_for_section("Outline")
        if not actions:
            return
        sub = menu.addMenu("Logos")
        for action in actions:
            act = QAction(action.label, sub)
            act.setToolTip(action.description)
            act.triggered.connect(
                lambda _=False, d=descriptor, n=action.name: self._on_logos_action(d, n)
            )
            sub.addAction(act)
        menu.addSeparator()

    def _show_act_menu(
        self, anchor: QWidget, act_name: str,
        act_index: int = 0, act_count: int = 1,
    ) -> None:
        menu = QMenu(anchor)

        self._add_logos_submenu(menu, {"kind": "act", "label": act_name})

        open_ms = QAction("Open in Manuscript", menu)
        open_ms.triggered.connect(lambda: self._open_act_in_manuscript(act_name))
        menu.addAction(open_ms)

        ai_gen = QAction("✨ AI Generate Chapters & Scenes", menu)
        ai_gen.triggered.connect(
            lambda: self._run_ai("chapter", act=_act_key(act_name)),
        )
        menu.addAction(ai_gen)
        menu.addSeparator()

        # -- Move --
        up = QAction("Move Act Up", menu)
        up.setEnabled(act_index > 0)
        up.triggered.connect(lambda: self.move_act(act_name, -1))
        menu.addAction(up)
        down = QAction("Move Act Down", menu)
        down.setEnabled(act_index < act_count - 1)
        down.triggered.connect(lambda: self.move_act(act_name, +1))
        menu.addAction(down)
        menu.addSeparator()

        rename_act = QAction("Rename Act", menu)
        rename_act.triggered.connect(lambda: self._rename_act_dialog(act_name))
        menu.addAction(rename_act)

        edit_sum = QAction("Edit Summary…", menu)
        edit_sum.triggered.connect(lambda: self._edit_act_summary_dialog(act_name))
        menu.addAction(edit_sum)

        if act_name != _UNTITLED_ACT:
            delete_act = QAction("Delete Act (clear label from scenes)", menu)
            delete_act.triggered.connect(
                lambda: self._delete_act_dialog(act_name)
            )
            menu.addAction(delete_act)

        menu.exec(anchor.mapToGlobal(anchor.rect().bottomLeft()))

    def _show_chapter_menu(
        self, anchor: QWidget, act_name: str, chapter_name: str,
    ) -> None:
        menu = QMenu(anchor)

        self._add_logos_submenu(
            menu, {"kind": "chapter", "label": chapter_name, "act": act_name},
        )

        open_ms = QAction("Open in Manuscript", menu)
        open_ms.triggered.connect(
            lambda: self._open_chapter_in_manuscript(act_name, chapter_name))
        menu.addAction(open_ms)

        ai_gen = QAction("✨ AI Generate Scenes", menu)
        ai_gen.triggered.connect(
            lambda: self._run_ai(
                "scene", act=_act_key(act_name),
                chapter=_chapter_key(chapter_name),
            ),
        )
        menu.addAction(ai_gen)
        menu.addSeparator()

        # -- Move --
        up = QAction("Move Chapter Up", menu)
        up.triggered.connect(lambda: self.move_chapter(act_name, chapter_name, -1))
        menu.addAction(up)
        down = QAction("Move Chapter Down", menu)
        down.triggered.connect(lambda: self.move_chapter(act_name, chapter_name, +1))
        menu.addAction(down)
        self._add_move_to_act_submenu(menu, act_name, chapter_name)
        menu.addSeparator()

        rename = QAction("Rename Chapter", menu)
        rename.triggered.connect(
            lambda: self._rename_chapter_dialog(chapter_name)
        )
        menu.addAction(rename)

        edit_sum = QAction("Edit Summary…", menu)
        edit_sum.triggered.connect(
            lambda: self._edit_chapter_summary_dialog(chapter_name))
        menu.addAction(edit_sum)

        if chapter_name != _UNTITLED_CHAPTER:
            delete = QAction("Delete Chapter (clear label from scenes)", menu)
            delete.triggered.connect(
                lambda: self._delete_chapter_dialog(chapter_name)
            )
            menu.addAction(delete)

        menu.exec(anchor.mapToGlobal(anchor.rect().bottomLeft()))

    def _show_scene_menu(self, anchor: QWidget, scene_id: int) -> None:
        menu = QMenu(anchor)

        scene = self._db.get_scene_by_id(scene_id)
        self._add_logos_submenu(menu, {
            "kind": "scene", "scene_id": scene_id,
            "label": scene.title if scene else "",
            "act": scene.act if scene else "",
            "chapter": scene.chapter if scene else "",
        })

        open_act = QAction("Open in Manuscript", menu)
        open_act.triggered.connect(lambda: self._open_in_manuscript(scene_id))
        menu.addAction(open_act)

        ai_expand = QAction("✨ AI Expand (add beats/scenes)", menu)
        ai_expand.triggered.connect(lambda: self._ai_expand_scene(scene_id))
        menu.addAction(ai_expand)
        menu.addSeparator()

        # -- Move --
        up = QAction("Move Scene Up", menu)
        up.triggered.connect(lambda: self.move_scene(scene_id, -1))
        menu.addAction(up)
        down = QAction("Move Scene Down", menu)
        down.triggered.connect(lambda: self.move_scene(scene_id, +1))
        menu.addAction(down)
        self._add_move_scene_submenu(menu, scene_id)
        menu.addSeparator()

        # -- Status --
        self._add_status_submenu(menu, scene_id, scene_status(scene) if scene else "")

        rename = QAction("Rename Scene", menu)
        rename.triggered.connect(lambda: self._rename_scene_dialog(scene_id))
        menu.addAction(rename)

        edit_sum = QAction("Edit Summary…", menu)
        edit_sum.triggered.connect(lambda: self._edit_scene_summary_dialog(scene_id))
        menu.addAction(edit_sum)

        delete = QAction("Delete Scene", menu)
        delete.triggered.connect(lambda: self._delete_scene_dialog(scene_id))
        menu.addAction(delete)

        menu.exec(anchor.mapToGlobal(anchor.rect().bottomLeft()))

    # -- Move / status submenu builders --------------------------------------

    def _add_move_to_act_submenu(
        self, menu: QMenu, act_name: str, chapter_name: str,
    ) -> None:
        acts = [a for a, _ in self._current_tree() if a != act_name]
        sub = menu.addMenu("Move Chapter to Act")
        sub.setEnabled(bool(acts))
        for a in acts:
            sub.addAction(
                a, lambda _a=a: self.move_chapter_to_act(act_name, chapter_name, _a))

    def _add_move_scene_submenu(self, menu: QMenu, scene_id: int) -> None:
        sub = menu.addMenu("Move Scene to…")
        any_target = False
        for act_name, chapters in self._current_tree():
            for chapter_name, _scenes in chapters:
                label = (f"{act_name} / {chapter_name}"
                         if chapter_name != _UNTITLED_CHAPTER else act_name)
                sub.addAction(
                    label,
                    lambda a=act_name, c=chapter_name:
                        self.move_scene_to_chapter(scene_id, a, c))
                any_target = True
        sub.setEnabled(any_target)

    def _add_status_submenu(
        self, menu: QMenu, scene_id: int, current: str,
    ) -> None:
        sub = menu.addMenu("Set Status")
        for value in STATUS_VALUES:
            act = QAction((f"● {value}" if value == current else value), sub)
            act.triggered.connect(
                lambda _=False, v=value: self._set_scene_status(scene_id, v))
            sub.addAction(act)
        sub.addSeparator()
        clear = QAction("Clear status", sub)
        clear.triggered.connect(lambda: self._set_scene_status(scene_id, ""))
        sub.addAction(clear)

    def _ai_expand_scene(self, scene_id: int) -> None:
        scene = self._db.get_scene_by_id(scene_id)
        if scene is None:
            return
        self._run_ai("scene", act=scene.act or "", chapter=scene.chapter or "")

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
            f"Remove the act '{act_name}'?\n\n"
            "Its child Chapters and Scenes are NOT deleted — they are detached "
            "(the act label is cleared) and their written text is preserved.",
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
            f"Remove the chapter '{chapter_name}'?\n\n"
            "Its child Scenes are NOT deleted — they are detached (the chapter "
            "label is cleared) and their written text is preserved.",
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return
        _delete_chapter(self._db, self._project_id, _chapter_key(chapter_name))
        self._notify()
        self.refresh()

    def _clear_outline_dialog(self) -> None:
        if not build_plan_tree(self._db, self._project_id):
            QMessageBox.information(
                self, "Clear Outline", "The Outline is already empty.",
            )
            return
        confirm = QMessageBox.warning(
            self,
            "Clear Outline",
            "Clear the entire Outline structure?\n\n"
            "• Acts and Chapters are removed.\n"
            "• Empty placeholder scenes are deleted.\n"
            "• Scenes with written text or a summary are kept (moved to "
            "Unsorted) — Manuscript text is never deleted.\n\n"
            "This cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return
        clear_outline_structure(self._db, self._project_id)
        from storyplanner.project_events import get_event_bus
        bus = get_event_bus()
        bus.scenes_changed.emit()
        bus.outline_changed.emit()
        bus.project_data_changed.emit()
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
        self._notify()

    def _save_chapter_summary(self, chapter_name: str, summary: str) -> None:
        _save_chapter_summary(
            self._db, self._project_id, _chapter_key(chapter_name), summary,
        )
        self._notify()

    def _save_scene_summary(self, scene_id: int, summary: str) -> None:
        self._db.update_scene_summary(scene_id, summary)
        self._notify()

    def _notify(self) -> None:
        if self._on_data_changed is not None:
            self._on_data_changed()

    # -- Move / reorder (single source of truth for menu + drag/drop) ---------

    def _current_tree(self):
        return build_plan_tree(self._db, self._project_id)

    def _apply_tree_order(self, tree) -> None:
        """Persist a (re)ordered tree: relabel any moved scene's Act/Chapter,
        then rewrite the global sort order from the tree. Only order/label
        fields change — never manuscript body, summaries, tags, or links."""
        order, structure = _flatten_tree_to_order(tree)
        for sid, (act, chapter) in structure.items():
            scene = self._db.get_scene_by_id(sid)
            if scene is None:
                continue
            if (scene.act or "") != act or (scene.chapter or "") != chapter:
                self._db.set_scene_structure(sid, act, chapter)
        self._db.reorder_scenes(self._project_id, order)
        self._after_structural_change()

    def _after_structural_change(self) -> None:
        """Persisted a move: mark dirty, fan out so Manuscript/Timeline stay in
        sync, and rebuild the board (which retracks numbering)."""
        from storyplanner.project_events import get_event_bus
        bus = get_event_bus()
        bus.scenes_changed.emit()
        bus.outline_changed.emit()
        bus.plot_changed.emit()
        bus.project_data_changed.emit()
        self._notify()
        self.refresh()

    def move_act(self, act_name: str, delta: int) -> None:
        tree = self._current_tree()
        names = [a for a, _ in tree]
        if act_name not in names:
            return
        i = names.index(act_name)
        j = i + delta
        if not (0 <= j < len(tree)):
            return
        tree[i], tree[j] = tree[j], tree[i]
        self._apply_tree_order(tree)

    def move_chapter(self, act_name: str, chapter_name: str, delta: int) -> None:
        tree = self._current_tree()
        for a, chs in tree:
            if a != act_name:
                continue
            names = [c for c, _ in chs]
            if chapter_name not in names:
                return
            i = names.index(chapter_name)
            j = i + delta
            if not (0 <= j < len(chs)):
                return
            chs[i], chs[j] = chs[j], chs[i]
            self._apply_tree_order(tree)
            return

    def move_chapter_to_act(
        self, act_name: str, chapter_name: str, target_act: str,
        index: int | None = None,
    ) -> None:
        tree = self._current_tree()
        moved = None
        for a, chs in tree:
            if a == act_name:
                for k, (c, _scs) in enumerate(chs):
                    if c == chapter_name:
                        moved = chs.pop(k)
                        break
                break
        if moved is None:
            return
        for a, chs in tree:
            if a == target_act:
                if index is None or index >= len(chs):
                    chs.append(moved)
                else:
                    chs.insert(max(0, index), moved)
                self._apply_tree_order(tree)
                return
        # Target act not currently in the tree: append it as a new act group.
        tree.append((target_act, [moved]))
        self._apply_tree_order(tree)

    def move_scene(self, scene_id: int, delta: int) -> None:
        tree = self._current_tree()
        for a, chs in tree:
            for c, scs in chs:
                ids = [s.id for s in scs]
                if scene_id in ids:
                    i = ids.index(scene_id)
                    j = i + delta
                    if not (0 <= j < len(scs)):
                        return
                    scs[i], scs[j] = scs[j], scs[i]
                    self._apply_tree_order(tree)
                    return

    def move_scene_to_chapter(
        self, scene_id: int, target_act: str, target_chapter: str,
        index: int | None = None,
    ) -> None:
        tree = self._current_tree()
        moved = None
        for a, chs in tree:
            for c, scs in chs:
                for k, s in enumerate(scs):
                    if s.id == scene_id:
                        moved = scs.pop(k)
                        break
                if moved is not None:
                    break
            if moved is not None:
                break
        if moved is None:
            return
        for a, chs in tree:
            if a != target_act:
                continue
            for c, scs in chs:
                if c == target_chapter:
                    if index is None or index >= len(scs):
                        scs.append(moved)
                    else:
                        scs.insert(max(0, index), moved)
                    self._apply_tree_order(tree)
                    return
            chs.append((target_chapter, [moved]))
            self._apply_tree_order(tree)
            return
        tree.append((target_act, [(target_chapter, [moved])]))
        self._apply_tree_order(tree)

    # -- Drop handlers (drag/drop calls into the move methods above) ----------

    def _drop_scene_before(self, src_id: int, target_id: int) -> None:
        for a, chs in self._current_tree():
            for c, scs in chs:
                ids = [s.id for s in scs]
                if target_id in ids:
                    self.move_scene_to_chapter(
                        src_id, a, c, index=ids.index(target_id))
                    return

    def _drop_scene_on_chapter(
        self, src_id: int, act_name: str, chapter_name: str,
    ) -> None:
        self.move_scene_to_chapter(src_id, act_name, chapter_name, index=None)

    def _drop_chapter_before(
        self, src_act: str, src_chapter: str, tgt_act: str, tgt_chapter: str,
    ) -> None:
        for a, chs in self._current_tree():
            if a == tgt_act:
                names = [c for c, _ in chs]
                if tgt_chapter in names:
                    self.move_chapter_to_act(
                        src_act, src_chapter, tgt_act,
                        index=names.index(tgt_chapter))
                return

    def _drop_chapter_on_act(
        self, src_act: str, src_chapter: str, tgt_act: str,
    ) -> None:
        self.move_chapter_to_act(src_act, src_chapter, tgt_act, index=None)

    # -- Open in Manuscript ---------------------------------------------------

    def _open_in_manuscript(self, scene_id: int) -> None:
        cb = self._on_open_in_manuscript or self._on_open_scene
        if cb is not None:
            cb(scene_id)

    def _first_scene_id(self, act_name: str, chapter_name: str | None) -> int | None:
        for a, chs in self._current_tree():
            if a != act_name:
                continue
            for c, scs in chs:
                if chapter_name is None or c == chapter_name:
                    if scs:
                        return scs[0].id
        return None

    def _open_chapter_in_manuscript(self, act_name: str, chapter_name: str) -> None:
        sid = self._first_scene_id(act_name, chapter_name)
        if sid is not None:
            self._open_in_manuscript(sid)

    def _open_act_in_manuscript(self, act_name: str) -> None:
        sid = self._first_scene_id(act_name, None)
        if sid is not None:
            self._open_in_manuscript(sid)

    # -- Status (stored as a status: tag) -------------------------------------

    def _set_scene_status(self, scene_id: int, value: str) -> None:
        scene = self._db.get_scene_by_id(scene_id)
        if scene is None:
            return
        set_scene_status(self._db, scene, value)
        self._notify()
        self.refresh()

    # -- Edit summaries via the compact menu (preview is read-only) -----------

    def _edit_act_summary_dialog(self, act_name: str) -> None:
        cur = _act_summaries(self._db, self._project_id).get(_act_key(act_name), "")
        text, ok = QInputDialog.getMultiLineText(
            self, "Edit Act Summary", "Summary:", cur)
        if ok:
            self._save_act_summary(act_name, text.strip())
            self.refresh()

    def _edit_chapter_summary_dialog(self, chapter_name: str) -> None:
        cur = _chapter_summaries(self._db, self._project_id).get(
            _chapter_key(chapter_name), "")
        text, ok = QInputDialog.getMultiLineText(
            self, "Edit Chapter Summary", "Summary:", cur)
        if ok:
            self._save_chapter_summary(chapter_name, text.strip())
            self.refresh()

    def _edit_scene_summary_dialog(self, scene_id: int) -> None:
        scene = self._db.get_scene_by_id(scene_id)
        if scene is None:
            return
        text, ok = QInputDialog.getMultiLineText(
            self, "Edit Scene Summary", "Summary:", scene.summary or "")
        if ok:
            self._save_scene_summary(scene_id, text.strip())
            self.refresh()

    # -- AI outline generation ------------------------------------------------

    def _set_ai_busy(self, busy: bool) -> None:
        self._ai_status.setText("Generating…" if busy else "")

    def _build_outline_prompt(self, scope: str, act: str, chapter: str) -> str:
        from storyplanner.outline_actions import build_outline_generation_prompt
        from storyplanner.outline_templates import get_template

        key = self._template_combo.currentData() if hasattr(self, "_template_combo") else ""
        tmpl = get_template(key) if key else None
        template_name = tmpl.name if tmpl else ""
        beats = [b.title for b in tmpl.beats] if tmpl else []
        try:
            from storyplanner.context_builder import gather_psyke_context
            psyke = gather_psyke_context(self._db, self._project_id)
        except Exception:
            psyke = ""
        target_title = chapter or act or ""
        return build_outline_generation_prompt(
            scope, engine=self._engine, template_name=template_name,
            template_beats=beats, psyke_context=psyke,
            target_title=target_title,
        )

    def _run_ai(self, scope: str = "full", act: str = "", chapter: str = "") -> bool:
        """Start an AI outline generation for *scope* (optionally scoped under
        an existing act/chapter). Returns False if busy or no provider."""
        if self._gen_worker is not None:
            return False
        provider = build_provider()
        if provider is None:
            QMessageBox.information(
                self, "AI Generate Outline",
                "No AI provider is configured. Set one in Settings first.",
            )
            return False
        self._pending_gen = (scope, act, chapter)
        prompt = self._build_outline_prompt(scope, act, chapter)
        self._set_ai_busy(True)
        self._gen_worker = OutlineGenWorker(outline_messages(prompt), provider)
        self._gen_worker.completed.connect(self._on_ai_done)
        self._gen_worker.failed.connect(self._on_ai_failed)
        self._gen_worker.start()
        return True

    def _on_ai_failed(self, error: str) -> None:
        self._gen_worker = None
        self._set_ai_busy(False)
        QMessageBox.warning(
            self, "AI Generate Outline", f"Generation failed:\n\n{error}",
        )

    def _on_ai_done(self, text: str) -> None:
        self._gen_worker = None
        self._set_ai_busy(False)
        scope, act, chapter = self._pending_gen
        self._apply_ai_outline(text, scope, act, chapter)

    def _apply_ai_outline(
        self, text: str, scope: str = "full", act: str = "", chapter: str = "",
        *, confirm: bool = True,
    ) -> list[int]:
        """Parse generated outline text, confirm, then apply it as Scenes.

        For act/chapter/scene scope the new scenes are nested under the given
        *act*/*chapter* so contextual generation lands in the right place.
        """
        from storyplanner.outline_actions import (
            apply_outline_as_scenes,
            count_ops,
            format_outline_preview,
            parse_outline_response,
            repair_outline_ops,
            validate_outline_ops,
        )
        ops = parse_outline_response(text or "")
        if not ops:
            QMessageBox.information(
                self, "AI Generate Outline",
                "The AI response did not contain a usable outline structure.",
            )
            return []
        # Fill empty descriptions / trim prose, then reject unusable output.
        ops, gen_warnings = repair_outline_ops(ops)
        ok, errors = validate_outline_ops(ops)
        if not ok:
            QMessageBox.warning(
                self, "AI Generate Outline",
                "The generated outline can't be applied safely:\n\n• "
                + "\n• ".join(errors),
            )
            return []
        if confirm:
            from storyplanner.ui.outline_confirm_dialog import OutlineConfirmDialog
            if not OutlineConfirmDialog.confirm(
                format_outline_preview(ops), count_ops(ops),
                title="Apply generated outline", warnings=gen_warnings,
                parent=self,
            ):
                return []
        base_act = act if scope in ("chapter", "scene") else ""
        base_chapter = chapter if scope == "scene" else ""
        created = apply_outline_as_scenes(
            self._db, self._project_id, ops,
            base_act=base_act, base_chapter=base_chapter,
        )
        if created:
            from storyplanner.project_events import get_event_bus
            bus = get_event_bus()
            bus.scenes_changed.emit()
            bus.outline_changed.emit()
            bus.plot_changed.emit()
            bus.project_data_changed.emit()
            self._notify()
            self.refresh()
        return created
