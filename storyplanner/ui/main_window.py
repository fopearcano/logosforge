"""Main window with a sidebar and content area."""

import os
from pathlib import Path

from PySide6.QtCore import QPropertyAnimation, QEasingCurve, Qt
from PySide6.QtGui import QAction, QCloseEvent, QColor, QIcon, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from storyplanner.ui import theme

from storyplanner import preferences, recent_projects
from storyplanner.db import Database
from storyplanner.settings import get_manager as get_settings
from storyplanner.export import (
    export_csv_scenes,
    export_docx_manuscript,
    export_fdx,
    export_formatted_text,
    export_fountain,
    export_html,
    export_json,
    export_manuscript,
    export_markdown,
    export_pdf,
    export_screenplay,
)
from storyplanner.import_data import import_json, validate_import_data
from storyplanner.plugin_manager import get_plugin_manager
from storyplanner.ui.assistant_view import AssistantPanel
from storyplanner.ui.settings_dialog import SettingsDialog
from storyplanner.ui.act_analysis_view import ActAnalysisView
from storyplanner.ui.beat_analysis_view import BeatAnalysisView
from storyplanner.ui.character_arc_view import CharacterArcView
from storyplanner.ui.characters_view import CharactersView
from storyplanner.ui.dashboard_view import DashboardView
from storyplanner.ui.focus_graph_view import FocusGraphView
from storyplanner.ui.story_health_view import StoryHealthView
from storyplanner.ui.character_balance_view import CharacterBalanceView
from storyplanner.ui.pacing_insights_view import PacingInsightsView
from storyplanner.ui.mode_suggestions_view import ModeSuggestionsView
from storyplanner.ui.graph_view import GraphView
from storyplanner.ui.notes_view import NotesView
from storyplanner.ui.outline_view import OutlineView
from storyplanner.ui.places_view import PlacesView
from storyplanner.ui.plugins_view import PluginsView
from storyplanner.ui.psyke_view import PsykeView
from storyplanner.ui.projects_view import ProjectsView
from storyplanner.ui.scenes_view import ScenesView
from storyplanner.ui.multi_plot_view import MultiPlotView
from storyplanner.ui.narrative_dashboard_view import NarrativeDashboardView
from storyplanner.ui.story_grid_view import StoryGridView
from storyplanner.ui.search_view import SearchView
from storyplanner.ui.structure_view import StructureView
from storyplanner.ui.tag_analysis_view import TagAnalysisView
from storyplanner.ui.timeline_view import TimelineView
from storyplanner.ui.welcome_view import WelcomeView
from storyplanner.ui.writing_core_view import WritingCoreView


_ICON_SLOT_WIDTH = 48


class _SidebarButton(QPushButton):
    """Sidebar button with fixed icon slot and collapsible label."""

    def __init__(self, icon_text: str, label: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._icon_text = icon_text
        self._label_text = label
        self._collapsed = False
        self.setCheckable(True)
        self.setFlat(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setObjectName("sidebarBtn")
        self._update_text()

    def set_collapsed(self, collapsed: bool) -> None:
        self._collapsed = collapsed
        self._update_text()

    def _update_text(self) -> None:
        if self._collapsed:
            self.setText(self._icon_text)
            self.setToolTip(self._label_text)
        else:
            self.setText(f"{self._icon_text}  {self._label_text}")
            self.setToolTip("")


class MainWindow(QMainWindow):
    def __init__(self, db: Database, project_id: int) -> None:
        super().__init__()
        self._db = db
        self._project_id = project_id
        self._current_file: str | None = None
        self._dirty = False
        self._current_section: str = "Dashboard"
        self._cached_scenes_view: ScenesView | None = None
        self._update_title()
        self.resize(900, 600)
        self.setMinimumSize(640, 400)

        from storyplanner.paths import get_assets_path
        assets = get_assets_path()
        for icon_name in ("icon.png", "icon.svg"):
            icon_path = str(assets / icon_name)
            if os.path.exists(icon_path):
                self.setWindowIcon(QIcon(icon_path))
                break

        # -- Menu bar --------------------------------------------------------
        self._build_menu_bar()

        central = QWidget()
        root_layout = QHBoxLayout(central)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # -- Left sidebar ----------------------------------------------------
        sidebar = QWidget()
        sidebar.setObjectName("sidebar")
        sidebar.setMinimumWidth(64)
        sidebar.setMaximumWidth(220)
        sidebar.setFixedWidth(220)
        sidebar.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Preferred)
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(0, 8, 0, 8)
        sidebar_layout.setSpacing(0)

        self._sidebar_collapsed = False
        self._sidebar_anim: QPropertyAnimation | None = None
        self._assistant_user_visible = False
        self._assistant_overlay = False
        self._layout_tier: str | None = None
        self._sidebar_icons = {
            "Projects": "\U0001F4C1",
            "Dashboard": "\U0001F3E0",
            "Characters": "\U0001F464",
            "Places": "\U0001F4CD",
            "Notes": "\U0001F4DD",
            "Scenes": "\U0001F3AC",
            "Manuscript": "\u2712",
            "Timeline": "\U0001F552",
            "Outline": "\U0001F4D1",
            "Structure": "\U0001F3D7",
            "Acts": "\U0001F3AD",
            "Beats": "\U0001F4CC",
            "Tags": "\U0001F3F7",
            "Graph": "\U0001F578",
            "Arcs": "\U0001F4C8",
            "Search": "\U0001F50D",
            "PSYKE": "\U0001F4D6",
            "Grid": "\U0001F5A5",
            "Plot": "\U0001F4CA",
            "Health": "\U0001F49A",
            "Balance": "\u2696",
            "Pacing": "\U0001F3B5",
            "Adapt": "\U0001F9E0",
            "Narrative": "\U0001F4CA",
            "Plugins": "\U0001F9E9",
            "Assistant": "\U0001F916",
        }

        self._toggle_btn = QPushButton("\u00ab")
        self._toggle_btn.clicked.connect(self._toggle_sidebar)
        sidebar_layout.addWidget(self._toggle_btn)

        _NAV_LABELS = [
            "Projects", "Dashboard", "Characters", "Places", "Notes",
            "Scenes", "Manuscript", "Timeline", "Grid", "Plot", "Outline",
            "Structure", "Acts", "Beats", "Tags", "Graph", "Arcs",
            "Health", "Balance", "Pacing", "Adapt", "Narrative", "Search", "PSYKE", "Plugins", "Assistant",
        ]
        self.sidebar_buttons: dict[str, _SidebarButton] = {}
        for label in _NAV_LABELS:
            icon = self._sidebar_icons.get(label, "")
            btn = _SidebarButton(icon, label)
            sidebar_layout.addWidget(btn)
            self.sidebar_buttons[label] = btn

        sidebar_layout.addStretch()

        # -- Appearance selector ------------------------------------------------
        self._appearance_label = QLabel("Appearance")
        self._appearance_label.setStyleSheet(
            "font-size: 10px; padding: 2px 14px; margin-top: 8px;"
        )
        sidebar_layout.addWidget(self._appearance_label)

        self._appearance_bar = QWidget()
        self._appearance_bar.setObjectName("appearanceBar")
        ab_layout = QHBoxLayout(self._appearance_bar)
        ab_layout.setContentsMargins(2, 2, 2, 2)
        ab_layout.setSpacing(0)
        self._appearance_btns: dict[str, QPushButton] = {}
        for name, short in (
            ("Dark", "Dark"),
            ("Light (Green)", "Green"),
            ("Light (Warm)", "Warm"),
        ):
            btn = QPushButton(short)
            btn.setCheckable(True)
            btn.setChecked(name == theme.current_palette())
            btn.clicked.connect(lambda _, n=name: self._switch_theme(n))
            ab_layout.addWidget(btn)
            self._appearance_btns[name] = btn
        sidebar_layout.addWidget(self._appearance_bar)

        # -- Import / Export ---------------------------------------------------
        self._import_btn = _SidebarButton("\U0001F4E5", "Import")
        sidebar_layout.addWidget(self._import_btn)
        self._import_btn.clicked.connect(self._on_import)

        self._export_btn = _SidebarButton("\U0001F4E4", "Export")
        sidebar_layout.addWidget(self._export_btn)
        self._export_btn.clicked.connect(self._on_export)

        # -- Connect navigation buttons (checkable + active tracking) ----------
        self._nav_labels = [
            "Projects", "Dashboard", "Characters", "Places", "Notes",
            "Scenes", "Manuscript", "Timeline", "Grid", "Plot", "Outline",
            "Structure", "Acts", "Beats", "Tags", "Graph", "Arcs",
            "Health", "Balance", "Pacing", "Adapt", "Narrative", "Search", "PSYKE", "Plugins",
        ]
        _nav_handlers = {
            "Projects": self._show_projects,
            "Dashboard": self._show_dashboard,
            "Characters": self._show_characters,
            "Places": self._show_places,
            "Notes": self._show_notes,
            "Scenes": self._show_scenes,
            "Manuscript": self._show_manuscript,
            "Timeline": self._show_timeline,
            "Grid": self._show_grid,
            "Plot": self._show_plot,
            "Outline": self._show_outline,
            "Structure": self._show_structure,
            "Acts": self._show_acts,
            "Beats": self._show_beats,
            "Tags": self._show_tags,
            "Graph": self._show_graph,
            "Arcs": self._show_arcs,
            "Health": self._show_health,
            "Balance": self._show_balance,
            "Pacing": self._show_pacing,
            "Adapt": self._show_adapt,
            "Narrative": self._show_narrative,
            "Search": self._show_search,
            "PSYKE": self._show_psyke,
            "Plugins": self._show_plugins,
        }
        for label in self._nav_labels:
            btn = self.sidebar_buttons[label]
            btn.setCheckable(True)
            handler = _nav_handlers[label]
            btn.clicked.connect(
                lambda _, l=label, h=handler: (
                    self._set_active_section(l), h()
                )
            )

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
            get_active_scene_id=self._detect_active_scene_id,
        )
        self._assistant_panel.panel_closed.connect(self._hide_assistant)
        self._assistant_panel.overlay_toggled.connect(self._on_overlay_toggled)
        self._assistant_panel.setVisible(False)
        self._assistant_panel.setSizePolicy(
            QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred,
        )
        self._assistant_panel.refresh_style()

        # -- Assemble --------------------------------------------------------
        self._sidebar = sidebar
        self._root_layout = root_layout
        root_layout.addWidget(sidebar, stretch=0)
        root_layout.addWidget(self.content_area, stretch=1)
        root_layout.addWidget(self._assistant_panel, stretch=0)

        self.setCentralWidget(central)

        # -- Restore persisted state -----------------------------------------
        mgr = get_settings()
        if mgr.get("sidebar_collapsed"):
            self._set_sidebar_collapsed(True, animate=False)
        if mgr.get("assistant_open"):
            self._assistant_user_visible = True
            self._assistant_panel.refresh_scenes()
            self._assistant_panel.setVisible(True)

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
                on_open_psyke_entry=self._open_psyke_entry,
            )
        if self.content_area is not self._cached_scenes_view:
            self._set_content(self._cached_scenes_view)
        self._cached_scenes_view.refresh()

    def _show_manuscript(self) -> None:
        self._set_content(
            WritingCoreView(
                self._db,
                self._project_id,
                on_data_changed=self._on_data_changed,
                on_focus_mode_changed=self._on_focus_mode_changed,
                on_open_psyke_entry=self._open_psyke_entry,
            )
        )

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

    def _show_grid(self) -> None:
        self._set_content(
            StoryGridView(
                self._db,
                self._project_id,
                on_data_changed=self._on_data_changed,
                on_open_scene=self._open_scene_in_editor,
            )
        )

    def _show_plot(self) -> None:
        self._set_content(
            MultiPlotView(
                self._db,
                self._project_id,
                on_data_changed=self._on_data_changed,
                on_open_scene=self._open_scene_in_editor,
            )
        )

    def _show_outline(self) -> None:
        self._set_content(OutlineView(self._db, self._project_id))

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
            FocusGraphView(
                self._db, self._project_id,
                on_node_selected=self._on_link_navigated,
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
        self._assistant_user_visible = not self._assistant_panel.isVisible()
        if self._assistant_user_visible:
            self._assistant_panel.refresh_scenes()
            if self._assistant_overlay:
                self._position_overlay_assistant()
        self._assistant_panel.setVisible(self._assistant_user_visible)
        get_settings().set("assistant_open", self._assistant_user_visible)

    def _hide_assistant(self) -> None:
        self._assistant_user_visible = False
        self._assistant_panel.setVisible(False)
        get_settings().set("assistant_open", False)

    def _on_overlay_toggled(self, overlay: bool) -> None:
        self._assistant_overlay = overlay
        layout = self._root_layout

        if overlay:
            layout.removeWidget(self._assistant_panel)
            self._assistant_panel.setParent(self.centralWidget())
            self._assistant_panel.setMaximumWidth(360)
            shadow = QGraphicsDropShadowEffect(self._assistant_panel)
            shadow.setColor(QColor(0, 0, 0, 60))
            shadow.setBlurRadius(24)
            shadow.setOffset(-4, 0)
            self._assistant_panel.setGraphicsEffect(shadow)
            self._position_overlay_assistant()
            self._assistant_panel.raise_()
            self._assistant_panel.show()
        else:
            self._assistant_panel.setGraphicsEffect(None)
            self._assistant_panel.setMaximumWidth(340)
            layout.addWidget(self._assistant_panel, stretch=0)
            self._assistant_panel.show()
        self._assistant_panel.refresh_style()

    def _position_overlay_assistant(self) -> None:
        if not self._assistant_overlay:
            return
        central = self.centralWidget()
        if central is None:
            return
        panel_w = min(360, central.width() // 3)
        panel_h = central.height() - 16
        x = central.width() - panel_w - 8
        y = 8
        self._assistant_panel.setGeometry(x, y, panel_w, panel_h)

    # -- Sidebar collapse/expand ---------------------------------------------

    def _toggle_sidebar(self) -> None:
        self._set_sidebar_collapsed(not self._sidebar_collapsed)

    def _set_sidebar_collapsed(self, collapsed: bool, animate: bool = True) -> None:
        if self._sidebar_collapsed == collapsed:
            return
        self._sidebar_collapsed = collapsed

        target_width = 64 if collapsed else 220

        if collapsed:
            self._apply_collapsed_labels()

        if animate and self.isVisible():
            if self._sidebar_anim is not None:
                self._sidebar_anim.stop()
            current = self._sidebar.width()
            self._sidebar.setMinimumWidth(min(current, target_width))
            self._sidebar.setMaximumWidth(max(current, target_width))
            anim = QPropertyAnimation(self._sidebar, b"maximumWidth")
            anim.setDuration(200)
            anim.setStartValue(current)
            anim.setEndValue(target_width)
            anim.setEasingCurve(QEasingCurve.Type.InOutCubic)
            anim.finished.connect(lambda: self._finalize_sidebar(target_width))
            self._sidebar_anim = anim
            self._sidebar.setMinimumWidth(target_width)
            anim.start()
        else:
            self._sidebar.setFixedWidth(target_width)
            self._finalize_sidebar(target_width)

        get_settings().set("sidebar_collapsed", collapsed)

    def _finalize_sidebar(self, width: int) -> None:
        if not self._sidebar_collapsed:
            self._apply_expanded_labels()
        self._sidebar.setFixedWidth(width)
        self._sidebar.setMinimumWidth(width)
        self._sidebar.setMaximumWidth(width)
        self._refresh_sidebar_style()

    def _apply_collapsed_labels(self) -> None:
        self._toggle_btn.setText("\u00bb")
        self._toggle_btn.setToolTip("Expand sidebar")
        for btn in self.sidebar_buttons.values():
            btn.set_collapsed(True)
        self._import_btn.set_collapsed(True)
        self._export_btn.set_collapsed(True)
        self._appearance_label.setVisible(False)
        self._appearance_bar.setVisible(False)

    def _apply_expanded_labels(self) -> None:
        self._toggle_btn.setText("\u00ab")
        self._toggle_btn.setToolTip("")
        for btn in self.sidebar_buttons.values():
            btn.set_collapsed(False)
        self._import_btn.set_collapsed(False)
        self._export_btn.set_collapsed(False)
        self._appearance_label.setVisible(True)
        self._appearance_bar.setVisible(True)

    def _refresh_sidebar_style(self) -> None:
        self._sidebar.style().unpolish(self._sidebar)
        self._sidebar.style().polish(self._sidebar)
        for child in self._sidebar.findChildren(QPushButton):
            child.style().unpolish(child)
            child.style().polish(child)
        self._sidebar.update()

    def _set_active_section(self, name: str) -> None:
        self._current_section = name
        for label in self._nav_labels:
            self.sidebar_buttons[label].setChecked(label == name)
        self._assistant_panel.set_active_section_name(name)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._apply_layout_for_width(event.size().width())
        if self._assistant_overlay:
            self._position_overlay_assistant()

    def _apply_layout_for_width(self, w: int) -> None:
        if w >= 1400:
            tier = "wide"
        elif w >= 1060:
            tier = "medium"
        elif w >= 820:
            tier = "narrow"
        else:
            tier = "minimal"

        if tier == self._layout_tier:
            return
        self._layout_tier = tier

        if tier == "wide":
            self._set_sidebar_collapsed(False)
            self._assistant_panel.setMaximumWidth(340)
            if self._assistant_user_visible:
                self._assistant_panel.setVisible(True)
        elif tier == "medium":
            self._set_sidebar_collapsed(True)
            self._assistant_panel.setMaximumWidth(320)
            if self._assistant_user_visible:
                self._assistant_panel.setVisible(True)
        elif tier == "narrow":
            self._set_sidebar_collapsed(True)
            self._assistant_panel.setMaximumWidth(300)
            if self._assistant_user_visible and not self._assistant_overlay:
                self._assistant_panel.setVisible(False)
        else:
            self._set_sidebar_collapsed(True)
            self._assistant_panel.setVisible(False)

    def _open_psyke_entry(self, entry_id: int) -> None:
        self._set_active_section("PSYKE")
        view = PsykeView(
            self._db,
            self._project_id,
            on_data_changed=self._on_data_changed,
            on_open_scene=self._open_scene_in_editor,
        )
        self._set_content(view)
        view.select_entry(entry_id)

    def _show_plugins(self) -> None:
        self._set_content(PluginsView())

    def _show_psyke(self) -> None:
        self._set_content(
            PsykeView(
                self._db,
                self._project_id,
                on_data_changed=self._on_data_changed,
                on_open_scene=self._open_scene_in_editor,
            )
        )

    def _show_health(self) -> None:
        self._set_content(StoryHealthView(self._db, self._project_id))

    def _show_balance(self) -> None:
        self._set_content(CharacterBalanceView(self._db, self._project_id))

    def _show_pacing(self) -> None:
        self._set_content(PacingInsightsView(self._db, self._project_id))

    def _show_adapt(self) -> None:
        self._set_content(ModeSuggestionsView(self._db, self._project_id))

    def _show_narrative(self) -> None:
        self._set_content(
            NarrativeDashboardView(
                self._db,
                self._project_id,
                on_scene_selected=self._open_scene_in_editor,
            )
        )

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
            self._set_active_section("Characters")
            view = CharactersView(
                self._db, self._project_id,
                on_data_changed=self._on_data_changed,
                on_link_clicked=self._on_link_navigated,
            )
            self._set_content(view)
            view.select_character(entity_id)
        elif entity_type == "Place":
            self._set_active_section("Places")
            view = PlacesView(
                self._db, self._project_id,
                on_data_changed=self._on_data_changed,
                on_link_clicked=self._on_link_navigated,
            )
            self._set_content(view)
            view.select_place(entity_id)
        elif entity_type == "Note":
            self._set_active_section("Notes")
            view = NotesView(
                self._db, self._project_id,
                on_data_changed=self._on_data_changed,
                on_link_clicked=self._on_link_navigated,
            )
            self._set_content(view)
            view.select_note(entity_id)
        elif entity_type == "Scene":
            self._open_scene_in_editor(entity_id)

    def _detect_active_scene_id(self) -> int | None:
        from storyplanner.ui.writing_core_view import WritingCoreView
        view = self.content_area
        if isinstance(view, WritingCoreView):
            editor = getattr(view, "_active_editor", None)
            if editor:
                return getattr(editor, "_scene_id", None)
        if self._cached_scenes_view is not None and self.content_area is self._cached_scenes_view:
            editor = getattr(self._cached_scenes_view, "_active_editor", None)
            if editor:
                return getattr(editor, "_scene_id", None)
        scenes = self._db.get_all_scenes(self._project_id)
        if len(scenes) == 1:
            return scenes[0].id
        return None

    def _open_scene_in_editor(self, scene_id: int) -> None:
        self._set_active_section("Scenes")
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
        self._cached_scenes_view = None
        self._mark_clean()
        self._reset_content("Import complete. Select a section from the sidebar.")
        QMessageBox.information(
            self, "Import", f"Project imported successfully (ID {new_project_id})."
        )

    def _on_export(self) -> None:
        project = self._db.get_project_by_id(self._project_id)
        fmt = (project.format_mode if project else "novel") or "novel"
        fmt_labels = {
            "novel": "Manuscript",
            "screenplay": "Screenplay",
            "graphic_novel": "Graphic Novel Script",
            "stage_script": "Stage Script",
            "series": "TV Script",
        }
        fmt_label = fmt_labels.get(fmt, "Formatted Text")

        filters = [
            f"PDF {fmt_label} (*.pdf)",
            f"DOCX {fmt_label} (*.docx)",
            f"{fmt_label} (*.txt)",
            "Fountain (*.fountain)",
            "Final Draft (*.fdx)",
            "HTML (*.html)",
            "Markdown (*.md)",
            "JSON (*.json)",
            "CSV – Scenes (*.csv)",
        ]

        path, selected_filter = QFileDialog.getSaveFileName(
            self,
            "Export Project",
            "",
            ";;".join(filters),
        )
        if not path:
            return

        if "PDF" in selected_filter:
            if not path.endswith(".pdf"):
                path += ".pdf"
            export_pdf(self._db, self._project_id, path)
            QMessageBox.information(self, "Export", f"Exported to {path}")
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
        elif "Fountain" in selected_filter or path.endswith(".fountain"):
            content = export_fountain(self._db, self._project_id)
            if not path.endswith(".fountain"):
                path += ".fountain"
        elif "Final Draft" in selected_filter or path.endswith(".fdx"):
            content = export_fdx(self._db, self._project_id)
            if not path.endswith(".fdx"):
                path += ".fdx"
        elif "HTML" in selected_filter or path.endswith(".html"):
            content = export_html(self._db, self._project_id)
            if not path.endswith(".html"):
                path += ".html"
        elif fmt_label in selected_filter:
            content = export_formatted_text(self._db, self._project_id)
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

        # -- File ---------------------------------------------------------------
        file_menu = menu_bar.addMenu("File")

        new_action = QAction("New Project", self)
        new_action.setShortcut(QKeySequence.StandardKey.New)
        new_action.triggered.connect(self._on_new_project)
        file_menu.addAction(new_action)

        open_action = QAction("Open Project...", self)
        open_action.setShortcut(QKeySequence.StandardKey.Open)
        open_action.triggered.connect(self._on_open_project)
        file_menu.addAction(open_action)

        file_menu.addSeparator()

        save_action = QAction("Save", self)
        save_action.setShortcut(QKeySequence.StandardKey.Save)
        save_action.triggered.connect(self._on_save)
        file_menu.addAction(save_action)

        save_as_action = QAction("Save As...", self)
        save_as_action.setShortcut(QKeySequence.StandardKey.SaveAs)
        save_as_action.triggered.connect(self._on_save_as)
        file_menu.addAction(save_as_action)

        file_menu.addSeparator()

        export_action = QAction("Export...", self)
        export_action.triggered.connect(self._on_export)
        file_menu.addAction(export_action)

        import_action = QAction("Import...", self)
        import_action.triggered.connect(self._on_import)
        file_menu.addAction(import_action)

        file_menu.addSeparator()

        self._recent_menu = QMenu("Recent Projects", self)
        file_menu.addMenu(self._recent_menu)
        self._refresh_recent_menu()

        file_menu.addSeparator()

        exit_action = QAction("Exit", self)
        exit_action.setShortcut(QKeySequence.StandardKey.Quit)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # -- Edit ---------------------------------------------------------------
        edit_menu = menu_bar.addMenu("Edit")

        undo_action = QAction("Undo", self)
        undo_action.setShortcut(QKeySequence.StandardKey.Undo)
        undo_action.triggered.connect(self._edit_undo)
        edit_menu.addAction(undo_action)

        redo_action = QAction("Redo", self)
        redo_action.setShortcut(QKeySequence.StandardKey.Redo)
        redo_action.triggered.connect(self._edit_redo)
        edit_menu.addAction(redo_action)

        edit_menu.addSeparator()

        cut_action = QAction("Cut", self)
        cut_action.setShortcut(QKeySequence.StandardKey.Cut)
        cut_action.triggered.connect(self._edit_cut)
        edit_menu.addAction(cut_action)

        copy_action = QAction("Copy", self)
        copy_action.setShortcut(QKeySequence.StandardKey.Copy)
        copy_action.triggered.connect(self._edit_copy)
        edit_menu.addAction(copy_action)

        paste_action = QAction("Paste", self)
        paste_action.setShortcut(QKeySequence.StandardKey.Paste)
        paste_action.triggered.connect(self._edit_paste)
        edit_menu.addAction(paste_action)

        edit_menu.addSeparator()

        prefs_action = QAction("Preferences...", self)
        prefs_action.setShortcut(QKeySequence("Ctrl+,"))
        prefs_action.triggered.connect(self._open_settings)
        edit_menu.addAction(prefs_action)

        # -- View ---------------------------------------------------------------
        view_menu = menu_bar.addMenu("View")

        toggle_sidebar_action = QAction("Toggle Sidebar", self)
        toggle_sidebar_action.setShortcut(QKeySequence("Ctrl+B"))
        toggle_sidebar_action.triggered.connect(self._toggle_sidebar)
        view_menu.addAction(toggle_sidebar_action)

        toggle_assistant_action = QAction("Toggle Assistant Panel", self)
        toggle_assistant_action.setShortcut(QKeySequence("Ctrl+\\"))
        toggle_assistant_action.triggered.connect(self._toggle_assistant)
        view_menu.addAction(toggle_assistant_action)

        focus_action = QAction("Focus Mode", self)
        focus_action.setShortcut(QKeySequence("Ctrl+Shift+F"))
        focus_action.triggered.connect(self._menu_toggle_focus)
        view_menu.addAction(focus_action)

        view_menu.addSeparator()

        appearance_menu = view_menu.addMenu("Appearance")
        for name in ("Dark", "Light (Green)", "Light (Warm)"):
            act = QAction(name, self)
            act.triggered.connect(
                lambda _, n=name: self._switch_theme(n)
            )
            appearance_menu.addAction(act)

        # -- Navigate -----------------------------------------------------------
        nav_menu = menu_bar.addMenu("Navigate")
        nav_items = [
            ("Dashboard", self._show_dashboard, "Ctrl+1"),
            ("Scenes", self._show_scenes, "Ctrl+2"),
            ("Manuscript", self._show_manuscript, "Ctrl+3"),
            ("Timeline", self._show_timeline, "Ctrl+4"),
            ("Characters", self._show_characters, "Ctrl+5"),
            ("Notes", self._show_notes, "Ctrl+6"),
            ("PSYKE", self._show_psyke, "Ctrl+7"),
        ]
        for label, handler, shortcut in nav_items:
            act = QAction(label, self)
            act.setShortcut(QKeySequence(shortcut))
            act.triggered.connect(
                lambda _, l=label, h=handler: (
                    self._set_active_section(l), h()
                )
            )
            nav_menu.addAction(act)

        # -- AI -----------------------------------------------------------------
        ai_menu = menu_bar.addMenu("AI")
        for preset in ("Rewrite", "Expand", "Dialogue"):
            act = QAction(preset, self)
            act.triggered.connect(
                lambda _, p=preset: self._menu_ai_preset(p)
            )
            ai_menu.addAction(act)
        ai_menu.addSeparator()
        open_assistant_action = QAction("Open Assistant", self)
        open_assistant_action.triggered.connect(self._toggle_assistant)
        ai_menu.addAction(open_assistant_action)

        # -- Plugins ------------------------------------------------------------
        self._plugins_menu = menu_bar.addMenu("Plugins")
        self._refresh_plugins_menu()

        # -- Help ---------------------------------------------------------------
        help_menu = menu_bar.addMenu("Help")

        about_action = QAction("About", self)
        about_action.triggered.connect(self._show_about)
        help_menu.addAction(about_action)

        docs_action = QAction("Documentation", self)
        docs_action.setEnabled(False)
        help_menu.addAction(docs_action)

        # -- Global QShortcuts (no menu item) -----------------------------------
        generate_shortcut = QShortcut(QKeySequence("Ctrl+Return"), self)
        generate_shortcut.activated.connect(self._menu_generate)

    def _refresh_plugins_menu(self) -> None:
        self._plugins_menu.clear()
        pm = get_plugin_manager()
        actions = pm.get_all_menu_actions()
        if actions:
            for name, callback in actions:
                act = QAction(name, self)
                act.triggered.connect(lambda _, cb=callback: cb())
                self._plugins_menu.addAction(act)
            self._plugins_menu.addSeparator()
        manage_act = QAction("Manage Plugins...", self)
        manage_act.triggered.connect(
            lambda: (self._set_active_section("Plugins"), self._show_plugins())
        )
        self._plugins_menu.addAction(manage_act)

    def _refresh_recent_menu(self) -> None:
        self._recent_menu.clear()
        paths = recent_projects.clean()
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

    # -- Menu action handlers ---------------------------------------------------

    def _on_new_project(self) -> None:
        project = self._db.create_project("Untitled")
        self._project_id = project.id
        self._current_file = None
        self._cached_scenes_view = None
        self._mark_clean()
        self._reset_content("New project created. Select a section from the sidebar.")

    def _on_save(self) -> None:
        if self._current_file:
            self._auto_save()
        else:
            self._on_save_as()

    def _edit_undo(self) -> None:
        w = QApplication.focusWidget()
        if hasattr(w, "undo"):
            w.undo()

    def _edit_redo(self) -> None:
        w = QApplication.focusWidget()
        if hasattr(w, "redo"):
            w.redo()

    def _edit_cut(self) -> None:
        w = QApplication.focusWidget()
        if hasattr(w, "cut"):
            w.cut()

    def _edit_copy(self) -> None:
        w = QApplication.focusWidget()
        if hasattr(w, "copy"):
            w.copy()

    def _edit_paste(self) -> None:
        w = QApplication.focusWidget()
        if hasattr(w, "paste"):
            w.paste()

    def _menu_toggle_focus(self) -> None:
        if (
            self._cached_scenes_view is not None
            and self.content_area is self._cached_scenes_view
        ):
            self._cached_scenes_view.toggle_focus_mode()

    def _menu_ai_preset(self, preset: str) -> None:
        if not self._assistant_panel.isVisible():
            self._assistant_user_visible = True
            self._assistant_panel.refresh_scenes()
            self._assistant_panel.setVisible(True)
        self._assistant_panel._send_preset(preset)

    def _menu_generate(self) -> None:
        if self._assistant_panel.isVisible():
            self._assistant_panel._send_custom()

    def _open_settings(self) -> None:
        dlg = SettingsDialog(
            on_theme_changed=self._switch_theme,
            parent=self,
        )
        dlg.exec()

    def _show_about(self) -> None:
        QMessageBox.about(
            self,
            "About Logosforge",
            "Logosforge\n\nA story planning and writing application.",
        )

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
        self._cached_scenes_view = None
        self._mark_clean()
        recent_projects.add(path)
        self._refresh_recent_menu()
        get_settings().set("last_project_path", str(Path(path).resolve()))

        self._reset_content("Project loaded. Select a section from the sidebar.")

    def load_file_quiet(self, path: str) -> bool:
        """Load a project file without showing dialogs on failure."""
        if not os.path.isfile(path):
            return False
        try:
            with open(path, "r", encoding="utf-8") as f:
                raw = f.read()
        except OSError:
            return False
        data, _ = validate_import_data(raw)
        if data is None:
            return False
        self._project_id = import_json(self._db, data)
        self._current_file = path
        self._cached_scenes_view = None
        self._mark_clean()
        recent_projects.add(path)
        self._refresh_recent_menu()
        self._update_title()
        return True

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
        get_settings().set("last_project_path", str(Path(path).resolve()))
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
        if active:
            self._sidebar.setVisible(False)
            self._assistant_panel.setVisible(False)
        else:
            self._sidebar.setVisible(True)
            self._layout_tier = None
            self._apply_layout_for_width(self.width())
        central = self.centralWidget()
        if central:
            central.layout().invalidate()
            central.update()

    def _mark_clean(self) -> None:
        self._dirty = False
        self._update_title()

    # -- Close event ---------------------------------------------------------

    def closeEvent(self, event: QCloseEvent) -> None:
        self._assistant_panel.save_settings()
        if self._dirty and not self._current_file:
            answer = QMessageBox.warning(
                self,
                "Unsaved Project",
                "Your project has unsaved changes.\n\n"
                "Do you want to save before closing?",
                QMessageBox.StandardButton.Save
                | QMessageBox.StandardButton.Discard
                | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Save,
            )
            if answer == QMessageBox.StandardButton.Save:
                self._on_save_as()
                if self._dirty:
                    event.ignore()
                    return
            elif answer == QMessageBox.StandardButton.Cancel:
                event.ignore()
                return
        elif self._dirty and self._current_file:
            self._auto_save()
        event.accept()

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
        get_settings().set("appearance", name)
