"""Minimal main window — just enough to confirm the app runs."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QMainWindow, QVBoxLayout, QWidget


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("StoryPlanner")
        self.resize(900, 600)

        central = QWidget()
        layout = QVBoxLayout(central)

        label = QLabel("StoryPlanner — ready for next steps")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(label)

        self.setCentralWidget(central)
