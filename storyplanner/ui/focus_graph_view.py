"""Graph Focus System — controlled graph exploration.

Replaces the full graph dump with focused navigation: click a node to see
only its neighborhood, expand/collapse, temporal filtering, type filters,
search, and hover highlighting.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass, field

from PySide6.QtCore import Qt
from PySide6.QtGui import QBrush, QColor, QFont, QPen
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFrame,
    QGraphicsEllipseItem,
    QGraphicsLineItem,
    QGraphicsPolygonItem,
    QGraphicsScene,
    QGraphicsSimpleTextItem,
    QGraphicsView,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)
from PySide6.QtGui import QPolygonF
from PySide6.QtCore import QPointF

from storyplanner.db import Database
from storyplanner.graph_meaning import (
    MeaningData,
    NodeMeaning,
    compute_meaning,
    importance_radius_delta,
    state_color,
)
from storyplanner.ui import theme


_TYPE_COLORS = {
    "Character": "#42a5f5",
    "Place": "#66bb6a",
    "Scene": "#ffa726",
    "Note": "#ab47bc",
    "PSYKE": "#4ade80",
}

_NODE_RADIUS = 22
_FOCUS_RADIUS = 28
_GRAPH_RADIUS = 200
_EDGE_COLOR = "#4a5568"
_EDGE_HIGHLIGHT = "#4ade80"
_DIM_OPACITY = 0.25

_ARC_PALETTE = ["#42a5f5", "#ab47bc", "#ef5350", "#26a69a", "#ffa726", "#78909c"]


def _arc_color(plotline: str) -> str:
    idx = hash(plotline) % len(_ARC_PALETTE)
    return _ARC_PALETTE[idx]


@dataclass
class GraphNode:
    """A node in the graph."""

    node_id: str  # "type:id" e.g. "Character:5"
    etype: str
    entity_id: int
    name: str


@dataclass
class GraphEdge:
    """A connection between two nodes."""

    source_id: str
    target_id: str


@dataclass
class GraphData:
    """Full graph data for a project."""

    nodes: dict[str, GraphNode] = field(default_factory=dict)
    edges: list[GraphEdge] = field(default_factory=list)
    adjacency: dict[str, set[str]] = field(default_factory=dict)


def build_graph_data(db: Database, project_id: int) -> GraphData:
    """Build structured graph data from DB link graph + PSYKE relations."""
    raw_nodes, raw_edges = db.build_link_graph(project_id)

    data = GraphData()

    for etype, eid, name in raw_nodes:
        node_id = f"{etype}:{eid}"
        data.nodes[node_id] = GraphNode(node_id, etype, eid, name)
        data.adjacency.setdefault(node_id, set())

    psyke_entries = db.get_all_psyke_entries(project_id)
    for entry in psyke_entries:
        node_id = f"PSYKE:{entry.id}"
        if node_id not in data.nodes:
            data.nodes[node_id] = GraphNode(node_id, "PSYKE", entry.id, entry.name)
            data.adjacency.setdefault(node_id, set())

        related = db.get_related_psyke_entries(entry.id)
        for rel in related:
            rel_id = f"PSYKE:{rel.id}"
            if rel_id not in data.nodes:
                data.nodes[rel_id] = GraphNode(rel_id, "PSYKE", rel.id, rel.name)
                data.adjacency.setdefault(rel_id, set())
            data.edges.append(GraphEdge(node_id, rel_id))
            data.adjacency.setdefault(node_id, set()).add(rel_id)
            data.adjacency.setdefault(rel_id, set()).add(node_id)

    name_to_id: dict[str, str] = {}
    for nid, node in data.nodes.items():
        name_to_id[node.name.lower()] = nid

    for src_name, tgt_name in raw_edges:
        src_id = name_to_id.get(src_name.lower())
        tgt_id = name_to_id.get(tgt_name.lower())
        if src_id and tgt_id:
            data.edges.append(GraphEdge(src_id, tgt_id))
            data.adjacency.setdefault(src_id, set()).add(tgt_id)
            data.adjacency.setdefault(tgt_id, set()).add(src_id)

    return data


def get_neighborhood(data: GraphData, node_id: str, hops: int = 1) -> set[str]:
    """Get all nodes within N hops of the given node."""
    visited: set[str] = {node_id}
    frontier: set[str] = {node_id}

    for _ in range(hops):
        next_frontier: set[str] = set()
        for nid in frontier:
            for neighbor in data.adjacency.get(nid, set()):
                if neighbor not in visited:
                    visited.add(neighbor)
                    next_frontier.add(neighbor)
        frontier = next_frontier

    return visited


def filter_by_type(data: GraphData, allowed_types: set[str]) -> set[str]:
    """Return node IDs matching the allowed types."""
    if not allowed_types:
        return set(data.nodes.keys())
    return {nid for nid, node in data.nodes.items() if node.etype in allowed_types}


def filter_by_scene_order(
    db: Database, project_id: int, data: GraphData, max_order: int,
) -> set[str]:
    """Return nodes active at or before the given scene order."""
    scenes = db.get_all_scenes(project_id)
    active_scene_ids = {s.id for s in scenes if s.sort_order <= max_order}
    active_scene_node_ids = {f"Scene:{sid}" for sid in active_scene_ids}

    active_char_ids: set[int] = set()
    active_place_ids: set[int] = set()
    for sid in active_scene_ids:
        active_char_ids.update(db.get_scene_character_ids(sid))
        active_place_ids.update(db.get_scene_place_ids(sid))

    active = set()
    for nid, node in data.nodes.items():
        if node.etype == "Scene" and nid in active_scene_node_ids:
            active.add(nid)
        elif node.etype == "Character" and node.entity_id in active_char_ids:
            active.add(nid)
        elif node.etype == "Place" and node.entity_id in active_place_ids:
            active.add(nid)
        elif node.etype == "PSYKE":
            active.add(nid)
        elif node.etype == "Note":
            active.add(nid)

    return active


# =============================================================================
# UI Widget
# =============================================================================

class _FocusNode(QGraphicsEllipseItem):
    """Clickable, hoverable graph node."""

    def __init__(
        self, x: float, y: float, radius: float,
        node_id: str,
        on_click: Callable[[str], None] | None = None,
        on_hover: Callable[[str, bool], None] | None = None,
    ) -> None:
        super().__init__(x - radius, y - radius, radius * 2, radius * 2)
        self.node_id = node_id
        self._on_click = on_click
        self._on_hover = on_hover
        self.setAcceptHoverEvents(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def mousePressEvent(self, event) -> None:
        if self._on_click and event.button() == Qt.MouseButton.LeftButton:
            self._on_click(self.node_id)
        super().mousePressEvent(event)

    def hoverEnterEvent(self, event) -> None:
        if self._on_hover:
            self._on_hover(self.node_id, True)
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event) -> None:
        if self._on_hover:
            self._on_hover(self.node_id, False)
        super().hoverLeaveEvent(event)


class FocusGraphView(QWidget):
    """Graph with focus-based exploration, temporal filter, and search."""

    def __init__(
        self,
        db: Database,
        project_id: int,
        on_node_selected: Callable[[str, int], None] | None = None,
    ) -> None:
        super().__init__()
        self._db = db
        self._project_id = project_id
        self._on_node_selected = on_node_selected

        self._graph_data: GraphData | None = None
        self._focus_node: str | None = None
        self._hops = 1
        self._type_filter: str = "All"
        self._temporal_enabled = False
        self._temporal_max_order: int = 9999
        self._show_future = False
        self._meaning_enabled = False
        self._meaning_data: MeaningData | None = None
        self._suggestions_visible = False
        self._suggestions = None  # GraphSuggestions | None
        self._trace_highlight: list[str] = []

        self._node_items: dict[str, _FocusNode] = {}
        self._label_items: dict[str, QGraphicsSimpleTextItem] = {}
        self._edge_items: list[QGraphicsLineItem] = []

        self._build_ui()
        self.refresh()

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # -- Toolbar ---------------------------------------------------------
        toolbar = QWidget()
        toolbar.setObjectName("graphToolbar")
        tb = QHBoxLayout(toolbar)
        tb.setContentsMargins(10, 6, 10, 6)
        tb.setSpacing(8)

        self._search_input = QLineEdit()
        self._search_input.setPlaceholderText("Search node...")
        self._search_input.setMaximumWidth(160)
        self._search_input.returnPressed.connect(self._on_search)
        tb.addWidget(self._search_input)

        self._clear_btn = QPushButton("Clear Focus")
        self._clear_btn.setFlat(True)
        self._clear_btn.clicked.connect(self.clear_focus)
        tb.addWidget(self._clear_btn)

        tb.addSpacing(12)

        self._hops_check = QCheckBox("2-hop")
        self._hops_check.setToolTip("Expand to 2-hop neighbors")
        self._hops_check.toggled.connect(self._on_hops_toggled)
        tb.addWidget(self._hops_check)

        tb.addSpacing(12)

        tb.addWidget(QLabel("Type:"))
        self._type_combo = QComboBox()
        self._type_combo.addItems(["All", "Character", "Place", "Scene", "Note", "PSYKE"])
        self._type_combo.currentTextChanged.connect(self._on_type_changed)
        tb.addWidget(self._type_combo)

        tb.addSpacing(12)

        self._temporal_check = QCheckBox("Temporal")
        self._temporal_check.setToolTip("Filter by story progression")
        self._temporal_check.toggled.connect(self._on_temporal_toggled)
        tb.addWidget(self._temporal_check)

        self._future_check = QCheckBox("Show future")
        self._future_check.setToolTip("Dim future nodes instead of hiding")
        self._future_check.toggled.connect(self._on_future_toggled)
        self._future_check.setEnabled(False)
        tb.addWidget(self._future_check)

        tb.addSpacing(12)

        self._meaning_check = QCheckBox("Meaning")
        self._meaning_check.setToolTip("Show narrative insight: state, importance, arcs")
        self._meaning_check.toggled.connect(self._on_meaning_toggled)
        tb.addWidget(self._meaning_check)

        tb.addSpacing(12)

        self._suggest_check = QCheckBox("Suggestions")
        self._suggest_check.setToolTip("Show graph-driven narrative suggestions")
        self._suggest_check.toggled.connect(self._on_suggestions_toggled)
        tb.addWidget(self._suggest_check)

        tb.addStretch()
        outer.addWidget(toolbar)

        # -- Main area: graph + suggestion panel -----------------------------
        content_area = QWidget()
        content_layout = QHBoxLayout(content_area)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)

        self._gscene = QGraphicsScene()
        self._gview = QGraphicsView(self._gscene)
        self._gview.setObjectName("focusGraphView")
        self._gview.setRenderHints(self._gview.renderHints())
        content_layout.addWidget(self._gview, stretch=3)

        self._suggest_panel = QFrame()
        self._suggest_panel.setObjectName("suggestPanel")
        self._suggest_panel.setMaximumWidth(280)
        self._suggest_panel.setMinimumWidth(200)
        sp_layout = QVBoxLayout(self._suggest_panel)
        sp_layout.setContentsMargins(8, 8, 8, 8)
        sp_layout.setSpacing(4)
        self._suggest_panel.hide()
        content_layout.addWidget(self._suggest_panel, stretch=1)

        outer.addWidget(content_area)

    # -- Data loading --------------------------------------------------------

    def refresh(self) -> None:
        self._graph_data = build_graph_data(self._db, self._project_id)
        self._rebuild_view()

    def _rebuild_view(self) -> None:
        self._gscene.clear()
        self._node_items.clear()
        self._label_items.clear()
        self._edge_items.clear()

        if not self._graph_data or not self._graph_data.nodes:
            text = self._gscene.addSimpleText("No graph data. Add [[links]] or PSYKE relations.")
            text.setPos(0, 0)
            return

        visible = self._compute_visible_nodes()
        if not visible:
            text = self._gscene.addSimpleText("No nodes match current filters.")
            text.setPos(0, 0)
            return

        temporal_active = None
        if self._temporal_enabled:
            temporal_active = filter_by_scene_order(
                self._db, self._project_id, self._graph_data, self._temporal_max_order,
            )

        if self._meaning_enabled:
            self._meaning_data = compute_meaning(self._db, self._project_id, visible)
        else:
            self._meaning_data = None

        positions = self._layout_nodes(visible)

        if self._meaning_data:
            for arc_link in self._meaning_data.arc_links:
                src_pos = positions.get(arc_link.source_id)
                tgt_pos = positions.get(arc_link.target_id)
                if src_pos and tgt_pos:
                    self._draw_arc_link(src_pos, tgt_pos, arc_link.plotline)

        for edge in self._graph_data.edges:
            if edge.source_id in visible and edge.target_id in visible:
                src_pos = positions.get(edge.source_id)
                tgt_pos = positions.get(edge.target_id)
                if src_pos and tgt_pos:
                    self._draw_edge(src_pos, tgt_pos, edge)

        if self._meaning_data:
            for src_id, tgt_id in self._meaning_data.flow_pairs:
                src_pos = positions.get(src_id)
                tgt_pos = positions.get(tgt_id)
                if src_pos and tgt_pos:
                    self._draw_flow_arrow(src_pos, tgt_pos)

        for nid in visible:
            pos = positions[nid]
            node = self._graph_data.nodes[nid]
            is_focal = (nid == self._focus_node)
            is_dimmed = (
                temporal_active is not None
                and nid not in temporal_active
                and self._show_future
            )
            node_meaning = (
                self._meaning_data.node_meanings.get(nid) if self._meaning_data else None
            )
            self._draw_node(pos[0], pos[1], node, is_focal, is_dimmed, node_meaning)

    def _compute_visible_nodes(self) -> set[str]:
        if not self._graph_data:
            return set()

        visible = set(self._graph_data.nodes.keys())

        if self._focus_node and self._focus_node in self._graph_data.nodes:
            visible = get_neighborhood(self._graph_data, self._focus_node, self._hops)

        if self._type_filter != "All":
            type_nodes = filter_by_type(self._graph_data, {self._type_filter})
            visible = visible & type_nodes

        if self._temporal_enabled and not self._show_future:
            temporal_active = filter_by_scene_order(
                self._db, self._project_id, self._graph_data, self._temporal_max_order,
            )
            visible = visible & temporal_active

        return visible

    def _layout_nodes(self, visible: set[str]) -> dict[str, tuple[float, float]]:
        nodes_list = sorted(visible)
        count = len(nodes_list)
        if count == 0:
            return {}

        if self._focus_node and self._focus_node in visible:
            center_id = self._focus_node
            others = [n for n in nodes_list if n != center_id]
            positions = {center_id: (0.0, 0.0)}
            radius = max(_GRAPH_RADIUS, len(others) * 18)
            for i, nid in enumerate(others):
                angle = 2 * math.pi * i / max(len(others), 1) - math.pi / 2
                x = radius * math.cos(angle)
                y = radius * math.sin(angle)
                positions[nid] = (x, y)
            return positions

        radius = max(_GRAPH_RADIUS, count * 18)
        positions: dict[str, tuple[float, float]] = {}
        for i, nid in enumerate(nodes_list):
            angle = 2 * math.pi * i / count - math.pi / 2
            x = radius * math.cos(angle)
            y = radius * math.sin(angle)
            positions[nid] = (x, y)
        return positions

    # -- Drawing -------------------------------------------------------------

    def _draw_node(
        self, x: float, y: float, node: GraphNode,
        is_focal: bool, is_dimmed: bool,
        meaning: NodeMeaning | None = None,
    ) -> None:
        radius = _FOCUS_RADIUS if is_focal else _NODE_RADIUS
        color_hex = _TYPE_COLORS.get(node.etype, "#9e9e9e")

        if meaning:
            radius += importance_radius_delta(meaning.importance)
            if meaning.state_warmth != "neutral" and node.etype == "Character":
                color_hex = state_color(meaning.state_warmth)
            if meaning.psyke_glow and node.etype == "PSYKE":
                color_hex = QColor(color_hex).lighter(130).name()

        color = QColor(color_hex)

        if meaning and meaning.is_dead_zone:
            color.setHsvF(color.hueF(), color.saturationF() * 0.5, color.valueF())

        if is_dimmed:
            color.setAlphaF(_DIM_OPACITY)

        ellipse = _FocusNode(
            x, y, radius, node.node_id,
            on_click=self._on_node_click,
            on_hover=self._on_node_hover,
        )
        ellipse.setBrush(QBrush(color))
        pen_color = color.darker(120) if not is_dimmed else QColor(color_hex)
        pen_color.setAlphaF(0.4 if is_dimmed else 1.0)
        pen_width = 3 if is_focal else 2
        if meaning and meaning.state_warmth != "neutral" and node.etype == "Character":
            pen_color = QColor(state_color(meaning.state_warmth))
            pen_width = 3
        ellipse.setPen(QPen(pen_color, pen_width))
        ellipse.setZValue(2 if is_focal else 1)
        self._gscene.addItem(ellipse)
        self._node_items[node.node_id] = ellipse

        label = QGraphicsSimpleTextItem(node.name)
        font = QFont()
        font.setPointSize(9 if not is_focal else 10)
        if is_focal:
            font.setBold(True)
        label.setFont(font)
        text_color = QColor(theme.TEXT_PRIMARY)
        if is_dimmed:
            text_color.setAlphaF(_DIM_OPACITY)
        label.setBrush(QBrush(text_color))
        rect = label.boundingRect()
        label.setPos(x - rect.width() / 2, y + radius + 4)
        label.setZValue(3)
        self._gscene.addItem(label)
        self._label_items[node.node_id] = label

    def _draw_edge(
        self, src: tuple[float, float], tgt: tuple[float, float],
        edge: GraphEdge,
    ) -> None:
        is_highlight = (
            self._focus_node is not None
            and (edge.source_id == self._focus_node or edge.target_id == self._focus_node)
        )
        color = QColor(_EDGE_HIGHLIGHT if is_highlight else _EDGE_COLOR)
        width = 2.0 if is_highlight else 1.2
        line = QGraphicsLineItem(src[0], src[1], tgt[0], tgt[1])
        line.setPen(QPen(color, width))
        line.setZValue(0)
        self._gscene.addItem(line)
        self._edge_items.append(line)

    def _draw_arc_link(
        self, src: tuple[float, float], tgt: tuple[float, float], plotline: str,
    ) -> None:
        color = QColor(_arc_color(plotline))
        color.setAlphaF(0.3)
        pen = QPen(color, 1.5, Qt.PenStyle.DashLine)
        line = QGraphicsLineItem(src[0], src[1], tgt[0], tgt[1])
        line.setPen(pen)
        line.setZValue(-1)
        self._gscene.addItem(line)

    def _draw_flow_arrow(
        self, src: tuple[float, float], tgt: tuple[float, float],
    ) -> None:
        dx = tgt[0] - src[0]
        dy = tgt[1] - src[1]
        length = math.sqrt(dx * dx + dy * dy)
        if length < 1:
            return
        ux, uy = dx / length, dy / length
        mid_x = (src[0] + tgt[0]) / 2
        mid_y = (src[1] + tgt[1]) / 2

        arrow_size = 4.0
        tip = QPointF(mid_x + ux * arrow_size, mid_y + uy * arrow_size)
        left = QPointF(
            mid_x - ux * arrow_size + uy * arrow_size * 0.6,
            mid_y - uy * arrow_size - ux * arrow_size * 0.6,
        )
        right = QPointF(
            mid_x - ux * arrow_size - uy * arrow_size * 0.6,
            mid_y - uy * arrow_size + ux * arrow_size * 0.6,
        )

        polygon = QPolygonF([tip, left, right])
        arrow = QGraphicsPolygonItem(polygon)
        color = QColor(theme.TEXT_MUTED)
        color.setAlphaF(0.4)
        arrow.setBrush(QBrush(color))
        arrow.setPen(QPen(Qt.PenStyle.NoPen))
        arrow.setZValue(-1)
        self._gscene.addItem(arrow)

    # -- Interaction ---------------------------------------------------------

    def _on_node_click(self, node_id: str) -> None:
        if self._focus_node == node_id:
            self.clear_focus()
        else:
            self.focus_on(node_id)

    def _on_node_hover(self, node_id: str, entered: bool) -> None:
        if entered:
            neighbors = self._graph_data.adjacency.get(node_id, set()) if self._graph_data else set()
            highlight_set = {node_id} | neighbors
            for nid, item in self._node_items.items():
                if nid in highlight_set:
                    item.setOpacity(1.0)
                else:
                    item.setOpacity(0.3)
            for nid, label in self._label_items.items():
                if nid in highlight_set:
                    label.setOpacity(1.0)
                else:
                    label.setOpacity(0.3)
        else:
            for item in self._node_items.values():
                item.setOpacity(1.0)
            for label in self._label_items.values():
                label.setOpacity(1.0)

    def focus_on(self, node_id: str) -> None:
        self._focus_node = node_id
        self._rebuild_view()
        if self._suggestions_visible:
            self._refresh_suggestions()
        if self._on_node_selected and self._graph_data:
            node = self._graph_data.nodes.get(node_id)
            if node:
                self._on_node_selected(node.etype, node.entity_id)

    def clear_focus(self) -> None:
        self._focus_node = None
        self._rebuild_view()
        if self._suggestions_visible:
            self._refresh_suggestions()

    def get_focus_node(self) -> str | None:
        return self._focus_node

    # -- Search --------------------------------------------------------------

    def _on_search(self) -> None:
        query = self._search_input.text().strip().lower()
        if not query or not self._graph_data:
            return
        for nid, node in self._graph_data.nodes.items():
            if query in node.name.lower():
                self.focus_on(nid)
                return

    # -- Filters -------------------------------------------------------------

    def _on_hops_toggled(self, checked: bool) -> None:
        self._hops = 2 if checked else 1
        if self._focus_node:
            self._rebuild_view()

    def _on_type_changed(self, text: str) -> None:
        self._type_filter = text
        self._rebuild_view()

    def _on_temporal_toggled(self, checked: bool) -> None:
        self._temporal_enabled = checked
        self._future_check.setEnabled(checked)
        self._rebuild_view()

    def _on_future_toggled(self, checked: bool) -> None:
        self._show_future = checked
        self._rebuild_view()

    def _on_meaning_toggled(self, checked: bool) -> None:
        self._meaning_enabled = checked
        self._rebuild_view()

    def _on_suggestions_toggled(self, checked: bool) -> None:
        self._suggestions_visible = checked
        if checked:
            self._suggest_panel.show()
            self._refresh_suggestions()
        else:
            self._suggest_panel.hide()
            self._suggestions = None
            self.clear_trace()

    def set_temporal_max_order(self, order: int) -> None:
        self._temporal_max_order = order
        if self._temporal_enabled:
            self._rebuild_view()

    # -- Suggestion panel ----------------------------------------------------

    def _refresh_suggestions(self) -> None:
        """Regenerate suggestions based on current focus/context."""
        layout = self._suggest_panel.layout()
        while layout.count():
            child = layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        scene_id = self._get_focal_scene_id()
        if scene_id is None:
            lbl = QLabel("Focus on a scene node to see suggestions.")
            lbl.setObjectName("suggestHint")
            lbl.setWordWrap(True)
            layout.addWidget(lbl)
            layout.addStretch()
            self._suggestions = None
            return

        from storyplanner.graph_suggestions import generate_graph_suggestions
        self._suggestions = generate_graph_suggestions(
            self._db, self._project_id, scene_id,
        )

        if not self._suggestions.suggestions:
            lbl = QLabel("No suggestions for this scene.")
            lbl.setObjectName("suggestHint")
            lbl.setWordWrap(True)
            layout.addWidget(lbl)
            layout.addStretch()
            return

        header = QLabel("Next Narrative Possibilities")
        header.setObjectName("suggestHeader")
        layout.addWidget(header)

        for idx, suggestion in enumerate(self._suggestions.suggestions):
            btn = QPushButton(f"{suggestion.category}")
            btn.setObjectName("suggestBtn")
            btn.setToolTip(
                f"{suggestion.text}\n\nTrace: {', '.join(suggestion.trace_nodes)}\n"
                f"Reason: {suggestion.reason}"
            )
            btn.setFlat(True)
            btn.clicked.connect(lambda _=False, s=suggestion: self._on_suggestion_clicked(s))
            layout.addWidget(btn)

            desc = QLabel(f"\u2192 {suggestion.text}")
            desc.setObjectName("suggestDesc")
            desc.setWordWrap(True)
            layout.addWidget(desc)

        layout.addStretch()

    def _on_suggestion_clicked(self, suggestion) -> None:
        """Focus graph on suggestion's trace nodes."""
        self.clear_trace()
        if suggestion.trace_nodes:
            primary = suggestion.trace_nodes[0]
            if primary in (self._graph_data.nodes if self._graph_data else {}):
                self.focus_on(primary)
            self.highlight_trace(suggestion.trace_nodes)

    def highlight_trace(self, node_ids: list[str]) -> None:
        """Highlight specific nodes as suggestion trace."""
        self._trace_highlight = list(node_ids)
        accent = QColor(_EDGE_HIGHLIGHT)
        for nid in node_ids:
            item = self._node_items.get(nid)
            if item:
                item.setPen(QPen(accent, 3))
                item.setZValue(5)
            label = self._label_items.get(nid)
            if label:
                label.setBrush(QBrush(accent))

    def clear_trace(self) -> None:
        """Remove trace highlights."""
        for nid in self._trace_highlight:
            item = self._node_items.get(nid)
            if item and self._graph_data:
                node = self._graph_data.nodes.get(nid)
                if node:
                    color_hex = _TYPE_COLORS.get(node.etype, "#9e9e9e")
                    item.setPen(QPen(QColor(color_hex).darker(120), 2))
                    item.setZValue(1)
            label = self._label_items.get(nid)
            if label:
                label.setBrush(QBrush(QColor(theme.TEXT_PRIMARY)))
        self._trace_highlight = []

    def _get_focal_scene_id(self) -> int | None:
        """Get a scene ID for suggestion context."""
        if self._focus_node and self._focus_node.startswith("Scene:"):
            try:
                return int(self._focus_node.split(":")[1])
            except (ValueError, IndexError):
                pass
        if self._graph_data:
            for nid, node in self._graph_data.nodes.items():
                if node.etype == "Scene":
                    return node.entity_id
        return None

    # -- Public API ----------------------------------------------------------

    def get_visible_count(self) -> int:
        return len(self._node_items)

    def get_type_filter(self) -> str:
        return self._type_filter

    def is_temporal_enabled(self) -> bool:
        return self._temporal_enabled

    def is_meaning_enabled(self) -> bool:
        return self._meaning_enabled

    def get_meaning_data(self) -> MeaningData | None:
        return self._meaning_data

    def is_suggestions_visible(self) -> bool:
        return self._suggestions_visible

    def get_suggestions(self):
        return self._suggestions

    def get_trace_highlight(self) -> list[str]:
        return list(self._trace_highlight)
