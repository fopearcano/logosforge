"""Timeline view — plotline-column or chapter-column overview with minimal editing."""

from collections.abc import Callable

from PySide6.QtCore import QEvent, QPoint, Qt
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
CARD_BEAT_STYLE = (
    "QFrame { background: #fafafa; border: 1px solid #d0d0d0;"
    " border-left: 3px solid #90a4ae; border-radius: 3px; }"
)
CARD_KEY_BEAT_STYLE = (
    "QFrame { background: #fff8f0; border: 1px solid #d0d0d0;"
    " border-left: 3px solid #ff9800; border-radius: 3px; }"
)
CARD_SELECTED_STYLE = (
    "QFrame { background: #e3f2fd; border: 2px solid #64b5f6; border-radius: 3px; }"
)

KEY_BEATS = {"Midpoint", "All Is Lost", "Finale", "Climax", "Break into Three"}

DRAG_THRESHOLD = 10


class TimelineView(QWidget):
    def __init__(
        self,
        db: Database,
        project_id: int,
        on_scene_selected: Callable[[int], None] | None = None,
        on_data_changed: Callable[[], None] | None = None,
    ) -> None:
        super().__init__()
        self._db = db
        self._project_id = project_id
        self._on_scene_selected = on_scene_selected
        self._on_data_changed = on_data_changed

        # Scene data: (row, col) → (scene_id, title, plotline)
        self._cell_data: dict[tuple[int, int], tuple[int, str, str]] = {}
        self._selected_scene_id: int | None = None
        self._selected_card: QWidget | None = None

        # Cached plotline list (refreshed on each table load)
        self._plotline_values: list[str] = []

        # Drag state
        self._reset_drag_state()

        # Column-to-plotline mapping (rebuilt on each load)
        self._col_to_plotline: dict[int, str] = {}

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

        self._filter_label = QLabel("Filter by Chapter")
        controls_row.addWidget(self._filter_label)
        self._filter_combo = QComboBox()
        self._filter_combo.currentTextChanged.connect(self._on_filter_changed)
        controls_row.addWidget(self._filter_combo)

        controls_row.addWidget(QLabel("Focus Character"))
        self._char_combo = QComboBox()
        self._char_combo.currentIndexChanged.connect(self._on_focus_char_changed)
        controls_row.addWidget(self._char_combo)

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
        self._table.viewport().installEventFilter(self)
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

        self._focus_char_id: int | None = None
        self._refresh_focus_characters()
        self._refresh_filter()
        self._reload()

    # -- Focus character -----------------------------------------------------

    def _refresh_focus_characters(self) -> None:
        self._char_combo.blockSignals(True)
        self._char_combo.clear()
        self._char_combo.addItem("None", None)
        for char in self._db.get_all_characters(self._project_id):
            self._char_combo.addItem(char.name, char.id)
        self._char_combo.blockSignals(False)

    def _on_focus_char_changed(self, index: int) -> None:
        self._focus_char_id = self._char_combo.currentData()
        self._reload()

    # -- Mode ----------------------------------------------------------------

    def _get_mode(self) -> str:
        return self._mode_combo.currentText()

    def _on_mode_changed(self) -> None:
        self._refresh_filter()
        self._reload()

    # -- Filter --------------------------------------------------------------

    def _is_filtered(self) -> bool:
        return self._filter_combo.currentText() != FILTER_ALL

    def _refresh_filter(self) -> None:
        if self._get_mode() == MODE_BY_PLOTLINE:
            self._filter_label.setText("Filter by Chapter")
            values = self._db.get_scene_chapters(self._project_id)
        else:
            self._filter_label.setText("Filter by Plotline")
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

        # Cache plotline values once per table load
        self._plotline_values = self._db.get_scene_plotlines(self._project_id)

        mode = self._get_mode()
        if mode == MODE_BY_PLOTLINE:
            columns = self._build_columns(scenes, key=lambda s: s.plotline)
            prefix = "Plotline"
        else:
            columns = self._build_columns(scenes, key=lambda s: s.chapter)
            prefix = "Chapter"

        col_to_idx = {name: i for i, name in enumerate(columns)}

        self._col_to_plotline.clear()
        if mode == MODE_BY_PLOTLINE:
            for name, idx in col_to_idx.items():
                self._col_to_plotline[idx] = "" if name == UNASSIGNED else name

        self._table.blockSignals(True)
        self._table.setRowCount(0)
        self._table.setColumnCount(max(len(columns), 1))

        if columns:
            headers = [f"{prefix}: {c}" for c in columns]
        else:
            headers = [f"{prefix}: {UNASSIGNED}"]
        self._table.setHorizontalHeaderLabels(headers)
        self._table.setRowCount(len(scenes))
        self._cell_data.clear()

        # Pre-fetch character states for focus character
        scene_state: dict[int, str] = {}
        if self._focus_char_id is not None:
            for scene in scenes:
                for cid, state in self._db.get_scene_character_states(scene.id):
                    if cid == self._focus_char_id:
                        scene_state[scene.id] = state
                        break

        for row, scene in enumerate(scenes):
            if mode == MODE_BY_PLOTLINE:
                col_name = scene.plotline if scene.plotline else UNASSIGNED
            else:
                col_name = scene.chapter if scene.chapter else UNASSIGNED
            col = col_to_idx[col_name]

            char_state = scene_state.get(scene.id, "")
            card = self._create_card(row + 1, scene, mode, char_state)
            self._table.setCellWidget(row, col, card)
            self._table.setRowHeight(row, max(card.sizeHint().height(), 56))
            self._cell_data[(row, col)] = (scene.id, scene.title, scene.plotline)

        header = self._table.horizontalHeader()
        for i in range(self._table.columnCount()):
            header.setSectionResizeMode(i, QHeaderView.ResizeMode.Stretch)

        self._table.blockSignals(False)
        self._update_status_count()

    def _update_status_count(self) -> None:
        count = len(self._cell_data)
        filter_text = self._filter_combo.currentText()
        is_filtered = filter_text != FILTER_ALL

        if count == 0 and is_filtered:
            self._status_label.setText(
                f'No scenes match filter "{filter_text}".'
            )
        elif count == 0:
            self._status_label.setText("No scenes to display.")
        elif is_filtered:
            self._status_label.setText(
                f"{count} scene(s) shown (filtered by {filter_text})."
            )
        else:
            self._status_label.setText(f"{count} scene(s).")

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

    def _create_card(self, index: int, scene, mode: str, char_state: str = "") -> QFrame:
        card = QFrame()
        card.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

        if scene.beat and scene.beat in KEY_BEATS:
            base_style = CARD_KEY_BEAT_STYLE
        elif scene.beat:
            base_style = CARD_BEAT_STYLE
        else:
            base_style = CARD_STYLE
        card.setStyleSheet(base_style)
        card.setProperty("base_style", base_style)

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
        if scene.act:
            meta_parts.append(scene.act)
        if mode == MODE_BY_PLOTLINE and scene.chapter:
            meta_parts.append(scene.chapter)
        elif mode == MODE_BY_CHAPTER and scene.plotline:
            meta_parts.append(scene.plotline)

        meta_label = QLabel(" \u00b7 ".join(meta_parts))
        meta_label.setStyleSheet("color: #757575;")
        card_layout.addWidget(meta_label)

        if scene.beat:
            beat_color = "#e65100" if scene.beat in KEY_BEATS else "#607d8b"
            beat_label = QLabel(f"[{scene.beat}]")
            beat_label.setStyleSheet(f"color: {beat_color}; font-size: 11px;")
            card_layout.addWidget(beat_label)

        if scene.tags:
            tags_label = QLabel(scene.tags)
            tags_label.setStyleSheet("color: #9e9e9e; font-size: 10px;")
            tags_label.setWordWrap(True)
            card_layout.addWidget(tags_label)

        if char_state:
            state_label = QLabel(f"\u2192 {char_state}")
            state_label.setStyleSheet(
                "color: #5c6bc0; font-size: 11px; font-style: italic;"
            )
            state_label.setWordWrap(True)
            card_layout.addWidget(state_label)

        return card

    # -- Drag-and-drop reordering --------------------------------------------

    def _reset_drag_state(self) -> None:
        self._drag_start_row: int | None = None
        self._drag_start_col: int | None = None
        self._drag_start_pos: QPoint | None = None
        self._drag_scene_id: int | None = None
        self._dragging = False

    def eventFilter(self, obj: object, event: QEvent) -> bool:
        if obj is not self._table.viewport():
            return super().eventFilter(obj, event)

        if event.type() == QEvent.Type.MouseButtonPress:
            return self._on_drag_press(event)

        if event.type() == QEvent.Type.MouseMove:
            return self._on_drag_move(event)

        if event.type() == QEvent.Type.MouseButtonRelease:
            return self._on_drag_release(event)

        return super().eventFilter(obj, event)

    def _on_drag_press(self, event) -> bool:
        if event.button() != Qt.MouseButton.LeftButton:
            return False

        self._reset_drag_state()

        if self._is_filtered():
            return False

        pos = event.position().toPoint()
        row = self._table.rowAt(pos.y())
        col = self._table.columnAt(pos.x())
        cell_data = self._cell_data.get((row, col))

        if cell_data is not None:
            self._drag_start_row = row
            self._drag_start_col = col
            self._drag_start_pos = pos
            self._drag_scene_id = cell_data[0]

        return False

    def _on_drag_move(self, event) -> bool:
        if self._drag_start_pos is None:
            return False

        if not self._dragging:
            distance = (
                event.position().toPoint() - self._drag_start_pos
            ).manhattanLength()
            if distance > DRAG_THRESHOLD:
                self._dragging = True
                self._table.setCursor(Qt.CursorShape.ClosedHandCursor)

        return False

    def _on_drag_release(self, event) -> bool:
        was_dragging = self._dragging
        drag_scene = self._drag_scene_id
        start_row = self._drag_start_row
        start_col = self._drag_start_col

        self._reset_drag_state()

        if not was_dragging or drag_scene is None:
            return False
        if start_row is None or start_col is None:
            return False

        self._table.unsetCursor()

        pos = event.position().toPoint()
        target_row = self._table.rowAt(pos.y())
        target_col = self._table.columnAt(pos.x())

        if target_row < 0 or target_col < 0:
            return True

        row_changed = target_row != start_row
        col_changed = target_col != start_col

        if not row_changed and not col_changed:
            return True

        self._selected_scene_id = drag_scene

        if col_changed and target_col in self._col_to_plotline:
            new_plotline = self._col_to_plotline[target_col]
            self._db.update_scene_plotline(drag_scene, new_plotline)

        if row_changed:
            self._db.reorder_scene(drag_scene, target_row)

        self._reload()
        if self._on_data_changed:
            self._on_data_changed()
        return True

    # -- Selection -----------------------------------------------------------

    def _on_cell_clicked(self, row: int, col: int) -> None:
        cell_data = self._cell_data.get((row, col))
        scene_id = cell_data[0] if cell_data else None
        self._apply_selection(scene_id)

    def _apply_selection(self, scene_id: int | None) -> None:
        self._selected_scene_id = scene_id
        has_scene = scene_id is not None
        self._set_actions_enabled(has_scene)

        if self._selected_card is not None:
            restore = self._selected_card.property("base_style") or CARD_STYLE
            self._selected_card.setStyleSheet(restore)
            self._selected_card = None

        if has_scene:
            cell = self._find_scene_cell(scene_id)
            if cell is not None:
                _, title, plotline = self._cell_data[cell]
                self._sync_plotline_combo(plotline)
                self._status_label.setText(f"Selected: {title}")
                card = self._table.cellWidget(cell[0], cell[1])
                if card:
                    card.setStyleSheet(CARD_SELECTED_STYLE)
                    self._selected_card = card
            else:
                self._selected_scene_id = None
                self._set_actions_enabled(False)
                self._clear_plotline_combo()
                self._update_status_count()
        else:
            self._clear_plotline_combo()
            self._table.setCurrentCell(-1, -1)
            self._update_status_count()

    def _find_scene_cell(self, scene_id: int) -> tuple[int, int] | None:
        for cell, data in self._cell_data.items():
            if data[0] == scene_id:
                return cell
        return None

    def _reselect(self) -> None:
        if self._selected_scene_id is None:
            self._apply_selection(None)
            return

        cell = self._find_scene_cell(self._selected_scene_id)
        if cell is not None:
            self._table.setCurrentCell(cell[0], cell[1])
            self._apply_selection(self._selected_scene_id)
        else:
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
        for pl in self._plotline_values:
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
        if self._on_data_changed:
            self._on_data_changed()

    def _on_move_down(self) -> None:
        if self._selected_scene_id is None:
            return
        self._db.move_scene_down(self._selected_scene_id)
        self._reload()
        if self._on_data_changed:
            self._on_data_changed()

    def _on_set_plotline(self) -> None:
        if self._selected_scene_id is None:
            return
        plotline = self._plotline_combo.currentText().strip()
        self._db.update_scene_plotline(self._selected_scene_id, plotline)
        self._reload()
        if self._on_data_changed:
            self._on_data_changed()

    # -- Navigation ----------------------------------------------------------

    def _on_double_click(self, row: int, column: int) -> None:
        if self._on_scene_selected is None:
            return
        cell_data = self._cell_data.get((row, column))
        if cell_data is not None:
            self._on_scene_selected(cell_data[0])
