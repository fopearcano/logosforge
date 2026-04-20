"""Visual Story Grid — spatial plotting system.

Displays scenes in a grid where columns are Acts (or Chapters) and rows are
scenes within each group. Supports drag-and-drop reordering, zoom levels,
color coding by plotline/tag/beat, and Story Flow indicators (tension bars,
character dots, scene type badges, pacing warnings).
"""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QMimeData, QPoint, Qt, QTimer
from PySide6.QtGui import QDrag, QMouseEvent, QPainter, QPixmap
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from storyplanner.db import Database
from storyplanner.story_flow import (
    FlowAnalysis,
    SceneTension,
    SceneType,
    analyze_flow,
    scene_type_icon,
    tension_color,
)
from storyplanner.ui import theme


_CARD_MIN_WIDTH = 180
_CARD_MAX_WIDTH = 260
_COLUMN_MIN_WIDTH = 200
_COLUMN_MAX_WIDTH = 280
_DRAG_THRESHOLD = 10

_COLOR_PALETTE = [
    "#4ade80", "#60a5fa", "#f59e0b", "#a78bfa",
    "#f472b6", "#34d399", "#fb923c", "#38bdf8",
]


class _SceneCard(QFrame):
    """Compact scene card displayed in the grid."""

    def __init__(
        self,
        scene,
        zoom: int,
        color_accent: str = "",
        flow_visible: bool = False,
        tension: SceneTension | None = None,
        scene_type: SceneType | None = None,
        char_colors: list[str] | None = None,
        pacing_warning: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.scene_id = scene.id
        self._scene = scene
        self.setObjectName("gridSceneCard")
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(3)

        # -- Title row with optional type icon --------------------------------
        title_row = QHBoxLayout()
        title_row.setContentsMargins(0, 0, 0, 0)
        title_row.setSpacing(4)

        self._title_label = QLabel(scene.title or "Untitled")
        self._title_label.setObjectName("gridCardTitle")
        self._title_label.setWordWrap(True)
        title_row.addWidget(self._title_label, stretch=1)

        self._type_label = QLabel()
        self._type_label.setObjectName("gridCardType")
        if scene_type and flow_visible:
            icon = scene_type_icon(scene_type.primary)
            self._type_label.setText(icon)
            self._type_label.setToolTip(scene_type.primary.capitalize())
        title_row.addWidget(self._type_label)
        layout.addLayout(title_row)

        # -- Summary ----------------------------------------------------------
        self._summary_label = QLabel()
        self._summary_label.setObjectName("gridCardSummary")
        self._summary_label.setWordWrap(True)
        summary_text = scene.summary or scene.synopsis or ""
        if len(summary_text) > 80:
            summary_text = summary_text[:77] + "..."
        self._summary_label.setText(summary_text)
        layout.addWidget(self._summary_label)

        # -- Meta line --------------------------------------------------------
        self._meta_label = QLabel()
        self._meta_label.setObjectName("gridCardMeta")
        meta_parts: list[str] = []
        if scene.beat:
            meta_parts.append(scene.beat)
        if scene.tags:
            tags_clean = [t.strip() for t in scene.tags.split(",") if not t.strip().lower().startswith("tension:")]
            if tags_clean:
                meta_parts.append(tags_clean[0])
        if scene.plotline:
            meta_parts.append(scene.plotline)
        self._meta_label.setText(" · ".join(meta_parts) if meta_parts else "")
        layout.addWidget(self._meta_label)

        # -- Character presence dots ------------------------------------------
        self._char_row = QWidget()
        self._char_row.setObjectName("gridCharRow")
        char_layout = QHBoxLayout(self._char_row)
        char_layout.setContentsMargins(0, 2, 0, 0)
        char_layout.setSpacing(3)
        if char_colors and flow_visible:
            for color in char_colors[:6]:
                dot = QLabel()
                dot.setFixedSize(6, 6)
                dot.setObjectName("gridCharDot")
                dot.setStyleSheet(
                    f"background-color: {color}; border-radius: 3px;"
                )
                char_layout.addWidget(dot)
        char_layout.addStretch()
        layout.addWidget(self._char_row)

        # -- Tension bar ------------------------------------------------------
        self._tension_bar = QWidget()
        self._tension_bar.setObjectName("gridTensionBar")
        self._tension_bar.setFixedHeight(3)
        if tension and tension.value > 0 and flow_visible:
            bar_color = tension_color(tension.value)
            width_pct = tension.value * 10
            self._tension_bar.setStyleSheet(
                f"background-color: {bar_color}; border-radius: 1px;"
                f" max-width: {width_pct}%;"
            )
            self._tension_bar.setToolTip(f"Tension: {tension.value}/10 ({tension.source})")
        else:
            self._tension_bar.hide()
        layout.addWidget(self._tension_bar)

        self._apply_zoom(zoom, flow_visible)
        self._apply_accent(color_accent)
        self._apply_pacing_warning(pacing_warning, flow_visible)

        self._drag_start: QPoint | None = None

    def _apply_zoom(self, zoom: int, flow_visible: bool = False) -> None:
        if zoom == 0:
            self._summary_label.hide()
            self._meta_label.hide()
            self._char_row.hide()
            self._type_label.hide()
        elif zoom == 1:
            self._summary_label.setVisible(bool(self._summary_label.text()))
            self._meta_label.hide()
            self._char_row.setVisible(flow_visible)
            self._type_label.setVisible(flow_visible)
        else:
            self._summary_label.setVisible(bool(self._summary_label.text()))
            self._meta_label.setVisible(bool(self._meta_label.text()))
            self._char_row.setVisible(flow_visible)
            self._type_label.setVisible(flow_visible)

    def _apply_accent(self, color: str) -> None:
        if color:
            self.setStyleSheet(
                self.styleSheet() + f"\n#gridSceneCard {{ border-left: 4px solid {color}; }}"
            )

    def _apply_pacing_warning(self, warning: bool, flow_visible: bool) -> None:
        if warning and flow_visible:
            self.setObjectName("gridSceneCardWarning")

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_start = event.pos()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._drag_start is None:
            return
        if (event.pos() - self._drag_start).manhattanLength() < _DRAG_THRESHOLD:
            return
        drag = QDrag(self)
        mime = QMimeData()
        mime.setText(str(self.scene_id))
        drag.setMimeData(mime)

        pixmap = QPixmap(self.size())
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        self.render(painter)
        painter.end()
        drag.setPixmap(pixmap)
        drag.setHotSpot(event.pos())

        self.setCursor(Qt.CursorShape.ClosedHandCursor)
        drag.exec(Qt.DropAction.MoveAction)
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        self._drag_start = None

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        self._drag_start = None
        super().mouseReleaseEvent(event)


class _GridColumn(QFrame):
    """A single column in the story grid, representing an Act or Chapter."""

    scene_dropped = None

    def __init__(
        self,
        group_name: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.group_name = group_name
        self.setObjectName("gridColumn")
        self.setAcceptDrops(True)
        self.setMinimumWidth(_COLUMN_MIN_WIDTH)
        self.setMaximumWidth(_COLUMN_MAX_WIDTH)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)

        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(8, 8, 8, 8)
        self._layout.setSpacing(6)

        self._header = QLabel(group_name or "Unassigned")
        self._header.setObjectName("gridColumnHeader")
        self._header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._layout.addWidget(self._header)

        self._cards_layout = QVBoxLayout()
        self._cards_layout.setContentsMargins(0, 0, 0, 0)
        self._cards_layout.setSpacing(6)
        self._layout.addLayout(self._cards_layout)
        self._layout.addStretch()

        self._cards: list[_SceneCard] = []
        self._drop_indicator: QWidget | None = None

    def add_card(self, card: _SceneCard) -> None:
        self._cards.append(card)
        self._cards_layout.addWidget(card)

    def card_count(self) -> int:
        return len(self._cards)

    def set_empty_state(self, text: str) -> None:
        lbl = QLabel(text)
        lbl.setObjectName("gridEmptyColumn")
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl.setWordWrap(True)
        self._cards_layout.addWidget(lbl)

    def _drop_index(self, pos: QPoint) -> int:
        for i, card in enumerate(self._cards):
            card_center = card.pos().y() + card.height() // 2
            if pos.y() < card_center:
                return i
        return len(self._cards)

    def dragEnterEvent(self, event) -> None:
        if event.mimeData().hasText():
            event.acceptProposedAction()
            self._show_drop_indicator()

    def dragMoveEvent(self, event) -> None:
        if event.mimeData().hasText():
            event.acceptProposedAction()

    def dragLeaveEvent(self, event) -> None:
        self._hide_drop_indicator()

    def dropEvent(self, event) -> None:
        self._hide_drop_indicator()
        if not event.mimeData().hasText():
            return
        scene_id = int(event.mimeData().text())
        drop_idx = self._drop_index(event.position().toPoint())
        event.acceptProposedAction()
        if self.scene_dropped:
            self.scene_dropped(scene_id, self.group_name, drop_idx)

    def _show_drop_indicator(self) -> None:
        if self._drop_indicator is None:
            self._drop_indicator = QWidget(self)
            self._drop_indicator.setFixedHeight(3)
            self._drop_indicator.setObjectName("gridDropIndicator")
            self._drop_indicator.setStyleSheet(
                f"background-color: {theme.ACCENT}; border-radius: 1px;"
            )
        self._drop_indicator.setFixedWidth(self.width() - 16)
        self._drop_indicator.move(8, self.height() - 20)
        self._drop_indicator.show()

    def _hide_drop_indicator(self) -> None:
        if self._drop_indicator:
            self._drop_indicator.hide()


class StoryGridView(QWidget):
    """Visual Story Grid — spatial plotting system."""

    def __init__(
        self,
        db: Database,
        project_id: int,
        on_data_changed: Callable[[], None] | None = None,
        on_open_scene: Callable[[int], None] | None = None,
    ) -> None:
        super().__init__()
        self._db = db
        self._project_id = project_id
        self._on_data_changed = on_data_changed
        self._on_open_scene = on_open_scene

        self._group_by = "act"  # "act" or "chapter"
        self._zoom = 1  # 0=titles, 1=title+summary, 2=full
        self._color_mode = "none"  # "none", "plotline", "tag", "beat"
        self._flow_visible = False
        self._flow_analysis: FlowAnalysis | None = None
        self._columns: list[_GridColumn] = []

        self._build_ui()
        self.refresh()

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # -- Toolbar ---------------------------------------------------------
        toolbar = QWidget()
        toolbar.setObjectName("gridToolbar")
        tb_layout = QHBoxLayout(toolbar)
        tb_layout.setContentsMargins(12, 6, 12, 6)
        tb_layout.setSpacing(8)

        tb_layout.addWidget(QLabel("Group:"))
        self._group_combo = QComboBox()
        self._group_combo.addItems(["By Act", "By Chapter"])
        self._group_combo.currentIndexChanged.connect(self._on_group_changed)
        tb_layout.addWidget(self._group_combo)

        tb_layout.addWidget(QLabel("Color:"))
        self._color_combo = QComboBox()
        self._color_combo.addItems(["None", "Plotline", "Tag", "Beat"])
        self._color_combo.currentIndexChanged.connect(self._on_color_changed)
        tb_layout.addWidget(self._color_combo)

        self._flow_check = QCheckBox("Flow")
        self._flow_check.setToolTip("Show tension, pacing, and character indicators")
        self._flow_check.toggled.connect(self._on_flow_toggled)
        tb_layout.addWidget(self._flow_check)

        tb_layout.addStretch()

        self._zoom_out_btn = QPushButton("−")
        self._zoom_out_btn.setFixedWidth(28)
        self._zoom_out_btn.setToolTip("Zoom out")
        self._zoom_out_btn.clicked.connect(self._zoom_out)
        tb_layout.addWidget(self._zoom_out_btn)

        self._zoom_label = QLabel("Zoom: 2")
        self._zoom_label.setObjectName("gridZoomLabel")
        tb_layout.addWidget(self._zoom_label)

        self._zoom_in_btn = QPushButton("+")
        self._zoom_in_btn.setFixedWidth(28)
        self._zoom_in_btn.setToolTip("Zoom in")
        self._zoom_in_btn.clicked.connect(self._zoom_in)
        tb_layout.addWidget(self._zoom_in_btn)

        outer.addWidget(toolbar)

        # -- Grid scroll area ------------------------------------------------
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._scroll.setObjectName("gridScrollArea")
        outer.addWidget(self._scroll)

        self._grid_container = QWidget()
        self._grid_container.setObjectName("gridContainer")
        self._grid_layout = QHBoxLayout(self._grid_container)
        self._grid_layout.setContentsMargins(12, 12, 12, 12)
        self._grid_layout.setSpacing(12)
        self._grid_layout.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        self._scroll.setWidget(self._grid_container)

        self._update_zoom_label()

    # -- Data loading --------------------------------------------------------

    def refresh(self) -> None:
        self._clear_grid()
        scenes = self._db.get_all_scenes(self._project_id)

        groups: dict[str, list] = {}
        for scene in scenes:
            key = (scene.act or "").strip() if self._group_by == "act" else (scene.chapter or "").strip()
            if not key:
                key = ""
            groups.setdefault(key, []).append(scene)

        color_map = self._build_color_map(scenes)

        if self._flow_visible:
            self._flow_analysis = analyze_flow(self._db, self._project_id)
            char_color_map = self._build_char_color_map(scenes)
            warned_ids = set()
            if self._flow_analysis:
                for w in self._flow_analysis.pacing_warnings:
                    warned_ids.update(w.scene_ids)
        else:
            self._flow_analysis = None
            char_color_map = {}
            warned_ids = set()

        if not groups:
            self._add_empty_grid_state()
            return

        sorted_keys = sorted(groups.keys(), key=lambda k: (k == "", k))

        for key in sorted_keys:
            col = _GridColumn(key if key else "Unassigned")
            col.scene_dropped = self._on_scene_dropped
            for scene in groups[key]:
                accent = color_map.get(scene.id, "")
                tension = self._flow_analysis.tensions.get(scene.id) if self._flow_analysis else None
                scene_type = self._flow_analysis.scene_types.get(scene.id) if self._flow_analysis else None
                char_colors = char_color_map.get(scene.id, [])
                card = _SceneCard(
                    scene, self._zoom,
                    color_accent=accent,
                    flow_visible=self._flow_visible,
                    tension=tension,
                    scene_type=scene_type,
                    char_colors=char_colors,
                    pacing_warning=scene.id in warned_ids,
                )
                col.add_card(card)
            self._columns.append(col)
            self._grid_layout.addWidget(col)

        self._grid_layout.addStretch()

    def _clear_grid(self) -> None:
        self._columns.clear()
        while self._grid_layout.count():
            item = self._grid_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

    def _add_empty_grid_state(self) -> None:
        empty = QWidget()
        empty.setObjectName("gridEmptyState")
        layout = QVBoxLayout(empty)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(12)

        msg = QLabel("Your story grid is empty.\nCreate scenes to see them here.")
        msg.setObjectName("gridEmptyLabel")
        msg.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(msg)

        add_btn = QPushButton("+ Add Scene")
        add_btn.setObjectName("gridAddSceneBtn")
        add_btn.clicked.connect(self._create_first_scene)
        layout.addWidget(add_btn, alignment=Qt.AlignmentFlag.AlignCenter)

        self._grid_layout.addWidget(empty)

    # -- Color coding --------------------------------------------------------

    def _build_color_map(self, scenes) -> dict[int, str]:
        if self._color_mode == "none":
            return {}

        assignments: dict[str, str] = {}
        result: dict[int, str] = {}
        idx = 0

        for scene in scenes:
            if self._color_mode == "plotline":
                key = (scene.plotline or "").strip()
            elif self._color_mode == "tag":
                tags = (scene.tags or "").split(",")
                key = tags[0].strip() if tags else ""
            elif self._color_mode == "beat":
                key = (scene.beat or "").strip()
            else:
                key = ""

            if not key:
                continue

            if key not in assignments:
                assignments[key] = _COLOR_PALETTE[idx % len(_COLOR_PALETTE)]
                idx += 1
            result[scene.id] = assignments[key]

        return result

    # -- Drag and drop -------------------------------------------------------

    def _on_scene_dropped(
        self, scene_id: int, target_group: str, drop_index: int,
    ) -> None:
        scene = self._db.get_scene_by_id(scene_id)
        if scene is None:
            return

        if target_group == "Unassigned":
            target_group = ""

        if self._group_by == "act":
            if scene.act != target_group:
                self._db.update_scene(scene_id, scene.title, act=target_group)
        else:
            if scene.chapter != target_group:
                self._db.update_scene(scene_id, scene.title, chapter=target_group)

        scenes_in_target = self._db.get_all_scenes(self._project_id)
        target_scenes = [
            s for s in scenes_in_target
            if ((s.act or "").strip() if self._group_by == "act" else (s.chapter or "").strip()) == target_group
            or (target_group == "" and not ((s.act or "").strip() if self._group_by == "act" else (s.chapter or "").strip()))
        ]

        scene_ids_in_target = [s.id for s in target_scenes if s.id != scene_id]
        if drop_index > len(scene_ids_in_target):
            drop_index = len(scene_ids_in_target)
        scene_ids_in_target.insert(drop_index, scene_id)

        all_scenes = self._db.get_all_scenes(self._project_id)
        all_ids = [s.id for s in all_scenes]
        other_ids = [sid for sid in all_ids if sid not in scene_ids_in_target]

        final_order = other_ids[:0]
        target_inserted = False
        for sid in all_ids:
            if sid in scene_ids_in_target:
                if not target_inserted:
                    final_order.extend(scene_ids_in_target)
                    target_inserted = True
            else:
                final_order.append(sid)
        if not target_inserted:
            final_order.extend(scene_ids_in_target)

        self._db.reorder_scene(scene_id, drop_index)

        if self._on_data_changed:
            self._on_data_changed()
        self.refresh()

    # -- Zoom ----------------------------------------------------------------

    def _zoom_in(self) -> None:
        if self._zoom < 2:
            self._zoom += 1
            self._update_zoom_label()
            self.refresh()

    def _zoom_out(self) -> None:
        if self._zoom > 0:
            self._zoom -= 1
            self._update_zoom_label()
            self.refresh()

    def _update_zoom_label(self) -> None:
        names = ["Titles", "Summary", "Detail"]
        self._zoom_label.setText(f"Zoom: {names[self._zoom]}")

    def get_zoom(self) -> int:
        return self._zoom

    # -- Flow indicators -------------------------------------------------------

    def _on_flow_toggled(self, checked: bool) -> None:
        self._flow_visible = checked
        self.refresh()

    def is_flow_visible(self) -> bool:
        return self._flow_visible

    def _build_char_color_map(self, scenes) -> dict[int, list[str]]:
        characters = self._db.get_all_characters(self._project_id)
        char_colors: dict[int, str] = {c.id: c.color for c in characters}
        result: dict[int, list[str]] = {}
        for scene in scenes:
            char_ids = self._db.get_scene_character_ids(scene.id)
            colors = [char_colors[cid] for cid in char_ids if cid in char_colors]
            if colors:
                result[scene.id] = colors
        return result

    # -- Group / color switching ---------------------------------------------

    def _on_group_changed(self, index: int) -> None:
        self._group_by = "act" if index == 0 else "chapter"
        self.refresh()

    def _on_color_changed(self, index: int) -> None:
        modes = ["none", "plotline", "tag", "beat"]
        self._color_mode = modes[index]
        self.refresh()

    def get_color_mode(self) -> str:
        return self._color_mode

    def get_group_by(self) -> str:
        return self._group_by

    # -- Scene creation ------------------------------------------------------

    def _create_first_scene(self) -> None:
        group = "Act 1" if self._group_by == "act" else "Chapter 1"
        self._db.create_scene(
            self._project_id, "New Scene",
            act=group if self._group_by == "act" else "",
            chapter=group if self._group_by == "chapter" else "",
        )
        if self._on_data_changed:
            self._on_data_changed()
        self.refresh()

    # -- Public API ----------------------------------------------------------

    def column_count(self) -> int:
        return len(self._columns)

    def total_cards(self) -> int:
        return sum(c.card_count() for c in self._columns)
