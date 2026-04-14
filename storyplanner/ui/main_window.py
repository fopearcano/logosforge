"""Main window with a sidebar and content area."""

from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("StoryPlanner")
        self.resize(900, 600)

        central = QWidget()
        root_layout = QHBoxLayout(central)

        # -- Left sidebar ----------------------------------------------------
        sidebar = QWidget()
        sidebar.setFixedWidth(160)
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(0, 0, 0, 0)

        for label in ("Projects", "Characters", "Places", "Notes", "Scenes"):
            btn = QPushButton(label)
            sidebar_layout.addWidget(btn)

        # Push buttons to the top
        sidebar_layout.addStretch()

        # -- Right content area ----------------------------------------------
        self.content_area = QLabel("Select a section from the sidebar")
        self.content_area.setWordWrap(True)

        # -- Assemble --------------------------------------------------------
        root_layout.addWidget(sidebar)
        root_layout.addWidget(self.content_area, stretch=1)

        self.setCentralWidget(central)
