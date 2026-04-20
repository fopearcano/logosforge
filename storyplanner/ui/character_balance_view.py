"""Character & Arc Balance View — distribution visualization."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from storyplanner.character_balance import (
    ArcPresence,
    BalanceData,
    CharacterPresence,
    compute_balance,
    flag_color,
)
from storyplanner.db import Database
from storyplanner.ui import theme


class _PresenceRow(QFrame):
    """A single row: name + bar + optional flag indicator."""

    def __init__(
        self, name: str, count: int, max_count: int,
        flag: str = "",
        on_click: Callable[[], None] | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("balanceRow")
        self.setCursor(Qt.CursorShape.PointingHandCursor if on_click else Qt.CursorShape.ArrowCursor)
        self._on_click = on_click

        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 3, 4, 3)
        layout.setSpacing(8)

        name_label = QLabel(name)
        name_label.setObjectName("balanceRowName")
        name_label.setMinimumWidth(100)
        name_label.setMaximumWidth(140)
        layout.addWidget(name_label)

        bar = QProgressBar()
        bar.setObjectName("balanceBar")
        bar.setMaximum(max(max_count, 1))
        bar.setValue(count)
        bar.setTextVisible(False)
        bar.setMaximumHeight(8)
        layout.addWidget(bar, stretch=1)

        if flag:
            color = flag_color(flag)
            bar.setStyleSheet(
                f"QProgressBar::chunk {{ background-color: {color}; border-radius: 4px; }}"
            )

        count_label = QLabel(str(count))
        count_label.setObjectName("balanceRowCount")
        count_label.setMinimumWidth(24)
        count_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        layout.addWidget(count_label)

        if flag:
            flag_label = QLabel(flag)
            flag_label.setObjectName("balanceFlag")
            flag_label.setStyleSheet(f"color: {flag_color(flag)};")
            layout.addWidget(flag_label)

    def mousePressEvent(self, event) -> None:
        if self._on_click and event.button() == Qt.MouseButton.LeftButton:
            self._on_click()
        super().mousePressEvent(event)


class CharacterBalanceView(QWidget):
    """Character and arc balance visualization."""

    def __init__(
        self,
        db: Database,
        project_id: int,
        on_character_selected: Callable[[int], None] | None = None,
        on_plotline_selected: Callable[[str], None] | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._db = db
        self._project_id = project_id
        self._on_character_selected = on_character_selected
        self._on_plotline_selected = on_plotline_selected
        self._balance: BalanceData | None = None

        self.setObjectName("characterBalanceView")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)

        title = QLabel("Character & Arc Balance")
        title.setObjectName("balanceTitle")
        layout.addWidget(title)

        scroll = QScrollArea()
        scroll.setObjectName("balanceScroll")
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self._content = QWidget()
        self._content_layout = QVBoxLayout(self._content)
        self._content_layout.setContentsMargins(0, 0, 0, 0)
        self._content_layout.setSpacing(4)
        scroll.setWidget(self._content)
        layout.addWidget(scroll)

        self.refresh()

    def refresh(self) -> None:
        self._balance = compute_balance(self._db, self._project_id)
        self._rebuild()

    def _rebuild(self) -> None:
        layout = self._content_layout
        while layout.count():
            child = layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        if self._balance is None:
            return

        if self._balance.characters:
            header = QLabel("Characters")
            header.setObjectName("balanceSectionHeader")
            layout.addWidget(header)

            max_char = max(p.scene_count for p in self._balance.characters) if self._balance.characters else 1

            for presence in self._balance.characters:
                callback = None
                if self._on_character_selected:
                    cid = presence.char_id
                    callback = lambda _cid=cid: self._on_character_selected(_cid)
                row = _PresenceRow(
                    presence.name, presence.scene_count, max_char,
                    flag=presence.flag, on_click=callback,
                )
                layout.addWidget(row)

        if self._balance.arcs:
            spacer = QWidget()
            spacer.setFixedHeight(16)
            layout.addWidget(spacer)

            header = QLabel("Arcs (Plotlines)")
            header.setObjectName("balanceSectionHeader")
            layout.addWidget(header)

            max_arc = max(a.scene_count for a in self._balance.arcs) if self._balance.arcs else 1

            for arc in self._balance.arcs:
                callback = None
                if self._on_plotline_selected:
                    pl = arc.plotline
                    callback = lambda _pl=pl: self._on_plotline_selected(_pl)
                row = _PresenceRow(
                    arc.plotline, arc.scene_count, max_arc,
                    flag=arc.flag, on_click=callback,
                )
                layout.addWidget(row)

        if not self._balance.characters and not self._balance.arcs:
            empty = QLabel("No characters or plotlines defined yet.")
            empty.setObjectName("balanceEmpty")
            layout.addWidget(empty)

        layout.addStretch()

    def get_balance(self) -> BalanceData | None:
        return self._balance
