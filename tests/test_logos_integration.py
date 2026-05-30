"""Logos Phase 0 — MainWindow + toolbar integration tests.

Verifies the inline Logos entry points in Manuscript and Outline, that the
toolbar is section-aware and non-intrusive, and — critically — that the
existing AssistantPanel / AssistantDock are present and unchanged.
"""

from __future__ import annotations

import warnings

import pytest
from PySide6.QtWidgets import QApplication

warnings.filterwarnings("ignore")

from storyplanner.db import Database
from storyplanner.ui.logos.logos_toolbar import LogosToolbar
from storyplanner.ui.main_window import MainWindow


@pytest.fixture(scope="module", autouse=True)
def _qapp():
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture(autouse=True)
def _isolated_settings(monkeypatch, tmp_path):
    import storyplanner.settings as settings
    settings._instance = None
    monkeypatch.setattr(settings, "CONFIG_DIR", tmp_path, raising=False)
    monkeypatch.setattr(settings, "SETTINGS_FILE", tmp_path / "settings.json", raising=False)
    yield
    settings._instance = None


def _window():
    db = Database()
    pid = db.create_project("P", narrative_engine="novel").id
    db.create_scene(pid, "Opening", act="Act I", content="The hero walks.")
    win = MainWindow(db, pid)
    win.resize(1400, 900)
    return win, db, pid


def test_window_has_logos_controller_and_hidden_toolbar():
    win, _, _ = _window()
    assert hasattr(win, "_logos_controller")
    assert isinstance(win._logos_toolbar, LogosToolbar)
    assert win._logos_visible is False  # hidden / non-intrusive by default


def test_assistant_panel_and_dock_unchanged_by_logos():
    win, _, _ = _window()
    # The Phase 1 assistant architecture is still intact and separate.
    assert hasattr(win, "_assistant_panel")
    assert hasattr(win, "_assistant_dock")
    assert win._assistant_dock.panel is win._assistant_panel
    # Logos toolbar is not the assistant panel.
    assert win._logos_toolbar is not win._assistant_panel


def test_toggle_logos_shows_manuscript_actions():
    win, _, _ = _window()
    win._show_manuscript()
    win._set_active_section("Manuscript")
    win._toggle_logos()
    QApplication.instance().processEvents()
    assert win._logos_visible is True
    labels = [b.text() for b in win._logos_toolbar._action_buttons]
    assert "Explain Selection" in labels
    assert "Identify Problem" in labels


def test_toolbar_actions_update_on_section_switch():
    win, _, _ = _window()
    win._show_manuscript(); win._set_active_section("Manuscript")
    win._toggle_logos()  # show
    win._show_plan(); win._set_active_section("Outline")
    QApplication.instance().processEvents()
    labels = [b.text() for b in win._logos_toolbar._action_buttons]
    assert "Identify Structure Problem" in labels
    assert "Explain Selection" not in labels  # manuscript-only


def test_build_logos_context_from_window():
    win, _, pid = _window()
    win._show_manuscript(); win._set_active_section("Manuscript")
    QApplication.instance().processEvents()
    ctx = win._build_logos_context()
    assert ctx.project_id == pid
    assert ctx.section_name == "Manuscript"
    assert ctx.narrative_engine == "novel"


def test_outline_context_has_template_field():
    win, _, _ = _window()
    win._show_plan(); win._set_active_section("Outline")
    QApplication.instance().processEvents()
    ctx = win._build_logos_context()
    assert ctx.section_name == "Outline"
    assert ctx.active_block_type == "outline_node"
    assert hasattr(ctx, "outline_template")


def test_toolbar_run_action_renders_result_with_injected_chat():
    win, _, _ = _window()
    win._show_manuscript(); win._set_active_section("Manuscript")
    win._toggle_logos()
    win._logos_controller._provider_resolver = lambda: object()
    win._logos_controller._chat_fn = lambda m, p: "Context summary.\n- point A"
    done = []
    win._logos_toolbar.action_completed.connect(lambda n, ok: done.append((n, ok)))
    win._logos_toolbar.run_action("summarize_context")
    QApplication.instance().processEvents()
    assert done == [("summarize_context", True)]
    assert "Context summary." in win._logos_toolbar._result.toPlainText()


def test_toolbar_does_not_grab_focus():
    win, _, _ = _window()
    from PySide6.QtCore import Qt
    assert win._logos_toolbar.focusPolicy() == Qt.FocusPolicy.NoFocus


def test_logos_toggle_does_not_mutate_db():
    win, db, pid = _window()
    before = len(db.get_all_scenes(pid))
    win._show_manuscript(); win._set_active_section("Manuscript")
    win._toggle_logos()
    win._logos_controller._provider_resolver = lambda: None
    win._logos_toolbar.run_action("summarize_context")
    QApplication.instance().processEvents()
    assert len(db.get_all_scenes(pid)) == before
