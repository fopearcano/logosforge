"""Global settings dialog — appearance and AI provider configuration.

Layout contract (small-screen safe): all settings content lives inside a
vertical ``QScrollArea`` and the Close button row is **sticky outside** the
scroll area, so the bottom controls stay reachable no matter how tall the
content grows. The dialog clamps its height to the available screen geometry
(~85%), so it works on small laptops, at high UI scale and in fullscreen.
"""

from __future__ import annotations

from collections.abc import Callable

from pathlib import Path

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QDesktopServices, QGuiApplication
from PySide6.QtCore import QUrl

import storyplanner.connector_actions  # noqa: F401 — registers actions
from storyplanner.cloud_storage import detect_cloud_folders
from storyplanner.connector_registry import list_actions
from storyplanner.settings import get_manager as get_settings
from storyplanner.ui import theme
from storyplanner.ui.provider_settings import ProviderSettingsWidget


class SettingsDialog(QDialog):
    def __init__(
        self,
        on_theme_changed: Callable[[str], None],
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._on_theme_changed = on_theme_changed

        self.setWindowTitle("Preferences")
        self.setMinimumWidth(480)
        self.setMaximumWidth(600)
        self.setMinimumHeight(320)
        # Never grow past the available screen height — on small screens the
        # content scrolls instead, and the bottom buttons stay reachable.
        avail_h = self._available_screen_height()
        if avail_h:
            self.setMaximumHeight(self._max_dialog_height(avail_h))
            self.resize(560, min(640, self.maximumHeight()))

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # -- Scrollable settings content --------------------------------------
        content = QWidget()
        content.setObjectName("prefsContent")
        layout = QVBoxLayout(content)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(10)

        # -- Appearance ---------------------------------------------------------
        layout.addWidget(self._section_label("Appearance"))

        theme_row = QHBoxLayout()
        theme_row.setSpacing(6)
        self._theme_btns: dict[str, QPushButton] = {}
        for name, label in (
            ("Dark", "Dark"),
            ("Light (Green)", "Light (Green)"),
            ("Light (Warm)", "Light (Warm)"),
        ):
            btn = QPushButton(label)
            btn.setCheckable(True)
            btn.setChecked(name == theme.current_palette())
            btn.clicked.connect(lambda _, n=name: self._select_theme(n))
            theme_row.addWidget(btn)
            self._theme_btns[name] = btn
        theme_row.addStretch()
        layout.addLayout(theme_row)

        layout.addWidget(self._separator())

        # -- AI Provider --------------------------------------------------------
        layout.addWidget(self._section_label("AI Provider"))

        self._provider_widget = ProviderSettingsWidget(compact=True)
        self._restore_ai_settings()
        layout.addWidget(self._provider_widget)

        layout.addWidget(self._separator())

        # -- Connector ----------------------------------------------------------
        layout.addWidget(self._section_label("Connector"))
        desc = QLabel(
            "Allow the AI to invoke safe actions on this project "
            "(listing scenes, creating notes, etc.)."
        )
        desc.setWordWrap(True)
        desc.setStyleSheet(f"color: {theme.TEXT_MUTED}; font-size: 11px;")
        layout.addWidget(desc)

        mgr = get_settings()
        self._conn_enabled = QCheckBox("Enable Connector")
        self._conn_enabled.setChecked(bool(mgr.get("connector_enabled")))
        layout.addWidget(self._conn_enabled)

        self._conn_writes = QCheckBox("Allow write actions (create / update)")
        self._conn_writes.setChecked(bool(mgr.get("connector_allow_writes")))
        layout.addWidget(self._conn_writes)

        self._conn_confirm = QCheckBox("Confirm before running write actions")
        self._conn_confirm.setChecked(bool(mgr.get("connector_confirm_writes")))
        layout.addWidget(self._conn_confirm)

        self._conn_enabled.toggled.connect(self._update_connector_enabled)
        self._update_connector_enabled(self._conn_enabled.isChecked())

        actions_label = QLabel("Available actions (uncheck to disable):")
        actions_label.setStyleSheet(
            f"color: {theme.TEXT_SECONDARY}; font-size: 11px; margin-top: 4px;"
        )
        layout.addWidget(actions_label)

        disabled = set(mgr.get("connector_disabled_actions") or [])
        self._conn_actions_list = QListWidget()
        self._conn_actions_list.setMaximumHeight(140)
        for action in sorted(list_actions(), key=lambda a: (a.category, a.name)):
            item = QListWidgetItem(f"[{action.category}] {action.name} — {action.description}")
            item.setData(Qt.ItemDataRole.UserRole, action.name)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(
                Qt.CheckState.Unchecked if action.name in disabled else Qt.CheckState.Checked
            )
            self._conn_actions_list.addItem(item)
        layout.addWidget(self._conn_actions_list)

        layout.addWidget(self._separator())

        # -- Project Storage ----------------------------------------------------
        layout.addWidget(self._section_label("Project Storage"))
        storage_desc = QLabel(
            "Pick a default folder for new projects.  Choosing a cloud-synced "
            "folder (Dropbox, Google Drive, iCloud Drive, OneDrive, NAS) lets "
            "you open the project from any device once the file sync completes."
        )
        storage_desc.setWordWrap(True)
        storage_desc.setStyleSheet(f"color: {theme.TEXT_MUTED}; font-size: 11px;")
        layout.addWidget(storage_desc)

        folder_row = QHBoxLayout()
        folder_row.setSpacing(6)
        self._default_folder_input = QLineEdit()
        self._default_folder_input.setText(
            str(mgr.get("default_projects_folder") or "")
        )
        self._default_folder_input.setPlaceholderText(
            "Default projects folder (optional)"
        )
        folder_row.addWidget(self._default_folder_input, stretch=1)

        choose_btn = QPushButton("Choose…")
        choose_btn.clicked.connect(self._on_choose_default_folder)
        folder_row.addWidget(choose_btn)

        open_btn = QPushButton("Open")
        open_btn.clicked.connect(self._on_open_default_folder)
        folder_row.addWidget(open_btn)

        layout.addLayout(folder_row)

        detected = detect_cloud_folders()
        if detected:
            detected_label = QLabel("Detected cloud folders on this machine:")
            detected_label.setStyleSheet(
                f"color: {theme.TEXT_SECONDARY}; font-size: 11px; margin-top: 4px;"
            )
            layout.addWidget(detected_label)
            self._cloud_combo = QComboBox()
            self._cloud_combo.addItem("(pick a detected folder)", "")
            for folder in detected:
                self._cloud_combo.addItem(
                    f"{folder.provider} — {folder.path}", str(folder.path)
                )
            self._cloud_combo.currentIndexChanged.connect(
                self._on_cloud_combo_changed
            )
            layout.addWidget(self._cloud_combo)
        else:
            self._cloud_combo = None  # type: ignore[assignment]

        layout.addStretch()

        scroll = QScrollArea()
        scroll.setObjectName("prefsScrollArea")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setWidget(content)
        outer.addWidget(scroll, stretch=1)

        # -- Sticky bottom button row (outside the scroll area) ---------------
        outer.addWidget(self._separator())
        close_row = QHBoxLayout()
        close_row.setContentsMargins(16, 8, 16, 10)
        close_row.addStretch()
        close_btn = QPushButton("Close")
        close_btn.setObjectName("prefsCloseButton")
        close_btn.setDefault(True)
        close_btn.clicked.connect(self.accept)
        close_row.addWidget(close_btn)
        outer.addLayout(close_row)

    # -- screen-aware sizing ---------------------------------------------------
    @staticmethod
    def _max_dialog_height(available_height: int) -> int:
        """Clamp to ~85% of the available screen height (never below the
        dialog's minimum, so tiny/odd geometries still get a usable window)."""
        return max(320, int(available_height * 0.85))

    def _available_screen_height(self) -> int:
        screen = self.screen() or QGuiApplication.primaryScreen()
        if screen is None:
            return 0
        return screen.availableGeometry().height()

    def _restore_ai_settings(self) -> None:
        mgr = get_settings()
        pw = self._provider_widget
        saved_provider = str(mgr.get("ai_provider") or "")

        raw_memory = mgr.get("ai_provider_memory")
        memory = dict(raw_memory) if isinstance(raw_memory, dict) else {}
        if saved_provider:
            entry = dict(memory.get(saved_provider) or {})
            entry.setdefault("model", str(mgr.get("ai_model") or ""))
            entry.setdefault("base_url", str(mgr.get("ai_base_url") or ""))
            entry.setdefault("api_key", str(mgr.get("ai_api_key") or ""))
            memory[saved_provider] = entry
        pw.set_provider_memory(memory)

        idx = pw._provider_combo.findText(saved_provider)
        if idx >= 0:
            pw._provider_combo.setCurrentIndex(idx)
        pw.reload_current_provider()

    def accept(self) -> None:
        config = self._provider_widget.get_provider_config()
        mgr = get_settings()
        mgr.set("ai_provider", config.name)
        mgr.set("ai_model", config.model)
        mgr.set("ai_api_key", self._provider_widget._key_input.text().strip())
        mgr.set("ai_base_url", config.base_url)
        mgr.set("ai_provider_memory", self._provider_widget.provider_memory())

        mgr.set("connector_enabled", self._conn_enabled.isChecked())
        mgr.set("connector_allow_writes", self._conn_writes.isChecked())
        mgr.set("connector_confirm_writes", self._conn_confirm.isChecked())
        disabled: list[str] = []
        for i in range(self._conn_actions_list.count()):
            item = self._conn_actions_list.item(i)
            if item.checkState() != Qt.CheckState.Checked:
                disabled.append(str(item.data(Qt.ItemDataRole.UserRole)))
        mgr.set("connector_disabled_actions", disabled)

        mgr.set(
            "default_projects_folder",
            self._default_folder_input.text().strip(),
        )
        super().accept()

    def _on_choose_default_folder(self) -> None:
        start = self._default_folder_input.text().strip() or str(Path.home())
        chosen = QFileDialog.getExistingDirectory(
            self, "Default Projects Folder", start,
        )
        if chosen:
            self._default_folder_input.setText(chosen)

    def _on_open_default_folder(self) -> None:
        path = self._default_folder_input.text().strip()
        if not path:
            return
        if not Path(path).is_dir():
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(path))

    def _on_cloud_combo_changed(self, index: int) -> None:
        if self._cloud_combo is None:
            return
        data = self._cloud_combo.itemData(index)
        if data:
            self._default_folder_input.setText(str(data))

    def _update_connector_enabled(self, enabled: bool) -> None:
        self._conn_writes.setEnabled(enabled)
        self._conn_confirm.setEnabled(enabled)

    def _select_theme(self, name: str) -> None:
        for key, btn in self._theme_btns.items():
            btn.setChecked(key == name)
        self._on_theme_changed(name)

    @staticmethod
    def _section_label(text: str) -> QLabel:
        label = QLabel(text)
        label.setStyleSheet(
            f"color: {theme.TEXT_PRIMARY}; font-weight: bold; font-size: 13px;"
            f" padding: 0; margin: 0;"
        )
        return label

    @staticmethod
    def _separator() -> QFrame:
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"color: {theme.BORDER};")
        return sep
