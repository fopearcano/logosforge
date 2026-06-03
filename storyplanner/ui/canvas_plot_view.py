"""Canvas Plot — a free, zoomable, pannable visual plotting board.

A calm dark-mode thinking canvas (not a table / not a timeline): blocks are
placed anywhere, moved freely, selected, edited and coloured. Layout is owned
per project by the dedicated ``CanvasPlotNode`` store (Phase 1) — never derived
from Timeline or scene order. The view transform (zoom / centre) is remembered
per project in the project settings.

Built on ``QGraphicsView`` / ``QGraphicsScene`` / ``QGraphicsItem`` — the natural
fit for zoom/pan/movable items.
"""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPainter, QPen
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGraphicsItem,
    QGraphicsScene,
    QGraphicsView,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from storyplanner.db import Database
from storyplanner.ui import theme
from storyplanner.ui.color_labels import COLOR_LABELS, color_hex

_SCENE_HALF = 6000          # half-extent of the (large) scene rect for panning
_MIN_ZOOM = 0.25
_MAX_ZOOM = 4.0
_DEF_W = 188.0
_DEF_H = 116.0
_SETTINGS_KEY = "canvas_plot_view"


# ===========================================================================
# Block item
# ===========================================================================


class _BlockItem(QGraphicsItem):
    """A movable, selectable card representing one CanvasPlotNode."""

    def __init__(self, node, owner: "CanvasPlotView") -> None:
        super().__init__()
        self._node = node
        self.node_id = node.id
        self._owner = owner
        self._w = float(node.width or _DEF_W)
        self._h = float(node.height or _DEF_H)
        self.setPos(float(node.x), float(node.y))
        self.setFlags(
            QGraphicsItem.GraphicsItemFlag.ItemIsMovable
            | QGraphicsItem.GraphicsItemFlag.ItemIsSelectable
            | QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges
        )
        self.setAcceptHoverEvents(True)
        self._press_scene_pos: QPointF | None = None

    def boundingRect(self) -> QRectF:
        return QRectF(0, 0, self._w, self._h)

    def paint(self, painter: QPainter, option, widget=None) -> None:
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        rect = QRectF(1, 1, self._w - 2, self._h - 2)
        selected = self.isSelected()
        painter.setBrush(QColor(theme.CARD_BG))
        painter.setPen(QPen(
            QColor(theme.ACCENT if selected else theme.CARD_BORDER),
            2 if selected else 1,
        ))
        painter.drawRoundedRect(rect, 8, 8)

        # Colour stripe down the left edge.
        stripe = color_hex(getattr(self._node, "color_label", ""))
        if stripe:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(stripe))
            painter.drawRoundedRect(QRectF(2, 2, 5, self._h - 4), 3, 3)

        left = 14
        # Title.
        title = (self._node.title or "Untitled").strip() or "Untitled"
        tf = QFont(painter.font())
        tf.setPointSize(10)
        tf.setBold(True)
        painter.setFont(tf)
        painter.setPen(QColor(theme.TEXT_PRIMARY))
        trect = QRectF(left, 8, self._w - left - 8, 18)
        painter.drawText(
            trect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            QFontMetrics(tf).elidedText(title, Qt.TextElideMode.ElideRight,
                                        int(trect.width())),
        )

        # Body / summary (wrapped, clipped).
        body = (self._node.body or "").strip()
        if body:
            bf = QFont(painter.font())
            bf.setPointSize(8)
            bf.setBold(False)
            painter.setFont(bf)
            painter.setPen(QColor(theme.TEXT_SECONDARY))
            brect = QRectF(left, 28, self._w - left - 8, self._h - 28 - 18)
            painter.drawText(
                brect,
                int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop
                    | Qt.TextFlag.TextWordWrap),
                body,
            )

        # Category chip at the bottom.
        cat = (self._node.group_label or "").strip()
        if cat:
            cf = QFont(painter.font())
            cf.setPointSize(8)
            cf.setBold(False)
            painter.setFont(cf)
            painter.setPen(QColor(theme.TEXT_MUTED))
            crect = QRectF(left, self._h - 18, self._w - left - 8, 14)
            painter.drawText(
                crect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                QFontMetrics(cf).elidedText("# " + cat, Qt.TextElideMode.ElideRight,
                                            int(crect.width())),
            )

    # -- interaction --------------------------------------------------------

    def mousePressEvent(self, event) -> None:
        self._press_scene_pos = self.scenePos()
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        super().mouseReleaseEvent(event)
        # Persist the new position only if it actually moved.
        if self._press_scene_pos is not None and self.scenePos() != self._press_scene_pos:
            self._owner._persist_position(self.node_id, self.x(), self.y())
        self._press_scene_pos = None

    def mouseDoubleClickEvent(self, event) -> None:
        self._owner._edit_block(self.node_id)

    def contextMenuEvent(self, event) -> None:
        self._owner._block_menu(self.node_id, event.screenPos())


# ===========================================================================
# Board view (zoom + pan)
# ===========================================================================


class _BoardView(QGraphicsView):
    def __init__(self, scene: QGraphicsScene, owner: "CanvasPlotView") -> None:
        super().__init__(scene)
        self._owner = owner
        self._panning = False
        self._pan_last = None
        self.setRenderHints(
            QPainter.RenderHint.Antialiasing | QPainter.RenderHint.TextAntialiasing
            | QPainter.RenderHint.SmoothPixmapTransform
        )
        self.setDragMode(QGraphicsView.DragMode.NoDrag)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setBackgroundBrush(QColor(theme.BG_DARK))

    def wheelEvent(self, event) -> None:
        factor = 1.15 if event.angleDelta().y() > 0 else 1 / 1.15
        self._owner._apply_zoom_factor(factor)
        event.accept()

    def mousePressEvent(self, event) -> None:
        if (event.button() == Qt.MouseButton.LeftButton
                and self.itemAt(event.pos()) is None):
            self._panning = True
            self._pan_last = event.pos()
            self.viewport().setCursor(Qt.CursorShape.ClosedHandCursor)
            self.scene().clearSelection()
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        if self._panning and self._pan_last is not None:
            delta = event.pos() - self._pan_last
            self._pan_last = event.pos()
            h = self.horizontalScrollBar()
            v = self.verticalScrollBar()
            h.setValue(h.value() - delta.x())
            v.setValue(v.value() - delta.y())
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        if self._panning:
            self._panning = False
            self.viewport().setCursor(Qt.CursorShape.ArrowCursor)
            self._owner._save_view_state()
            event.accept()
            return
        super().mouseReleaseEvent(event)


# ===========================================================================
# Edit dialog
# ===========================================================================


class _BlockEditDialog(QDialog):
    def __init__(self, node, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Edit block")
        self.setMinimumWidth(360)
        form = QFormLayout(self)
        self._title = QLineEdit(node.title or "")
        form.addRow("Title", self._title)
        self._body = QPlainTextEdit(node.body or "")
        self._body.setMaximumHeight(120)
        form.addRow("Summary", self._body)
        self._category = QLineEdit(node.group_label or "")
        self._category.setPlaceholderText("e.g. theme, subplot, idea…")
        form.addRow("Category", self._category)
        self._color = QComboBox()
        for key, label in COLOR_LABELS.items():
            self._color.addItem(label, key)
        idx = self._color.findData(node.color_label or "")
        if idx >= 0:
            self._color.setCurrentIndex(idx)
        form.addRow("Colour", self._color)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

    def values(self) -> dict:
        return {
            "title": self._title.text().strip(),
            "body": self._body.toPlainText().strip(),
            "group_label": self._category.text().strip(),
            "color_label": self._color.currentData() or "",
        }


# ===========================================================================
# Canvas Plot view
# ===========================================================================


class CanvasPlotView(QWidget):
    """Free zoomable/pannable plotting board, persisted per project."""

    def __init__(
        self,
        db: Database,
        project_id: int,
        on_data_changed: Callable[[], None] | None = None,
    ) -> None:
        super().__init__()
        self._db = db
        self._project_id = project_id
        self._on_data_changed = on_data_changed
        self._zoom = 1.0
        self._items: dict[int, _BlockItem] = {}

        outer = QVBoxLayout(self)
        outer.setContentsMargins(8, 8, 8, 8)
        outer.setSpacing(6)
        outer.addLayout(self._build_toolbar())

        self._scene = QGraphicsScene(self)
        self._scene.setSceneRect(-_SCENE_HALF, -_SCENE_HALF,
                                 _SCENE_HALF * 2, _SCENE_HALF * 2)
        self._view = _BoardView(self._scene, self)
        outer.addWidget(self._view, stretch=1)

        self.refresh()

    # -- toolbar ------------------------------------------------------------

    def _build_toolbar(self) -> QHBoxLayout:
        bar = QHBoxLayout()
        bar.setSpacing(6)
        title = QLabel("Canvas Plot")
        title.setStyleSheet(
            f"color: {theme.TEXT_PRIMARY}; font-size: 14px; font-weight: 700;")
        bar.addWidget(title)

        new_btn = QPushButton("New Block")
        new_btn.setStyleSheet(theme.primary_btn())
        new_btn.clicked.connect(self._new_block)
        bar.addWidget(new_btn)

        reset = QPushButton("Reset View")
        reset.clicked.connect(self.reset_view)
        bar.addWidget(reset)

        bar.addStretch()

        zoom_out = QPushButton("−")          # minus
        zoom_out.setFixedWidth(28)
        zoom_out.clicked.connect(lambda: self._apply_zoom_factor(1 / 1.15))
        bar.addWidget(zoom_out)
        self._zoom_label = QPushButton("100%")
        self._zoom_label.setFixedWidth(56)
        self._zoom_label.setFlat(True)
        self._zoom_label.clicked.connect(self._zoom_to_100)
        self._zoom_label.setStyleSheet(
            f"QPushButton {{ color: {theme.TEXT_SECONDARY}; border: none; }}")
        bar.addWidget(self._zoom_label)
        zoom_in = QPushButton("+")
        zoom_in.setFixedWidth(28)
        zoom_in.clicked.connect(lambda: self._apply_zoom_factor(1.15))
        bar.addWidget(zoom_in)
        return bar

    # -- load / rebuild -----------------------------------------------------

    def refresh(self) -> None:
        # Preserve scroll while rebuilding (avoids jumps on data-change refresh).
        h = self._view.horizontalScrollBar().value()
        v = self._view.verticalScrollBar().value()
        self._scene.clear()
        self._items.clear()
        nodes = self._db.get_canvas_plot_nodes(self._project_id)
        for node in nodes:
            item = _BlockItem(node, self)
            self._scene.addItem(item)
            self._items[node.id] = item
        # Apply the saved per-project view transform on first load.
        self._restore_view_state()
        self._view.horizontalScrollBar().setValue(h)
        self._view.verticalScrollBar().setValue(v)
        self._update_zoom_label()

    # -- block CRUD ---------------------------------------------------------

    def _new_block(self) -> None:
        # Place near the current viewport centre, nudged so repeated creates
        # don't land exactly on top of each other.
        centre = self._view.mapToScene(self._view.viewport().rect().center())
        n = len(self._items)
        off = (n % 6) * 26
        node = self._db.create_canvas_plot_node(
            self._project_id,
            title="New block",
            x=centre.x() - _DEF_W / 2 + off,
            y=centre.y() - _DEF_H / 2 + off,
            width=_DEF_W, height=_DEF_H,
        )
        self.refresh()
        self._select_only(node.id)
        self._touch()

    def _edit_block(self, node_id: int) -> None:
        node = self._db.get_canvas_plot_nodes(self._project_id)
        node = next((n for n in node if n.id == node_id), None)
        if node is None:
            return
        dlg = _BlockEditDialog(node, parent=self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        v = dlg.values()
        self._db.update_canvas_plot_node(
            node_id, title=v["title"], body=v["body"],
            group_label=v["group_label"], color_label=v["color_label"],
        )
        self.refresh()
        self._select_only(node_id)
        self._touch()

    def _block_menu(self, node_id: int, global_pos) -> None:
        menu = QMenu(self)
        menu.addAction("Edit…", lambda: self._edit_block(node_id))
        menu.addSeparator()
        menu.addAction("Delete block…", lambda: self._delete_block(node_id))
        menu.exec(global_pos)

    def _delete_block(self, node_id: int) -> None:
        answer = QMessageBox.question(
            self, "Delete block",
            "Delete this Canvas Plot block? This cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        self._db.delete_canvas_plot_node(node_id)
        self.refresh()
        self._touch()

    def _persist_position(self, node_id: int, x: float, y: float) -> None:
        # Pure layout change — persist directly; no rebuild (item already moved).
        self._db.update_canvas_plot_node(node_id, x=float(x), y=float(y))

    def _select_only(self, node_id: int) -> None:
        self._scene.clearSelection()
        item = self._items.get(node_id)
        if item is not None:
            item.setSelected(True)

    def _touch(self) -> None:
        if self._on_data_changed:
            self._on_data_changed()

    # -- zoom / view state --------------------------------------------------

    def _apply_zoom_factor(self, factor: float) -> None:
        new = max(_MIN_ZOOM, min(_MAX_ZOOM, self._zoom * factor))
        actual = new / self._zoom if self._zoom else 1.0
        if abs(actual - 1.0) < 1e-6:
            return
        self._view.scale(actual, actual)
        self._zoom = new
        self._update_zoom_label()
        self._save_view_state()

    def _zoom_to_100(self) -> None:
        if self._zoom:
            self._view.scale(1.0 / self._zoom, 1.0 / self._zoom)
        self._zoom = 1.0
        self._update_zoom_label()
        self._save_view_state()

    def reset_view(self) -> None:
        self._zoom_to_100()
        # Centre on the blocks (or the origin if empty).
        if self._items:
            rect = self._scene.itemsBoundingRect()
            self._view.centerOn(rect.center())
        else:
            self._view.centerOn(0, 0)
        self._save_view_state()

    def _update_zoom_label(self) -> None:
        self._zoom_label.setText(f"{int(round(self._zoom * 100))}%")

    def _save_view_state(self) -> None:
        centre = self._view.mapToScene(self._view.viewport().rect().center())
        settings = self._db.get_project_settings(self._project_id)
        settings[_SETTINGS_KEY] = {
            "zoom": self._zoom, "cx": centre.x(), "cy": centre.y(),
        }
        self._db.save_project_settings(self._project_id, settings)

    def _restore_view_state(self) -> None:
        state = self._db.get_project_settings(self._project_id).get(_SETTINGS_KEY)
        if not isinstance(state, dict):
            return
        zoom = float(state.get("zoom", 1.0) or 1.0)
        zoom = max(_MIN_ZOOM, min(_MAX_ZOOM, zoom))
        if self._zoom:
            self._view.scale(zoom / self._zoom, zoom / self._zoom)
        self._zoom = zoom
        cx, cy = state.get("cx"), state.get("cy")
        if cx is not None and cy is not None:
            self._view.centerOn(float(cx), float(cy))
