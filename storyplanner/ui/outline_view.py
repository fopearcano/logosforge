"""Outline view — read-only outline with Structure and Prose modes."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from storyplanner.db import Database
from storyplanner.export import export_outline_markdown
from storyplanner.ui import theme


class OutlineView(QWidget):
    def __init__(self, db: Database, project_id: int) -> None:
        super().__init__()
        self._db = db
        self._project_id = project_id
        self._mode = "structure"

        layout = QVBoxLayout(self)

        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)

        self._structure_btn = QPushButton("Structure")
        self._structure_btn.setCheckable(True)
        self._structure_btn.setChecked(True)
        self._structure_btn.clicked.connect(lambda: self._set_mode("structure"))
        toolbar.addWidget(self._structure_btn)

        self._prose_btn = QPushButton("Prose")
        self._prose_btn.setCheckable(True)
        self._prose_btn.clicked.connect(lambda: self._set_mode("prose"))
        toolbar.addWidget(self._prose_btn)

        toolbar.addStretch()

        self._export_btn = QPushButton("Export")
        self._export_btn.clicked.connect(self._on_export)
        toolbar.addWidget(self._export_btn)

        layout.addLayout(toolbar)

        self._browser = QTextBrowser()
        self._browser.setOpenLinks(False)
        layout.addWidget(self._browser)

        self._render()

    def _set_mode(self, mode: str) -> None:
        self._mode = mode
        self._structure_btn.setChecked(mode == "structure")
        self._prose_btn.setChecked(mode == "prose")
        self._render()

    def _on_export(self) -> None:
        if self._mode == "structure":
            self._export_structure()
        else:
            self._export_prose()

    def _export_structure(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, "Export Outline", "", "Markdown (*.md)",
        )
        if not path:
            return
        if not path.endswith(".md"):
            path += ".md"
        content = export_outline_markdown(self._db, self._project_id)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        QMessageBox.information(self, "Export", f"Outline exported to {path}")

    def _export_prose(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, "Export Prose Outline", "", "Text (*.txt)",
        )
        if not path:
            return
        if not path.endswith(".txt"):
            path += ".txt"
        text = self._build_prose_text()
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
        QMessageBox.information(self, "Export", f"Outline exported to {path}")

    # -- Rendering ---------------------------------------------------------------

    def _render(self) -> None:
        if self._mode == "structure":
            self._render_structure()
        else:
            self._render_prose()

    def _render_structure(self) -> None:
        project = self._db.get_project_by_id(self._project_id)
        characters = self._db.get_all_characters(self._project_id)
        places = self._db.get_all_places(self._project_id)
        scenes = self._db.get_all_scenes(self._project_id)

        char_name_by_id = {c.id: c.name for c in characters}
        place_name_by_id = {p.id: p.name for p in places}

        html_parts: list[str] = []
        title = project.title if project else "Untitled"
        html_parts.append(f"<h1>{_esc(title)}</h1>")

        if not scenes:
            html_parts.append("<p>No scenes to display.</p>")
            self._browser.setHtml("".join(html_parts))
            return

        chapter_groups = _group_by_chapter(scenes)

        scene_index = 0
        for chapter_name, group_scenes in chapter_groups:
            if chapter_name:
                html_parts.append(f"<h2>{_esc(chapter_name)}</h2>")
            else:
                html_parts.append("<h2>Uncategorized</h2>")

            for scene in group_scenes:
                scene_index += 1
                html_parts.append(
                    self._render_structure_scene(
                        scene, scene_index, char_name_by_id, place_name_by_id,
                    )
                )

        self._browser.setHtml("".join(html_parts))

    def _render_structure_scene(
        self,
        scene,
        index: int,
        char_name_by_id: dict[int, str],
        place_name_by_id: dict[int, str],
    ) -> str:
        parts: list[str] = []
        parts.append(f"<h3>{index}. {_esc(scene.title)}</h3>")

        meta_lines: list[str] = []
        if scene.act:
            meta_lines.append(f"<b>Act:</b> {_esc(scene.act)}")
        if scene.plotline:
            meta_lines.append(f"<b>Plotline:</b> {_esc(scene.plotline)}")
        if scene.beat:
            meta_lines.append(f"<b>Beat:</b> {_esc(scene.beat)}")
        if scene.tags:
            meta_lines.append(f"<b>Tags:</b> {_esc(scene.tags)}")

        char_ids = self._db.get_scene_character_ids(scene.id)
        char_names = [
            char_name_by_id[cid] for cid in char_ids if cid in char_name_by_id
        ]
        if char_names:
            meta_lines.append(
                f"<b>Characters:</b> {_esc(', '.join(char_names))}"
            )

        place_ids = self._db.get_scene_place_ids(scene.id)
        place_names = [
            place_name_by_id[pid] for pid in place_ids if pid in place_name_by_id
        ]
        if place_names:
            meta_lines.append(
                f"<b>Places:</b> {_esc(', '.join(place_names))}"
            )

        if meta_lines:
            parts.append("<p>" + "<br>".join(meta_lines) + "</p>")

        if scene.summary:
            parts.append(f"<p>{_esc(scene.summary)}</p>")

        if scene.synopsis:
            parts.append(f"<p><b>Synopsis:</b> {_esc(scene.synopsis)}</p>")

        gco: list[str] = []
        if scene.goal:
            gco.append(f"<b>Goal:</b> {_esc(scene.goal)}")
        if scene.conflict:
            gco.append(f"<b>Conflict:</b> {_esc(scene.conflict)}")
        if scene.outcome:
            gco.append(f"<b>Outcome:</b> {_esc(scene.outcome)}")
        if gco:
            parts.append("<p>" + "<br>".join(gco) + "</p>")

        char_states = self._db.get_scene_character_states(scene.id)
        if char_states:
            state_lines = []
            for cid, state in char_states:
                cname = char_name_by_id.get(cid, "Unknown")
                state_lines.append(f"{_esc(cname)}: {_esc(state)}")
            parts.append(
                "<p><b>Character States:</b><br>"
                + "<br>".join(state_lines)
                + "</p>"
            )

        return "".join(parts)

    def _render_prose(self) -> None:
        project = self._db.get_project_by_id(self._project_id)
        scenes = self._db.get_all_scenes(self._project_id)

        parts: list[str] = []
        title = project.title if project else "Untitled"
        parts.append(f"<h1>{_esc(title)}</h1>")

        if not scenes:
            parts.append("<p>No scenes yet.</p>")
            self._browser.setHtml("".join(parts))
            return

        chapter_groups = _group_by_chapter(scenes)

        scene_index = 0
        for chapter_name, group_scenes in chapter_groups:
            if chapter_name:
                parts.append(f"<h2>{_esc(chapter_name)}</h2>")

            for scene in group_scenes:
                scene_index += 1
                parts.append(self._render_prose_scene(scene, scene_index))

        self._browser.setHtml("".join(parts))

    def _render_prose_scene(self, scene, index: int) -> str:
        parts: list[str] = []
        parts.append(f"<h3>{index}. {_esc(scene.title)}</h3>")

        if scene.synopsis:
            parts.append(
                f"<p style='color: {theme.TEXT_SECONDARY}; font-style: italic;'>"
                f"{_esc(scene.synopsis)}</p>"
            )

        if scene.content:
            content_html = _esc(scene.content).replace("\n\n", "</p><p>")
            content_html = content_html.replace("\n", "<br>")
            parts.append(f"<p>{content_html}</p>")
        elif scene.summary:
            parts.append(f"<p>{_esc(scene.summary)}</p>")

        return "".join(parts)

    def _build_prose_text(self) -> str:
        project = self._db.get_project_by_id(self._project_id)
        scenes = self._db.get_all_scenes(self._project_id)

        lines: list[str] = []
        title = project.title if project else "Untitled"
        lines.append(title.upper())
        lines.append("=" * len(title))
        lines.append("")

        if not scenes:
            lines.append("No scenes yet.")
            return "\n".join(lines)

        chapter_groups = _group_by_chapter(scenes)

        scene_index = 0
        for chapter_name, group_scenes in chapter_groups:
            if chapter_name:
                lines.append("")
                lines.append(chapter_name.upper())
                lines.append("-" * len(chapter_name))
                lines.append("")

            for scene in group_scenes:
                scene_index += 1
                lines.append(f"{scene_index}. {scene.title}")
                lines.append("")
                if scene.synopsis:
                    lines.append(scene.synopsis)
                    lines.append("")
                if scene.content:
                    lines.append(scene.content)
                elif scene.summary:
                    lines.append(scene.summary)
                lines.append("")
                lines.append("")

        return "\n".join(lines)


def _group_by_chapter(scenes: list) -> list[tuple[str, list]]:
    groups: list[tuple[str, list]] = []
    current_chapter: str | None = None
    current_group: list = []

    for scene in scenes:
        chapter = scene.chapter if scene.chapter else ""
        if chapter != current_chapter:
            if current_group:
                groups.append((current_chapter or "", current_group))
            current_chapter = chapter
            current_group = [scene]
        else:
            current_group.append(scene)
    if current_group:
        groups.append((current_chapter or "", current_group))

    return groups


def _esc(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )
