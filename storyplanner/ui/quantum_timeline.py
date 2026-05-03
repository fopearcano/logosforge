"""Quantum Timeline Superposition — canon scenes + active branches in parallel."""

from __future__ import annotations

from collections import defaultdict
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMenu,
    QMessageBox,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from storyplanner.quantum_outliner.state import get_state
from storyplanner.ui import theme

if TYPE_CHECKING:
    from storyplanner.db import Database


class QuantumTimelineWidget(QWidget):
    """Canon timeline with quantum branch lanes beneath linked scenes."""

    branch_selected = Signal(str, str)
    collapse_requested = Signal(str, str)
    archive_requested = Signal(str)

    def __init__(self, db: "Database", project_id: int) -> None:
        super().__init__()
        self._db = db
        self._project_id = project_id
        self._selected_wf: str | None = None
        self._selected_branch: str | None = None

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll.setObjectName("qtlScroll")
        self._scroll.setFixedHeight(0)
        outer.addWidget(self._scroll)

        self._container = QWidget()
        self._container.setObjectName("qtlContainer")
        self._h_layout = QHBoxLayout(self._container)
        self._h_layout.setContentsMargins(4, 4, 4, 4)
        self._h_layout.setSpacing(0)
        self._h_layout.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        self._scroll.setWidget(self._container)

        self._empty_label = QLabel(
            "Generate possibilities to view timeline superposition."
        )
        self._empty_label.setObjectName("qtlEmpty")
        self._empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        outer.addWidget(self._empty_label)

    def refresh(self) -> None:
        self._clear()
        scenes = self._db.get_all_scenes(self._project_id)
        state = get_state(self._project_id)

        wf_by_scene: dict[int | None, list] = defaultdict(list)
        for wf in state.wavefunctions.values():
            wf_by_scene[wf.source_scene_id].append(wf)

        has_wavefunctions = bool(state.wavefunctions)

        if not has_wavefunctions:
            self._empty_label.setVisible(True)
            self._scroll.setFixedHeight(0)
            return

        self._empty_label.setVisible(False)

        max_branch_rows = 0
        for scene in scenes:
            wfs = wf_by_scene.get(scene.id, [])
            col = self._build_scene_column(scene, wfs)
            self._h_layout.addWidget(col)
            self._h_layout.addSpacing(2)
            for wf in wfs:
                branch_count = len(wf.branches)
                if branch_count > max_branch_rows:
                    max_branch_rows = branch_count

        unlinked = wf_by_scene.get(None, [])
        if unlinked:
            col = self._build_unlinked_column(unlinked)
            self._h_layout.addWidget(col)
            for wf in unlinked:
                branch_count = len(wf.branches)
                if branch_count > max_branch_rows:
                    max_branch_rows = branch_count

        self._h_layout.addStretch()

        height = 28 + max(max_branch_rows, 1) * 52 + 8
        self._scroll.setFixedHeight(min(height, 260))

    def _clear(self) -> None:
        while self._h_layout.count():
            item = self._h_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

    def _build_scene_column(self, scene, wavefunctions: list) -> QFrame:
        col = QFrame()
        col.setObjectName("qtlColumn")
        col.setFixedWidth(140)
        col.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Minimum)

        layout = QVBoxLayout(col)
        layout.setContentsMargins(4, 3, 4, 3)
        layout.setSpacing(2)

        title_text = scene.title or "Untitled"
        if len(title_text) > 20:
            title_text = title_text[:18] + "…"
        title = QLabel(title_text)
        title.setObjectName("qtlSceneTitle")
        title.setToolTip(scene.title or "")
        layout.addWidget(title)

        if wavefunctions:
            for wf in wavefunctions:
                lane = self._build_branch_lane(wf)
                layout.addWidget(lane)
        else:
            spacer = QLabel("")
            spacer.setFixedHeight(4)
            layout.addWidget(spacer)

        layout.addStretch()
        return col

    def _build_unlinked_column(self, wavefunctions: list) -> QFrame:
        col = QFrame()
        col.setObjectName("qtlColumn")
        col.setFixedWidth(140)
        col.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Minimum)

        layout = QVBoxLayout(col)
        layout.setContentsMargins(4, 3, 4, 3)
        layout.setSpacing(2)

        title = QLabel("(unlinked)")
        title.setObjectName("qtlSceneTitle")
        title.setStyleSheet(f"color: {theme.TEXT_MUTED}; font-style: italic;")
        layout.addWidget(title)

        for wf in wavefunctions:
            lane = self._build_branch_lane(wf)
            layout.addWidget(lane)

        layout.addStretch()
        return col

    def _build_branch_lane(self, wf) -> QWidget:
        lane = QWidget()
        lane_layout = QVBoxLayout(lane)
        lane_layout.setContentsMargins(0, 1, 0, 1)
        lane_layout.setSpacing(1)

        for branch in wf.branches:
            node = self._build_branch_node(wf, branch)
            lane_layout.addWidget(node)

        return lane

    def _build_branch_node(self, wf, branch) -> QFrame:
        is_collapsed = wf.collapsed_branch_id == branch.id
        is_archived = wf.is_collapsed() and not is_collapsed
        is_selected = (
            self._selected_wf == wf.id and self._selected_branch == branch.id
        )

        node = QFrame()
        node.setObjectName("qtlBranch")
        node.setCursor(Qt.CursorShape.PointingHandCursor)
        node.setFixedWidth(130)
        node.setProperty("wf_id", wf.id)
        node.setProperty("branch_id", branch.id)

        if is_collapsed:
            status = "collapsed"
            border_color = theme.ACCENT
            bg = theme.get("SELECTION_BG")
        elif is_archived:
            status = "archived"
            border_color = theme.TEXT_MUTED
            bg = theme.BG_DARK
        elif is_selected:
            status = "selected"
            border_color = theme.ACCENT_DIM
            bg = theme.BG_HOVER
        else:
            status = "active"
            border_color = theme.BORDER
            bg = theme.BG_INPUT

        node.setStyleSheet(
            f"QFrame#qtlBranch {{"
            f"  background: {bg};"
            f"  border: 1px solid {border_color};"
            f"  border-radius: 4px;"
            f"}}"
        )

        layout = QVBoxLayout(node)
        layout.setContentsMargins(4, 3, 4, 3)
        layout.setSpacing(1)

        top_row = QHBoxLayout()
        top_row.setSpacing(3)

        title_text = branch.title or "Branch"
        if len(title_text) > 16:
            title_text = title_text[:14] + "…"
        title_lbl = QLabel(title_text)
        title_lbl.setObjectName("qtlBranchTitle")
        title_lbl.setToolTip(branch.title)
        top_row.addWidget(title_lbl, stretch=1)

        badge = QLabel(self._status_badge(status))
        badge.setObjectName("qtlBadge")
        badge.setStyleSheet(self._badge_style(status))
        top_row.addWidget(badge)

        layout.addLayout(top_row)

        if branch.stakes:
            stakes_text = branch.stakes
            if len(stakes_text) > 30:
                stakes_text = stakes_text[:28] + "…"
            stakes_lbl = QLabel(stakes_text)
            stakes_lbl.setObjectName("qtlBranchMeta")
            stakes_lbl.setToolTip(branch.stakes)
            layout.addWidget(stakes_lbl)

        if branch.consequence:
            cons_text = branch.consequence
            if len(cons_text) > 30:
                cons_text = cons_text[:28] + "…"
            cons_lbl = QLabel(cons_text)
            cons_lbl.setObjectName("qtlBranchMeta")
            cons_lbl.setToolTip(branch.consequence)
            layout.addWidget(cons_lbl)

        node.mousePressEvent = lambda ev, w=wf.id, b=branch.id: self._on_branch_click(ev, w, b)

        return node

    def _on_branch_click(self, event, wf_id: str, branch_id: str) -> None:
        if event.button() == Qt.MouseButton.RightButton:
            self._show_branch_menu(event, wf_id, branch_id)
            return
        self._selected_wf = wf_id
        self._selected_branch = branch_id
        self.branch_selected.emit(wf_id, branch_id)
        self.refresh()

    def _show_branch_menu(self, event, wf_id: str, branch_id: str) -> None:
        state = get_state(self._project_id)
        wf = state.get(wf_id)
        if wf is None:
            return

        menu = QMenu(self)

        if not wf.is_collapsed():
            menu.addAction(
                "Collapse this branch",
                lambda: self._confirm_collapse(wf_id, branch_id),
            )

        menu.addAction(
            "Archive wavefunction",
            lambda: self.archive_requested.emit(wf_id),
        )

        menu.exec(event.globalPosition().toPoint())

    def _confirm_collapse(self, wf_id: str, branch_id: str) -> None:
        state = get_state(self._project_id)
        wf = state.get(wf_id)
        if wf is None:
            return
        branch = wf.get_branch(branch_id)
        title = branch.title if branch else branch_id

        reply = QMessageBox.question(
            self,
            "Collapse Branch",
            f"Collapse wavefunction to \"{title}\"?\n\n"
            "This commits this branch as canonical and archives the rest.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.collapse_requested.emit(wf_id, branch_id)

    @staticmethod
    def _status_badge(status: str) -> str:
        return {
            "active": "○",
            "selected": "◉",
            "collapsed": "●",
            "archived": "◌",
        }.get(status, "")

    @staticmethod
    def _badge_style(status: str) -> str:
        color = {
            "active": theme.TEXT_MUTED,
            "selected": theme.ACCENT_DIM,
            "collapsed": theme.ACCENT,
            "archived": theme.TEXT_MUTED,
        }.get(status, theme.TEXT_MUTED)
        return (
            f"QLabel {{ color: {color}; font-size: 10px;"
            f" background: transparent; padding: 0; }}"
        )
