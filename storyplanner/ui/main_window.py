"""Main window with a sidebar and content area."""

import os
from pathlib import Path

from PySide6.QtCore import QEasingCurve, QPropertyAnimation, Qt, QUrl, QVariantAnimation, Signal
from PySide6.QtGui import QAction, QCloseEvent, QColor, QDesktopServices, QIcon, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
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
from storyplanner.autosave import AutosaveManager
from storyplanner.cloud_storage import (
    LockInfo,
    acquire_lock,
    atomic_write_text,
    classify_path,
    current_lock_info,
    release_lock,
    write_conflict_copy,
)
from storyplanner.db import Database
from storyplanner.settings import get_manager as get_settings
from storyplanner.version_manager import VersionManager
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
from storyplanner.psyke_command_registry import CommandContext, CommandRegistry
from storyplanner.psyke_command_validator import ValidationStatus, validate_command
from storyplanner.psyke_system_commands import SystemCommandHandlers
from storyplanner.ui.assistant_view import AssistantPanel
from storyplanner.ui.chat_view import ChatView
from storyplanner.ui.stages_view import StagesView
from storyplanner.ui.settings_dialog import SettingsDialog
from storyplanner.ui.act_analysis_view import ActAnalysisView
from storyplanner.ui.beat_analysis_view import BeatAnalysisView
from storyplanner.ui.character_arc_view import CharacterArcView
from storyplanner.ui.dashboard_view import DashboardView
from storyplanner.ui.focus_graph_view import FocusGraphView
from storyplanner.ui.story_health_view import StoryHealthView
from storyplanner.ui.character_balance_view import CharacterBalanceView
from storyplanner.ui.pacing_insights_view import PacingInsightsView
from storyplanner.ui.mode_suggestions_view import ModeSuggestionsView
from storyplanner.ui.graph_view import GraphView
from storyplanner.ui.notes_view import NotesView
from storyplanner.ui.plan_view import PlanView
from storyplanner.ui.plugins_view import PluginsView
from storyplanner.ui.psyke_console import PsykeConsole
from storyplanner.ui.psyke_view import PsykeView
from storyplanner.ui.projects_view import ProjectsView
from storyplanner.ui.scenes_view import ScenesView
from storyplanner.ui.multi_plot_view import MultiPlotView
from storyplanner.ui.narrative_dashboard_view import NarrativeDashboardView
from storyplanner.ui.structure_view import StructureView
from storyplanner.ui.tag_analysis_view import TagAnalysisView
from storyplanner.ui.timeline_view import TimelineView
from storyplanner.ui.welcome_view import WelcomeView
from storyplanner.ui.writing_core_view import WritingCoreView


_ICON_SLOT_WIDTH = 48


# Display labels can differ from the internal section *key*. The key (used by
# nav handlers, highlight, the assistant section logic, and tests via
# ``sidebar_buttons[key]``) stays stable; only the visible text changes. This
# lets us rename "Plot" → "Canvas Plot" with zero behavioural risk.
SECTION_DISPLAY_NAMES: dict[str, str] = {
    "Plot": "Canvas Plot",
}


def _display_name(key: str) -> str:
    return SECTION_DISPLAY_NAMES.get(key, key)


class _SidebarButton(QPushButton):
    """Sidebar button with fixed icon slot and collapsible label."""

    def __init__(
        self, icon_text: str, label: str,
        parent: QWidget | None = None, indent: bool = False,
        icon_color: str = "",
    ) -> None:
        super().__init__(parent)
        self._icon_text = icon_text
        self._label_text = label
        self._icon_color = icon_color or "#9aa4b2"
        self._collapsed = False
        self._indent = indent
        self.setCheckable(True)
        self.setFlat(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setObjectName("sidebarBtn")
        self._render_icon()
        self._update_text()

        self._hover_blend = 0.0
        self._hover_anim = QVariantAnimation(self)
        self._hover_anim.setDuration(120)
        self._hover_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._hover_anim.valueChanged.connect(self._on_hover_tick)
        self.toggled.connect(self._on_toggled)

    def enterEvent(self, event) -> None:
        if not self.isChecked():
            bg = QColor(theme.get('BG_HOVER'))
            self.setStyleSheet(
                f"background-color: rgba({bg.red()},{bg.green()},{bg.blue()},0);"
                f" color: {theme.get('TEXT_SECONDARY')};"
            )
        self._animate_hover(1.0)
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self._animate_hover(0.0)
        super().leaveEvent(event)

    def _animate_hover(self, target: float) -> None:
        self._hover_anim.stop()
        self._hover_anim.setStartValue(self._hover_blend)
        self._hover_anim.setEndValue(target)
        self._hover_anim.start()

    def _on_hover_tick(self, value: float) -> None:
        self._hover_blend = value
        if self.isChecked():
            return
        if value < 0.01:
            if self.styleSheet():
                self.setStyleSheet("")
            return
        bg = QColor(theme.get('BG_HOVER'))
        ts = QColor(theme.get('TEXT_SECONDARY'))
        tp = QColor(theme.get('TEXT_PRIMARY'))
        r = int(ts.red() + (tp.red() - ts.red()) * value)
        g = int(ts.green() + (tp.green() - ts.green()) * value)
        b = int(ts.blue() + (tp.blue() - ts.blue()) * value)
        self.setStyleSheet(
            f"background-color: rgba({bg.red()},{bg.green()},{bg.blue()},{int(value * 255)});"
            f" color: rgb({r},{g},{b});"
        )

    def _on_toggled(self, checked: bool) -> None:
        self._hover_anim.stop()
        self._hover_blend = 0.0
        if self.styleSheet():
            self.setStyleSheet("")
        if not checked and self.underMouse():
            self._animate_hover(1.0)

    def set_collapsed(self, collapsed: bool) -> None:
        self._collapsed = collapsed
        self._render_icon()
        self._update_text()

    def _render_icon(self) -> None:
        """Render the glyph into a flat, per-section coloured QIcon.

        Group children get extra left space baked into the icon geometry so the
        whole row is clearly indented — and because it lives in the icon (not a
        QSS padding rule) the indent survives the inline hover/checked styles.
        """
        from PySide6.QtCore import QRect, QSize
        from PySide6.QtGui import QFont, QPainter, QPixmap

        slot = 18                      # glyph cell
        pad_left = 16 if (self._indent and not self._collapsed) else 0
        w, h = slot + pad_left, slot
        pm = QPixmap(w, h)
        pm.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pm)
        try:
            font = QFont(self.font())
            font.setPixelSize(14)
            painter.setFont(font)
            painter.setPen(QColor(self._icon_color))
            painter.drawText(
                QRect(pad_left, 0, slot, h),
                Qt.AlignmentFlag.AlignCenter, self._icon_text,
            )
        finally:
            painter.end()
        self.setIcon(QIcon(pm))
        self.setIconSize(QSize(w, h))

    def _update_text(self) -> None:
        # The coloured glyph lives in the QIcon; the button text is just the
        # label (hidden when the sidebar is collapsed to icon-only).
        if self._collapsed:
            self.setText("")
            self.setToolTip(self._label_text)
        else:
            self.setText(self._label_text)
            self.setToolTip("")


class _SidebarGroupHeader(QPushButton):
    """Collapsible group header that toggles visibility of child buttons."""

    expanded_changed = Signal(str, bool)  # group_label, expanded

    def __init__(
        self, label: str, children: list[QPushButton],
        parent: QWidget | None = None,
        expanded: bool = False,
    ) -> None:
        super().__init__(parent)
        self._label_text = label
        self._children = children
        self._expanded = expanded
        self._sidebar_collapsed = False
        self.setFlat(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setObjectName("sidebarGroupHeader")
        self.setStyleSheet(
            "QPushButton#sidebarGroupHeader {"
            " border: none; text-align: left; padding: 6px 8px;"
            " margin: 6px 4px 2px 4px; background-color: transparent;"
            " font-size: 11px; font-weight: bold; }"
            "QPushButton#sidebarGroupHeader:hover { background-color: rgba(255,255,255,0.05); }"
        )
        self.clicked.connect(self._toggle)
        for c in self._children:
            c.setVisible(self._expanded and self._child_available(c))
        self._update_text()

    @staticmethod
    def _child_available(child: QPushButton) -> bool:
        """A child may be marked unavailable (``nav_available`` property False)
        for the current project's writing mode — e.g. the Graphic-Novel-only
        Pages item. Such children stay hidden through expand/collapse."""
        return child.property("nav_available") is not False

    def refresh_child_visibility(self) -> None:
        """Re-apply child visibility honoring expand/collapse + availability."""
        if self._sidebar_collapsed:
            for c in self._children:
                c.setVisible(self._child_available(c))
        else:
            for c in self._children:
                c.setVisible(self._expanded and self._child_available(c))

    @property
    def label(self) -> str:
        return self._label_text

    @property
    def expanded(self) -> bool:
        return self._expanded

    def set_expanded(self, expanded: bool) -> None:
        if self._expanded == expanded:
            return
        self._expanded = expanded
        if not self._sidebar_collapsed:
            for c in self._children:
                c.setVisible(self._expanded and self._child_available(c))
        self._update_text()

    def expand_for_member(self, member_btn: QPushButton) -> bool:
        """Expand if the given child is one of ours. Returns True if expanded."""
        if member_btn in self._children and not self._expanded:
            self.set_expanded(True)
            self.expanded_changed.emit(self._label_text, True)
            return True
        return self._expanded and member_btn in self._children

    def set_sidebar_collapsed(self, collapsed: bool) -> None:
        self._sidebar_collapsed = collapsed
        if collapsed:
            for c in self._children:
                c.setVisible(self._child_available(c))
            self.setVisible(False)
        else:
            self.setVisible(True)
            for c in self._children:
                c.setVisible(self._expanded and self._child_available(c))
        self._update_text()

    def _toggle(self) -> None:
        if self._sidebar_collapsed:
            return
        self.set_expanded(not self._expanded)
        self.expanded_changed.emit(self._label_text, self._expanded)

    def _update_text(self) -> None:
        arrow = "▾" if self._expanded else "▸"
        self.setText(f"{arrow}  {self._label_text}")


class MainWindow(QMainWindow):
    def __init__(self, db: Database, project_id: int) -> None:
        super().__init__()
        self._db = db
        self._project_id = project_id
        self._current_file: str | None = None  # kept for backward compat; use _set_current_file
        self._dirty = False
        self._read_only = False
        self._external_change_warned = False
        self._current_section: str = "Projects"

        self._autosave = AutosaveManager(db, project_id, parent=self)
        self._autosave.status_changed.connect(self._on_autosave_status)
        self._autosave.external_change_detected.connect(self._on_external_change)

        self._versions = VersionManager(db, project_id, parent=self)
        self._versions.start()
        self._cached_scenes_view: ScenesView | None = None
        self._cached_scene_entry_scene: int | None = None
        self._cached_scene_entry_ids: set[int] | None = None
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
        outer_layout = QVBoxLayout(central)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setSpacing(0)

        main_row = QWidget()
        root_layout = QHBoxLayout(main_row)
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
        self._logos_visible = False
        # Single source of truth for the inline Logos layer ON/OFF state.
        self._logos_enabled = bool(get_settings().get("logos_enabled"))
        self._layout_tier: str | None = None
        # Flat monochrome icon set (centralized in ui/sidebar_icons.py). These
        # are text-presentation glyphs, so they inherit the button's theme color
        # (muted gray idle, accent when active) across Dark / Green / Warm.
        from storyplanner.ui.sidebar_icons import SIDEBAR_ICONS, sidebar_icon_color
        self._sidebar_icons = dict(SIDEBAR_ICONS)

        self._toggle_btn = QPushButton("\u00ab")
        self._toggle_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._toggle_btn.clicked.connect(self._toggle_sidebar)
        sidebar_layout.addWidget(self._toggle_btn)

        # Pages is a Graphic-Novel-only surface. The button is always created in
        # a stable layout slot (last Plan member), but its sidebar registration
        # + visibility are toggled per the *current* project's writing mode via
        # _apply_pages_availability() — at startup and on every project switch.
        self._is_graphic_novel = self._project_is_graphic_novel()
        _plan_members = ["Outline", "Scenes", "Timeline", "Plot", "Pages"]

        _SIDEBAR_LAYOUT: list = [
            "Projects", "Dashboard", "Notes", "Manuscript",
            ("group", "Plan", _plan_members),
            ("group", "Structure", ["Structure", "Acts", "Beats", "Arcs"]),
            "Tags", "Graph",
            ("group", "Analytics", ["Health", "Balance", "Pacing", "Narrative"]),
            "Adapt", "PSYKE", "Stages", "Plugins", "Assistant", "Logos", "Chat",
        ]
        self.sidebar_buttons: dict[str, _SidebarButton] = {}
        self._sidebar_groups: list[_SidebarGroupHeader] = []
        # Groups always open collapsed (the previous session's expanded state is
        # intentionally not restored — see _SidebarGroupHeader(expanded=False)).
        for item in _SIDEBAR_LAYOUT:
            if isinstance(item, tuple) and item[0] == "group":
                _, group_label, member_labels = item
                children: list[QPushButton] = []
                for member in member_labels:
                    icon = self._sidebar_icons.get(member, "")
                    btn = _SidebarButton(
                        icon, _display_name(member), indent=True,
                        icon_color=sidebar_icon_color(member),
                    )
                    self.sidebar_buttons[member] = btn
                    children.append(btn)
                # Groups always start collapsed on app open (never restore the
                # previous session's expanded state).
                header = _SidebarGroupHeader(
                    group_label, children, expanded=False,
                )
                header.expanded_changed.connect(self._on_group_expanded_changed)
                sidebar_layout.addWidget(header)
                for btn in children:
                    sidebar_layout.addWidget(btn)
                self._sidebar_groups.append(header)
            else:
                icon = self._sidebar_icons.get(item, "")
                btn = _SidebarButton(icon, _display_name(item),
                                     icon_color=sidebar_icon_color(item))
                sidebar_layout.addWidget(btn)
                self.sidebar_buttons[item] = btn

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
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setChecked(name == theme.current_palette())
            btn.clicked.connect(lambda _, n=name: self._switch_theme(n))
            ab_layout.addWidget(btn)
            self._appearance_btns[name] = btn
        sidebar_layout.addWidget(self._appearance_bar)

        # -- Import / Export / Settings ---------------------------------------
        self._import_btn = _SidebarButton(self._sidebar_icons["Import"], "Import",
                                          icon_color=sidebar_icon_color("Import"))
        sidebar_layout.addWidget(self._import_btn)
        self._import_btn.clicked.connect(self._on_import)

        self._export_btn = _SidebarButton(self._sidebar_icons["Export"], "Export",
                                          icon_color=sidebar_icon_color("Export"))
        sidebar_layout.addWidget(self._export_btn)
        self._export_btn.clicked.connect(self._on_export)

        self._settings_btn = _SidebarButton(self._sidebar_icons["Settings"], "Settings",
                                            icon_color=sidebar_icon_color("Settings"))
        sidebar_layout.addWidget(self._settings_btn)
        self._settings_btn.clicked.connect(self._open_settings)

        # -- Connect navigation buttons (checkable + active tracking) ----------
        self._nav_labels = [
            "Projects", "Dashboard", "Notes",
            "Outline", "Scenes", "Manuscript", "Timeline", "Plot",
            "Structure", "Acts", "Beats", "Tags", "Graph", "Arcs",
            "Health", "Balance", "Pacing", "Adapt", "Narrative", "PSYKE", "Plugins",
            "Stages", "Chat",
        ]
        # "Pages" is added/removed by _apply_pages_availability() for the current
        # project's writing mode (called below + on project switch).
        self._nav_section_handlers = {
            "Projects": self._show_projects,
            "Dashboard": self._show_dashboard,
            "Notes": self._show_notes,
            "Outline": self._show_plan,
            "Scenes": self._show_scenes,
            "Manuscript": self._show_manuscript,
            "Timeline": self._show_timeline,
            "Plot": self._show_plot,
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
            "PSYKE": self._show_psyke,
            "Plugins": self._show_plugins,
            "Chat": self._show_chat,
            "Stages": self._show_stages,
            # "Pages" handler registered by _apply_pages_availability().
        }
        for label in self._nav_labels:
            btn = self.sidebar_buttons[label]
            btn.setCheckable(True)
            handler = self._nav_section_handlers[label]
            btn.clicked.connect(
                lambda _, l=label, h=handler: (
                    self._set_active_section(l), h()
                )
            )

        self.sidebar_buttons["Assistant"].clicked.connect(
            self._toggle_assistant
        )

        # Logos is NOT a navigation section — it is an ON/OFF toggle for the
        # inline contextual Logos layer. It stays out of _nav_labels so it never
        # steals the active-section highlight; its checked state simply reflects
        # whether the inline layer is enabled.
        logos_btn = self.sidebar_buttons.get("Logos")
        if logos_btn is not None:
            logos_btn.setCheckable(True)
            logos_btn.clicked.connect(self._toggle_logos_layer)

        # The Pages button widget always exists (last Plan member) so its click
        # is wired exactly once here; registration/visibility are toggled per
        # writing mode by _apply_pages_availability(). It is kept out of the
        # nav-wiring loop above to avoid a double connection.
        self._pages_btn = self.sidebar_buttons["Pages"]
        self._pages_btn.setCheckable(True)
        self._pages_btn.clicked.connect(
            lambda _: (self._set_active_section("Pages"), self._show_gn_pages())
        )
        self._apply_pages_availability()

        # -- Right content area ----------------------------------------------
        self.content_area = self._build_initial_content()

        # -- Assistant side panel --------------------------------------------
        self._assistant_panel = AssistantPanel(
            self._db,
            self._project_id,
            on_data_changed=self._on_data_changed,
            on_open_scene=self._open_scene_in_editor,
            get_active_scene_id=self._detect_active_scene_id,
            get_selected_text=self._detect_selected_text,
            get_active_editor=self._detect_active_editor,
        )
        self._assistant_panel.panel_closed.connect(self._hide_assistant)
        self._assistant_panel.overlay_toggled.connect(self._on_overlay_toggled)
        self._assistant_panel.setVisible(False)

        # Single reusable dock that owns content + assistant sizing/collapse/pin
        # so every section behaves identically.
        from storyplanner.ui.assistant_dock import AssistantDock
        self._assistant_dock = AssistantDock(self._assistant_panel)
        self._assistant_dock.set_content(self.content_area)
        self._assistant_dock.collapsed_changed.connect(
            lambda c: get_settings().set("assistant_collapsed", bool(c))
        )
        self._assistant_dock.pinned_changed.connect(
            lambda p: get_settings().set("assistant_pinned", bool(p))
        )

        # Subscribe to the project event bus so any write — Assistant
        # direct edits or Connector-mediated actions — refreshes the
        # active view without each path needing its own callback.
        from storyplanner.project_events import get_event_bus
        get_event_bus().project_data_changed.connect(self._on_data_changed)
        self._assistant_panel.setSizePolicy(
            QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred,
        )
        self._assistant_panel.refresh_style()

        # -- Assemble --------------------------------------------------------
        self._sidebar = sidebar
        self._root_layout = root_layout
        root_layout.addWidget(sidebar, stretch=0)
        root_layout.addWidget(self._assistant_dock, stretch=1)

        outer_layout.addWidget(main_row, stretch=1)

        # -- Logos inline assistant (Phase 0) --------------------------------
        # A separate, non-intrusive inline layer that reuses the shared
        # Assistant backend. It does NOT touch AssistantPanel/AssistantDock.
        from storyplanner.logos.controller import LogosController
        from storyplanner.ui.logos.logos_toolbar import LogosToolbar
        self._logos_controller = LogosController(self._db)
        self._logos_toolbar = LogosToolbar(
            self._logos_controller, self._build_logos_context,
            on_request_apply=self._logos_request_apply,
        )
        self._logos_toolbar.setVisible(False)
        outer_layout.addWidget(self._logos_toolbar, stretch=0)

        # -- Logos proactive suggestions (Phase 4) ---------------------------
        # Rule-based, non-intrusive. Hidden until a scan produces suggestions.
        from storyplanner.logos.proactive import ProactiveEngine
        from storyplanner.ui.logos.logos_suggestions import LogosSuggestionBar
        self._logos_engine = ProactiveEngine(self._db, self._project_id)
        self._logos_suggestions = LogosSuggestionBar()
        self._logos_suggestions.run_action.connect(self._on_logos_suggestion_action)
        self._logos_suggestions.suppress.connect(self._on_logos_suggestion_suppress)
        self._logos_suggestions.setVisible(False)
        outer_layout.addWidget(self._logos_suggestions, stretch=0)

        # -- Logos PSYKE diagnostics (Phase 5) -------------------------------
        # Deeper, PSYKE-aware diagnostics. Drawer hidden until toggled; shares
        # the proactive engine's suppression so dismissals are consistent.
        from storyplanner.logos.diagnostics import DiagnosticsEngine
        from storyplanner.ui.logos.logos_diagnostics import LogosDiagnosticsDrawer
        self._diagnostics_engine = DiagnosticsEngine(
            self._db, self._project_id,
            suppression=self._logos_engine.suppression,
        )
        self._diagnostics_visible = False
        self._diagnostics_drawer = LogosDiagnosticsDrawer()
        self._diagnostics_drawer.run_action.connect(self._on_diagnostic_action)
        self._diagnostics_drawer.suppress.connect(self._on_diagnostic_suppress)
        self._diagnostics_drawer.open_target.connect(self._on_diagnostic_open_target)
        self._diagnostics_drawer.rescan_requested.connect(self._scan_diagnostics)
        self._diagnostics_drawer.project_scan_requested.connect(self._scan_diagnostics_project)
        self._diagnostics_drawer.setVisible(False)
        outer_layout.addWidget(self._diagnostics_drawer, stretch=0)

        # -- Narrative Health (Phase 6) --------------------------------------
        from storyplanner.logos.health import HealthEngine
        from storyplanner.ui.logos.logos_health import LogosHealthDrawer
        self._health_engine = HealthEngine(
            self._db, self._project_id,
            suppression=self._logos_engine.suppression,
        )
        self._health_report = None
        self._health_visible = False
        self._health_drawer = LogosHealthDrawer()
        self._health_drawer.set_show_unknown(bool(get_settings().get("health_show_unknown")))
        self._health_drawer.run_action.connect(self._on_health_action)
        self._health_drawer.open_target.connect(self._on_health_open_target)
        self._health_drawer.refresh_requested.connect(self._refresh_health)
        self._health_drawer.export_requested.connect(self._export_health)
        self._health_drawer.setVisible(False)
        outer_layout.addWidget(self._health_drawer, stretch=0)

        # -- Strategy router (Phase 7) ---------------------------------------
        # Deterministic medium-aware reasoning router. Does NOT touch the
        # Assistant; it informs Logos action ordering and the health indicator.
        from storyplanner.logos.strategy import StrategyRouter
        self._strategy_router = StrategyRouter(self._db, self._project_id)

        # Apply the persisted Logos ON/OFF state to the inline layer + sidebar
        # button now that all Logos surfaces exist.
        self._apply_logos_enabled(initial=True)

        # -- PSYKE Console (global bottom bar) --------------------------------
        console_row = QWidget()
        console_row.setFixedHeight(28)
        console_layout = QHBoxLayout(console_row)
        console_layout.setContentsMargins(0, 2, 0, 2)
        console_layout.setSpacing(0)

        self._psyke_console = PsykeConsole(self._db, self._project_id)
        self._psyke_console.entry_selected.connect(self._on_psyke_entry_selected)
        self._psyke_console.entry_open_requested.connect(self._open_psyke_entry)
        self._psyke_console.command_submitted.connect(self._on_console_command)

        self._save_status_label = QLabel("")
        self._save_status_label.setObjectName("saveStatusLabel")
        self._save_status_label.setStyleSheet(
            f"color: {theme.TEXT_MUTED}; font-size: 10px; padding: 0 8px;"
        )
        console_layout.addWidget(self._save_status_label)
        self._storage_label = QLabel("")
        self._storage_label.setObjectName("storageLabel")
        self._storage_label.setStyleSheet(
            f"color: {theme.TEXT_MUTED}; font-size: 10px; padding: 0 8px;"
        )
        self._storage_label.setToolTip(
            "Where this project lives. Cloud-synced folders (Dropbox, "
            "Google Drive, iCloud, OneDrive) are treated as ordinary "
            "synced filesystem paths."
        )
        console_layout.addWidget(self._storage_label)
        console_layout.addStretch(1)
        console_layout.addWidget(self._psyke_console, stretch=0)
        console_layout.addStretch(1)

        outer_layout.addWidget(console_row, stretch=0)

        self._setup_system_commands()

        self.setCentralWidget(central)

        # -- Global "/" shortcut to focus PSYKE console ----------------------
        app = QApplication.instance()
        if app:
            app.installEventFilter(self)

        # -- Restore persisted state -----------------------------------------
        mgr = get_settings()
        if mgr.get("sidebar_collapsed"):
            self._set_sidebar_collapsed(True, animate=False)
        # Restore pin/collapse before visibility so the first layout is right.
        self._assistant_dock.set_pinned(bool(mgr.get("assistant_pinned")))
        if mgr.get("assistant_open"):
            self._assistant_user_visible = True
            self._assistant_panel.refresh_scenes()
            self._assistant_dock.set_panel_user_visible(True)
            if mgr.get("assistant_collapsed"):
                self._assistant_dock.set_collapsed(True)

    def _set_content(self, widget: QWidget) -> None:
        """Replace the content area inside the assistant dock with a new view."""
        self._psyke_console.clear_previous_focus()
        old = self._assistant_dock.set_content(widget)
        if old is not None and old is not self._cached_scenes_view:
            old.deleteLater()
        elif old is self._cached_scenes_view:
            old.hide()
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
                on_new_project=self._on_new_project,
            )
        )

    def show_initial_section(self) -> None:
        """Land the app on the Projects section at startup.

        Called once by the application factory after any session restore.
        Projects — not Dashboard — is the default first view; Dashboard is
        only shown when the user (or an explicit open) selects it. Building
        a fresh ProjectsView here guarantees the recent-projects list
        reflects the current state, including a just-restored session.
        """
        self._set_active_section("Projects")
        self._show_projects()

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
            self._show_psyke()
        elif name == "timeline":
            self._show_timeline()

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

    def _show_plan(self) -> None:
        self._set_content(
            PlanView(
                self._db,
                self._project_id,
                on_data_changed=self._on_data_changed,
                on_open_scene=self._open_scene_in_editor,
                on_logos_action=self._run_logos_outline,
            )
        )

    def _show_manuscript(self) -> None:
        self._set_content(
            WritingCoreView(
                self._db,
                self._project_id,
                on_data_changed=self._on_data_changed,
                on_focus_mode_changed=self._on_focus_mode_changed,
                on_open_psyke_entry=self._open_psyke_entry,
                on_content_saved=self._on_scene_content_saved,
            )
        )

    def _show_timeline(self) -> None:
        preferences.set_flag("has_seen_timeline_hint", True)
        from storyplanner.ui.plot_timeline_view import PlotTimelineView
        self._set_content(
            PlotTimelineView(
                self._db,
                self._project_id,
                on_scene_selected=self._open_scene_in_editor,
                on_data_changed=self._on_data_changed,
            )
        )

    def _show_plot(self) -> None:
        from storyplanner.ui.canvas_plot_view import CanvasPlotView
        self._set_content(
            CanvasPlotView(
                self._db,
                self._project_id,
                on_data_changed=self._on_data_changed,
            )
        )

    def _show_structure(self) -> None:
        self._set_content(StructureView(self._db, self._project_id))

    def _show_acts(self) -> None:
        self._set_content(ActAnalysisView(self._db, self._project_id))

    def _show_beats(self) -> None:
        self._set_content(BeatAnalysisView(self._db, self._project_id))

    def _show_tags(self) -> None:
        self._set_content(TagAnalysisView(self._db, self._project_id))

    def _show_graph(self) -> None:
        view = FocusGraphView(
            self._db, self._project_id,
            on_node_selected=self._on_link_navigated,
            on_send_to_assistant=self._send_graph_analysis_to_assistant,
        )
        # Restore last-used filter / mode / flow state from settings.json.
        view.restore_persisted_state()
        self._set_content(view)

    def _send_graph_analysis_to_assistant(self, text: str) -> None:
        """Drop a graph-analysis block into the Assistant's prompt and reveal the panel."""
        if not text:
            return
        try:
            existing = self._assistant_panel._prompt_input.toPlainText().strip()
            combined = f"{existing}\n\n{text}" if existing else text
            self._assistant_panel._prompt_input.setPlainText(combined)
        except Exception:
            return
        if not self._assistant_dock.is_panel_user_visible():
            self._assistant_user_visible = True
            self._assistant_panel.refresh_scenes()
            self._assistant_dock.set_panel_user_visible(True)
            if self._assistant_overlay:
                self._assistant_panel.setVisible(True)

    def _show_arcs(self) -> None:
        self._set_content(
            CharacterArcView(
                self._db, self._project_id,
                on_scene_selected=self._open_scene_in_editor,
            )
        )

    def _toggle_assistant(self) -> None:
        self._assistant_user_visible = not self._assistant_dock.is_panel_user_visible()
        if self._assistant_user_visible:
            self._assistant_panel.refresh_scenes()
            if self._assistant_overlay:
                self._position_overlay_assistant()
        self._assistant_dock.set_panel_user_visible(self._assistant_user_visible)
        if self._assistant_overlay:
            self._assistant_panel.setVisible(self._assistant_user_visible)
        get_settings().set("assistant_open", self._assistant_user_visible)

    def _hide_assistant(self) -> None:
        self._assistant_user_visible = False
        self._assistant_dock.set_panel_user_visible(False)
        if self._assistant_overlay:
            self._assistant_panel.setVisible(False)
        get_settings().set("assistant_open", False)

    def _on_overlay_toggled(self, overlay: bool) -> None:
        self._assistant_overlay = overlay
        # Hand the panel to / back from the dock so the content reflows.
        self._assistant_dock.set_floating(overlay)

        if overlay:
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
            # set_floating(False) re-added the panel to the dock; let the dock
            # re-apply its responsive width.
            self._assistant_dock.apply_responsive()
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
        for group in self._sidebar_groups:
            group.set_sidebar_collapsed(True)
        self._import_btn.set_collapsed(True)
        self._export_btn.set_collapsed(True)
        self._settings_btn.set_collapsed(True)
        self._appearance_label.setVisible(False)
        self._appearance_bar.setVisible(False)

    def _apply_expanded_labels(self) -> None:
        self._toggle_btn.setText("\u00ab")
        self._toggle_btn.setToolTip("")
        for btn in self.sidebar_buttons.values():
            btn.set_collapsed(False)
        for group in self._sidebar_groups:
            group.set_sidebar_collapsed(False)
        self._import_btn.set_collapsed(False)
        self._export_btn.set_collapsed(False)
        self._settings_btn.set_collapsed(False)
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
        self._ensure_active_visible(name)
        self._assistant_panel.set_active_section_name(name)
        # Keep the (optional) Logos inline toolbar in sync with the section.
        logos = getattr(self, "_logos_toolbar", None)
        if logos is not None and self._logos_visible:
            logos.set_section(name)
        # Proactive suggestions are section-scoped — rescan on section change.
        self._scan_logos_suggestions()
        self._scan_diagnostics()

    def _ensure_active_visible(self, name: str) -> None:
        """Expand the parent group if the active section is collapsed inside it."""
        btn = self.sidebar_buttons.get(name)
        if btn is None:
            return
        for group in self._sidebar_groups:
            group.expand_for_member(btn)

    def _on_group_expanded_changed(self, label: str, expanded: bool) -> None:
        state = get_settings().get("sidebar_groups_expanded") or {}
        if not isinstance(state, dict):
            state = {}
        state = dict(state)
        state[label] = bool(expanded)
        get_settings().set("sidebar_groups_expanded", state)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._psyke_console.reposition()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._apply_layout_for_width(event.size().width())
        if self._assistant_overlay:
            self._position_overlay_assistant()
        self._psyke_console.reposition()

    def _apply_layout_for_width(self, w: int) -> None:
        # Responsive sizing + minimum content-width protection is centralised in
        # the AssistantDock, which uses its own (content-area) width rather than
        # the whole-window width. Overlay mode is handled separately.
        if self._assistant_overlay:
            return
        self._assistant_dock.apply_responsive()

    def _setup_system_commands(self) -> None:
        self._command_registry = CommandRegistry()
        self._system_command_handlers = SystemCommandHandlers(
            self._db,
            self._project_id,
            open_scene=self._open_scene_in_editor,
            open_psyke_entry=self._open_psyke_entry,
            get_active_scene_id=self._detect_active_scene_id,
            get_selected_text=self._detect_selected_text,
            run_ai_action=self._assistant_panel.run_action,
            on_data_changed=self._on_data_changed,
        )
        self._system_command_handlers.register_all(self._command_registry)
        self._psyke_console.set_registry(self._command_registry)
        self._psyke_console.set_scene_context(self._get_scene_entry_ids)

    def _on_console_command(self, command: str, args: list) -> None:
        result = validate_command(command, args, registry=self._command_registry)

        if result.status == ValidationStatus.ERROR:
            QMessageBox.warning(self, "Command Error", result.error)
            return

        if result.status == ValidationStatus.CONFIRM:
            reply = QMessageBox.question(
                self,
                "Confirm Action",
                result.confirm_message,
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                return

        entry = self._command_registry.resolve(command)
        if entry is None:
            return
        ctx = CommandContext(command=command, args=args)
        handler_result = entry.handler(ctx)
        if isinstance(handler_result, dict):
            if not handler_result.get("ok", True):
                QMessageBox.warning(
                    self, "Command Failed",
                    handler_result.get("error", "Unknown error"),
                )
            elif handler_result.get("show_message") and handler_result.get("message"):
                QMessageBox.information(self, "Logos", handler_result["message"])

    def _on_psyke_entry_selected(self, entry_id: int, name: str) -> None:
        editor = self._detect_active_editor()
        if editor:
            cursor = editor.textCursor()
            cursor.insertText(name)
            editor.setTextCursor(cursor)
            editor.setFocus(Qt.FocusReason.OtherFocusReason)
        else:
            self._open_psyke_entry(entry_id)

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

    def _show_chat(self) -> None:
        self._set_content(
            ChatView(
                self._db,
                self._project_id,
                on_data_changed=self._on_data_changed,
                get_active_scene_id=self._detect_active_scene_id,
            )
        )

    def _show_stages(self) -> None:
        self._set_content(
            StagesView(
                self._db,
                self._project_id,
                on_data_changed=self._on_data_changed,
                get_active_scene_id=self._detect_active_scene_id,
            )
        )

    def _project_is_graphic_novel(self) -> bool:
        """True if the *current* project's writing mode is graphic_novel."""
        try:
            from storyplanner.project_compat import get_project_narrative_engine
            project = self._db.get_project_by_id(self._project_id)
            return get_project_narrative_engine(project) == "graphic_novel"
        except Exception:
            return False

    def _apply_pages_availability(self) -> None:
        """Show/register the Graphic-Novel-only Pages item for the *current*
        project's writing mode. Idempotent; called at startup and on every
        project switch so the sidebar never shows a stale (or missing) Pages
        item after switching projects."""
        is_gn = self._project_is_graphic_novel()
        self._is_graphic_novel = is_gn
        btn = getattr(self, "_pages_btn", None)
        if btn is None:
            return
        btn.setProperty("nav_available", is_gn)
        if is_gn:
            self.sidebar_buttons["Pages"] = btn
            self._nav_section_handlers["Pages"] = self._show_gn_pages
            if "Pages" not in self._nav_labels:
                self._nav_labels.append("Pages")
        else:
            self.sidebar_buttons.pop("Pages", None)
            self._nav_section_handlers.pop("Pages", None)
            if "Pages" in self._nav_labels:
                self._nav_labels.remove("Pages")
            # If we were viewing Pages in the previous (GN) project, fall back to
            # the Dashboard so a non-GN project never lands on the Pages view.
            if getattr(self, "_current_section", None) == "Pages":
                self._current_section = "Dashboard"
        # Re-apply Plan-group child visibility honoring availability.
        plan = next((g for g in getattr(self, "_sidebar_groups", [])
                     if g.label == "Plan"), None)
        if plan is not None:
            plan.refresh_child_visibility()

    def _show_gn_pages(self) -> None:
        # Defensive: Pages is a Graphic-Novel-only surface. If the current
        # project is not a graphic novel, never mount the Pages view — route to
        # the Dashboard instead (the button is normally hidden for non-GN).
        if not self._project_is_graphic_novel():
            self._show_dashboard()
            return
        from storyplanner.ui.graphic_novel_pages_view import GraphicNovelPagesView
        self._set_content(
            GraphicNovelPagesView(
                self._db,
                self._project_id,
                on_data_changed=self._on_data_changed,
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

    def _on_link_navigated(self, entity_type: str, entity_id: int) -> None:
        if entity_type in ("Character", "Place", "PsykeEntry"):
            self._set_active_section("PSYKE")
            self._show_psyke()
            psyke_view = self.content_area
            if entity_type == "PsykeEntry":
                psyke_view.select_entry(entity_id)
            else:
                name = None
                if entity_type == "Character":
                    c = self._db.get_character_by_id(entity_id)
                    name = c.name if c else None
                elif entity_type == "Place":
                    p = self._db.get_place_by_id(entity_id)
                    name = p.name if p else None
                if name:
                    for e in self._db.get_all_psyke_entries(self._project_id):
                        if e.name.lower() == name.lower():
                            psyke_view.select_entry(e.id)
                            break
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

    def _get_scene_entry_ids(self) -> set[int] | None:
        scene_id = self._detect_active_scene_id()
        if scene_id is None:
            return None
        if (
            hasattr(self, "_cached_scene_entry_ids")
            and self._cached_scene_entry_scene == scene_id
        ):
            return self._cached_scene_entry_ids

        char_ids = set(self._db.get_scene_character_ids(scene_id))
        place_ids = set(self._db.get_scene_place_ids(scene_id))

        linked_names: set[str] = set()
        for cid in char_ids:
            c = self._db.get_character_by_id(cid)
            if c:
                linked_names.add(c.name.lower())
        for pid in place_ids:
            p = self._db.get_place_by_id(pid)
            if p:
                linked_names.add(p.name.lower())

        entry_ids: set[int] = set()
        if linked_names:
            for entry in self._db.get_all_psyke_entries(self._project_id):
                if entry.name.lower() in linked_names:
                    entry_ids.add(entry.id)

        result = entry_ids if entry_ids else None
        self._cached_scene_entry_scene = scene_id
        self._cached_scene_entry_ids = result
        return result

    def _detect_active_editor(self):
        from storyplanner.ui.writing_core_view import WritingCoreView
        view = self.content_area
        if isinstance(view, WritingCoreView):
            editor = getattr(view, "_active_editor", None)
            if editor and hasattr(editor, "textCursor"):
                return editor
        if self._cached_scenes_view is not None and self.content_area is self._cached_scenes_view:
            for attr in ("_active_editor", "_content_input"):
                editor = getattr(self._cached_scenes_view, attr, None)
                if editor and hasattr(editor, "textCursor"):
                    return editor
        return None

    def _detect_selected_text(self) -> str:
        editor = self._detect_active_editor()
        if editor:
            return editor.textCursor().selectedText().replace(" ", "\n")
        return ""

    # -- Logos inline assistant (Phase 0) ------------------------------------

    def _build_logos_context(self):
        """Capture a lightweight LogosContext from the current UI state.

        Reuses the existing detection helpers and reads only safe, primitive
        values — no ORM rows, no widgets, no secrets.
        """
        from storyplanner.logos.context import build_logos_context

        section = self._current_section or ""
        scene_id = self._detect_active_scene_id()
        selected = self._detect_selected_text()
        excerpt = ""
        editor = self._detect_active_editor()
        if editor is not None:
            try:
                excerpt = editor.toPlainText()[:600]
            except Exception:
                excerpt = ""
        outline_template = ""
        block_type = "prose" if section == "Manuscript" else ""
        # Phase 3 section-specific selection, read non-invasively from the
        # live view (existing attributes only — no new view callbacks).
        extra: dict = {}
        view = self.content_area
        try:
            # Manuscript: carry the current screenplay element type into context
            # (only when it's a screenplay element, so Novel stays "prose").
            if section == "Manuscript":
                getter = getattr(view, "current_element_type", None)
                if callable(getter):
                    from storyplanner.screenplay import is_valid_element
                    et = getter() or ""
                    if is_valid_element(et):
                        block_type = et
            from storyplanner.ui.plan_view import PlanView
            if isinstance(view, PlanView):
                block_type = "outline_node"
                outline_template = view._template_combo.currentData() or ""
            elif section == "PSYKE":
                entry_id = getattr(view, "_selected_id", None)
                if entry_id is not None:
                    extra["selected_psyke_entry_id"] = entry_id
                    extra["current_psyke_entry_id"] = entry_id
                    block_type = "psyke_entry"
            elif section == "Timeline":
                tid = getattr(view, "_selected_scene_id", None)
                if tid is not None:
                    extra["current_timeline_event_id"] = tid
                    scene_id = scene_id or tid
                block_type = "timeline_event"
            elif section == "Plot":
                block_type = "plot_block"
                filters = getattr(view, "_filters", None)
                pl = getattr(filters, "plotline", "") if filters else ""
                if pl:
                    extra["current_plot_block_id"] = pl
            elif section == "Graph":
                block_type = "graph_node"
                extra.update(self._graph_logos_extra(view))
        except Exception:
            pass

        return build_logos_context(
            self._db, self._project_id,
            section_name=section, current_scene_id=scene_id,
            selected_text=selected, cursor_text_excerpt=excerpt,
            active_block_type=block_type, outline_template=outline_template,
            **extra,
        )

    def _graph_logos_extra(self, view) -> dict:
        """Capture the focused graph node + neighbours into context kwargs.

        Graph node ids look like ``"Character:5"``; PSYKE/scene entities are
        carried as linked ids so an apply can route to the source of truth.
        """
        node_id = getattr(view, "_focus_node", None)
        if not node_id:
            return {}
        out: dict = {"current_graph_node_id": node_id}
        data = getattr(view, "_graph_data", None)
        node = data.nodes.get(node_id) if data else None
        if node is not None:
            out["current_graph_node_type"] = node.etype
            if node.etype == "PSYKE":
                out["linked_psyke_entry_ids"] = [node.entity_id]
                out["current_psyke_entry_id"] = node.entity_id
            elif node.etype == "Scene":
                out["linked_scene_ids"] = [node.entity_id]
                out["current_scene_id"] = node.entity_id
        if data is not None:
            neighbors = sorted(data.adjacency.get(node_id, set()))
            out["current_graph_neighbors"] = neighbors[:20]
        return out

    def _toggle_logos(self) -> None:
        self._logos_visible = not self._logos_visible
        if self._logos_visible:
            self._logos_toolbar.set_section(self._current_section or "")
            self._logos_toolbar.refresh_actions()
        self._logos_toolbar.setVisible(self._logos_visible)

    # -- Inline Logos layer ON/OFF (contextual assistant, not a section) ------

    def _toggle_logos_layer(self) -> None:
        """Left-panel Logos toggle: flip the inline contextual Logos layer.

        Does NOT change the central section — the user stays exactly where they
        are; only the ambient Logos layer (toolbar + contextual suggestions) is
        shown/hidden, scoped to the current section.
        """
        self._logos_enabled = not self._logos_enabled
        try:
            get_settings().set("logos_enabled", self._logos_enabled)
        except Exception:
            pass
        self._apply_logos_enabled()

    def _apply_logos_enabled(self, *, initial: bool = False) -> None:
        """Sync the inline Logos surfaces + sidebar button to ``logos_enabled``."""
        on = bool(getattr(self, "_logos_enabled", False))
        btn = self.sidebar_buttons.get("Logos")
        if btn is not None and btn.isChecked() != on:
            btn.setChecked(on)
        # Inline toolbar tracks the master switch.
        self._logos_visible = on
        toolbar = getattr(self, "_logos_toolbar", None)
        if toolbar is not None:
            if on:
                toolbar.set_section(self._current_section or "")
                toolbar.refresh_actions()
            toolbar.setVisible(on)
        # Contextual suggestions: rescan for the current section when ON,
        # clear + hide when OFF.
        if on:
            self._scan_logos_suggestions()
        else:
            bar = getattr(self, "_logos_suggestions", None)
            if bar is not None:
                bar.set_suggestions([])
                bar.setVisible(False)

    # -- Proactive suggestions (Phase 4) -------------------------------------

    def _scan_logos_suggestions(self) -> None:
        """Run a fast, rule-based proactive scan for the current section.

        Safe to call on section-open / selection-change / data-changed. Never
        calls an LLM, never mutates the DB, never blocks. Hidden when empty.
        """
        engine = getattr(self, "_logos_engine", None)
        bar = getattr(self, "_logos_suggestions", None)
        if engine is None or bar is None:
            return
        # The inline Logos layer must be turned ON (left-panel toggle) for any
        # contextual suggestions to surface.
        if not getattr(self, "_logos_enabled", False):
            bar.set_suggestions([])
            bar.setVisible(False)
            return
        if not engine.config.enabled:
            bar.set_suggestions([])
            bar.setVisible(False)
            return
        section = self._current_section or ""
        try:
            ctx = self._build_logos_context()
            suggestions = engine.scan_section(section, ctx)
        except Exception:
            suggestions = []
        bar.set_suggestions(suggestions)
        bar.setVisible(bool(suggestions))

    def _on_logos_suggestion_action(self, suggestion, action_name: str) -> None:
        """Run the existing Logos action a suggestion points to (preview/confirm)."""
        if not self._logos_visible:
            self._logos_visible = True
            self._logos_toolbar.set_section(self._current_section or "")
            self._logos_toolbar.refresh_actions()
            self._logos_toolbar.setVisible(True)
        ctx = self._build_logos_context()
        self._logos_toolbar.run_action_with_context(ctx, action_name)

    def _on_logos_suggestion_suppress(self, suggestion, kind: str) -> None:
        store = self._logos_engine.suppression
        if kind == "dismiss":
            store.dismiss(suggestion.id)
        elif kind == "snooze":
            store.snooze(suggestion.id)
        elif kind == "hide_type":
            store.hide_type(suggestion.type)
        self._scan_logos_suggestions()

    def _refresh_logos_suggestions_command(self) -> None:
        """Manual 'Refresh Logos Suggestions' command."""
        self._scan_logos_suggestions()

    # -- PSYKE narrative diagnostics (Phase 5) -------------------------------

    def _toggle_diagnostics(self) -> None:
        self._diagnostics_visible = not self._diagnostics_visible
        if self._diagnostics_visible:
            self._scan_diagnostics()
        self._diagnostics_drawer.setVisible(self._diagnostics_visible)

    def _scan_diagnostics(self) -> None:
        """Current-section diagnostics scan (fast, rule-based, no LLM/mutation)."""
        engine = getattr(self, "_diagnostics_engine", None)
        drawer = getattr(self, "_diagnostics_drawer", None)
        if engine is None or drawer is None or not self._diagnostics_visible:
            return
        section = self._current_section or ""
        try:
            diags = engine.scan_section(section) if section else engine.scan_project()
        except Exception:
            diags = []
        drawer.set_diagnostics(diags)

    def _scan_diagnostics_project(self) -> None:
        """Manual project-wide diagnostics scan."""
        engine = getattr(self, "_diagnostics_engine", None)
        drawer = getattr(self, "_diagnostics_drawer", None)
        if engine is None or drawer is None:
            return
        self._diagnostics_visible = True
        self._diagnostics_drawer.setVisible(True)
        try:
            diags = engine.scan_project()
        except Exception:
            diags = []
        drawer.set_diagnostics(diags)

    def _on_diagnostic_action(self, diagnostic, action_name: str) -> None:
        """Run the suggested Logos action for a diagnostic (preview/confirm)."""
        if not self._logos_visible:
            self._logos_visible = True
            self._logos_toolbar.set_section(self._current_section or "")
            self._logos_toolbar.refresh_actions()
            self._logos_toolbar.setVisible(True)
        ctx = self._diagnostic_context(diagnostic, action_name)
        self._logos_toolbar.run_action_with_context(ctx, action_name)

    def _diagnostic_context(self, diagnostic, action_name: str):
        """Build a LogosContext targeting the diagnostic's entity."""
        from storyplanner.logos.context import build_logos_context

        kwargs: dict = {}
        section = "PSYKE"
        if diagnostic.target_type == "psyke_entry":
            try:
                kwargs["selected_psyke_entry_id"] = int(diagnostic.target_id)
            except (TypeError, ValueError):
                pass
        elif diagnostic.target_type == "scene":
            try:
                kwargs["current_scene_id"] = int(diagnostic.target_id)
                section = "Outline"
            except (TypeError, ValueError):
                pass
        elif diagnostic.target_type == "graph_node":
            kwargs["current_graph_node_id"] = diagnostic.target_id
            section = "Graph"
        return build_logos_context(
            self._db, self._project_id, section_name=section, **kwargs,
        )

    def _on_diagnostic_suppress(self, diagnostic, kind: str) -> None:
        store = self._diagnostics_engine._suppression
        if store is not None and kind == "dismiss":
            store.dismiss(diagnostic.to_suggestion().id)
        self._scan_diagnostics()

    def _on_diagnostic_open_target(self, diagnostic) -> None:
        self._open_logos_target(diagnostic.target_type, diagnostic.target_id)

    def _open_logos_target(self, target_type: str, target_id: str) -> None:
        if target_type == "psyke_entry":
            try:
                self._open_psyke_entry(int(target_id))
            except (TypeError, ValueError):
                pass
        elif target_type == "scene":
            try:
                self._open_scene_in_editor(int(target_id))
            except (TypeError, ValueError):
                pass

    # -- Narrative Health (Phase 6) ------------------------------------------

    def _toggle_health(self) -> None:
        self._health_visible = not self._health_visible
        if self._health_visible:
            self._refresh_health()
        self._health_drawer.setVisible(self._health_visible)

    def _refresh_health(self) -> None:
        """Generate the project health report (rule-based, no LLM/mutation)."""
        engine = getattr(self, "_health_engine", None)
        drawer = getattr(self, "_health_drawer", None)
        if engine is None or drawer is None:
            return
        if not bool(get_settings().get("health_enabled")):
            self._health_report = None
            drawer.set_report(None)
            return
        try:
            self._health_report = engine.generate_report()
        except Exception:
            self._health_report = None
        drawer.set_report(self._health_report)
        self._update_strategy_indicator()

    def _update_strategy_indicator(self) -> None:
        """Reflect the active dominant strategy in the health drawer header."""
        router = getattr(self, "_strategy_router", None)
        drawer = getattr(self, "_health_drawer", None)
        if router is None or drawer is None:
            return
        try:
            from storyplanner.settings import get_manager
            if not bool(get_manager().get("strategy_show_indicator")):
                drawer.set_strategy_label("")
                return
            decision = router.decide(self._current_section or "")
            from storyplanner.logos.strategy import get_strategy
            s = get_strategy(decision.dominant_strategy)
            name = s.name if s else decision.dominant_strategy
            drawer.set_strategy_label(f"Strategy: {name}")
        except Exception:
            drawer.set_strategy_label("")

    def _on_health_action(self, recommendation, action_name: str) -> None:
        """Launch the Logos action a health recommendation maps to."""
        if not self._logos_visible:
            self._logos_visible = True
            self._logos_toolbar.set_section(self._current_section or "")
            self._logos_toolbar.refresh_actions()
            self._logos_toolbar.setVisible(True)
        ctx = self._recommendation_context(recommendation)
        self._logos_toolbar.run_action_with_context(ctx, action_name)

    def _recommendation_context(self, rec):
        from storyplanner.logos.context import build_logos_context

        kwargs: dict = {}
        section = "PSYKE"
        if rec.target_type == "psyke_entry":
            try:
                kwargs["selected_psyke_entry_id"] = int(rec.target_id)
            except (TypeError, ValueError):
                pass
        elif rec.target_type == "scene":
            try:
                kwargs["current_scene_id"] = int(rec.target_id)
                section = "Outline"
            except (TypeError, ValueError):
                pass
        elif rec.target_type == "graph_node":
            kwargs["current_graph_node_id"] = rec.target_id
            section = "Graph"
        return build_logos_context(
            self._db, self._project_id, section_name=section, **kwargs,
        )

    def _on_health_open_target(self, rec) -> None:
        self._open_logos_target(rec.target_type, rec.target_id)

    def _export_health(self, fmt: str) -> None:
        if self._health_report is None:
            self._refresh_health()
        report = self._health_report
        if report is None:
            return
        from PySide6.QtWidgets import QFileDialog, QMessageBox
        ext = "json" if fmt == "json" else "md"
        default = f"narrative_health.{ext}"
        path, _ = QFileDialog.getSaveFileName(
            self, "Export Narrative Health", default,
            "JSON (*.json)" if fmt == "json" else "Markdown (*.md)",
        )
        if not path:
            return
        try:
            text = report.to_json() if fmt == "json" else report.to_markdown()
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(text)
        except OSError as exc:
            QMessageBox.warning(self, "Export failed", str(exc))

    def _run_logos_outline(self, descriptor: dict, action_name: str) -> None:
        """Run a Logos action for a selected Outline node (from PlanView menus).

        Builds a node-scoped LogosContext and runs it through the shared Logos
        toolbar — non-destructive (no outline mutation).
        """
        from storyplanner.logos.context import build_logos_context

        if not self._logos_visible:
            self._logos_visible = True
            self._logos_toolbar.set_section("Outline")
            self._logos_toolbar.refresh_actions()
            self._logos_toolbar.setVisible(True)

        outline_template = ""
        try:
            from storyplanner.ui.plan_view import PlanView
            if isinstance(self.content_area, PlanView):
                outline_template = self.content_area._template_combo.currentData() or ""
        except Exception:
            outline_template = ""

        ctx = build_logos_context(
            self._db, self._project_id,
            section_name="Outline",
            current_scene_id=descriptor.get("scene_id"),
            outline_node_label=descriptor.get("label", ""),
            outline_node_kind=descriptor.get("kind", ""),
            active_block_type="outline_node",
            outline_template=outline_template,
        )
        self._logos_toolbar.run_action_with_context(ctx, action_name)

    def _logos_request_apply(self, result, context) -> None:
        """Open the preview dialog for a Logos result and apply on confirm.

        Non-destructive until the user confirms: the dialog only returns a
        finalized operation; this method validates and applies it through the
        existing write paths, then marks dirty / autosave / versioning and
        refreshes the active view.
        """
        from storyplanner.logos import operations as logos_ops
        from storyplanner.ui.logos.logos_apply_preview import LogosApplyPreview

        op = LogosApplyPreview.get_operation(result, context, parent=self)
        if op is None:
            return  # Cancel — no mutation.

        editor = None
        if op.get("target") == logos_ops.TARGET_MANUSCRIPT:
            editor = self._detect_active_editor()

        outcome = logos_ops.apply_logos_operation(
            self._db, self._project_id, op, editor=editor,
        )
        if not outcome.get("ok"):
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "Logos apply", outcome.get("detail", "Could not apply."))
            self._logos_toolbar.set_status("Apply failed")
            return

        # Emit the bus events the operation reported.
        from storyplanner.project_events import get_event_bus
        bus = get_event_bus()
        scene_id = outcome.get("scene_id")
        entry_id = outcome.get("entry_id")
        for name in outcome.get("events", []):
            sig = getattr(bus, name, None)
            if sig is None:
                continue
            try:
                if name == "scene_changed" and scene_id is not None:
                    sig.emit(scene_id)
                elif name == "psyke_changed" and entry_id is not None:
                    sig.emit(entry_id)
                else:
                    sig.emit()
            except TypeError:
                pass  # signal signature mismatch — skip safely
        # Mark dirty + autosave + versioning + refresh active view.
        self._on_data_changed()
        self._logos_toolbar.set_status("Applied")

    def _open_scene_in_editor(self, scene_id: int) -> None:
        self._set_active_section("Scenes")
        if self._cached_scenes_view is None:
            self._cached_scenes_view = ScenesView(
                self._db, self._project_id,
                on_data_changed=self._on_data_changed,
                on_link_clicked=self._on_link_navigated,
                on_focus_mode_changed=self._on_focus_mode_changed,
                on_open_psyke_entry=self._open_psyke_entry,
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
        self._set_active_section("Dashboard")
        self._switch_project(new_project_id)
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

        try:
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
        except (ImportError, ModuleNotFoundError) as exc:
            # PDF/DOCX need optional libraries (reportlab / python-docx).
            QMessageBox.warning(
                self, "Export failed",
                f"This format needs an optional library that isn't installed:\n"
                f"{exc}\n\nTry Markdown, TXT, Fountain or JSON instead.")
            return
        except Exception as exc:  # write/permission/serialization errors
            QMessageBox.warning(self, "Export failed",
                                f"Could not export:\n{exc}")
            return

        QMessageBox.information(self, "Export", f"Exported to {path}")

    # -- Structured data export ---------------------------------------------

    def _on_export_story_elements(self) -> None:
        self._run_data_export("story_elements")

    def _on_export_psyke_data(self) -> None:
        self._run_data_export("psyke_data")

    def _on_export_full_project(self) -> None:
        self._run_data_export("full_project")

    def _run_data_export(self, mode: str) -> None:
        """Drive an :class:`ExportDataDialog` for *mode* and write the result."""
        from storyplanner.data_export import (
            build_full_export,
            default_filename,
            gather_export,
            write_export,
        )
        from storyplanner.ui.export_data_dialog import ExportDataDialog

        project = self._db.get_project_by_id(self._project_id)
        if project is None:
            QMessageBox.warning(self, "Export", "No project is open.")
            return

        dialog = ExportDataDialog(mode, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        opts = dialog.get_options()
        fmt = opts.fmt

        # Make sure any pending edits are flushed to disk before reading. The
        # exporters read live from the DB (which already reflects committed
        # changes), but this keeps the on-disk file consistent too.
        try:
            self._autosave.save_now()
        except Exception:
            pass

        ext = {"json": "json", "markdown": "md", "csv": "csv"}[fmt]
        suggested = default_filename(project.title, mode, ext)

        filters = {
            "json": "JSON (*.json)",
            "markdown": "Markdown (*.md)",
            "csv": "CSV (*.csv)",
        }
        path, _ = QFileDialog.getSaveFileName(
            self, "Export Data", suggested, filters[fmt],
        )
        if not path:
            return

        try:
            if mode == "full_project":
                data = build_full_export(self._db, self._project_id)
            else:
                data = gather_export(self._db, self._project_id, opts)
            written = write_export(data, fmt, path)
        except (OSError, ValueError, PermissionError) as exc:
            QMessageBox.warning(self, "Export failed", str(exc))
            return
        except Exception as exc:  # serialization / unexpected errors
            QMessageBox.warning(
                self, "Export failed", f"Could not export data:\n{exc}",
            )
            return

        if len(written) == 1:
            msg = f"Exported to {written[0]}"
        else:
            msg = f"Exported {len(written)} files to {written[0].rsplit('/', 1)[0]}"
        QMessageBox.information(self, "Export", msg)

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

        move_action = QAction("Move Project to Folder...", self)
        move_action.triggered.connect(self._on_move_project)
        file_menu.addAction(move_action)

        open_folder_action = QAction("Open Project Folder", self)
        open_folder_action.triggered.connect(self._on_open_project_folder)
        file_menu.addAction(open_folder_action)

        proj_settings_action = QAction("Project Settings...", self)
        proj_settings_action.triggered.connect(self._on_project_settings)
        file_menu.addAction(proj_settings_action)

        file_menu.addSeparator()

        export_menu = file_menu.addMenu("Export")

        export_manuscript_action = QAction("Manuscript...", self)
        export_manuscript_action.triggered.connect(self._on_export)
        export_menu.addAction(export_manuscript_action)

        export_story_action = QAction("Story Elements...", self)
        export_story_action.triggered.connect(self._on_export_story_elements)
        export_menu.addAction(export_story_action)

        export_psyke_action = QAction("PSYKE Data...", self)
        export_psyke_action.triggered.connect(self._on_export_psyke_data)
        export_menu.addAction(export_psyke_action)

        export_full_action = QAction("Full Project Data...", self)
        export_full_action.triggered.connect(self._on_export_full_project)
        export_menu.addAction(export_full_action)

        import_action = QAction("Import...", self)
        import_action.triggered.connect(self._on_import)
        file_menu.addAction(import_action)

        file_menu.addSeparator()

        snapshot_action = QAction("Create Snapshot", self)
        snapshot_action.triggered.connect(self._on_create_snapshot)
        file_menu.addAction(snapshot_action)

        history_action = QAction("Version History...", self)
        history_action.triggered.connect(self._on_version_history)
        file_menu.addAction(history_action)

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
        prefs_action.setMenuRole(QAction.MenuRole.PreferencesRole)
        prefs_action.triggered.connect(self._open_settings)
        edit_menu.addAction(prefs_action)

        edit_menu.addSeparator()

        self._grammar_check_action = QAction("Grammar Check", self)
        self._grammar_check_action.setCheckable(True)
        self._grammar_check_action.triggered.connect(self._on_toggle_grammar_check)
        edit_menu.addAction(self._grammar_check_action)

        lang_menu = edit_menu.addMenu("Grammar Language")
        self._grammar_lang_actions: list[QAction] = []
        for code, label in (
            ("auto", "Auto"),
            ("en", "English"),
            ("it", "Italian"),
            ("es", "Spanish"),
            ("fr", "French"),
            ("de", "German"),
        ):
            act = QAction(label, self)
            act.setCheckable(True)
            act.setData(code)
            act.triggered.connect(
                lambda _checked=False, c=code: self._on_grammar_language(c)
            )
            lang_menu.addAction(act)
            self._grammar_lang_actions.append(act)

        edit_menu.aboutToShow.connect(self._sync_grammar_menu_state)

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

        toggle_logos_action = QAction("Toggle Logos (inline)", self)
        toggle_logos_action.setShortcut(QKeySequence("Ctrl+L"))
        toggle_logos_action.triggered.connect(self._toggle_logos)
        view_menu.addAction(toggle_logos_action)

        refresh_logos_action = QAction("Refresh Logos Suggestions", self)
        refresh_logos_action.triggered.connect(self._refresh_logos_suggestions_command)
        view_menu.addAction(refresh_logos_action)

        toggle_diag_action = QAction("Toggle Logos Diagnostics", self)
        toggle_diag_action.setShortcut(QKeySequence("Ctrl+Shift+D"))
        toggle_diag_action.triggered.connect(self._toggle_diagnostics)
        view_menu.addAction(toggle_diag_action)

        scan_diag_action = QAction("Scan Project (Logos Diagnostics)", self)
        scan_diag_action.triggered.connect(self._scan_diagnostics_project)
        view_menu.addAction(scan_diag_action)

        toggle_health_action = QAction("Toggle Narrative Health", self)
        toggle_health_action.setShortcut(QKeySequence("Ctrl+Shift+H"))
        toggle_health_action.triggered.connect(self._toggle_health)
        view_menu.addAction(toggle_health_action)

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
            ("Notes", self._show_notes, "Ctrl+5"),
            ("PSYKE", self._show_psyke, "Ctrl+6"),
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
        from storyplanner.ui.new_project_dialog import NewProjectDialog
        dlg = NewProjectDialog(parent=self)
        if not dlg.exec():
            return
        self._read_only = False
        project = self._db.create_project(
            dlg.get_title(),
            narrative_engine=dlg.get_engine(),
            default_writing_format=dlg.get_format(),
        )
        # New projects land on the Dashboard so the user sees the empty
        # state for the new project rather than (say) an empty Plot view.
        self._set_active_section("Dashboard")
        self._switch_project(project.id)
        # _switch_project already emitted project_loaded; additionally
        # announce that this project is brand new.
        from storyplanner.project_events import get_event_bus
        get_event_bus().project_created.emit(project.id)

    def _on_project_settings(self) -> None:
        if not self._project_id:
            return
        from storyplanner.ui.project_settings_dialog import ProjectSettingsDialog
        dlg = ProjectSettingsDialog(self._db, self._project_id, parent=self)
        if dlg.exec():
            # Re-enter the current project so the active view rebuilds
            # against the new engine/format.
            self._switch_project(self._project_id)

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

    # -- Versioning menu handlers -----------------------------------------------

    def _on_create_snapshot(self) -> None:
        from PySide6.QtWidgets import QInputDialog
        label, ok = QInputDialog.getText(
            self, "Create Snapshot", "Optional label:",
        )
        if not ok:
            return
        path = self._versions.create_snapshot(
            reason="manual", label=label.strip(),
        )
        if path:
            QMessageBox.information(
                self, "Snapshot Created",
                f"Version snapshot saved.",
            )
        else:
            QMessageBox.warning(
                self, "Snapshot Failed", "Could not create snapshot.",
            )

    def _on_version_history(self) -> None:
        from storyplanner.ui.version_history_dialog import VersionHistoryDialog
        dlg = VersionHistoryDialog(self._versions, parent=self)
        result = dlg.exec()
        if result and dlg.restored_project_id is not None:
            self._set_active_section("Dashboard")
            self._switch_project(dlg.restored_project_id)

    def _menu_ai_preset(self, preset: str) -> None:
        if not self._assistant_dock.is_panel_user_visible():
            self._assistant_user_visible = True
            self._assistant_panel.refresh_scenes()
            self._assistant_dock.set_panel_user_visible(True)
            if self._assistant_overlay:
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

    # -- Grammar menu (moved out of Manuscript top bar) ----------------------

    def _writing_view(self):
        from storyplanner.ui.writing_core_view import WritingCoreView
        view = self.content_area
        if isinstance(view, WritingCoreView):
            return view
        return None

    def _sync_grammar_menu_state(self) -> None:
        view = self._writing_view()
        enabled = view is not None
        self._grammar_check_action.setEnabled(enabled)
        for act in self._grammar_lang_actions:
            act.setEnabled(enabled)
        if view is None:
            self._grammar_check_action.setChecked(False)
            for act in self._grammar_lang_actions:
                act.setChecked(False)
            return
        self._grammar_check_action.setChecked(view.is_grammar_checking())
        current = view.language_override
        for act in self._grammar_lang_actions:
            act.setChecked(act.data() == current)

    def _on_toggle_grammar_check(self, checked: bool) -> None:
        view = self._writing_view()
        if view is None:
            self._grammar_check_action.setChecked(False)
            return
        if view.is_grammar_checking() != checked:
            view._toggle_grammar()

    def _on_grammar_language(self, code: str) -> None:
        view = self._writing_view()
        if view is None:
            return
        view._on_language_changed(code)

    def _show_about(self) -> None:
        QMessageBox.about(
            self,
            "About Logosforge",
            "Logosforge\n\nA story planning and writing application.",
        )

    def _update_title(self) -> None:
        dirty_mark = " *" if self._dirty else ""
        ro_mark = " [read-only]" if self._read_only else ""
        if self._current_file:
            name = Path(self._current_file).name
            self.setWindowTitle(f"Logosforge \u2014 {name}{dirty_mark}{ro_mark}")
        else:
            self.setWindowTitle(f"Logosforge{dirty_mark}{ro_mark}")

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

        if not self._handle_existing_lock(path):
            return

        resolved = str(Path(path).resolve())
        existing = self._db.get_project_by_source_path(resolved)
        if existing is not None:
            # Already imported once — activate that project instead of importing
            # a duplicate (prevents project bloat + stale duplicates).
            new_project_id = existing
        else:
            new_project_id = import_json(self._db, data)
            self._db.set_project_source_path(new_project_id, resolved)
        # Land on the Dashboard so the user sees the new project's summary.
        self._set_active_section("Dashboard")
        self._switch_project(new_project_id, file_path=path)
        recent_projects.add(path)
        self._refresh_recent_menu()
        get_settings().set("last_project_path", resolved)

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

        existing = current_lock_info(path)
        if existing is not None and not existing.is_stale() and not existing.is_same_machine():
            self._read_only = True
        else:
            self._read_only = False

        resolved = str(Path(path).resolve())
        existing_project = self._db.get_project_by_source_path(resolved)
        if existing_project is not None:
            # Don't re-import on every launch — activate the existing project.
            new_id = existing_project
        else:
            new_id = import_json(self._db, data)
            self._db.set_project_source_path(new_id, resolved)
        self._set_active_section("Dashboard")
        self._switch_project(new_id, file_path=path)
        recent_projects.add(path)
        self._refresh_recent_menu()
        self._update_title()
        return True

    def _on_save_as(self) -> None:
        start_dir = self._default_save_dir()
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Project As",
            start_dir,
            "JSON (*.json)",
        )
        if not path:
            return
        if not path.endswith(".json"):
            path += ".json"

        content = export_json(self._db, self._project_id)
        try:
            atomic_write_text(path, content)
        except OSError as e:
            QMessageBox.warning(self, "Save As", f"Could not write file:\n{e}")
            return

        # Release the previous lock (if any) before switching paths.
        if self._current_file and self._current_file != path:
            release_lock(self._current_file)

        self._set_current_file(path)
        self._mark_clean()
        try:
            acquire_lock(path)
        except OSError:
            pass
        recent_projects.add(path)
        self._refresh_recent_menu()
        get_settings().set("last_project_path", str(Path(path).resolve()))
        self._update_storage_indicator()
        QMessageBox.information(self, "Save As", f"Project saved to {path}")

    def _on_move_project(self) -> None:
        """Copy the current project to a chosen folder and switch to it.

        The old file (and its lock) are left in place until the user removes
        them — safer than auto-deleting cloud-synced files.  The recent list
        is updated to point at the new location.
        """
        if not self._current_file:
            QMessageBox.information(
                self, "Move Project",
                "Save the project first before moving it.",
            )
            return

        start_dir = self._default_save_dir()
        target_dir = QFileDialog.getExistingDirectory(
            self, "Move Project to Folder", start_dir,
        )
        if not target_dir:
            return

        source = Path(self._current_file)
        dest = Path(target_dir) / source.name
        if dest.resolve() == source.resolve():
            QMessageBox.information(
                self, "Move Project",
                "The selected folder is the project's current location.",
            )
            return
        if dest.exists():
            answer = QMessageBox.question(
                self, "Move Project",
                f"A file named '{dest.name}' already exists in that folder.\n\n"
                "Overwrite it?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                return

        try:
            content = export_json(self._db, self._project_id)
            atomic_write_text(dest, content)
        except OSError as e:
            QMessageBox.warning(self, "Move Project", f"Could not copy file:\n{e}")
            return

        release_lock(self._current_file)
        old_path = self._current_file
        new_path = str(dest)
        self._set_current_file(new_path)
        try:
            acquire_lock(new_path)
        except OSError:
            pass
        self._mark_clean()
        recent_projects.rename(old_path, new_path)
        self._refresh_recent_menu()
        get_settings().set("last_project_path", str(Path(new_path).resolve()))
        self._update_storage_indicator()
        QMessageBox.information(
            self, "Move Project",
            f"Project now points to:\n{new_path}\n\n"
            f"The original file at\n{old_path}\nis still on disk; "
            "delete it manually when you're sure the move succeeded.",
        )

    def _on_open_project_folder(self) -> None:
        if not self._current_file:
            QMessageBox.information(
                self, "Open Project Folder",
                "Save the project first to open its folder.",
            )
            return
        folder = Path(self._current_file).parent
        url = QUrl.fromLocalFile(str(folder))
        QDesktopServices.openUrl(url)

    def _default_save_dir(self) -> str:
        if self._current_file:
            return str(Path(self._current_file).parent)
        default = str(get_settings().get("default_projects_folder") or "")
        if default and Path(default).is_dir():
            return default
        return ""

    def _reset_content(self, message: str) -> None:
        widget = QWidget()
        QVBoxLayout(widget).addWidget(QLabel(message))
        self._set_content(widget)

    # -- Dirty state and autosave --------------------------------------------

    def _refresh_active_view(self) -> None:
        """Refresh the current content view if it supports refresh."""
        view = self.content_area
        if view is not None and hasattr(view, 'refresh'):
            view.refresh()

    def _switch_project(self, new_id: int, file_path: str | None = None) -> None:
        """Update all subsystems to point at *new_id*.

        Clears project-scoped caches, swaps sub-systems, and rebuilds the
        currently-active content view so it shows the new project's data
        — no caller-side navigation needed.
        """
        old_id = self._project_id
        # Release the lock on whatever project we were on before switching.
        if self._current_file and self._current_file != file_path:
            release_lock(self._current_file)

        # 1. Tear down project-scoped module caches BEFORE swapping the id
        # so each hook sees the project it's clearing.
        from storyplanner.project_lifecycle import clear_project_caches
        clear_project_caches(old_id)

        # 2. Swap the active project id and hand it to long-lived
        # sub-systems.
        self._project_id = new_id
        # Recompute the writing-mode-dependent sidebar nav (Graphic-Novel-only
        # Pages item) for the new project before the active section is rebuilt.
        self._apply_pages_availability()
        # Re-bind the always-on PSYKE console to the new project: clears its
        # in-progress query + stale results and rebuilds the index eagerly.
        # (The PSYKE section view itself is rebuilt fresh in step 4, so its
        # entry list / selection / relations / progressions reload cleanly.)
        self._psyke_console.set_project(new_id)
        self._set_current_file(file_path)
        self._autosave.set_project(new_id)
        self._versions.set_project(new_id)
        self._assistant_panel.set_project(new_id)
        if hasattr(self, '_system_command_handlers'):
            self._system_command_handlers.set_project(new_id)
        # Rebuild the proactive engine for the new project (fresh suppression).
        from storyplanner.logos.proactive import ProactiveEngine
        self._logos_engine = ProactiveEngine(self._db, new_id)
        from storyplanner.logos.diagnostics import DiagnosticsEngine
        self._diagnostics_engine = DiagnosticsEngine(
            self._db, new_id, suppression=self._logos_engine.suppression,
        )
        from storyplanner.logos.health import HealthEngine
        self._health_engine = HealthEngine(
            self._db, new_id, suppression=self._logos_engine.suppression,
        )
        from storyplanner.logos.strategy import StrategyRouter
        self._strategy_router = StrategyRouter(self._db, new_id)
        self._health_report = None
        # Clear stale Logos surfaces so the previous project's findings never
        # linger after a switch; rescan/refresh below for the new project.
        if hasattr(self, "_logos_suggestions"):
            self._logos_suggestions.set_suggestions([])
            self._logos_suggestions.setVisible(False)
        # The inline Logos toolbar (always-present, not rebuilt on switch) keeps
        # its last result — drop it so a prior project's Logos output doesn't
        # linger in the bar after switching.
        if hasattr(self, "_logos_toolbar"):
            self._logos_toolbar.clear_result()
        if hasattr(self, "_diagnostics_drawer"):
            self._diagnostics_drawer.set_diagnostics([])
        if hasattr(self, "_health_drawer"):
            self._health_drawer.set_report(None)
        if self._health_visible:
            self._refresh_health()

        # 3. Drop MainWindow's own per-project caches.
        self._cached_scenes_view = None
        self._cached_scene_entry_scene = None
        self._cached_scene_entry_ids = None
        self._external_change_warned = False

        if file_path:
            try:
                acquire_lock(file_path)
            except OSError:
                pass
        self._mark_clean()
        self._update_storage_indicator()

        # 4. Rebuild the currently visible content view so it shows the
        # new project's data without forcing the user to a different
        # section.
        self._rebuild_active_section()

        # 4b. Rescan Logos surfaces for the new project (the nav handlers in
        # step 4 don't go through _set_active_section, which is where the
        # per-section scan normally fires).
        self._scan_logos_suggestions()
        self._scan_diagnostics()
        self._update_strategy_indicator()

        # 5. Announce the load so self-subscribed views (e.g. Dashboard)
        # re-point at the new project and recompute, regardless of whether
        # they were rebuilt above.
        from storyplanner.project_events import emit_project_loaded
        emit_project_loaded(new_id)

        self._debug_log_switch(old_id, new_id, file_path)

    def _debug_log_switch(self, old_id, new_id, file_path) -> None:
        """Optional project-switch diagnostics (set STORYPLANNER_DEBUG_PROJECT=1)."""
        import os
        if not os.environ.get("STORYPLANNER_DEBUG_PROJECT"):
            return
        try:
            import logging
            logging.getLogger("storyplanner.project").info(
                "project switch %s -> %s file=%s scenes=%d psyke=%d outline=%d "
                "notes=%d assistant_pid=%s",
                old_id, new_id, file_path,
                len(self._db.get_all_scenes(new_id)),
                len(self._db.get_all_psyke_entries(new_id)),
                len(self._db.get_outline_nodes(new_id)),
                len(self._db.get_all_notes(new_id)),
                getattr(self._assistant_panel, "_project_id", None),
            )
        except Exception:
            pass

    def _rebuild_active_section(self) -> None:
        """Re-invoke the handler for the currently active sidebar section.

        The content widgets read project_id at construction time, so
        rebuilding from scratch is what guarantees they show the new
        project's data.
        """
        if not hasattr(self, "_nav_section_handlers"):
            return
        handler = self._nav_section_handlers.get(self._current_section)
        if handler is None:
            handler = self._nav_section_handlers.get("Dashboard")
        if handler is not None:
            handler()

    def _on_data_changed(self) -> None:
        self._dirty = True
        self._update_title()
        if not self._read_only:
            self._autosave.mark_dirty()
            self._versions.mark_dirty()
        self._assistant_panel.refresh_scenes()
        self._cached_scene_entry_scene = None
        self._cached_scene_entry_ids = None
        self._psyke_console.mark_index_dirty()
        self._refresh_active_view()
        # Re-run the lightweight proactive scan after any data change.
        self._scan_logos_suggestions()
        self._scan_diagnostics()

    def _on_scene_content_saved(self) -> None:
        """Lightweight notification for in-place edits.

        The active view already reflects the change — skipping the view
        refresh prevents the editor from being destroyed mid-keystroke.
        """
        self._dirty = True
        self._update_title()
        if not self._read_only:
            self._autosave.mark_dirty()
            self._versions.mark_dirty()
        self._cached_scene_entry_scene = None
        self._cached_scene_entry_ids = None
        self._psyke_console.mark_index_dirty()

    def _auto_save(self) -> None:
        if not self._current_file:
            return
        self._autosave.save_now()

    def _on_autosave_status(self, status: str) -> None:
        if status == "Saved":
            self._dirty = False
            self._update_title()
        if hasattr(self, "_save_status_label"):
            self._save_status_label.setText(status)

    def _on_focus_mode_changed(self, active: bool) -> None:
        if active:
            self._sidebar.setVisible(False)
            self._assistant_panel.setVisible(False)
        else:
            self._sidebar.setVisible(True)
            if self._assistant_user_visible:
                self._assistant_panel.setVisible(True)
        central = self.centralWidget()
        if central:
            central.layout().invalidate()
            central.update()

    def _set_current_file(self, path: str | None) -> None:
        self._current_file = path
        self._autosave.file_path = path

    def _mark_clean(self) -> None:
        self._dirty = False
        self._autosave.mark_clean()
        self._update_title()

    # -- Lock & conflict handling --------------------------------------------

    def _handle_existing_lock(self, path: str) -> bool:
        """Return True if the project may be opened, False to cancel."""
        info = current_lock_info(path)
        if info is None or info.is_stale() or info.is_same_machine():
            return True

        when = ""
        if info.timestamp > 0:
            import datetime as _dt
            when = _dt.datetime.fromtimestamp(info.timestamp).strftime(
                "%Y-%m-%d %H:%M",
            )

        details = (
            f"This project may already be open on another device.\n\n"
            f"Device: {info.device or 'unknown'}\n"
            f"User: {info.user or 'unknown'}\n"
            f"Opened: {when or 'unknown'}\n\n"
            "Open it anyway only if you're sure the other session has closed.\n"
            "Otherwise, opening read-only is safer."
        )
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Warning)
        box.setWindowTitle("Project May Be Open Elsewhere")
        box.setText(details)
        read_only_btn = box.addButton(
            "Open Read-Only", QMessageBox.ButtonRole.AcceptRole,
        )
        anyway_btn = box.addButton(
            "Open Anyway", QMessageBox.ButtonRole.DestructiveRole,
        )
        cancel_btn = box.addButton(
            "Cancel", QMessageBox.ButtonRole.RejectRole,
        )
        box.setDefaultButton(read_only_btn)
        box.exec()
        clicked = box.clickedButton()
        if clicked is cancel_btn:
            return False
        self._read_only = clicked is read_only_btn
        return True

    def _on_external_change(self, path: str) -> None:
        if self._external_change_warned:
            return
        self._external_change_warned = True
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Warning)
        box.setWindowTitle("Project Changed on Disk")
        box.setText(
            f"The project file changed externally since it was loaded:\n{path}\n\n"
            "Saving now would overwrite those changes."
        )
        reload_btn = box.addButton(
            "Reload from Disk", QMessageBox.ButtonRole.AcceptRole,
        )
        conflict_btn = box.addButton(
            "Save Conflict Copy", QMessageBox.ButtonRole.ActionRole,
        )
        overwrite_btn = box.addButton(
            "Overwrite", QMessageBox.ButtonRole.DestructiveRole,
        )
        cancel_btn = box.addButton(
            "Cancel", QMessageBox.ButtonRole.RejectRole,
        )
        box.setDefaultButton(reload_btn)
        box.exec()
        clicked = box.clickedButton()
        if clicked is reload_btn:
            self._external_change_warned = False
            self.load_file_quiet(path)
        elif clicked is conflict_btn:
            dest = self._autosave.write_conflict_copy_now()
            self._external_change_warned = False
            if dest:
                QMessageBox.information(
                    self, "Conflict Copy",
                    f"Your changes were saved to:\n{dest}\n\n"
                    "Reload the project to see the on-disk version.",
                )
        elif clicked is overwrite_btn:
            self._external_change_warned = False
            self._autosave.force_next_save()
            self._autosave.save_now()
        else:
            # Cancel — leave the warning latched so we don't pester repeatedly.
            pass

    def _update_storage_indicator(self) -> None:
        if not hasattr(self, "_save_status_label"):
            return
        if not self._current_file:
            self._storage_label_text = ""
        else:
            provider = classify_path(self._current_file)
            badge = f"{provider}"
            if self._read_only:
                badge = f"{badge} (read-only)"
            self._storage_label_text = badge
        if hasattr(self, "_storage_label"):
            self._storage_label.setText(self._storage_label_text)

    # -- Close event ---------------------------------------------------------

    def closeEvent(self, event: QCloseEvent) -> None:
        self._versions.stop()
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
        elif self._dirty and self._current_file and not self._read_only:
            self._auto_save()
        if self._current_file:
            release_lock(self._current_file)
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
        self._psyke_console.refresh_style()
        preferences.set_string("appearance", name)
        get_settings().set("appearance", name)

    # -- Global "/" shortcut to PSYKE console --------------------------------

    def eventFilter(self, obj, event) -> bool:
        if event.type() == event.Type.KeyPress and event.text() == "/":
            focus = QApplication.focusWidget()
            if focus is not None:
                for cls in ("QLineEdit", "QPlainTextEdit", "QTextEdit"):
                    if focus.inherits(cls):
                        return super().eventFilter(obj, event)
            self._psyke_console.activate()
            return True
        return super().eventFilter(obj, event)
