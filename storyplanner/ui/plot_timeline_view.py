"""Plot-lane Timeline — a horizontal, scrollable, plot-lane based narrative view.

Layout
  * Vertical axis  = Plot lanes / subplots (one row per ``TimelineLane``, plus a
    virtual "Unassigned" lane for events with no plotline).
  * Horizontal axis = shared narrative order / story time (a scene's column is
    its global ``sort_order`` rank — the same single order Manuscript uses).
  * Sticky left column of lane headers; the event canvas scrolls horizontally
    and vertically; the two share one vertical offset.

Events are existing ``Scene`` rows. Lane membership is ``Scene.plotline`` (so the
Plot section stays in sync); event colour is ``Scene.color_label``; horizontal
order is ``Scene.sort_order``. Lane metadata (colour/order/collapsed) lives in
``TimelineLane``; event links in ``TimelineLink``. Everything persists.

The view is intentionally compact and theme-driven (Dark / Green / Warm).
"""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QMimeData, QPoint, QRect, Qt, QSize
from PySide6.QtGui import QColor, QDrag, QFontMetrics, QPainter, QPen
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMenu,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from storyplanner.db import Database
from storyplanner.models import TIMELINE_LINK_TYPES
from storyplanner.story_structure import (
    build_structure_tree,
    canonical_scene_order,
    compute_structural_numbers,
    is_novel_project,
)
from storyplanner.ui import theme
from storyplanner.ui.color_labels import build_color_menu, color_hex

# Layout geometry (kept small for 13-inch screens).
RULER_H = 22
LANE_H = 88
LANE_COLLAPSED_H = 30
SLOT_W = 158
CARD_W = SLOT_W - 14
CARD_H = LANE_H - 26
LEFT_PAD = 14
HEADER_W = 168

_UNASSIGNED = "— Unassigned"   # display label for the virtual lane


# ===========================================================================
# Event card
# ===========================================================================


class _EventCard(QFrame):
    """A compact, draggable card representing one Timeline event (a scene)."""

    _DRAG_THRESHOLD = 8

    def __init__(self, scene, view: "PlotTimelineView") -> None:
        super().__init__()
        self._scene = scene
        self._view = view
        self.scene_id = scene.id
        self._drag_start: QPoint | None = None
        self.setFixedSize(CARD_W, CARD_H)
        self.setObjectName("timelineEventCard")
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_menu)
        self._build()
        self._apply_style()

    # -- build / style ------------------------------------------------------

    def _build(self) -> None:
        lay = QVBoxLayout(self)
        lay.setContentsMargins(8, 5, 6, 5)
        lay.setSpacing(1)
        title = (self._scene.title or "Untitled").strip() or "Untitled"
        # Prefix the canonical structural number (e.g. "1.1.1") so the event
        # reads as a clear Act→Chapter→Scene path, never a bare "Untitled".
        snum = (self._view._structure_numbers.get("scenes", {})
                .get(self.scene_id, "")) if hasattr(self._view, "_structure_numbers") else ""
        if snum:
            title = f"{snum}  {title}"
        self._title_lbl = QLabel(title)
        self._title_lbl.setStyleSheet(
            f"color: {theme.TEXT_PRIMARY}; font-size: 11px; font-weight: 600;"
        )
        self._title_lbl.setText(
            QFontMetrics(self._title_lbl.font()).elidedText(
                title, Qt.TextElideMode.ElideRight, CARD_W - 18
            )
        )
        lay.addWidget(self._title_lbl)

        ref_bits = [b for b in (self._scene.act, self._scene.chapter) if b]
        summary = (self._scene.summary or self._scene.synopsis or "").strip()
        sub = " · ".join(ref_bits) if ref_bits else summary
        if sub:
            sub_lbl = QLabel(sub)
            sub_lbl.setStyleSheet(
                f"color: {theme.TEXT_SECONDARY}; font-size: 9px;"
            )
            sub_lbl.setText(
                QFontMetrics(sub_lbl.font()).elidedText(
                    sub, Qt.TextElideMode.ElideRight, CARD_W - 18
                )
            )
            lay.addWidget(sub_lbl)

        # Compact planning status chip (reuses the Outline `status:` tag), if set.
        from storyplanner.ui.plan_view import scene_status
        status = scene_status(self._scene)
        if status:
            st_lbl = QLabel(f"● {status}")
            st_lbl.setObjectName("timelineStatusChip")
            st_lbl.setStyleSheet(
                f"color: {theme.TEXT_SECONDARY}; font-size: 9px;")
            lay.addWidget(st_lbl)

        # Compact "linked Outline target" indicator showing the canonical number
        # (Act 1 / Ch 1.2) from the shared structure adapter.
        struct = self._view._struct_by_scene.get(self.scene_id, [])
        if struct:
            refs = ", ".join(self._view._struct_ref_label(s) for s in struct)
            link_lbl = QLabel(f"🔗 {refs}")
            link_lbl.setStyleSheet(
                f"color: {theme.ACCENT}; font-size: 9px;"
            )
            link_lbl.setText(
                QFontMetrics(link_lbl.font()).elidedText(
                    f"🔗 {refs}", Qt.TextElideMode.ElideRight, CARD_W - 18
                )
            )
            link_lbl.setToolTip("Linked to: " + refs)
            lay.addWidget(link_lbl)
        lay.addStretch()

    def _apply_style(self) -> None:
        stripe = color_hex(getattr(self._scene, "color_label", "")) or theme.BORDER
        self.setStyleSheet(
            f"QFrame#timelineEventCard {{"
            f"  background: {theme.CARD_BG};"
            f"  border: 1px solid {theme.CARD_BORDER};"
            f"  border-left: 4px solid {stripe};"
            f"  border-radius: 5px;"
            f"}}"
            f"QFrame#timelineEventCard:hover {{ border-color: {theme.ACCENT}; }}"
        )

    # -- drag ---------------------------------------------------------------

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_start = event.pos()

    def mouseMoveEvent(self, event) -> None:
        if self._drag_start is None:
            return
        if (event.pos() - self._drag_start).manhattanLength() < self._DRAG_THRESHOLD:
            return
        drag = QDrag(self)
        mime = QMimeData()
        mime.setText(str(self.scene_id))
        drag.setMimeData(mime)
        drag.setPixmap(self.grab())
        drag.setHotSpot(event.pos())
        drag.exec(Qt.DropAction.MoveAction)

    def mouseDoubleClickEvent(self, event) -> None:
        self._view._open_scene(self.scene_id)

    # -- context menu -------------------------------------------------------

    def _show_menu(self, pos) -> None:
        self._view._show_card_menu(self, self.mapToGlobal(pos))


# ===========================================================================
# Lane header (sticky left)
# ===========================================================================


class _LaneHeader(QFrame):
    def __init__(self, lane, name: str, count: int, view: "PlotTimelineView",
                 height: int) -> None:
        super().__init__()
        self._lane = lane            # TimelineLane or None (unassigned)
        self._name = name
        self._view = view
        self.setFixedHeight(height)
        self.setObjectName("timelineLaneHeader")
        dot = color_hex(getattr(lane, "color_label", "")) if lane else None
        # Subtle lane-colour accent: a coloured left edge on the header.
        left = dot or theme.BORDER
        self.setStyleSheet(
            f"QFrame#timelineLaneHeader {{ background: {theme.BG_PANEL};"
            f" border-left: 3px solid {left};"
            f" border-bottom: 1px solid {theme.BORDER}; }}"
        )
        lay = QHBoxLayout(self)
        lay.setContentsMargins(8, 4, 6, 4)
        lay.setSpacing(6)

        if lane is not None:
            collapse = QPushButton("▾" if not lane.collapsed else "▸")
            collapse.setFixedWidth(16)
            collapse.setFlat(True)
            collapse.setStyleSheet(
                f"QPushButton {{ color: {theme.TEXT_SECONDARY}; border: none; }}"
            )
            collapse.clicked.connect(lambda: view._toggle_lane(lane.id))
            lay.addWidget(collapse)

        swatch = QLabel("●")
        swatch.setStyleSheet(
            f"color: {dot or theme.TEXT_MUTED}; font-size: 12px;"
        )
        lay.addWidget(swatch)

        text = QVBoxLayout()
        text.setSpacing(0)
        name_lbl = QLabel(name)
        name_lbl.setStyleSheet(
            f"color: {theme.TEXT_PRIMARY}; font-size: 11px; font-weight: 600;"
        )
        name_lbl.setText(QFontMetrics(name_lbl.font()).elidedText(
            name, Qt.TextElideMode.ElideRight, HEADER_W - 60))
        text.addWidget(name_lbl)
        count_lbl = QLabel(f"{count} event{'s' if count != 1 else ''}")
        count_lbl.setStyleSheet(f"color: {theme.TEXT_MUTED}; font-size: 9px;")
        text.addWidget(count_lbl)
        lay.addLayout(text, stretch=1)

        if lane is not None:
            menu_btn = QPushButton("⋯")
            menu_btn.setFixedWidth(18)
            menu_btn.setFlat(True)
            menu_btn.setStyleSheet(
                f"QPushButton {{ color: {theme.TEXT_SECONDARY}; border: none;"
                f" font-size: 14px; }}"
                f"QPushButton:hover {{ color: {theme.TEXT_PRIMARY}; }}"
            )
            menu_btn.clicked.connect(
                lambda: view._show_lane_menu(
                    lane, menu_btn.mapToGlobal(QPoint(0, menu_btn.height())))
            )
            lay.addWidget(menu_btn)


# ===========================================================================
# Event canvas (scrolls; draws cards + link lines + ruler)
# ===========================================================================


class _TimelineCanvas(QWidget):
    def __init__(self, view: "PlotTimelineView") -> None:
        super().__init__()
        self._view = view
        self.setAcceptDrops(True)
        self.setObjectName("timelineCanvas")
        self.setStyleSheet(
            f"QWidget#timelineCanvas {{ background: {theme.BG_DARK}; }}"
        )

    # Link lines are drawn behind the child cards.
    def paintEvent(self, event) -> None:
        super().paintEvent(event)
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        width = self.width()
        # Per-lane coloured band + centre line (subtle), behind cards & links, so
        # each lane reads in its own colour without neon chaos.
        for y, h, chex in self._view._lane_bands:
            if chex:
                fill = QColor(chex)
                fill.setAlpha(22)
                p.fillRect(QRect(0, y, width, h), fill)
                line = QColor(chex)
                line.setAlpha(150)
                p.setPen(QPen(line, 1))
            else:
                p.setPen(QPen(QColor(theme.BORDER), 1))
            mid = y + h // 2
            p.drawLine(LEFT_PAD, mid, width - LEFT_PAD, mid)
        # Ruler ticks / order numbers along the top.
        p.setPen(QPen(QColor(theme.TEXT_MUTED), 1))
        for col in range(self._view._n_cols):
            x = LEFT_PAD + col * SLOT_W + CARD_W // 2
            p.drawLine(x, RULER_H - 5, x, RULER_H - 1)
            p.drawText(QRect(x - 18, 2, 36, RULER_H - 6),
                       Qt.AlignmentFlag.AlignCenter, str(col + 1))
        # Links.
        rects = self._view._card_rects
        for link in self._view._links:
            a = rects.get(link.source_scene_id)
            b = rects.get(link.target_scene_id)
            if a is None or b is None:
                continue
            color = QColor(color_hex(link.color_label) or theme.TEXT_MUTED)
            pen = QPen(color, 2)
            p.setPen(pen)
            p.drawLine(a.center(), b.center())
            # small dot at each end for readability
            p.setBrush(color)
            p.drawEllipse(a.center(), 3, 3)
            p.drawEllipse(b.center(), 3, 3)
            # Optional link label, drawn just above the line's midpoint so it
            # stays legible and never sits on top of a card's text.
            label = (getattr(link, "label", "") or "").strip()
            if label:
                mid = (a.center() + b.center()) / 2
                p.setPen(QPen(color, 1))
                p.drawText(QRect(mid.x() - 60, mid.y() - 16, 120, 14),
                           Qt.AlignmentFlag.AlignCenter, label)
        p.end()

    def dragEnterEvent(self, event) -> None:
        if event.mimeData().hasText():
            event.acceptProposedAction()

    def dragMoveEvent(self, event) -> None:
        if event.mimeData().hasText():
            event.acceptProposedAction()

    def dropEvent(self, event) -> None:
        if not event.mimeData().hasText():
            return
        try:
            scene_id = int(event.mimeData().text())
        except ValueError:
            return
        pos = event.position().toPoint()
        self._view._handle_drop(scene_id, pos.x(), pos.y())
        event.acceptProposedAction()


# ===========================================================================
# The Timeline section view
# ===========================================================================


class PlotTimelineView(QWidget):
    """Horizontal, plot-lane based, persistent narrative Timeline."""

    def __init__(
        self,
        db: Database,
        project_id: int,
        on_scene_selected: Callable[[int], None] | None = None,
        on_data_changed: Callable[[], None] | None = None,
    ) -> None:
        super().__init__()
        # Diagnostic marker: confirms the running app uses the improved Timeline
        # (coloured lanes + event/structure linking), not an old plain view.
        self.setObjectName("timeline_target_colored_lane_link_view")
        from storyplanner.diagnostics import attach_dev_marker
        attach_dev_marker(self, "NEW TIMELINE VIEW")
        self._db = db
        self._project_id = project_id
        self._on_scene_selected = on_scene_selected
        self._on_data_changed = on_data_changed

        # Live layout state (rebuilt every refresh; tests introspect these).
        self._lanes: list = []                     # TimelineLane rows
        self._rows: list[tuple] = []               # (lane|None, name, [scenes])
        self._links: list = []
        self._card_rects: dict[int, QRect] = {}    # scene_id -> rect in canvas
        self._card_by_scene: dict[int, _EventCard] = {}
        self._n_cols = 0
        # Timeline-specific event order (scene ids) — independent of Outline's
        # Scene.sort_order, so moving a block here never reorders the Outline.
        self._event_order: list[int] = []
        # Column-ordering mode: "structural" (default — follow the canonical
        # Outline order) or "custom" (timeline-local order, opt-in via a move).
        self._order_mode: str = "structural"
        self._pending_link_source: int | None = None
        # Event → Act/Chapter structure links, grouped by event scene id.
        self._struct_by_scene: dict[int, list] = {}
        # Per-lane coloured bands: (y, height, color_hex|None) for paintEvent.
        self._lane_bands: list[tuple[int, int, str | None]] = []

        self._build_chrome()
        self.refresh()

    # -- chrome -------------------------------------------------------------

    def _build_chrome(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(8, 8, 8, 8)
        outer.setSpacing(6)

        bar = QHBoxLayout()
        bar.setSpacing(6)
        title = QLabel("Timeline")
        title.setStyleSheet(
            f"color: {theme.TEXT_PRIMARY}; font-size: 14px; font-weight: 700;"
        )
        bar.addWidget(title)
        add_lane = QPushButton("+ Lane")
        add_lane.setStyleSheet(theme.primary_btn() if hasattr(theme, "primary_btn") else "")
        add_lane.clicked.connect(self._add_lane)
        bar.addWidget(add_lane)
        # Column-ordering mode toggle. Default "Structural" lines events up with
        # the Outline; "Custom" lets the user reorder events independently.
        self._order_mode_btn = QPushButton("Order: Structural")
        self._order_mode_btn.setFlat(True)
        self._order_mode_btn.setToolTip(
            "Structural Order follows the Outline (1.1.1, 1.1.2, …). "
            "Custom Timeline Order lets you reorder events independently.")
        self._order_mode_btn.setStyleSheet(
            f"QPushButton {{ color: {theme.TEXT_SECONDARY}; border: 1px solid "
            f"{theme.BORDER}; border-radius: 4px; padding: 2px 8px;"
            f" font-size: 10px; }}")
        self._order_mode_btn.clicked.connect(self._toggle_order_mode)
        bar.addWidget(self._order_mode_btn)
        bar.addStretch()
        self._status = QLabel("")
        self._status.setStyleSheet(f"color: {theme.ACCENT}; font-size: 10px;")
        bar.addWidget(self._status)
        self._cancel_link_btn = QPushButton("Cancel link")
        self._cancel_link_btn.setFlat(True)
        self._cancel_link_btn.setStyleSheet(
            f"QPushButton {{ color: {theme.TEXT_SECONDARY}; border: none;"
            f" font-size: 10px; }}"
        )
        self._cancel_link_btn.clicked.connect(self._cancel_link)
        self._cancel_link_btn.setVisible(False)
        bar.addWidget(self._cancel_link_btn)
        outer.addLayout(bar)

        body = QHBoxLayout()
        body.setSpacing(0)

        # Sticky left header column (vertical scroll synced, no scrollbars).
        self._vheader = QScrollArea()
        self._vheader.setFixedWidth(HEADER_W)
        self._vheader.setWidgetResizable(True)
        self._vheader.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._vheader.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._vheader.setFrameShape(QFrame.Shape.NoFrame)
        self._header_holder = QWidget()
        self._header_layout = QVBoxLayout(self._header_holder)
        self._header_layout.setContentsMargins(0, 0, 0, 0)
        self._header_layout.setSpacing(0)
        self._vheader.setWidget(self._header_holder)
        body.addWidget(self._vheader)

        # Event canvas (both scrollbars).
        self._hscroll = QScrollArea()
        self._hscroll.setWidgetResizable(False)
        self._hscroll.setFrameShape(QFrame.Shape.NoFrame)
        self._canvas = _TimelineCanvas(self)
        self._hscroll.setWidget(self._canvas)
        self._hscroll.verticalScrollBar().valueChanged.connect(
            self._sync_header_scroll
        )
        body.addWidget(self._hscroll, stretch=1)

        outer.addLayout(body, stretch=1)

        self._empty = QLabel(
            "No events yet. Add scenes (Scenes/Manuscript), then assign them to "
            "plot lanes here — or click “+ Lane” to start."
        )
        self._empty.setWordWrap(True)
        self._empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty.setStyleSheet(f"color: {theme.TEXT_MUTED}; font-size: 12px;")
        self._empty.setVisible(False)
        outer.addWidget(self._empty)

    def _sync_header_scroll(self, value: int) -> None:
        # Header holder is offset to match the canvas vertical scroll.
        self._header_holder.move(0, -value + RULER_H)

    # -- data load / layout -------------------------------------------------

    def _effective_order(self, scenes) -> list[int]:
        """Resolve the timeline column order.

        "structural" (default): the canonical Outline order, so linked scene
        events line up with Outline/Manuscript (1.1.1, 1.1.2, 1.1.3, …). Any
        stale custom order is ignored.

        "custom" (opt-in, set when the user moves a card): the timeline-local
        order, then any newer scenes appended in canonical sort_order. Never
        mutates Scene.sort_order.
        """
        existing = {s.id for s in scenes}
        if self._order_mode == "custom":
            base = self._db.get_timeline_order(self._project_id)
        else:
            base = canonical_scene_order(self._db, self._project_id)
        order = [sid for sid in base if sid in existing]
        seen = set(order)
        for s in scenes:                      # scenes arrive in sort_order
            if s.id not in seen:
                order.append(s.id)
                seen.add(s.id)
        return order

    def _sync_order_mode_button(self) -> None:
        btn = getattr(self, "_order_mode_btn", None)
        if btn is not None:
            btn.setText("Order: Custom" if self._order_mode == "custom"
                        else "Order: Structural")

    def _toggle_order_mode(self) -> None:
        new = "structural" if self._order_mode == "custom" else "custom"
        self._db.set_timeline_order_mode(self._project_id, new)
        if new == "custom":
            # Seed the custom order from what's shown now (the canonical order)
            # so switching starts from the visible order, not a stale one.
            self._db.set_timeline_order(self._project_id, list(self._event_order))
        self._notify()

    def _enter_custom_order(self, order: list[int]) -> None:
        """Persist an explicit horizontal reorder, switching the project into
        Custom Timeline Order (never touches Scene.sort_order / the Outline)."""
        self._db.set_timeline_order_mode(self._project_id, "custom")
        self._db.set_timeline_order(self._project_id, order)

    def refresh(self) -> None:
        # Ensure lanes exist for any pre-existing plotline strings.
        self._lanes = self._db.ensure_timeline_lanes(self._project_id)
        self._links = self._db.get_timeline_links(self._project_id)
        # Group event→Act/Chapter structure links by source event for the cards.
        self._struct_by_scene = {}
        for sl in self._db.get_all_timeline_structure_links(self._project_id):
            self._struct_by_scene.setdefault(sl.source_scene_id, []).append(sl)
        # Canonical structural numbers for linked Act/Chapter chips — shared with
        # Outline & Manuscript so a chip's path always matches the real number.
        self._structure_numbers = compute_structural_numbers(
            build_structure_tree(self._db, self._project_id),
            is_novel_project(self._db, self._project_id),
        )
        self._cur_acts = set(self._db.get_scene_acts(self._project_id))
        self._cur_chapters = set(self._db.get_scene_chapters(self._project_id))
        self._order_mode = self._db.get_timeline_order_mode(self._project_id)
        self._sync_order_mode_button()
        scenes = self._db.get_all_scenes(self._project_id)
        # Column order follows the canonical Outline order by default
        # ("structural"); only "custom" mode uses a timeline-local order.
        self._event_order = self._effective_order(scenes)
        self._time_index = {sid: i for i, sid in enumerate(self._event_order)}
        self._n_cols = len(self._event_order)

        lane_names = {ln.name for ln in self._lanes}
        by_lane: dict[str, list] = {ln.name: [] for ln in self._lanes}
        unassigned: list = []
        for s in scenes:
            pl = (s.plotline or "").strip()
            if pl and pl in lane_names:
                by_lane[pl].append(s)
            else:
                unassigned.append(s)

        self._rows = [(ln, ln.name, by_lane[ln.name]) for ln in self._lanes]
        if unassigned:
            self._rows.append((None, _UNASSIGNED, unassigned))

        self._rebuild_headers()
        self._relayout_cards()
        has_any = bool(scenes) or bool(self._lanes)
        self._empty.setVisible(not has_any)
        self._hscroll.setVisible(has_any)
        self._vheader.setVisible(has_any)

    def _row_height(self, lane) -> int:
        if lane is not None and lane.collapsed:
            return LANE_COLLAPSED_H
        return LANE_H

    def _rebuild_headers(self) -> None:
        while self._header_layout.count():
            item = self._header_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
        # Top spacer aligns the first lane header below the ruler band.
        for lane, name, scenes in self._rows:
            self._header_layout.addWidget(
                _LaneHeader(lane, name, len(scenes), self, self._row_height(lane))
            )
        self._header_layout.addStretch()
        self._sync_header_scroll(self._hscroll.verticalScrollBar().value())

    def _relayout_cards(self) -> None:
        # Clear old cards.
        for card in self._card_by_scene.values():
            card.setParent(None)
            card.deleteLater()
        self._card_by_scene.clear()
        self._card_rects.clear()
        self._lane_bands = []

        y = RULER_H
        for lane, name, scenes in self._rows:
            h = self._row_height(lane)
            band_color = color_hex(getattr(lane, "color_label", "")) if lane else None
            self._lane_bands.append((y, h, band_color))
            if not (lane is not None and lane.collapsed):
                for s in scenes:
                    col = self._time_index.get(s.id, 0)
                    x = LEFT_PAD + col * SLOT_W
                    card = _EventCard(s, self)
                    card.setParent(self._canvas)
                    cy = y + (h - CARD_H) // 2
                    card.setGeometry(x, cy, CARD_W, CARD_H)
                    card.show()
                    self._card_by_scene[s.id] = card
                    self._card_rects[s.id] = QRect(x, cy, CARD_W, CARD_H)
            y += h

        width = max(LEFT_PAD + self._n_cols * SLOT_W + LEFT_PAD, 400)
        self._canvas.setMinimumSize(QSize(width, y + 8))
        self._canvas.resize(width, y + 8)
        self._canvas.update()

    # -- interactions: lanes ------------------------------------------------

    def _add_lane(self) -> None:
        name, ok = QInputDialog.getText(self, "New plot lane", "Lane name:")
        if not ok or not name.strip():
            return
        self._db.create_timeline_lane(self._project_id, name.strip())
        self._notify()

    def _toggle_lane(self, lane_id: int) -> None:
        lane = next((ln for ln in self._lanes if ln.id == lane_id), None)
        if lane is None:
            return
        self._db.set_timeline_lane_collapsed(lane_id, not lane.collapsed)
        self.refresh()

    def _show_lane_menu(self, lane, global_pos) -> None:
        menu = QMenu(self)
        menu.addAction(
            "Create linked scene…",
            lambda nm=lane.name: self._add_event_to_lane(nm))
        menu.addAction("Rename…", lambda: self._rename_lane(lane))
        build_color_menu(
            menu, lane.color_label,
            lambda key, lid=lane.id: self._set_lane_color(lid, key),
        )
        menu.addSeparator()
        menu.addAction(
            "Delete lane (keeps its events)",
            lambda lid=lane.id: self._delete_lane(lid),
        )
        menu.exec(global_pos)

    def _add_event_to_lane(self, lane_name: str) -> None:
        """Explicitly create a linked Scene in this lane. The Scene is parented
        under a valid Act → Chapter (structure service) so Timeline never makes
        an orphan Scene; it sets only title + plotline, never body."""
        title, ok = QInputDialog.getText(
            self, "Create linked scene", "Scene title:", text="New scene")
        if not ok or not title.strip():
            return
        from storyplanner import story_structure
        story_structure.create_scene(
            self._db, self._project_id, title=title.strip(),
            plotline=lane_name or "")
        self._notify()

    def _rename_lane(self, lane) -> None:
        name, ok = QInputDialog.getText(
            self, "Rename lane", "Lane name:", text=lane.name)
        if ok and name.strip():
            self._db.rename_timeline_lane(lane.id, name.strip())
            self._notify()

    def _set_lane_color(self, lane_id: int, key: str) -> None:
        self._db.set_timeline_lane_color(lane_id, key)
        self._notify()

    def _delete_lane(self, lane_id: int) -> None:
        self._db.delete_timeline_lane(lane_id)
        self._notify()

    # -- interactions: events ----------------------------------------------

    def _handle_drop(self, scene_id: int, x: int, y: int) -> None:
        # Resolve the target lane from the drop's vertical position.
        row_y = RULER_H
        target_lane_name = ""
        for lane, name, scenes in self._rows:
            h = self._row_height(lane)
            if row_y <= y < row_y + h:
                target_lane_name = "" if lane is None else lane.name
                break
            row_y += h
        # Move between lanes (plotline) when it changed — independent of order.
        scene = self._db.get_scene_by_id(scene_id)
        if scene is not None and (scene.plotline or "") != target_lane_name:
            self._db.update_scene_plotline(scene_id, target_lane_name)
        # An actual horizontal move is an explicit reorder: opt into Custom
        # Timeline Order and write the timeline-local order only (never
        # Scene.sort_order, so the Outline/Manuscript order is untouched). A
        # pure lane change (same column) stays in Structural Order.
        col = round((x - LEFT_PAD) / SLOT_W)
        col = max(0, min(col, max(self._n_cols - 1, 0)))
        cur = (self._event_order.index(scene_id)
               if scene_id in self._event_order else -1)
        if col != cur:
            order = [sid for sid in self._event_order if sid != scene_id]
            order.insert(min(col, len(order)), scene_id)
            self._enter_custom_order(order)
        self._notify()

    def _open_scene(self, scene_id: int) -> None:
        if self._on_scene_selected:
            self._on_scene_selected(scene_id)

    def _show_card_menu(self, card: _EventCard, global_pos) -> None:
        menu = QMenu(self)
        menu.addAction(
            "Open in Manuscript", lambda: self._open_scene(card.scene_id))
        menu.addAction("Rename…", lambda: self._rename_event(card.scene_id))
        build_color_menu(
            menu, getattr(card._scene, "color_label", ""),
            lambda key, sid=card.scene_id: self._set_event_color(sid, key),
        )
        menu.addSeparator()

        # Move along the story-time axis (drag works too; these are the precise,
        # always-available controls).
        menu.addAction(
            "Move ◀ (earlier)", lambda sid=card.scene_id: self._move_event(sid, -1))
        menu.addAction(
            "Move ▶ (later)", lambda sid=card.scene_id: self._move_event(sid, +1))
        # Assign to lane.
        lane_menu = QMenu("Move to lane", menu)
        for lane in self._lanes:
            lane_menu.addAction(
                lane.name,
                lambda _n=lane.name, sid=card.scene_id: self._assign_lane(sid, _n),
            )
        lane_menu.addAction(
            "Unassigned",
            lambda sid=card.scene_id: self._assign_lane(sid, ""),
        )
        menu.addMenu(lane_menu)
        menu.addSeparator()

        # Link this event to Outline structure (Act / Chapter) or directly to
        # another scene/event from a list.
        struct_menu = QMenu("Link to…", menu)
        act_sub = struct_menu.addMenu("Act")
        acts = self._db.get_scene_acts(self._project_id)
        act_sub.setEnabled(bool(acts))
        for a in acts:
            act_sub.addAction(
                a, lambda _a=a, sid=card.scene_id:
                    self._add_structure_link(sid, "act", _a),
            )
        chap_sub = struct_menu.addMenu("Chapter")
        chapters = self._db.get_scene_chapters(self._project_id)
        chap_sub.setEnabled(bool(chapters))
        for c in chapters:
            chap_sub.addAction(
                c, lambda _c=c, sid=card.scene_id:
                    self._add_structure_link(sid, "chapter", _c),
            )
        scene_sub = struct_menu.addMenu("Scene (event)")
        others = [s for s in self._db.get_all_scenes(self._project_id)
                  if s.id != card.scene_id]
        scene_sub.setEnabled(bool(others))
        for s in others:
            scene_sub.addAction(
                (s.title or "Untitled"),
                lambda _sid=s.id, src=card.scene_id:
                    self._link_to_scene_direct(src, _sid),
            )
        menu.addMenu(struct_menu)

        # Remove existing Act/Chapter links on this event.
        struct_links = self._struct_by_scene.get(card.scene_id, [])
        if struct_links:
            rm2 = QMenu("Remove Outline link", menu)
            for sl in struct_links:
                rm2.addAction(
                    f"{sl.target_type.title()}: {sl.target_ref}",
                    lambda lid=sl.id: self._remove_structure_link(lid),
                )
            menu.addMenu(rm2)
        menu.addSeparator()

        # Linking.
        if self._pending_link_source is None:
            menu.addAction(
                "Start link from here",
                lambda sid=card.scene_id: self._start_link(sid),
            )
        elif self._pending_link_source != card.scene_id:
            link_menu = QMenu("Link to here", menu)
            for key, tlabel in TIMELINE_LINK_TYPES.items():
                sub = QMenu(tlabel, link_menu)
                build_color_menu(
                    sub, "gray",
                    lambda ckey, sid=card.scene_id, lt=key:
                        self._finish_link(sid, lt, ckey),
                    title="Colour",
                )
                link_menu.addMenu(sub)
            menu.addMenu(link_menu)
            menu.addAction("Cancel link", self._cancel_link)

        # Edit existing links on this event: label / colour / relation type /
        # remove. (Removing a link never deletes the linked events.)
        related = [
            ln for ln in self._links
            if card.scene_id in (ln.source_scene_id, ln.target_scene_id)
        ]
        if related:
            edit = QMenu("Edit links", menu)
            for ln in related:
                other_id = (ln.target_scene_id if ln.source_scene_id == card.scene_id
                            else ln.source_scene_id)
                other = self._db.get_scene_by_id(other_id)
                other_t = (other.title if other else f"scene {other_id}") or "?"
                tlabel = TIMELINE_LINK_TYPES.get(ln.link_type, ln.link_type)
                tag = f' “{ln.label}”' if (ln.label or "").strip() else ""
                sub = QMenu(f"{tlabel} ↔ {other_t}{tag}", edit)
                sub.addAction(
                    "Set label…", lambda lid=ln.id: self._set_link_label(lid))
                ctype = QMenu("Relation type", sub)
                for key, name in TIMELINE_LINK_TYPES.items():
                    ctype.addAction(
                        (f"● {name}" if key == ln.link_type else name),
                        lambda _k=key, lid=ln.id: self._set_link_type(lid, _k))
                sub.addMenu(ctype)
                build_color_menu(
                    sub, ln.color_label,
                    lambda key, lid=ln.id: self._set_link_color(lid, key),
                    title="Colour",
                )
                sub.addSeparator()
                sub.addAction(
                    "Remove link", lambda lid=ln.id: self._remove_link(lid))
                edit.addMenu(sub)
            menu.addMenu(edit)
        menu.exec(global_pos)

    def _move_event(self, scene_id: int, delta: int) -> None:
        """Move an event one column earlier/later — an explicit reorder that
        opts into Custom Timeline Order. Writes the timeline-specific order
        only, never Scene.sort_order, so the Outline/Manuscript is unaffected."""
        order = list(self._event_order)
        if scene_id not in order:
            return
        i = order.index(scene_id)
        j = max(0, min(i + delta, len(order) - 1))
        if j != i:
            order.insert(j, order.pop(i))
            self._enter_custom_order(order)
            self._notify()

    def _rename_event(self, scene_id: int) -> None:
        scene = self._db.get_scene_by_id(scene_id)
        if scene is None:
            return
        name, ok = QInputDialog.getText(
            self, "Rename event", "Title:", text=scene.title or "")
        if ok and name.strip():
            self._db.update_scene_title(scene_id, name.strip())
            self._notify()

    def _set_event_color(self, scene_id: int, key: str) -> None:
        self._db.update_scene_color(scene_id, key)
        self._notify()

    def _assign_lane(self, scene_id: int, lane_name: str) -> None:
        self._db.update_scene_plotline(scene_id, lane_name)
        self._notify()

    # -- interactions: links ------------------------------------------------

    def _start_link(self, scene_id: int) -> None:
        self._pending_link_source = scene_id
        scene = self._db.get_scene_by_id(scene_id)
        title = (scene.title if scene else "") or f"scene {scene_id}"
        self._status.setText(f"Linking from “{title}” — pick a target's menu")
        self._cancel_link_btn.setVisible(True)

    def _finish_link(self, target_id: int, link_type: str, color_key: str) -> None:
        src = self._pending_link_source
        self._cancel_link()
        if src is None:
            return
        self._db.add_timeline_link(
            self._project_id, src, target_id,
            color_label=color_key or "gray", link_type=link_type,
        )
        self._notify()

    def _cancel_link(self) -> None:
        self._pending_link_source = None
        self._status.setText("")
        self._cancel_link_btn.setVisible(False)

    def _remove_link(self, link_id: int) -> None:
        self._db.remove_timeline_link(link_id)
        self._notify()

    def _set_link_label(self, link_id: int) -> None:
        link = next((ln for ln in self._links if ln.id == link_id), None)
        cur = (link.label if link else "") or ""
        text, ok = QInputDialog.getText(
            self, "Link label", "Label (relation note):", text=cur)
        if ok:
            self._db.set_timeline_link_label(link_id, text.strip())
            self._notify()

    def _set_link_color(self, link_id: int, key: str) -> None:
        self._db.set_timeline_link_color(link_id, key)
        self._notify()

    def _set_link_type(self, link_id: int, link_type: str) -> None:
        self._db.set_timeline_link_type(link_id, link_type)
        self._notify()

    # -- interactions: structure links (event → Act / Chapter / Scene) -------

    def _struct_ref_label(self, sl) -> str:
        """Canonical chip label for a structure link: 'Act 1' / 'Ch 1.2'.

        Falls back to the raw target name if the Act/Chapter no longer exists
        (a renamed/deleted target shows safely, never crashes)."""
        nums = getattr(self, "_structure_numbers", {})
        if sl.target_type == "act":
            n = nums.get("acts", {}).get(sl.target_ref, "")
            return f"Act {n}" if n else sl.target_ref
        if sl.target_type == "chapter":
            for (_a, c), v in nums.get("chapters", {}).items():
                if c == sl.target_ref:
                    return f"Ch {v}" if v else sl.target_ref
        return sl.target_ref

    def _add_structure_link(self, scene_id: int, ttype: str, ref: str) -> None:
        self._db.add_timeline_structure_link(
            self._project_id, scene_id, ttype, ref,
        )
        self._notify()

    def _remove_structure_link(self, link_id: int) -> None:
        self._db.remove_timeline_structure_link(link_id)
        self._notify()

    def _link_to_scene_direct(self, source_id: int, target_id: int) -> None:
        """Direct 'Link to Scene' (event↔event) chosen from a list."""
        self._db.add_timeline_link(
            self._project_id, source_id, target_id,
            color_label="gray", link_type="custom",
        )
        self._notify()

    # -- notify / refresh ---------------------------------------------------

    def _notify(self) -> None:
        from storyplanner.project_events import get_event_bus
        bus = get_event_bus()
        bus.plot_changed.emit()
        bus.project_data_changed.emit()
        if self._on_data_changed:
            self._on_data_changed()
        self.refresh()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._sync_header_scroll(self._hscroll.verticalScrollBar().value())
