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

# Section identifiers Logos integrates with.
SECTION_MANUSCRIPT = "Manuscript"
SECTION_OUTLINE = "Outline"
# Phase 3 — section-aware coverage.
SECTION_PSYKE = "PSYKE"
SECTION_PLOT = "Plot"
SECTION_TIMELINE = "Timeline"
SECTION_GRAPH = "Graph"

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
    sections=(SECTION_MANUSCRIPT, SECTION_OUTLINE, SECTION_PSYKE,
              SECTION_PLOT, SECTION_TIMELINE, SECTION_GRAPH),
    prompt=(
        "Act as a sharp, skeptical counterpart critic. Challenge this "
        "selection/element: name its weakest assumptions, where it "
        "underdelivers, and what a demanding reader would object to. Be "
        "specific and honest, but constructive. Do not rewrite anything."
    ),
))


# ---------------------------------------------------------------------------
# PSYKE actions (entry-aware)
# ---------------------------------------------------------------------------

_PSYKE = (SECTION_PSYKE,)
for _name, _label, _desc, _cat, _prompt in [
    ("explain_entry_role", "Explain Entry Role",
     "Explain this entry's narrative role.", CATEGORY_DIAGNOSTIC,
     "Explain this PSYKE entry's role in the story — what it contributes and "
     "how it connects to the rest. Do not modify it."),
    ("find_missing_details", "Find Missing Details",
     "Point out gaps in this entry's details.", CATEGORY_DIAGNOSTIC,
     "Review this PSYKE entry and list the most important missing or thin "
     "details that would strengthen it. List them as diagnostics."),
    ("check_continuity", "Check Continuity",
     "Check this entry for continuity issues.", CATEGORY_DIAGNOSTIC,
     "Check this PSYKE entry for continuity issues against the scenes it "
     "appears in and its progressions. List concerns. Do not modify anything."),
    ("check_relationships", "Check Relationships",
     "Assess this entry's relationships.", CATEGORY_DIAGNOSTIC,
     "Assess this entry's relationships: which are strong, missing, or "
     "underused. List observations. Do not modify anything."),
    ("suggest_arc_development", "Suggest Arc Development",
     "Suggest how this entry could develop.", CATEGORY_GENERATIVE,
     "Suggest how this entry could develop across the story (an arc). Offer "
     "concrete progression ideas as suggestions only."),
    ("suggest_details", "Suggest Details",
     "Suggest concrete details to add.", CATEGORY_GENERATIVE,
     "Suggest concrete details (traits, history, specifics) that would enrich "
     "this entry. Offer them as suggestions for the author to add."),
    ("suggest_relations", "Suggest Relations",
     "Suggest relationships to other entries.", CATEGORY_GENERATIVE,
     "Suggest meaningful relationships between this entry and other story "
     "elements, with a one-line rationale each. Suggestions only."),
    ("suggest_progression", "Suggest Progression",
     "Suggest a progression note for this entry.", CATEGORY_GENERATIVE,
     "Suggest a single concrete progression note describing how this entry "
     "changes at this point in the story."),
    ("suggest_aliases", "Suggest Aliases",
     "Suggest alternate names/aliases.", CATEGORY_GENERATIVE,
     "Suggest a few fitting aliases or alternate names for this entry. "
     "Suggestions only."),
    ("suggest_notes", "Suggest Notes",
     "Suggest a note worth recording.", CATEGORY_GENERATIVE,
     "Suggest a useful note the author should record about this entry."),
]:
    register(LogosAction(name=_name, label=_label, description=_desc,
                         category=_cat, sections=_PSYKE, prompt=_prompt))


# ---------------------------------------------------------------------------
# Plot actions (block / structural-unit aware; Plot is scene-derived)
# ---------------------------------------------------------------------------

_PLOT = (SECTION_PLOT,)
for _name, _label, _desc, _cat, _prompt in [
    ("explain_plot_function", "Explain Plot Function",
     "Explain this block's plot function.", CATEGORY_DIAGNOSTIC,
     "Explain the function of this plot block / structural unit in the story. "
     "Do not modify anything."),
    ("identify_weak_conflict", "Identify Weak Conflict",
     "Diagnose weak conflict here.", CATEGORY_DIAGNOSTIC,
     "Identify where the conflict in this plot block is weak or unclear. List "
     "concrete diagnostics. Do not rewrite anything."),
    ("check_escalation", "Check Escalation",
     "Check whether tension escalates.", CATEGORY_DIAGNOSTIC,
     "Assess whether tension and stakes escalate across this block and its "
     "scenes. Note any plateaus or drops. Do not modify anything."),
    ("check_cause_effect", "Check Cause/Effect",
     "Check cause-and-effect logic.", CATEGORY_DIAGNOSTIC,
     "Check the cause-and-effect logic linking the scenes in this block. Flag "
     "gaps or coincidences. Do not modify anything."),
    ("suggest_stronger_turn", "Suggest Stronger Turn",
     "Suggest a stronger turning point.", CATEGORY_GENERATIVE,
     "Suggest how to make the turning point of this block sharper and more "
     "consequential. Suggestions only."),
    ("suggest_plot_block_summary", "Suggest Plot Block Summary",
     "Draft a summary for this block/scene.", CATEGORY_GENERATIVE,
     "Draft a concise summary capturing the dramatic function of this plot "
     "block or its selected scene."),
    ("suggest_scene_purpose", "Suggest Scene Purpose",
     "Clarify the scene's purpose.", CATEGORY_GENERATIVE,
     "Articulate the dramatic purpose this scene should serve within its "
     "plotline. Offer as a suggestion."),
    ("suggest_conflict_upgrade", "Suggest Conflict Upgrade",
     "Suggest ways to raise the conflict.", CATEGORY_GENERATIVE,
     "Suggest concrete ways to upgrade the conflict and stakes here. "
     "Suggestions only."),
    ("suggest_setup_payoff_link", "Suggest Setup/Payoff Link",
     "Suggest a setup/payoff connection.", CATEGORY_GENERATIVE,
     "Suggest a setup/payoff link this block could plant or resolve, with a "
     "rationale. Suggestion only — do not modify data."),
]:
    register(LogosAction(name=_name, label=_label, description=_desc,
                         category=_cat, sections=_PLOT, prompt=_prompt))


# ---------------------------------------------------------------------------
# Timeline actions (event / scene aware; chronology is sort-order based)
# ---------------------------------------------------------------------------

_TIMELINE = (SECTION_TIMELINE,)
for _name, _label, _desc, _cat, _prompt in [
    ("explain_timeline_position", "Explain Timeline Position",
     "Explain this event's place in time.", CATEGORY_DIAGNOSTIC,
     "Explain this event's position in the story's chronology and what it "
     "accomplishes there. Do not modify anything."),
    ("check_chronology", "Check Chronology",
     "Check chronology consistency.", CATEGORY_DIAGNOSTIC,
     "Check the chronology around this event for inconsistencies or ordering "
     "problems. List concerns. Do not reorder anything."),
    ("check_pacing", "Check Pacing",
     "Assess pacing around this event.", CATEGORY_DIAGNOSTIC,
     "Assess the pacing around this event — is it rushed or slack relative to "
     "its neighbours? Do not modify anything."),
    ("check_gap", "Check Gap",
     "Detect a gap before/after this event.", CATEGORY_DIAGNOSTIC,
     "Detect whether there is a narrative or temporal gap before or after this "
     "event that needs bridging. Do not modify anything."),
    ("check_causality", "Check Causality",
     "Check causal links to neighbours.", CATEGORY_DIAGNOSTIC,
     "Check the causal links between this event and the ones around it. Flag "
     "missing causation. Do not modify anything."),
    ("suggest_next_event", "Suggest Next Event",
     "Suggest what could come next.", CATEGORY_GENERATIVE,
     "Suggest 2-3 candidate next events that could follow, each with a brief "
     "rationale. Suggestions only — do not create events."),
    ("suggest_timeline_note", "Suggest Timeline Note",
     "Suggest a note for this point.", CATEGORY_GENERATIVE,
     "Suggest a useful timeline note to record at this point in the story."),
    ("suggest_event_summary", "Suggest Event Summary",
     "Draft a summary for this event.", CATEGORY_GENERATIVE,
     "Draft a concise summary of this timeline event / scene."),
    ("suggest_causal_link", "Suggest Causal Link",
     "Suggest a causal connection.", CATEGORY_GENERATIVE,
     "Suggest a causal link between this event and a neighbouring one, with a "
     "rationale. Suggestion only."),
    ("suggest_bridge_scene", "Suggest Missing Bridge Scene",
     "Suggest a bridge scene to fill a gap.", CATEGORY_GENERATIVE,
     "Suggest a bridge scene that would smooth a gap around this event. "
     "Describe it as a suggestion — do not create it."),
]:
    register(LogosAction(name=_name, label=_label, description=_desc,
                         category=_cat, sections=_TIMELINE, prompt=_prompt))


# ---------------------------------------------------------------------------
# Graph actions (node / relationship aware; graph is a view, not a source)
# ---------------------------------------------------------------------------

_GRAPH = (SECTION_GRAPH,)
for _name, _label, _desc, _cat, _prompt in [
    ("explain_node", "Explain Node",
     "Explain the selected node.", CATEGORY_DIAGNOSTIC,
     "Explain the selected graph node: what it represents and its role in the "
     "story network. Do not modify anything."),
    ("explain_relationship_cluster", "Explain Relationship Cluster",
     "Explain this node's cluster.", CATEGORY_DIAGNOSTIC,
     "Explain the cluster of relationships around the selected node — who/what "
     "it connects and why. Do not modify anything."),
    ("identify_missing_links", "Identify Missing Links",
     "Find likely missing connections.", CATEGORY_DIAGNOSTIC,
     "Identify likely missing links for the selected node given its "
     "neighbours. List them as diagnostics."),
    ("identify_isolated_node", "Identify Isolated Node",
     "Assess whether this node is isolated.", CATEGORY_DIAGNOSTIC,
     "Assess whether the selected node is under-connected or isolated, and why "
     "that might be a problem. Do not modify anything."),
    ("check_thematic_cluster", "Check Thematic Cluster",
     "Check thematic coherence of the cluster.", CATEGORY_DIAGNOSTIC,
     "Check whether the thematic cluster around this node is coherent. Note "
     "tensions or gaps. Do not modify anything."),
    ("suggest_relationship", "Suggest Relationship",
     "Suggest a relationship for this node.", CATEGORY_GENERATIVE,
     "Suggest a meaningful relationship the selected node could have, with a "
     "rationale. Suggestion only."),
    ("suggest_psyke_relation", "Suggest PSYKE Relation",
     "Suggest a PSYKE relation to add.", CATEGORY_GENERATIVE,
     "Suggest a PSYKE relation involving the selected entity, with a rationale. "
     "Suggestion only — applied via PSYKE if the author confirms."),
    ("suggest_note_from_graph", "Suggest Note",
     "Suggest a note about this node.", CATEGORY_GENERATIVE,
     "Suggest a useful note to record about the selected node."),
    ("suggest_setup_payoff_edge", "Suggest Setup/Payoff Edge",
     "Suggest a setup/payoff edge.", CATEGORY_GENERATIVE,
     "Suggest a setup/payoff connection involving this node, with a rationale. "
     "Suggestion only."),
    ("suggest_character_theme_link", "Suggest Character/Theme Link",
     "Suggest a character↔theme link.", CATEGORY_GENERATIVE,
     "Suggest a meaningful character-to-theme link involving this node, with a "
     "rationale. Suggestion only."),
]:
    register(LogosAction(name=_name, label=_label, description=_desc,
                         category=_cat, sections=_GRAPH, prompt=_prompt))


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
