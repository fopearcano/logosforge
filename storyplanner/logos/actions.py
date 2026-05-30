"""Logos action registry.

Mirrors the lightweight declarative style of ``connector_registry`` but for the
inline Logos layer. Phase 1 registers real, non-destructive Manuscript and
Outline actions (analysis, critique, and *preview* generation — alternatives are
returned for the author to consider, never auto-applied).

Destructive / auto-applying actions are listed in :data:`FUTURE_ACTIONS` as TODO
names and are intentionally NOT registered, so the controller can never run them
yet. Every registered action has ``destructive=False``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

# Section identifiers Phase 1 integrates with.
SECTION_MANUSCRIPT = "Manuscript"
SECTION_OUTLINE = "Outline"

# Categories are descriptive tags only; the binding safety invariant is
# ``destructive=False`` for everything registered in this phase.
CATEGORY_DIAGNOSTIC = "diagnostic"   # explain / identify / critique / check
CATEGORY_GENERATIVE = "generative"   # produce suggestions / alternatives (preview)


@dataclass(frozen=True)
class LogosAction:
    name: str
    label: str
    description: str
    category: str
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
# Manuscript actions (selection-aware, non-destructive)
# ---------------------------------------------------------------------------

register(LogosAction(
    name="explain_selection", label="Explain Selection",
    description="Explain what the selected passage is doing and how it reads.",
    category=CATEGORY_DIAGNOSTIC, sections=(SECTION_MANUSCRIPT,),
    needs_selection=True,
    prompt=(
        "Explain the selected passage: its intent, tone, technique, and how it "
        "reads. Note anything notable. Do not rewrite it."
    ),
))

register(LogosAction(
    name="suggest_revision", label="Suggest Revision",
    description="Suggest concrete revision directions (no rewrite).",
    category=CATEGORY_GENERATIVE, sections=(SECTION_MANUSCRIPT,),
    needs_selection=True,
    prompt=(
        "Suggest concrete revision directions for the selected passage "
        "(clarity, rhythm, imagery, tension). Present them as a short bullet "
        "list of options. Do NOT produce a finished rewrite."
    ),
))

register(LogosAction(
    name="rewrite_options", label="Rewrite Options",
    description="Offer 2–3 labelled alternate versions (preview only).",
    category=CATEGORY_GENERATIVE, sections=(SECTION_MANUSCRIPT,),
    needs_selection=True,
    prompt=(
        "Provide 2 to 3 distinct alternate versions of the selected passage, "
        "each preserving its meaning but varying voice/rhythm/emphasis. Label "
        "them clearly as 'Option 1:', 'Option 2:', 'Option 3:'. These are "
        "options for the author to consider — do not pick one or apply changes."
    ),
))

register(LogosAction(
    name="expand", label="Expand",
    description="Show a richer, expanded version of the selection (preview).",
    category=CATEGORY_GENERATIVE, sections=(SECTION_MANUSCRIPT,),
    needs_selection=True,
    prompt=(
        "Show an expanded version of the selected passage — add sensory detail, "
        "beats, or interiority where it serves the scene. Present it as a "
        "labelled 'Expanded version:' preview. Do not replace the original."
    ),
))

register(LogosAction(
    name="compress", label="Compress",
    description="Show a tighter, compressed version of the selection (preview).",
    category=CATEGORY_GENERATIVE, sections=(SECTION_MANUSCRIPT,),
    needs_selection=True,
    prompt=(
        "Show a tighter, compressed version of the selected passage that keeps "
        "its essential meaning and impact. Present it as a labelled 'Compressed "
        "version:' preview. Do not replace the original."
    ),
))

register(LogosAction(
    name="improve_dialogue", label="Improve Dialogue",
    description="Diagnose and suggest stronger dialogue (preview).",
    category=CATEGORY_GENERATIVE, sections=(SECTION_MANUSCRIPT,),
    needs_selection=True,
    prompt=(
        "Focus on the dialogue in the selection. Note what works and what is "
        "flat or on-the-nose, then offer a few sharper line options. Keep them "
        "as suggestions — do not rewrite the whole passage."
    ),
))

register(LogosAction(
    name="improve_subtext", label="Improve Subtext",
    description="Suggest ways to deepen subtext (preview).",
    category=CATEGORY_GENERATIVE, sections=(SECTION_MANUSCRIPT,),
    needs_selection=True,
    prompt=(
        "Analyse the subtext of the selection — what is left unsaid, the gap "
        "between surface and intent — and suggest concrete ways to deepen it. "
        "Offer suggestions, not a finished rewrite."
    ),
))

register(LogosAction(
    name="identify_weakness", label="Identify Weakness",
    description="Diagnose craft weaknesses in the selection/scene.",
    category=CATEGORY_DIAGNOSTIC, sections=(SECTION_MANUSCRIPT,),
    prompt=(
        "Identify the most likely craft weaknesses here (goal, conflict, "
        "stakes, pacing, POV, clarity, continuity). List them as concise "
        "diagnostics. Do not rewrite anything."
    ),
))

# ---------------------------------------------------------------------------
# Outline actions (node-aware, non-destructive)
# ---------------------------------------------------------------------------

register(LogosAction(
    name="summarize_node", label="Summarize Node",
    description="Summarize the selected outline node in context.",
    category=CATEGORY_DIAGNOSTIC, sections=(SECTION_OUTLINE,),
    prompt=(
        "Summarize the selected outline node (what it is about and the work it "
        "does in the story) in a few sentences, using the surrounding outline."
    ),
))

register(LogosAction(
    name="identify_structure_problem", label="Identify Structure Problem",
    description="Diagnose structural problems around the selected node.",
    category=CATEGORY_DIAGNOSTIC, sections=(SECTION_OUTLINE,),
    prompt=(
        "Using the outline context, identify likely structural problems around "
        "the selected node (missing turning points, pacing, act balance, "
        "cause/effect gaps). List them as diagnostics. Do not generate nodes."
    ),
))

register(LogosAction(
    name="suggest_next_beat", label="Suggest Next Beat",
    description="Suggest candidate next beats (suggestions only).",
    category=CATEGORY_GENERATIVE, sections=(SECTION_OUTLINE,),
    prompt=(
        "Suggest 2 to 3 candidate next beats that could follow the selected "
        "node, each with a one-line rationale. These are suggestions only — do "
        "NOT create outline nodes."
    ),
))

register(LogosAction(
    name="strengthen_conflict", label="Strengthen Conflict",
    description="Suggest ways to raise conflict/stakes for the node.",
    category=CATEGORY_GENERATIVE, sections=(SECTION_OUTLINE,),
    prompt=(
        "Suggest concrete ways to strengthen the conflict and stakes of the "
        "selected node and its surrounding beats. Offer suggestions only."
    ),
))

register(LogosAction(
    name="check_template_fit", label="Check Template Fit",
    description="Assess how the outline fits the selected template.",
    category=CATEGORY_DIAGNOSTIC, sections=(SECTION_OUTLINE,),
    prompt=(
        "Assess how well the current outline fits the selected structural "
        "template. Point out which template beats are present, missing, or "
        "out of place. Do not modify the outline."
    ),
))

# ---------------------------------------------------------------------------
# Cross-section
# ---------------------------------------------------------------------------

register(LogosAction(
    name="counterpart_critique", label="Counterpart Critique",
    description="A sharp, skeptical critique from an opposing viewpoint.",
    category=CATEGORY_DIAGNOSTIC,
    sections=(SECTION_MANUSCRIPT, SECTION_OUTLINE),
    prompt=(
        "Act as a sharp, skeptical counterpart critic. Challenge this "
        "selection/node: name its weakest assumptions, where it underdelivers, "
        "and what a demanding reader would object to. Be specific and honest, "
        "but constructive. Do not rewrite anything."
    ),
))


# ---------------------------------------------------------------------------
# Deferred to later phases (NOT registered — TODO only).
# These will require explicit preview + confirmation before any mutation.
# ---------------------------------------------------------------------------

FUTURE_ACTIONS: tuple[str, ...] = (
    "rewrite_selection",       # apply a rewrite to the manuscript
    "replace_selection",       # replace the selected text
    "expand_selection",        # apply an expansion in place
    "generate_scene",          # create a scene
    "generate_outline_node",   # create an outline node
)
