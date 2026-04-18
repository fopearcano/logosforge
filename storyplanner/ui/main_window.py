"""Main window with a sidebar and content area."""

import os
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from storyplanner.ui import theme

from storyplanner import preferences, recent_projects
from storyplanner.db import Database
from storyplanner.export import (
    export_csv_scenes,
    export_docx_manuscript,
    export_json,
    export_manuscript,
    export_markdown,
    export_screenplay,
)
from storyplanner.import_data import import_json, validate_import_data
from storyplanner.ui.assistant_view import AssistantPanel
from storyplanner.ui.act_analysis_view import ActAnalysisView
from storyplanner.ui.beat_analysis_view import BeatAnalysisView
from storyplanner.ui.character_arc_view import CharacterArcView
from storyplanner.ui.characters_view import CharactersView
from storyplanner.ui.dashboard_view import DashboardView
from storyplanner.ui.graph_view import GraphView
from storyplanner.ui.notes_view import NotesView
from storyplanner.ui.outline_view import OutlineView
from storyplanner.ui.places_view import PlacesView
from storyplanner.ui.projects_view import ProjectsView
from storyplanner.ui.scenes_view import ScenesView
from storyplanner.ui.search_view import SearchView
from storyplanner.ui.structure_view import StructureView
from storyplanner.ui.tag_analysis_view import TagAnalysisView
from storyplanner.ui.timeline_view import TimelineView
from storyplanner.ui.welcome_view import WelcomeView
from storyplanner.ui.writer_outline_view import WriterOutlineView


class MainWindow(QMainWindow):
    def __init__(self, db: Database, project_id: int) -> None:
        super().__init__()
        self._db = db
        self._project_id = project_id
        self._current_file: str | None = None
        self._dirty = False
        self._cached_scenes_view: ScenesView | None = None
        self._update_title()
        self.resize(900, 600)
        self.setMinimumSize(640, 400)

        icon_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            "assets", "icon.svg",
        )
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        # -- Menu bar --------------------------------------------------------
        self._build_menu_bar()

        central = QWidget()
        root_layout = QHBoxLayout(central)

        # -- Left sidebar ----------------------------------------------------
        sidebar = QWidget()
        sidebar.setObjectName("sidebar")
        sidebar.setMinimumWidth(140)
        sidebar.setMaximumWidth(200)
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(0, 8, 0, 8)
        sidebar_layout.setSpacing(0)

        _ICONS = {
            "Projects": "\U0001F4C1",
            "Dashboard": "\U0001F3E0",
            "Characters": "\U0001F464",
            "Places": "\U0001F4CD",
            "Notes": "\U0001F4DD",
            "Scenes": "\U0001F3AC",
            "Timeline": "\U0001F552",
            "Outline": "\U0001F4D1",
            "Writer": "\u270D",
            "Structure": "\U0001F3D7",
            "Acts": "\U0001F3AD",
            "Beats": "\U0001F4CC",
            "Tags": "\U0001F3F7",
            "Graph": "\U0001F578",
            "Arcs": "\U0001F4C8",
            "Search": "\U0001F50D",
            "Assistant": "\U0001F916",
        }

        self.sidebar_buttons: dict[str, QPushButton] = {}
        for label in ("Projects", "Dashboard", "Characters", "Places", "Notes", "Scenes", "Timeline", "Outline", "Writer", "Structure", "Acts", "Beats", "Tags", "Graph", "Arcs", "Search", "Assistant"):
            icon = _ICONS.get(label, "")
            btn = QPushButton(f"{icon}  {label}")
            sidebar_layout.addWidget(btn)
            self.sidebar_buttons[label] = btn

        sidebar_layout.addStretch()

        # -- Appearance selector ------------------------------------------------
        app_label = QLabel("Appearance")
        app_label.setStyleSheet(
            "font-size: 10px; padding: 2px 14px; margin-top: 8px;"
        )
        sidebar_layout.addWidget(app_label)

        appearance_bar = QWidget()
        appearance_bar.setObjectName("appearanceBar")
        ab_layout = QHBoxLayout(appearance_bar)
        ab_layout.setContentsMargins(2, 2, 2, 2)
        ab_layout.setSpacing(0)
        self._appearance_btns: dict[str, QPushButton] = {}
        for name, short in (("Dark", "Dark"), ("Light (Green)", "Green"), ("Light (Warm)", "Warm")):
            btn = QPushButton(short)
            btn.setCheckable(True)
            btn.setChecked(name == theme.current_palette())
            btn.clicked.connect(lambda _, n=name: self._switch_theme(n))
            ab_layout.addWidget(btn)
            self._appearance_btns[name] = btn
        sidebar_layout.addWidget(appearance_bar)

        # -- Import / Export ---------------------------------------------------
        self._import_btn = QPushButton("\U0001F4E5  Import")
        sidebar_layout.addWidget(self._import_btn)
        self._import_btn.clicked.connect(self._on_import)

        self._export_btn = QPushButton("\U0001F4E4  Export")
        sidebar_layout.addWidget(self._export_btn)
        self._export_btn.clicked.connect(self._on_export)

        # Connect sidebar buttons
        self.sidebar_buttons["Projects"].clicked.connect(self._show_projects)
        self.sidebar_buttons["Dashboard"].clicked.connect(self._show_dashboard)
        self.sidebar_buttons["Characters"].clicked.connect(self._show_characters)
        self.sidebar_buttons["Places"].clicked.connect(self._show_places)
        self.sidebar_buttons["Notes"].clicked.connect(self._show_notes)
        self.sidebar_buttons["Scenes"].clicked.connect(self._show_scenes)
        self.sidebar_buttons["Timeline"].clicked.connect(self._show_timeline)
        self.sidebar_buttons["Outline"].clicked.connect(self._show_outline)
        self.sidebar_buttons["Writer"].clicked.connect(self._show_writer_outline)
        self.sidebar_buttons["Structure"].clicked.connect(self._show_structure)
        self.sidebar_buttons["Acts"].clicked.connect(self._show_acts)
        self.sidebar_buttons["Beats"].clicked.connect(self._show_beats)
        self.sidebar_buttons["Tags"].clicked.connect(self._show_tags)
        self.sidebar_buttons["Graph"].clicked.connect(self._show_graph)
        self.sidebar_buttons["Arcs"].clicked.connect(self._show_arcs)
        self.sidebar_buttons["Search"].clicked.connect(self._show_search)
        self.sidebar_buttons["Assistant"].clicked.connect(
            self._toggle_assistant
        )

        # -- Right content area ----------------------------------------------
        self.content_area = self._build_initial_content()

        # -- Assistant side panel --------------------------------------------
        self._assistant_panel = AssistantPanel(
            self._db,
            self._project_id,
            on_data_changed=self._on_data_changed,
            on_open_scene=self._open_scene_in_editor,
        )
        self._assistant_panel.panel_closed.connect(self._hide_assistant)
        self._assistant_panel.setVisible(False)

        # -- Assemble --------------------------------------------------------
        self._sidebar = sidebar
        root_layout.addWidget(sidebar)
        root_layout.addWidget(self.content_area, stretch=1)
        root_layout.addWidget(self._assistant_panel)

        self.setCentralWidget(central)

    def _set_content(self, widget: QWidget) -> None:
        """Replace the content area with a new widget."""
        layout = self.centralWidget().layout()
        layout.replaceWidget(self.content_area, widget)
        old = self.content_area
        if old is self._cached_scenes_view:
            old.hide()
        else:
            old.deleteLater()
        self.content_area = widget
        widget.show()

    def _build_initial_content(self) -> QWidget:
        scenes = self._db.get_all_scenes(self._project_id)
        if not scenes and not preferences.get_flag("has_seen_onboarding"):
            return WelcomeView(on_create_scene=self._on_welcome_create_scene)
        placeholder = QWidget()
        QVBoxLayout(placeholder).addWidget(
            QLabel("Select a section from the sidebar")
        )
        return placeholder

    def _on_welcome_create_scene(self) -> None:
        scene = self._db.create_scene(self._project_id, "Untitled Scene")
        preferences.set_flag("has_seen_onboarding", True)
        self._on_data_changed()
        self._open_scene_in_editor(scene.id)

    def _show_projects(self) -> None:
        self._set_content(
            ProjectsView(
                on_open_file=self._open_file,
                on_save_as=self._on_save_as,
            )
        )

    def _show_dashboard(self) -> None:
        self._set_content(
            DashboardView(
                self._db, self._project_id,
                on_navigate=self._on_link_navigated,
                on_open_section=self._open_section,
            )
        )

    def _open_section(self, name: str) -> None:
        if name == "scenes":
            self._show_scenes()
        elif name == "characters":
            self._show_characters()
        elif name == "timeline":
            self._show_timeline()

    def _show_characters(self) -> None:
        self._set_content(
            CharactersView(
                self._db, self._project_id,
                on_data_changed=self._on_data_changed,
                on_link_clicked=self._on_link_navigated,
            )
        )

    def _show_places(self) -> None:
        self._set_content(
            PlacesView(
                self._db, self._project_id,
                on_data_changed=self._on_data_changed,
                on_link_clicked=self._on_link_navigated,
            )
        )

    def _show_notes(self) -> None:
        self._set_content(
            NotesView(
                self._db,
                self._project_id,
                on_data_changed=self._on_data_changed,
                on_link_clicked=self._on_link_navigated,
            )
        )

    def _show_scenes(self) -> None:
        if self._cached_scenes_view is None:
            self._cached_scenes_view = ScenesView(
                self._db,
                self._project_id,
                on_data_changed=self._on_data_changed,
                on_link_clicked=self._on_link_navigated,
                on_focus_mode_changed=self._on_focus_mode_changed,
            )
        if self.content_area is not self._cached_scenes_view:
            self._set_content(self._cached_scenes_view)
        self._cached_scenes_view.refresh()

    def _show_timeline(self) -> None:
        preferences.set_flag("has_seen_timeline_hint", True)
        self._set_content(
            TimelineView(
                self._db,
                self._project_id,
                on_scene_selected=self._open_scene_in_editor,
                on_data_changed=self._on_data_changed,
            )
        )

    def _show_outline(self) -> None:
        self._set_content(OutlineView(self._db, self._project_id))

    def _show_writer_outline(self) -> None:
        self._set_content(WriterOutlineView(self._db, self._project_id))

    def _show_structure(self) -> None:
        self._set_content(StructureView(self._db, self._project_id))

    def _show_acts(self) -> None:
        self._set_content(ActAnalysisView(self._db, self._project_id))

    def _show_beats(self) -> None:
        self._set_content(BeatAnalysisView(self._db, self._project_id))

    def _show_tags(self) -> None:
        self._set_content(TagAnalysisView(self._db, self._project_id))

    def _show_graph(self) -> None:
        self._set_content(
            GraphView(
                self._db, self._project_id,
                on_node_clicked=self._on_link_navigated,
            )
        )

    def _show_arcs(self) -> None:
        self._set_content(
            CharacterArcView(
                self._db, self._project_id,
                on_scene_selected=self._open_scene_in_editor,
            )
        )

    def _toggle_assistant(self) -> None:
        visible = self._assistant_panel.isVisible()
        if not visible:
            self._assistant_panel.refresh_scenes()
        self._assistant_panel.setVisible(not visible)

    def _hide_assistant(self) -> None:
        self._assistant_panel.setVisible(False)

    def _show_search(self) -> None:
        self._set_content(
            SearchView(
                self._db,
                self._project_id,
                on_result_selected=self._on_search_result_selected,
            )
        )

    def _on_search_result_selected(self, entity_type: str, entity_id: int) -> None:
        self._on_link_navigated(entity_type, entity_id)

    def _on_link_navigated(self, entity_type: str, entity_id: int) -> None:
        if entity_type == "Character":
            view = CharactersView(
                self._db, self._project_id,
                on_data_changed=self._on_data_changed,
                on_link_clicked=self._on_link_navigated,
            )
            self._set_content(view)
            view.select_character(entity_id)
        elif entity_type == "Place":
            view = PlacesView(
                self._db, self._project_id,
                on_data_changed=self._on_data_changed,
                on_link_clicked=self._on_link_navigated,
            )
            self._set_content(view)
            view.select_place(entity_id)
        elif entity_type == "Note":
            view = NotesView(
                self._db, self._project_id,
                on_data_changed=self._on_data_changed,
                on_link_clicked=self._on_link_navigated,
            )
            self._set_content(view)
            view.select_note(entity_id)
        elif entity_type == "Scene":
            self._open_scene_in_editor(entity_id)

    def _open_scene_in_editor(self, scene_id: int) -> None:
        if self._cached_scenes_view is None:
            self._cached_scenes_view = ScenesView(
                self._db, self._project_id,
                on_data_changed=self._on_data_changed,
                on_link_clicked=self._on_link_navigated,
                on_focus_mode_changed=self._on_focus_mode_changed,
            )
        if self.content_area is not self._cached_scenes_view:
            self._set_content(self._cached_scenes_view)
        self._cached_scenes_view.refresh()
        self._cached_scenes_view.select_scene(scene_id)
        self._assistant_panel.set_active_scene(scene_id)

    def _on_import(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Import Project",
            "",
            "JSON (*.json)",
        )
        if not path:
            return

        try:
            with open(path, "r", encoding="utf-8") as f:
                raw = f.read()
        except OSError as e:
            QMessageBox.warning(self, "Import", f"Could not read file:\n{e}")
            return

        data, error = validate_import_data(raw)
        if data is None:
            QMessageBox.warning(self, "Import", error)
            return

        new_project_id = import_json(self._db, data)
        self._project_id = new_project_id
        self._current_file = None
        self._mark_clean()
        self._reset_content("Import complete. Select a section from the sidebar.")
        QMessageBox.information(
            self, "Import", f"Project imported successfully (ID {new_project_id})."
        )

    def _on_export(self) -> None:
        path, selected_filter = QFileDialog.getSaveFileName(
            self,
            "Export Project",
            "",
            "JSON (*.json);;Markdown (*.md);;Screenplay (*.txt);;"
            "Manuscript (*.txt);;DOCX Manuscript (*.docx);;"
            "CSV – Scenes (*.csv)",
        )
        if not path:
            return

        if "DOCX" in selected_filter:
            if not path.endswith(".docx"):
                path += ".docx"
            export_docx_manuscript(self._db, self._project_id, path)
            QMessageBox.information(self, "Export", f"Exported to {path}")
            return

        if path.endswith(".csv") or "CSV" in selected_filter:
            content = export_csv_scenes(self._db, self._project_id)
            if not path.endswith(".csv"):
                path += ".csv"
        elif "Screenplay" in selected_filter:
            content = export_screenplay(self._db, self._project_id)
            if not path.endswith(".txt"):
                path += ".txt"
        elif "Manuscript" in selected_filter:
            content = export_manuscript(self._db, self._project_id)
            if not path.endswith(".txt"):
                path += ".txt"
        elif path.endswith(".md") or "Markdown" in selected_filter:
            content = export_markdown(self._db, self._project_id)
            if not path.endswith(".md"):
                path += ".md"
        else:
            content = export_json(self._db, self._project_id)
            if not path.endswith(".json"):
                path += ".json"

        with open(path, "w", encoding="utf-8") as f:
            f.write(content)

        QMessageBox.information(self, "Export", f"Exported to {path}")

    # -- Menu bar ------------------------------------------------------------

    def _build_menu_bar(self) -> None:
        menu_bar = self.menuBar()
        file_menu = menu_bar.addMenu("File")

        open_action = QAction("Open Project...", self)
        open_action.triggered.connect(self._on_open_project)
        file_menu.addAction(open_action)

        save_as_action = QAction("Save As...", self)
        save_as_action.triggered.connect(self._on_save_as)
        file_menu.addAction(save_as_action)

        file_menu.addSeparator()

        self._recent_menu = QMenu("Recent Projects", self)
        file_menu.addMenu(self._recent_menu)
        self._refresh_recent_menu()

    def _refresh_recent_menu(self) -> None:
        self._recent_menu.clear()
        paths = recent_projects.load()
        if not paths:
            no_recent = QAction("(no recent projects)", self)
            no_recent.setEnabled(False)
            self._recent_menu.addAction(no_recent)
            return
        for path in paths:
            label = Path(path).name
            action = QAction(label, self)
            action.setToolTip(path)
            action.triggered.connect(lambda checked, p=path: self._open_file(p))
            self._recent_menu.addAction(action)

    def _update_title(self) -> None:
        dirty_mark = " *" if self._dirty else ""
        if self._current_file:
            name = Path(self._current_file).name
            self.setWindowTitle(f"Logosforge \u2014 {name}{dirty_mark}")
        else:
            self.setWindowTitle(f"Logosforge{dirty_mark}")

    def _on_open_project(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Open Project",
            "",
            "JSON (*.json)",
        )
        if path:
            self._open_file(path)

    def _open_file(self, path: str) -> None:
        try:
            with open(path, "r", encoding="utf-8") as f:
                raw = f.read()
        except OSError as e:
            QMessageBox.warning(self, "Open Project", f"Could not read file:\n{e}")
            return

        data, error = validate_import_data(raw)
        if data is None:
            QMessageBox.warning(self, "Open Project", error)
            return

        new_project_id = import_json(self._db, data)
        self._project_id = new_project_id
        self._current_file = path
        self._mark_clean()
        recent_projects.add(path)
        self._refresh_recent_menu()

        self._reset_content("Project loaded. Select a section from the sidebar.")

    def _on_save_as(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Project As",
            "",
            "JSON (*.json)",
        )
        if not path:
            return
        if not path.endswith(".json"):
            path += ".json"

        content = export_json(self._db, self._project_id)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)

        self._current_file = path
        self._mark_clean()
        recent_projects.add(path)
        self._refresh_recent_menu()
        QMessageBox.information(self, "Save As", f"Project saved to {path}")

    def _reset_content(self, message: str) -> None:
        widget = QWidget()
        QVBoxLayout(widget).addWidget(QLabel(message))
        self._set_content(widget)

    # -- Dirty state and autosave --------------------------------------------

    def _on_data_changed(self) -> None:
        self._dirty = True
        self._update_title()
        self._auto_save()
        self._assistant_panel.refresh_scenes()

    def _auto_save(self) -> None:
        if not self._current_file:
            return
        content = export_json(self._db, self._project_id)
        with open(self._current_file, "w", encoding="utf-8") as f:
            f.write(content)
        self._dirty = False
        self._update_title()

    def _on_focus_mode_changed(self, active: bool) -> None:
        self._sidebar.setVisible(not active)
        if active:
            self._assistant_panel.setVisible(False)

    def _mark_clean(self) -> None:
        self._dirty = False
        self._update_title()

    # -- Theme switching -----------------------------------------------------

    def _switch_theme(self, name: str) -> None:
        theme.set_palette(name)
        theme._rebuild_html()
        app = QApplication.instance()
        if app:
            app.setStyleSheet(theme.build_stylesheet())
        for key, btn in self._appearance_btns.items():
            btn.setChecked(key == name)
        preferences.set_string("appearance", name)
