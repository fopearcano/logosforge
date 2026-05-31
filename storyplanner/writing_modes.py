"""Project Writing Mode — the unified, project-level source of truth (Phase 9).

A project declares *what kind of work it is* (Novel / Screenplay / Graphic Novel
/ Stage Script / Series) and every section adapts to that declaration. This
module is the single API every feature should use instead of scattering mode
strings.

Design note — no duplicate column:
    The project's writing mode is **the existing ``Project.narrative_engine``
    field**, not a new column. Its allowed values already match the five modes
    exactly, it already migrates safely (``db/database.py::_migrate`` backfills
    legacy ``format_mode`` → engine, defaulting to ``novel``), and
    ``project_compat`` already validates it. Adding a second ``writing_mode``
    column would duplicate that field and risk the two diverging, so this module
    is a thin facade over ``narrative_engine`` plus the one piece that did not
    exist yet: per-mode **display structural vocabulary** and a short
    **medium-constraints** summary for the Assistant.

Pure data/logic: no Qt, no LLM, no DB mutation (except the explicit
``set_project_writing_mode`` helper, which writes the canonical field).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from storyplanner.project_compat import (
    ENGINE_GRAPHIC_NOVEL,
    ENGINE_NOVEL,
    ENGINE_SCREENPLAY,
    ENGINE_SERIES,
    ENGINE_STAGE_SCRIPT,
    ENGINE_LABELS,
    get_project_narrative_engine,
)

if TYPE_CHECKING:
    from storyplanner.models.models import Project

# -- Mode identity -----------------------------------------------------------
# Mode names are the same canonical strings as the narrative engine, so the
# Strategy Layer / Logos / engines all keep working unchanged.
NOVEL = ENGINE_NOVEL
SCREENPLAY = ENGINE_SCREENPLAY
GRAPHIC_NOVEL = ENGINE_GRAPHIC_NOVEL
STAGE_SCRIPT = ENGINE_STAGE_SCRIPT
SERIES = ENGINE_SERIES

DEFAULT_MODE = NOVEL

ALL_MODES: tuple[str, ...] = (
    NOVEL, SCREENPLAY, GRAPHIC_NOVEL, STAGE_SCRIPT, SERIES,
)

# Human-readable names (re-exported from the engine labels — one source).
MODE_LABELS: dict[str, str] = dict(ENGINE_LABELS)


def is_valid_mode(mode: str | None) -> bool:
    """True if *mode* is one of the five supported writing modes."""
    return (mode or "").strip() in ALL_MODES


def normalize_mode(mode: str | None) -> str:
    """Return a valid mode, falling back safely to ``novel``."""
    candidate = (mode or "").strip()
    return candidate if candidate in ALL_MODES else DEFAULT_MODE


def mode_label(mode: str | None) -> str:
    """Display name for a mode (``novel`` fallback)."""
    return MODE_LABELS.get(normalize_mode(mode), MODE_LABELS[DEFAULT_MODE])


# -- Structural vocabulary (Dashboard / section display layer) ---------------
# A curated, friendly display vocabulary per mode. This is the *presentation*
# layer; the generation-level structural units live on each NarrativeEngine
# (``narrative_engines`` / ``engine_structural_units``) and are intentionally
# finer-grained. These match the Phase 9 spec's Dashboard examples.
_STRUCTURAL_UNITS: dict[str, tuple[str, ...]] = {
    NOVEL: ("Acts", "Chapters", "Scenes"),
    SCREENPLAY: ("Acts", "Sequences", "Scenes"),
    GRAPHIC_NOVEL: ("Chapters", "Pages", "Panels"),
    STAGE_SCRIPT: ("Acts", "Scenes", "Beats", "Stage Directions"),
    SERIES: ("Seasons", "Episodes", "A/B/C Plots", "Scenes"),
}


def structural_units(mode: str | None) -> tuple[str, ...]:
    """Ordered display labels for a mode's structural hierarchy."""
    return _STRUCTURAL_UNITS[normalize_mode(mode)]


def structural_vocabulary(mode: str | None) -> str:
    """One-line vocabulary string, e.g. ``"Acts / Chapters / Scenes"``."""
    return " / ".join(structural_units(mode))


# -- Medium constraints (Assistant [Project Mode] block) ---------------------
# Short, deterministic phrase naming the craft priorities the medium imposes.
# Kept terse on purpose — the Assistant should never receive a mode manual.
_MEDIUM_CONSTRAINTS: dict[str, str] = {
    NOVEL: ("prose voice, interiority, chapter rhythm, character arc, "
            "thematic recurrence"),
    SCREENPLAY: ("visual action, scene economy, dialogue subtext, "
                 "setup/payoff, cinematic pacing"),
    GRAPHIC_NOVEL: ("page turns, panel rhythm, visual motif, image/text "
                    "balance, dialogue compression"),
    STAGE_SCRIPT: ("playable conflict, blocking, entrances/exits, "
                   "performable dialogue, scene economy"),
    SERIES: ("episode engine, A/B/C plots, season arc, recurring payoff, "
             "long-term continuity"),
}


def medium_constraints(mode: str | None) -> str:
    """Compact primary-constraints phrase for a mode."""
    return _MEDIUM_CONSTRAINTS[normalize_mode(mode)]


def mode_context_block(mode: str | None) -> str:
    """The short, labelled ``[Project Mode]`` block for Assistant context.

    Deterministic and tiny — mode name plus the medium's primary constraints.
    """
    m = normalize_mode(mode)
    return (
        "[Project Mode]\n"
        f"Mode: {mode_label(m)}\n"
        f"Primary constraints: {medium_constraints(m)}."
    )


# -- Project accessors -------------------------------------------------------


def get_project_writing_mode(project: "Project | None") -> str:
    """Return the project's writing mode (the canonical ``narrative_engine``).

    Always a valid mode — unknown / missing values fall back to ``novel`` via
    ``project_compat``.
    """
    return normalize_mode(get_project_narrative_engine(project))


def get_project_writing_mode_by_id(db, project_id: int) -> str:
    """Convenience: resolve a project id straight to its writing mode."""
    try:
        return get_project_writing_mode(db.get_project_by_id(project_id))
    except Exception:
        return DEFAULT_MODE


def set_project_writing_mode(db, project_id: int, mode: str) -> str:
    """Persist *mode* as the project's writing mode (canonical field).

    Normalizes invalid input to ``novel`` and writes via the existing
    ``update_project_narrative_engine`` path so all downstream behavior (manuscript
    format sync, strategy routing, etc.) stays consistent. Returns the stored mode.
    """
    normalized = normalize_mode(mode)
    db.update_project_narrative_engine(project_id, normalized)
    return normalized
