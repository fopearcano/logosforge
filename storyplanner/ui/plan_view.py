"""Plan view — hierarchical Acts → Chapters → Scenes outline.

Acts and Chapters are derived from Scene.act and Scene.chapter string fields.
Renaming an act/chapter updates all scenes that share that label.
Summaries for acts and chapters live in the project's settings_json under
`act_summaries` and `chapter_summaries` keyed by the act/chapter name.
Scene summaries live on Scene.summary.
"""

from collections.abc import Callable

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QComboBox,
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
from storyplanner.ui import theme
from storyplanner.ui.outline_ai import OutlineGenWorker, build_provider, outline_messages


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


class PlanView(QWidget):
    """Hierarchical Acts → Chapters → Scenes plan view."""

    def __init__(
        self,
        db: Database,
        project_id: int,
        on_data_changed: Callable[[], None] | None = None,
        on_open_scene: Callable[[int], None] | None = None,
        on_logos_action: Callable[[dict, str], None] | None = None,
    ) -> None:
        super().__init__()
        self._db = db
        self._project_id = project_id
        self._on_data_changed = on_data_changed
        self._on_open_scene = on_open_scene
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
            lambda: self._show_chapter_menu(more, act_name, chapter_name)
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

    def _show_act_menu(self, anchor: QWidget, act_name: str) -> None:
        menu = QMenu(anchor)

        self._add_logos_submenu(menu, {"kind": "act", "label": act_name})

        ai_gen = QAction("✨ AI Generate Chapters & Scenes", menu)
        ai_gen.triggered.connect(
            lambda: self._run_ai("chapter", act=_act_key(act_name)),
        )
        menu.addAction(ai_gen)
        menu.addSeparator()

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

    def _show_chapter_menu(
        self, anchor: QWidget, act_name: str, chapter_name: str,
    ) -> None:
        menu = QMenu(anchor)

        self._add_logos_submenu(
            menu, {"kind": "chapter", "label": chapter_name, "act": act_name},
        )

        ai_gen = QAction("✨ AI Generate Scenes", menu)
        ai_gen.triggered.connect(
            lambda: self._run_ai(
                "scene", act=_act_key(act_name),
                chapter=_chapter_key(chapter_name),
            ),
        )
        menu.addAction(ai_gen)
        menu.addSeparator()

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

        scene = self._db.get_scene_by_id(scene_id)
        self._add_logos_submenu(menu, {
            "kind": "scene", "scene_id": scene_id,
            "label": scene.title if scene else "",
            "act": scene.act if scene else "",
            "chapter": scene.chapter if scene else "",
        })

        ai_expand = QAction("✨ AI Expand (add beats/scenes)", menu)
        ai_expand.triggered.connect(lambda: self._ai_expand_scene(scene_id))
        menu.addAction(ai_expand)
        menu.addSeparator()

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
        )
        ops = parse_outline_response(text or "")
        if not ops:
            QMessageBox.information(
                self, "AI Generate Outline",
                "The AI response did not contain a usable outline structure.",
            )
            return []
        if confirm:
            from storyplanner.ui.outline_confirm_dialog import OutlineConfirmDialog
            if not OutlineConfirmDialog.confirm(
                format_outline_preview(ops), count_ops(ops),
                title="Apply generated outline", parent=self,
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
