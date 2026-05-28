"""Central registry mapping mode names → NarrativeEngine instances."""

from __future__ import annotations

from typing import TYPE_CHECKING

from storyplanner.narrative_engines.base import NarrativeEngine
from storyplanner.narrative_engines.novel import NOVEL_ENGINE
from storyplanner.narrative_engines.screenplay import SCREENPLAY_ENGINE

if TYPE_CHECKING:
    from storyplanner.models.models import Project


ALL_ENGINES: dict[str, NarrativeEngine] = {
    NOVEL_ENGINE.name: NOVEL_ENGINE,
    SCREENPLAY_ENGINE.name: SCREENPLAY_ENGINE,
}

# Display order in pickers.  Other engines (stage_script, graphic_novel,
# series) will register here in later iterations; for now the codebase
# still has format_mode values for them — we transparently fall back to
# the Novel engine so existing projects keep working.
ENGINE_ORDER: tuple[str, ...] = (NOVEL_ENGINE.name, SCREENPLAY_ENGINE.name)


def get_engine(name: str | None) -> NarrativeEngine:
    """Resolve a mode name to its engine; unknown names fall back to Novel."""
    if not name:
        return NOVEL_ENGINE
    return ALL_ENGINES.get(name, NOVEL_ENGINE)


def engine_for_project(project: "Project | None") -> NarrativeEngine:
    """Pick the engine for a Project — driven by project.format_mode today."""
    if project is None:
        return NOVEL_ENGINE
    return get_engine(getattr(project, "format_mode", "novel"))
