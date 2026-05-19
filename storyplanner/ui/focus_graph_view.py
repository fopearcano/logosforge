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
    QGraphicsPathItem,
    QGraphicsPolygonItem,
    QGraphicsRectItem,
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

# -- Semantic node kinds (subtype-aware) --------------------------------------
# Visible node kinds the user can toggle via the Layers panel. Each kind maps
# to a distinct shape + color so types are recognizable at a glance.

NODE_KIND_CHARACTER = "character"
NODE_KIND_PLACE = "place"
NODE_KIND_OBJECT = "object"
NODE_KIND_THEME = "theme"
NODE_KIND_LORE = "lore"
NODE_KIND_SCENE = "scene"
NODE_KIND_ACT = "act"
NODE_KIND_NOTE = "note"
NODE_KIND_OTHER = "other"

LAYER_KINDS: tuple[str, ...] = (
    NODE_KIND_CHARACTER, NODE_KIND_PLACE, NODE_KIND_OBJECT,
    NODE_KIND_THEME, NODE_KIND_LORE, NODE_KIND_SCENE,
    NODE_KIND_ACT, NODE_KIND_NOTE, NODE_KIND_OTHER,
)

SKELETON_LAYERS: frozenset[str] = frozenset({
    NODE_KIND_CHARACTER, NODE_KIND_THEME, NODE_KIND_ACT,
})

_KIND_COLORS: dict[str, str] = {
    NODE_KIND_CHARACTER: "#42a5f5",
    NODE_KIND_PLACE: "#66bb6a",
    NODE_KIND_OBJECT: "#f59e0b",
    NODE_KIND_THEME: "#c084fc",
    NODE_KIND_LORE: "#22d3ee",
    NODE_KIND_SCENE: "#ffa726",
    NODE_KIND_ACT: "#94a3b8",
    NODE_KIND_NOTE: "#ab47bc",
    NODE_KIND_OTHER: "#9e9e9e",
}

_KIND_SHAPES: dict[str, str] = {
    NODE_KIND_CHARACTER: "circle",
    NODE_KIND_PLACE: "square",
    NODE_KIND_OBJECT: "triangle",
    NODE_KIND_THEME: "diamond",
    NODE_KIND_LORE: "hexagon",
    NODE_KIND_SCENE: "rounded_rect",
    NODE_KIND_ACT: "act_band",
    NODE_KIND_NOTE: "small_circle",
    NODE_KIND_OTHER: "circle",
}

# -- Semantic edge kinds ------------------------------------------------------

EDGE_LINK = "link"                  # generic / unknown
EDGE_MENTION = "mention"            # [[text-link]] reference
EDGE_PSYKE_RELATION = "psyke_relation"   # PSYKE entry ↔ related entry
EDGE_PARTICIPATION = "participation"     # scene ↔ character / place
EDGE_CONTAINMENT = "containment"         # Act → Scene

EDGE_STYLE: dict[str, dict] = {
    EDGE_PARTICIPATION: {"color": "#4ade80", "width": 1.3, "dash": "solid"},
    EDGE_CONTAINMENT:   {"color": "#60a5fa", "width": 2.4, "dash": "solid"},
    EDGE_PSYKE_RELATION:{"color": "#c084fc", "width": 1.6, "dash": "solid"},
    EDGE_MENTION:       {"color": "#94a3b8", "width": 0.9, "dash": "dash"},
    EDGE_LINK:          {"color": "#4a5568", "width": 1.2, "dash": "solid"},
}

_PSYKE_SUBTYPE_MAP = {
    "character": NODE_KIND_CHARACTER,
    "place": NODE_KIND_PLACE,
    "object": NODE_KIND_OBJECT,
    "theme": NODE_KIND_THEME,
    "lore": NODE_KIND_LORE,
    "other": NODE_KIND_OTHER,
}


def node_kind(node: "GraphNode") -> str:
    """Resolve the semantic kind of a node — uses subtype when available."""
    if node.subtype:
        return node.subtype
    etype = (node.etype or "").lower()
    if etype in {NODE_KIND_CHARACTER, NODE_KIND_PLACE, NODE_KIND_SCENE,
                 NODE_KIND_NOTE, NODE_KIND_ACT}:
        return etype
    if node.etype == "PSYKE":
        return NODE_KIND_OTHER
    return NODE_KIND_OTHER


_NODE_RADIUS = 22
_FOCUS_RADIUS = 28
_GRAPH_RADIUS = 200
_EDGE_COLOR = "#4a5568"
_EDGE_HIGHLIGHT = "#4ade80"
_DIM_OPACITY = 0.25

# Zoom thresholds — below these, parts of the graph are progressively hidden.
_ZOOM_HIDE_LABELS = 0.6
_ZOOM_HIDE_MENTIONS = 0.5
_ZOOM_HIDE_WEAK_EDGES = 0.3

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
    subtype: str = ""  # e.g. "theme", "lore", "object" for PSYKE entries


@dataclass
class GraphEdge:
    """A connection between two nodes."""

    source_id: str
    target_id: str
    edge_type: str = EDGE_LINK


@dataclass
class GraphData:
    """Full graph data for a project."""

    nodes: dict[str, GraphNode] = field(default_factory=dict)
    edges: list[GraphEdge] = field(default_factory=list)
    adjacency: dict[str, set[str]] = field(default_factory=dict)


def build_graph_data(db: Database, project_id: int) -> GraphData:
    """Build structured graph data from DB link graph + PSYKE relations,
    enriched with subtypes, Act clusters, and semantic edge types."""
    raw_nodes, raw_edges = db.build_link_graph(project_id)

    data = GraphData()

    for etype, eid, name in raw_nodes:
        node_id = f"{etype}:{eid}"
        data.nodes[node_id] = GraphNode(node_id, etype, eid, name)
        data.adjacency.setdefault(node_id, set())

    psyke_entries = db.get_all_psyke_entries(project_id)
    for entry in psyke_entries:
        node_id = f"PSYKE:{entry.id}"
        sub = _PSYKE_SUBTYPE_MAP.get((entry.entry_type or "").lower(), NODE_KIND_OTHER)
        if node_id not in data.nodes:
            data.nodes[node_id] = GraphNode(
                node_id, "PSYKE", entry.id, entry.name, subtype=sub,
            )
            data.adjacency.setdefault(node_id, set())
        else:
            data.nodes[node_id].subtype = sub

        related = db.get_related_psyke_entries(entry.id)
        for rel in related:
            rel_id = f"PSYKE:{rel.id}"
            rel_sub = _PSYKE_SUBTYPE_MAP.get((rel.entry_type or "").lower(), NODE_KIND_OTHER)
            if rel_id not in data.nodes:
                data.nodes[rel_id] = GraphNode(
                    rel_id, "PSYKE", rel.id, rel.name, subtype=rel_sub,
                )
                data.adjacency.setdefault(rel_id, set())
            data.edges.append(GraphEdge(node_id, rel_id, edge_type=EDGE_PSYKE_RELATION))
            data.adjacency.setdefault(node_id, set()).add(rel_id)
            data.adjacency.setdefault(rel_id, set()).add(node_id)

    name_to_id: dict[str, str] = {}
    for nid, node in data.nodes.items():
        name_to_id[node.name.lower()] = nid

    for src_name, tgt_name in raw_edges:
        src_id = name_to_id.get(src_name.lower())
        tgt_id = name_to_id.get(tgt_name.lower())
        if src_id and tgt_id:
            data.edges.append(GraphEdge(src_id, tgt_id, edge_type=EDGE_MENTION))
            data.adjacency.setdefault(src_id, set()).add(tgt_id)
            data.adjacency.setdefault(tgt_id, set()).add(src_id)

    # Participation: scene ↔ character / place from the junction tables.
    # To avoid polluting the graph with isolated scenes (no participants, no
    # mentions, no act), we only ADD a scene node here if it has at least one
    # participant, place, or act assignment. Scenes already in data.nodes
    # (because they were referenced via [[link]]) are kept as-is.
    char_name_by_id = {c.id: c.name for c in db.get_all_characters(project_id)}
    place_name_by_id = {p.id: p.name for p in db.get_all_places(project_id)}
    scenes = db.get_all_scenes(project_id)
    for scene in scenes:
        scene_id = f"Scene:{scene.id}"
        char_ids = db.get_scene_character_ids(scene.id)
        place_ids = db.get_scene_place_ids(scene.id)
        has_act = bool((scene.act or "").strip())
        has_participants = bool(char_ids) or bool(place_ids) or has_act
        already_in_graph = scene_id in data.nodes
        if not already_in_graph and not has_participants:
            continue
        if not already_in_graph:
            data.nodes[scene_id] = GraphNode(scene_id, "Scene", scene.id, scene.title)
            data.adjacency.setdefault(scene_id, set())
        for cid in char_ids:
            char_id = f"Character:{cid}"
            if char_id not in data.nodes:
                name = char_name_by_id.get(cid, f"Character {cid}")
                data.nodes[char_id] = GraphNode(char_id, "Character", cid, name)
                data.adjacency.setdefault(char_id, set())
            data.edges.append(GraphEdge(scene_id, char_id, edge_type=EDGE_PARTICIPATION))
            data.adjacency.setdefault(scene_id, set()).add(char_id)
            data.adjacency.setdefault(char_id, set()).add(scene_id)
        for pid in place_ids:
            place_id = f"Place:{pid}"
            if place_id not in data.nodes:
                name = place_name_by_id.get(pid, f"Place {pid}")
                data.nodes[place_id] = GraphNode(place_id, "Place", pid, name)
                data.adjacency.setdefault(place_id, set())
            data.edges.append(GraphEdge(scene_id, place_id, edge_type=EDGE_PARTICIPATION))
            data.adjacency.setdefault(scene_id, set()).add(place_id)
            data.adjacency.setdefault(place_id, set()).add(scene_id)

    # Act cluster nodes — one per distinct non-empty scene.act.  We only emit
    # an act node if at least one scene with that act ended up in the graph.
    act_order: dict[str, int] = {}
    for scene in scenes:
        scene_id = f"Scene:{scene.id}"
        if scene_id not in data.nodes:
            continue
        act = (scene.act or "").strip()
        if act and act not in act_order:
            act_order[act] = len(act_order) + 1
    for act, idx in act_order.items():
        act_id = f"Act:{idx}"
        data.nodes[act_id] = GraphNode(act_id, "Act", idx, act, subtype=NODE_KIND_ACT)
        data.adjacency.setdefault(act_id, set())
    for scene in scenes:
        scene_id = f"Scene:{scene.id}"
        if scene_id not in data.nodes:
            continue
        act = (scene.act or "").strip()
        if not act:
            continue
        act_id = f"Act:{act_order[act]}"
        data.edges.append(GraphEdge(act_id, scene_id, edge_type=EDGE_CONTAINMENT))
        data.adjacency[act_id].add(scene_id)
        data.adjacency.setdefault(scene_id, set()).add(act_id)

    return data


def default_skeleton_layers() -> frozenset[str]:
    """The minimal narrative skeleton: characters, themes, acts."""
    return SKELETON_LAYERS


def filter_by_layers(data: GraphData, layers: set[str]) -> set[str]:
    """Return node IDs whose semantic kind is in *layers*.

    Empty set means 'no layers active' → returns empty.
    """
    if not layers:
        return set()
    return {nid for nid, node in data.nodes.items() if node_kind(node) in layers}


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

class _NodeInteractionMixin:
    """Click + hover behaviour shared across node shapes."""

    def _init_interaction(
        self, node_id: str,
        on_click: Callable[[str], None] | None,
        on_hover: Callable[[str, bool], None] | None,
    ) -> None:
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


class _FocusNode(_NodeInteractionMixin, QGraphicsEllipseItem):
    """Clickable, hoverable graph node — ellipse shape (back-compat)."""

    def __init__(
        self, x: float, y: float, radius: float,
        node_id: str,
        on_click: Callable[[str], None] | None = None,
        on_hover: Callable[[str, bool], None] | None = None,
    ) -> None:
        QGraphicsEllipseItem.__init__(
            self, x - radius, y - radius, radius * 2, radius * 2,
        )
        self._init_interaction(node_id, on_click, on_hover)


class _PolygonNode(_NodeInteractionMixin, QGraphicsPolygonItem):
    """Clickable, hoverable polygon node (triangle, diamond, hexagon)."""

    def __init__(
        self, polygon: "QPolygonF",
        node_id: str,
        on_click: Callable[[str], None] | None = None,
        on_hover: Callable[[str, bool], None] | None = None,
    ) -> None:
        QGraphicsPolygonItem.__init__(self, polygon)
        self._init_interaction(node_id, on_click, on_hover)


class _RectNode(_NodeInteractionMixin, QGraphicsRectItem):
    """Clickable, hoverable rect node (square, scene)."""

    def __init__(
        self, x: float, y: float, w: float, h: float,
        node_id: str,
        on_click: Callable[[str], None] | None = None,
        on_hover: Callable[[str, bool], None] | None = None,
    ) -> None:
        QGraphicsRectItem.__init__(self, x - w / 2, y - h / 2, w, h)
        self._init_interaction(node_id, on_click, on_hover)


def _make_shape_node(
    kind: str, x: float, y: float, radius: float, node_id: str,
    on_click: Callable[[str], None] | None,
    on_hover: Callable[[str, bool], None] | None,
):
    """Factory: return a node graphics-item matching the kind's shape."""
    shape = _KIND_SHAPES.get(kind, "circle")

    if shape == "small_circle":
        return _FocusNode(x, y, radius * 0.7, node_id, on_click, on_hover)
    if shape == "circle":
        return _FocusNode(x, y, radius, node_id, on_click, on_hover)
    if shape == "square":
        side = radius * 1.7
        return _RectNode(x, y, side, side, node_id, on_click, on_hover)
    if shape == "rounded_rect":
        return _RectNode(x, y, radius * 2.2, radius * 1.5, node_id, on_click, on_hover)
    if shape == "act_band":
        return _RectNode(x, y, radius * 3.0, radius * 1.4, node_id, on_click, on_hover)
    if shape == "triangle":
        h = radius * 1.7
        poly = QPolygonF([
            QPointF(x, y - h),
            QPointF(x - h * 0.9, y + h * 0.7),
            QPointF(x + h * 0.9, y + h * 0.7),
        ])
        return _PolygonNode(poly, node_id, on_click, on_hover)
    if shape == "diamond":
        r = radius * 1.2
        poly = QPolygonF([
            QPointF(x, y - r), QPointF(x + r, y),
            QPointF(x, y + r), QPointF(x - r, y),
        ])
        return _PolygonNode(poly, node_id, on_click, on_hover)
    if shape == "hexagon":
        r = radius
        pts = []
        for i in range(6):
            angle = math.pi / 3 * i - math.pi / 2
            pts.append(QPointF(x + r * math.cos(angle), y + r * math.sin(angle)))
        return _PolygonNode(QPolygonF(pts), node_id, on_click, on_hover)
    # Fallback
    return _FocusNode(x, y, radius, node_id, on_click, on_hover)


class _ZoomGraphicsView(QGraphicsView):
    """QGraphicsView that reports zoom changes to the parent on wheel events."""

    def __init__(self, scene, on_zoom: Callable[[float], None] | None = None) -> None:
        super().__init__(scene)
        self._on_zoom = on_zoom
        self._zoom = 1.0
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)

    def wheelEvent(self, event) -> None:
        if event.angleDelta().y() > 0:
            factor = 1.15
        else:
            factor = 1 / 1.15
        new_zoom = self._zoom * factor
        # Clamp to a sane range.
        new_zoom = max(0.1, min(5.0, new_zoom))
        actual = new_zoom / self._zoom
        self._zoom = new_zoom
        self.scale(actual, actual)
        if self._on_zoom:
            self._on_zoom(self._zoom)


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
        # Layers panel — which semantic kinds are visible.  Default: all.
        self._active_layers: set[str] = set(LAYER_KINDS)
        self._layer_checks: dict[str, QCheckBox] = {}
        self._zoom: float = 1.0

        self._node_items: dict[str, object] = {}
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

        # Type combo kept for back-compat with the old single-type filter.
        # Hidden by default — superseded by the Layers panel below.
        self._type_combo = QComboBox()
        self._type_combo.addItems(["All", "Character", "Place", "Scene", "Note", "PSYKE"])
        self._type_combo.currentTextChanged.connect(self._on_type_changed)
        self._type_combo.setVisible(False)
        tb.addWidget(self._type_combo)

        self._skeleton_btn = QPushButton("Skeleton")
        self._skeleton_btn.setCheckable(True)
        self._skeleton_btn.setToolTip(
            "Narrative skeleton — Characters + Themes + Acts only"
        )
        self._skeleton_btn.toggled.connect(self._on_skeleton_toggled)
        tb.addWidget(self._skeleton_btn)

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

        # -- Main area: layers panel + graph + suggestion panel --------------
        content_area = QWidget()
        content_layout = QHBoxLayout(content_area)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)

        self._layers_panel = self._build_layers_panel()
        content_layout.addWidget(self._layers_panel)

        self._gscene = QGraphicsScene()
        self._gview = _ZoomGraphicsView(self._gscene, on_zoom=self._on_zoom)
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

    # -- Layers panel --------------------------------------------------------

    def _build_layers_panel(self) -> QFrame:
        """Vertical column of layer toggles — one checkbox per semantic kind."""
        panel = QFrame()
        panel.setObjectName("graphLayersPanel")
        panel.setFixedWidth(132)
        lay = QVBoxLayout(panel)
        lay.setContentsMargins(8, 8, 8, 8)
        lay.setSpacing(4)

        header = QLabel("Layers")
        header.setStyleSheet(
            f"color: {theme.TEXT_SECONDARY}; font-size: 11px; font-weight: bold;"
        )
        lay.addWidget(header)

        labels = {
            NODE_KIND_CHARACTER: "Characters",
            NODE_KIND_PLACE: "Places",
            NODE_KIND_OBJECT: "Objects",
            NODE_KIND_THEME: "Themes",
            NODE_KIND_LORE: "Lore",
            NODE_KIND_SCENE: "Scenes",
            NODE_KIND_ACT: "Acts",
            NODE_KIND_NOTE: "Notes",
            NODE_KIND_OTHER: "Other",
        }
        for kind in LAYER_KINDS:
            cb = QCheckBox(labels[kind])
            cb.setChecked(True)
            cb.setStyleSheet(
                f"QCheckBox {{ color: {theme.TEXT_PRIMARY}; font-size: 11px; }}"
            )
            cb.toggled.connect(lambda checked, k=kind: self._on_layer_toggled(k, checked))
            lay.addWidget(cb)
            self._layer_checks[kind] = cb

        lay.addStretch()
        return panel

    def _on_layer_toggled(self, kind: str, checked: bool) -> None:
        if checked:
            self._active_layers.add(kind)
        else:
            self._active_layers.discard(kind)
        # Skeleton button stays pressed only while skeleton-set is active.
        if self._skeleton_btn.isChecked() and self._active_layers != set(SKELETON_LAYERS):
            self._skeleton_btn.blockSignals(True)
            self._skeleton_btn.setChecked(False)
            self._skeleton_btn.blockSignals(False)
        self._rebuild_view()

    def _on_skeleton_toggled(self, checked: bool) -> None:
        target = set(SKELETON_LAYERS) if checked else set(LAYER_KINDS)
        self._active_layers = target
        for kind, cb in self._layer_checks.items():
            cb.blockSignals(True)
            cb.setChecked(kind in target)
            cb.blockSignals(False)
        self._rebuild_view()

    # -- Zoom + culling ------------------------------------------------------

    def _on_zoom(self, zoom: float) -> None:
        self._zoom = zoom
        self._apply_zoom_culling()

    def _apply_zoom_culling(self) -> None:
        """Hide labels and weak edges progressively as the user zooms out."""
        show_labels = self._zoom >= _ZOOM_HIDE_LABELS
        for label in self._label_items.values():
            label.setVisible(show_labels)

        for edge_item in self._edge_items:
            etype = edge_item.data(0)
            if self._zoom < _ZOOM_HIDE_WEAK_EDGES:
                edge_item.setVisible(etype == EDGE_CONTAINMENT)
            elif self._zoom < _ZOOM_HIDE_MENTIONS:
                edge_item.setVisible(etype != EDGE_MENTION)
            else:
                edge_item.setVisible(True)

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

        # Layer mask — restrict to enabled semantic kinds.
        if self._active_layers != set(LAYER_KINDS):
            layer_nodes = filter_by_layers(self._graph_data, self._active_layers)
            visible = visible & layer_nodes

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
        kind = node_kind(node)
        color_hex = _KIND_COLORS.get(kind, "#9e9e9e")

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

        item = _make_shape_node(
            kind, x, y, radius, node.node_id,
            on_click=self._on_node_click,
            on_hover=self._on_node_hover,
        )
        item.setBrush(QBrush(color))
        pen_color = color.darker(120) if not is_dimmed else QColor(color_hex)
        pen_color.setAlphaF(0.4 if is_dimmed else 1.0)
        pen_width = 3 if is_focal else 2
        if meaning and meaning.state_warmth != "neutral" and node.etype == "Character":
            pen_color = QColor(state_color(meaning.state_warmth))
            pen_width = 3
        item.setPen(QPen(pen_color, pen_width))
        item.setZValue(2 if is_focal else 1)
        self._gscene.addItem(item)
        self._node_items[node.node_id] = item

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
        style = EDGE_STYLE.get(edge.edge_type, EDGE_STYLE[EDGE_LINK])
        if is_highlight:
            color = QColor(_EDGE_HIGHLIGHT)
            width = max(style["width"] + 0.8, 2.0)
        else:
            color = QColor(style["color"])
            width = style["width"]
        pen = QPen(color, width)
        if style.get("dash") == "dash":
            pen.setStyle(Qt.PenStyle.DashLine)
        elif style.get("dash") == "dot":
            pen.setStyle(Qt.PenStyle.DotLine)
        line = QGraphicsLineItem(src[0], src[1], tgt[0], tgt[1])
        line.setPen(pen)
        line.setZValue(0 if edge.edge_type != EDGE_CONTAINMENT else -1)
        # Tag with edge_type so zoom-culling can target specific kinds.
        line.setData(0, edge.edge_type)
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
