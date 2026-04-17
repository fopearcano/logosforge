"""Search view — global search across project entities."""

from collections.abc import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from storyplanner.db import Database

USER_ROLE = Qt.ItemDataRole.UserRole
MAX_PREVIEW = 80


class SearchView(QWidget):
    def __init__(
        self,
        db: Database,
        project_id: int,
        on_result_selected: Callable[[str, int], None] | None = None,
    ) -> None:
        super().__init__()
        self._db = db
        self._project_id = project_id
        self._on_result_selected = on_result_selected

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Search"))

        search_row = QHBoxLayout()
        self._search_input = QLineEdit()
        self._search_input.setPlaceholderText("Search characters, places, notes, scenes...")
        self._search_input.returnPressed.connect(self._on_search)
        search_row.addWidget(self._search_input)

        search_btn = QPushButton("Search")
        search_btn.clicked.connect(self._on_search)
        search_row.addWidget(search_btn)

        layout.addLayout(search_row)

        self._status_label = QLabel("")
        layout.addWidget(self._status_label)

        self._results_list = QListWidget()
        self._results_list.itemDoubleClicked.connect(self._on_item_double_clicked)
        layout.addWidget(self._results_list)

        self._search_input.setFocus()

    def _on_search(self) -> None:
        query = self._search_input.text().strip()
        self._results_list.clear()

        if not query:
            self._status_label.setText("Enter a search term.")
            return

        results = self._db.search_project(self._project_id, query)

        if not results:
            self._status_label.setText(f'No results for "{query}".')
            return

        self._status_label.setText(f"{len(results)} result(s) for \"{query}\".")

        for result in results:
            label = f"[{result['type']}] {result['label']}"
            preview = result.get("preview", "")
            if preview:
                if len(preview) > MAX_PREVIEW:
                    preview = preview[:MAX_PREVIEW] + "..."
                label += f"  —  {preview}"

            item = QListWidgetItem(label)
            item.setData(USER_ROLE, (result["type"], result["id"]))
            self._results_list.addItem(item)

    def _on_item_double_clicked(self, item: QListWidgetItem) -> None:
        if self._on_result_selected is None:
            return
        data = item.data(USER_ROLE)
        if data:
            entity_type, entity_id = data
            self._on_result_selected(entity_type, entity_id)
