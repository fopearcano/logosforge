"""Timeline view — plotline-column or chapter-column overview with minimal editing."""

from collections.abc import Callable

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableWidget,
    QVBoxLayout,
    QWidget,
)

from storyplanner.db import Database

FILTER_ALL = "All"
UNASSIGNED = "Unassigned"

MODE_BY_PLOTLINE = "By Plotline"
MODE_BY_CHAPTER = "By Chapter"

CARD_STYLE = "QFrame { background: #ffffff; border: 1px solid #d0d0d0; border-radius: 3px; }"
CARD_SELECTED_STYLE = (
    "QFrame { background: #e3f2fd; border: 2px solid #64b5f6; border-radius: 3px; }"
)


class TimelineView(QWidget):
    def __init__(
        self,
        db: Database,
        project_id: int,
        on_scene_selected: Callable[[int], None] | None = None,
    ) -> None:
        super().__init__()
        self._db = db
        self._project_id = project_id
        self._on_scene_selected = on_scene_selected
        self._cell_scene_ids: dict[tuple[int, int], int] = {}
        self._selected_scene_id: int | None = None
        self._selected_card: QWidget | None = None

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Timeline"))

        # -- Mode + filter row -----------------------------------------------
        controls_row = QHBoxLayout()

        controls_row.addWidget(QLabel("View"))
        self._mode_combo = QComboBox()
        self._mode_combo.addItem(MODE_BY_PLOTLINE)
        self._mode_combo.addItem(MODE_BY_CHAPTER)
        self._mode_combo.currentTextChanged.connect(self._on_mode_changed)
        controls_row.addWidget(self._mode_combo)

        self._filter_label = QLabel("Chapter")
        controls_row.addWidget(self._filter_label)
        self._filter_combo = QComboBox()
        self._filter_combo.currentTextChanged.connect(self._on_filter_changed)
        controls_row.addWidget(self._filter_combo)

        controls_row.addStretch()
        layout.addLayout(controls_row)

        # -- Table -----------------------------------------------------------
        self._table = QTableWidget()
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self._table.verticalHeader().setVisible(False)
        self._table.setShowGrid(False)
        self._table.cellClicked.connect(self._on_cell_clicked)
        self._table.cellDoubleClicked.connect(self._on_double_click)
        layout.addWidget(self._table)

        # -- Status line -----------------------------------------------------
        self._status_label = QLabel("")
        layout.addWidget(self._status_label)

        # -- Actions ---------------------------------------------------------
        actions_row = QHBoxLayout()

        self._move_up_btn = QPushButton("Move Up")
        self._move_up_btn.setEnabled(False)
        self._move_up_btn.clicked.connect(self._on_move_up)
        actions_row.addWidget(self._move_up_btn)

        self._move_down_btn = QPushButton("Move Down")
        self._move_down_btn.setEnabled(False)
        self._move_down_btn.clicked.connect(self._on_move_down)
        actions_row.addWidget(self._move_down_btn)

        actions_row.addWidget(QLabel("Plotline:"))
        self._plotline_combo = QComboBox()
        self._plotline_combo.setEditable(True)
        self._plotline_combo.setEnabled(False)
        actions_row.addWidget(self._plotline_combo)

        self._set_plotline_btn = QPushButton("Set Plotline")
        self._set_plotline_btn.setEnabled(False)
        self._set_plotline_btn.clicked.connect(self._on_set_plotline)
        actions_row.addWidget(self._set_plotline_btn)

        actions_row.addStretch()
        layout.addLayout(actions_row)

        self._refresh_filter()
        self._reload()

    # -- Mode ----------------------------------------------------------------

    def _get_mode(self) -> str:
        return self._mode_combo.currentText()

    def _on_mode_changed(self) -> None:
        self._refresh_filter()
        self._reload()

    # -- Filter --------------------------------------------------------------

    def _refresh_filter(self) -> None:
        if self._get_mode() == MODE_BY_PLOTLINE:
            self._filter_label.setText("Chapter")
            values = self._db.get_scene_chapters(self._project_id)
        else:
            self._filter_label.setText("Plotline")
            values = self._db.get_scene_plotlines(self._project_id)

        combo = self._filter_combo
        combo.blockSignals(True)
        current = combo.currentText()
        combo.clear()
        combo.addItem(FILTER_ALL)
        for val in values:
            combo.addItem(val)
        idx = combo.findText(current)
        combo.setCurrentIndex(idx if idx >= 0 else 0)
        combo.blockSignals(False)

    def _get_filter_kwargs(self) -> dict[str, str | None]:
        text = self._filter_combo.currentText()
        value = None if text == FILTER_ALL else text
        if self._get_mode() == MODE_BY_PLOTLINE:
            return {"chapter": value}
        else:
            return {"plotline": value}

    def _on_filter_changed(self) -> None:
        self._reload()

    # -- Reload (single entry point) -----------------------------------------

    def _reload(self) -> None:
        self._selected_card = None
        self._load_table()
        self._reselect()

    def _load_table(self) -> None:
        scenes = self._db.get_all_scenes(
            self._project_id,
            **self._get_filter_kwargs(),
        )

        mode = self._get_mode()
        if mode == MODE_BY_PLOTLINE:
            columns = self._build_columns(scenes, key=lambda s: s.plotline)
            prefix = "Plotline"
        else:
            columns = self._build_columns(scenes, key=lambda s: s.chapter)
            prefix = "Chapter"

        col_to_idx = {name: i for i, name in enumerate(columns)}

        self._table.blockSignals(True)
        self._table.setRowCount(0)
        self._table.setColumnCount(max(len(columns), 1))

        if columns:
            headers = [f"{prefix}: {c}" for c in columns]
        else:
            headers = [f"{prefix}: {UNASSIGNED}"]
        self._table.setHorizontalHeaderLabels(headers)
        self._table.setRowCount(len(scenes))
        self._cell_scene_ids.clear()

        for row, scene in enumerate(scenes):
            if mode == MODE_BY_PLOTLINE:
                col_name = scene.plotline if scene.plotline else UNASSIGNED
            else:
                col_name = scene.chapter if scene.chapter else UNASSIGNED
            col = col_to_idx[col_name]

            card = self._create_card(row + 1, scene, mode)
            self._table.setCellWidget(row, col, card)
            self._table.setRowHeight(row, max(card.sizeHint().height(), 56))
            self._cell_scene_ids[(row, col)] = scene.id

        header = self._table.horizontalHeader()
        for i in range(self._table.columnCount()):
            header.setSectionResizeMode(i, QHeaderView.ResizeMode.Stretch)

        self._table.blockSignals(False)

        if not scenes:
            self._status_label.setText("No scenes to display.")
        else:
            self._status_label.setText(f"{len(scenes)} scene(s).")

    def _build_columns(self, scenes: list, key: Callable) -> list[str]:
        columns: list[str] = []
        seen: set[str] = set()
        has_unassigned = False
        for scene in scenes:
            value = key(scene)
            if not value:
                has_unassigned = True
            elif value not in seen:
                seen.add(value)
                columns.append(value)
        if has_unassigned:
            columns.append(UNASSIGNED)
        return columns

    def _create_card(self, index: int, scene, mode: str) -> QFrame:
        card = QFrame()
        card.setStyleSheet(CARD_STYLE)
        card.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(6, 4, 6, 4)
        card_layout.setSpacing(2)

        title_label = QLabel(scene.title)
        bold_font = QFont()
        bold_font.setBold(True)
        title_label.setFont(bold_font)
        title_label.setWordWrap(True)
        card_layout.addWidget(title_label)

        meta_parts = [f"#{index}"]
        if mode == MODE_BY_PLOTLINE and scene.chapter:
            meta_parts.append(scene.chapter)
        elif mode == MODE_BY_CHAPTER and scene.plotline:
            meta_parts.append(scene.plotline)

        meta_label = QLabel(" \u00b7 ".join(meta_parts))
        meta_label.setStyleSheet("color: #757575;")
        card_layout.addWidget(meta_label)

        return card

    # -- Selection -----------------------------------------------------------

    def _on_cell_clicked(self, row: int, col: int) -> None:
        self._apply_selection(self._cell_scene_ids.get((row, col)))

    def _apply_selection(self, scene_id: int | None) -> None:
        self._selected_scene_id = scene_id
        has_scene = scene_id is not None
        self._set_actions_enabled(has_scene)

        if self._selected_card is not None:
            self._selected_card.setStyleSheet(CARD_STYLE)
            self._selected_card = None

        if has_scene:
            scene = self._db.get_scene_by_id(scene_id)
            if scene:
                self._sync_plotline_combo(scene.plotline)
                self._status_label.setText(f"Selected: {scene.title}")
                self._highlight_selected_card()
            else:
                self._selected_scene_id = None
                self._set_actions_enabled(False)
                self._clear_plotline_combo()
        else:
            self._clear_plotline_combo()
            self._table.setCurrentCell(-1, -1)

    def _highlight_selected_card(self) -> None:
        if self._selected_scene_id is None:
            return
        for (row, col), sid in self._cell_scene_ids.items():
            if sid == self._selected_scene_id:
                card = self._table.cellWidget(row, col)
                if card:
                    card.setStyleSheet(CARD_SELECTED_STYLE)
                    self._selected_card = card
                return

    def _reselect(self) -> None:
        if self._selected_scene_id is None:
            self._apply_selection(None)
            return

        for (row, col), sid in self._cell_scene_ids.items():
            if sid == self._selected_scene_id:
                self._table.setCurrentCell(row, col)
                self._apply_selection(sid)
                return

        self._apply_selection(None)

    def _set_actions_enabled(self, enabled: bool) -> None:
        self._move_up_btn.setEnabled(enabled)
        self._move_down_btn.setEnabled(enabled)
        self._plotline_combo.setEnabled(enabled)
        self._set_plotline_btn.setEnabled(enabled)

    def _sync_plotline_combo(self, current_plotline: str) -> None:
        combo = self._plotline_combo
        combo.blockSignals(True)
        combo.clear()
        combo.addItem("")
        for pl in self._db.get_scene_plotlines(self._project_id):
            combo.addItem(pl)
        idx = combo.findText(current_plotline)
        if idx >= 0:
            combo.setCurrentIndex(idx)
        else:
            combo.setCurrentText(current_plotline)
        combo.blockSignals(False)

    def _clear_plotline_combo(self) -> None:
        combo = self._plotline_combo
        combo.blockSignals(True)
        combo.clear()
        combo.blockSignals(False)

    # -- Actions -------------------------------------------------------------

    def _on_move_up(self) -> None:
        if self._selected_scene_id is None:
            return
        self._db.move_scene_up(self._selected_scene_id)
        self._reload()

    def _on_move_down(self) -> None:
        if self._selected_scene_id is None:
            return
        self._db.move_scene_down(self._selected_scene_id)
        self._reload()

    def _on_set_plotline(self) -> None:
        if self._selected_scene_id is None:
            return
        plotline = self._plotline_combo.currentText().strip()
        self._db.update_scene_plotline(self._selected_scene_id, plotline)
        self._reload()

    # -- Navigation ----------------------------------------------------------

    def _on_double_click(self, row: int, column: int) -> None:
        if self._on_scene_selected is None:
            return
        scene_id = self._cell_scene_ids.get((row, column))
        if scene_id is not None:
            self._on_scene_selected(scene_id)
