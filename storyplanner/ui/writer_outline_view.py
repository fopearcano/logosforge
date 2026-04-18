"""Writer Outline view — clean narrative outline for writing purposes."""

from PySide6.QtWidgets import (
    QFileDialog,
    QLabel,
    QMessageBox,
    QPushButton,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from storyplanner.db import Database
from storyplanner.ui import theme


class WriterOutlineView(QWidget):
    def __init__(self, db: Database, project_id: int) -> None:
        super().__init__()
        self._db = db
        self._project_id = project_id

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Writer Outline"))

        self._browser = QTextBrowser()
        self._browser.setOpenLinks(False)
        layout.addWidget(self._browser)

        self._export_btn = QPushButton("Export Writer Outline")
        self._export_btn.clicked.connect(self._on_export)
        layout.addWidget(self._export_btn)

        self._render()

    def _on_export(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, "Export Writer Outline", "", "Text (*.txt)",
        )
        if not path:
            return
        if not path.endswith(".txt"):
            path += ".txt"

        text = self._build_plain_text()
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)

        QMessageBox.information(self, "Export", f"Writer outline exported to {path}")

    def _render(self) -> None:
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
                parts.append(self._render_scene(scene, scene_index))

        self._browser.setHtml("".join(parts))

    def _render_scene(self, scene, index: int) -> str:
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

    def _build_plain_text(self) -> str:
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
