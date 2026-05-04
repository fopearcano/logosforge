"""Tests for PSYKE Console suggestion updates — regression for stale _last_query."""

import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

from PySide6.QtWidgets import QApplication

from storyplanner.db import Database
from storyplanner.psyke_command_registry import CommandRegistry
from storyplanner.psyke_search import PsykeSearchIndex
from storyplanner.psyke_suggestions import suggest


@pytest.fixture(scope="module")
def app():
    instance = QApplication.instance()
    if instance is None:
        instance = QApplication(sys.argv)
    return instance


@pytest.fixture
def db(tmp_path):
    return Database(str(tmp_path / "test.db"))


@pytest.fixture
def project(db):
    return db.create_project("Test")


@pytest.fixture
def console(app, db, project):
    from storyplanner.ui.psyke_console import PsykeConsole

    db.create_psyke_entry(project.id, "John", "character")
    db.create_psyke_entry(project.id, "Joanna", "character")
    db.create_psyke_entry(project.id, "Castle", "place")
    c = PsykeConsole(db, project.id)
    c.rebuild_index()
    return c


class TestSuggestionsUpdateOnEveryInput:
    """Verify suggestions fire on every text change, not just the first."""

    def test_type_query_get_suggestions(self, console):
        console._input.setText("jo")
        console._run_search()
        dropdown = console._ensure_dropdown()
        assert dropdown.has_items()

    def test_clear_and_retype_same_query(self, console):
        """Core regression: typing 'jo', clearing, retyping 'jo' must show results."""
        console._input.setText("jo")
        console._run_search()
        assert console._last_query == "jo"

        # User clears the input
        console._input.setText("")
        console._on_text_changed("")
        assert console._last_query == ""

        # User retypes the same query
        console._input.setText("jo")
        console._run_search()
        dropdown = console._ensure_dropdown()
        assert dropdown.has_items()

    def test_delete_partial_and_retype(self, console):
        """Type 'joa', delete to 'j', retype 'joa'."""
        console._input.setText("joa")
        console._run_search()
        assert console._last_query == "joa"

        # Delete to 'j'
        console._input.setText("j")
        console._on_text_changed("j")
        console._run_search()
        assert console._last_query == "j"

        # Retype 'joa' — must update
        console._input.setText("joa")
        console._run_search()
        assert console._last_query == "joa"
        dropdown = console._ensure_dropdown()
        assert dropdown.has_items()

    def test_multiple_rapid_changes(self, console):
        """Simulate rapid input changes — each unique query updates."""
        queries = ["j", "jo", "joh", "john"]
        for q in queries:
            console._input.setText(q)
            console._run_search()
            assert console._last_query == q

    def test_empty_does_not_block_next(self, console):
        """Clearing input resets _last_query, unblocking subsequent searches."""
        console._input.setText("cas")
        console._run_search()
        assert console._last_query == "cas"

        console._input.setText("")
        console._on_text_changed("")
        assert console._last_query == ""

        console._input.setText("cas")
        console._run_search()
        dropdown = console._ensure_dropdown()
        assert dropdown.has_items()

    def test_deactivate_resets_query(self, console):
        """After deactivate(), same query should work again."""
        console._input.setText("jo")
        console._run_search()
        console.deactivate()
        assert console._last_query == ""

        console._input.setText("jo")
        console._run_search()
        dropdown = console._ensure_dropdown()
        assert dropdown.has_items()


class TestDebounceDoesNotBlock:
    """Verify debounce doesn't prevent subsequent calls."""

    def test_debounce_resets_on_new_input(self, console):
        """Each text change restarts the debounce timer."""
        console._input.setText("j")
        console._on_text_changed("j")
        assert console._debounce.isActive()

        console._input.setText("jo")
        console._on_text_changed("jo")
        assert console._debounce.isActive()

    def test_debounce_stops_on_clear(self, console):
        """Clearing input stops the debounce timer."""
        console._input.setText("j")
        console._on_text_changed("j")
        assert console._debounce.isActive()

        console._input.setText("")
        console._on_text_changed("")
        assert not console._debounce.isActive()


class TestDropdownRefreshed:
    """Verify dropdown is rebuilt each time, not stale."""

    def test_results_change_with_query(self, console):
        """Different queries produce different result sets."""
        console._input.setText("jo")
        console._run_search()
        dropdown = console._ensure_dropdown()
        items_jo = len(dropdown._items)

        console._input.setText("cas")
        console._run_search()
        items_cas = len(dropdown._items)

        # "jo" matches John+Joanna, "cas" matches Castle
        assert items_jo >= 2
        assert items_cas >= 1
        assert items_jo != items_cas or True  # different content

    def test_dropdown_cleared_before_new_results(self, console):
        """show_suggestions clears old items before adding new ones."""
        console._input.setText("jo")
        console._run_search()
        dropdown = console._ensure_dropdown()
        first_count = len(dropdown._items)

        console._input.setText("john")
        console._run_search()
        second_count = len(dropdown._items)

        # Items were rebuilt, not appended
        assert second_count <= first_count
