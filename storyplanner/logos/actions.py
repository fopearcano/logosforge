"""Logos action registry.

Mirrors the lightweight declarative style of ``connector_registry`` but for the
inline Logos layer. Phase 0 registers only **diagnostic / read-only** actions;
destructive actions are listed in :data:`FUTURE_ACTIONS` as TODO names and are
intentionally NOT registered, so the controller can never run them yet.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# Section identifiers Phase 0 integrates with.
SECTION_MANUSCRIPT = "Manuscript"
SECTION_OUTLINE = "Outline"


@dataclass(frozen=True)
class LogosAction:
    name: str
    label: str
    description: str
    category: str               # "diagnostic" (Phase 0) | "destructive" (future)
    sections: tuple[str, ...]   # sections this action is offered in
    prompt: str                 # instruction sent to the shared chat backend
    needs_selection: bool = False
    destructive: bool = False

    def applies_to(self, section_name: str) -> bool:
        return not self.sections or section_name in self.sections

    def describe(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "label": self.label,
            "description": self.description,
            "category": self.category,
            "sections": list(self.sections),
            "needs_selection": self.needs_selection,
            "destructive": self.destructive,
        }


_REGISTRY: dict[str, LogosAction] = {}


def register(action: LogosAction) -> LogosAction:
    _REGISTRY[action.name] = action
    return action


def get_action(name: str) -> LogosAction | None:
    return _REGISTRY.get(name)


def list_actions() -> list[LogosAction]:
    return list(_REGISTRY.values())


def list_actions_for_section(section_name: str) -> list[LogosAction]:
    return [a for a in _REGISTRY.values() if a.applies_to(section_name)]


def describe_all_actions() -> list[dict[str, Any]]:
    return [a.describe() for a in _REGISTRY.values()]


# ---------------------------------------------------------------------------
# Phase 0 diagnostic actions (read-only, non-destructive)
# ---------------------------------------------------------------------------

_LOGOS_INSTRUCTION = (
    "You are Logos, an inline writing companion embedded next to the author's "
    "work. Give concise, concrete, non-destructive feedback. Do NOT rewrite or "
    "replace the text. When helpful, end with a short bullet list (lines "
    "starting with '- ') of specific, optional suggestions."
)

register(LogosAction(
    name="explain_selection",
    label="Explain Selection",
    description="Explain what the selected passage is doing and how it reads.",
    category="diagnostic",
    sections=(SECTION_MANUSCRIPT,),
    prompt=(
        "Explain the selected passage: its intent, tone, and how it reads. "
        "Point out anything notable. Do not rewrite it."
    ),
    needs_selection=True,
))

register(LogosAction(
    name="suggest_revision",
    label="Suggest Revision",
    description="Suggest revision directions for the selection (no rewrite).",
    category="diagnostic",
    sections=(SECTION_MANUSCRIPT,),
    prompt=(
        "Suggest concrete revision directions for the selected passage "
        "(clarity, rhythm, imagery, tension). Describe the options as "
        "suggestions only — do NOT produce a rewritten version."
    ),
    needs_selection=True,
))

register(LogosAction(
    name="identify_scene_problem",
    label="Identify Problem",
    description="Diagnose possible problems in the current scene/selection.",
    category="diagnostic",
    sections=(SECTION_MANUSCRIPT,),
    prompt=(
        "Identify likely craft problems in this scene/selection (goal, "
        "conflict, stakes, pacing, POV, continuity). List them as concise "
        "diagnostics. Do not rewrite anything."
    ),
))

register(LogosAction(
    name="identify_structure_problem",
    label="Identify Structure Problem",
    description="Diagnose structural problems in the current outline context.",
    category="diagnostic",
    sections=(SECTION_OUTLINE,),
    prompt=(
        "Using the outline context, identify likely structural problems "
        "(missing turning points, pacing, act balance, cause/effect gaps). "
        "List them as diagnostics. Do not generate new outline nodes."
    ),
))

register(LogosAction(
    name="summarize_context",
    label="Summarize Context",
    description="Summarize the current working context for orientation.",
    category="diagnostic",
    sections=(SECTION_MANUSCRIPT, SECTION_OUTLINE),
    prompt=(
        "Summarize the current working context (what this scene/section is "
        "about and where it sits in the story) in a few sentences."
    ),
))


# ---------------------------------------------------------------------------
# Deferred to later phases (NOT registered — TODO only).
# These will require explicit preview + confirmation before any mutation.
# ---------------------------------------------------------------------------

FUTURE_ACTIONS: tuple[str, ...] = (
    "rewrite_selection",
    "replace_selection",
    "expand_selection",
    "generate_scene",
    "generate_outline_node",
)
