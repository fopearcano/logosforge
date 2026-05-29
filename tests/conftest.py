"""Shared test fixtures."""

import os
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication


@pytest.fixture(scope="session", autouse=True)
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


@pytest.fixture(autouse=True)
def _nonblocking_message_boxes(monkeypatch):
    """Stop modal QMessageBox dialogs from blocking headless tests.

    Several flows (e.g. MainWindow.closeEvent's unsaved-changes prompt)
    open a modal QMessageBox; with no event loop and no user, exec()
    blocks forever. No test asserts on QMessageBox return values, so we
    return safe non-destructive defaults: warnings discard, questions
    answer No, info/critical acknowledge.
    """
    from PySide6.QtWidgets import QMessageBox

    SB = QMessageBox.StandardButton
    monkeypatch.setattr(
        QMessageBox, "warning",
        staticmethod(lambda *a, **k: SB.Discard), raising=False,
    )
    monkeypatch.setattr(
        QMessageBox, "question",
        staticmethod(lambda *a, **k: SB.No), raising=False,
    )
    monkeypatch.setattr(
        QMessageBox, "information",
        staticmethod(lambda *a, **k: SB.Ok), raising=False,
    )
    monkeypatch.setattr(
        QMessageBox, "critical",
        staticmethod(lambda *a, **k: SB.Ok), raising=False,
    )
    yield


@pytest.fixture(autouse=True)
def _auto_accept_project_dialogs(monkeypatch):
    """Auto-accept the modal project dialogs so headless tests that
    invoke _on_new_project() (which opens NewProjectDialog.exec()) don't
    block. No test drives these dialogs interactively, so returning
    Accepted lets the create-new-project flow proceed with its defaults.
    """
    from PySide6.QtWidgets import QDialog
    from storyplanner.ui.new_project_dialog import NewProjectDialog
    monkeypatch.setattr(
        NewProjectDialog, "exec",
        lambda self: QDialog.DialogCode.Accepted, raising=False,
    )
    try:
        from storyplanner.ui.project_settings_dialog import ProjectSettingsDialog
        monkeypatch.setattr(
            ProjectSettingsDialog, "exec",
            lambda self: QDialog.DialogCode.Rejected, raising=False,
        )
    except Exception:
        pass
    yield


@pytest.fixture(autouse=True)
def _reset_event_bus():
    """Give every test a fresh project event bus.

    The bus is a process-global singleton. Headless tests have no Qt
    event loop, so widgets and windows connected to it are never
    destroyed (deleteLater never runs, objects aren't GC'd promptly) and
    their slots would accumulate across tests — every emit would then fan
    out to a growing pile of stale receivers, eventually stalling the
    suite. Resetting the singleton around each test keeps emits scoped to
    that test's own objects.
    """
    from storyplanner import project_events
    project_events._INSTANCE = None
    yield
    project_events._INSTANCE = None
