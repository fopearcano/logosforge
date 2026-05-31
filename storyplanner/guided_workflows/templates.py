"""Built-in guided-workflow templates A–H (Phase 10O).

Data-driven, mode-aware recommendations. Each template threads existing systems
(Project Intelligence, PSYKE, Outline, Manuscript, Rewrite Sandbox, Controlled
Apply, Revision Intelligence, Production Draft, Export) into a resumable,
checkable path. No template mutates project content — creative steps are the
user's; verifiable steps carry a deterministic completion check; any actual
mutation routes through Controlled Apply / Rewrite Sandbox with confirmation.
"""

from __future__ import annotations

from storyplanner.guided_workflows.models import (
    KIND_CHECK,
    KIND_CREATIVE,
    KIND_MANUAL,
    WorkflowStep,
    WorkflowTemplate,
)
from storyplanner.writing_modes import SCREENPLAY

# Section display names (match Decision Radar related_section values).
_MANUSCRIPT = "Manuscript"
_PSYKE = "PSYKE"
_OUTLINE = "Outline"
_GRAPH = "Graph"
_EXPORT = "Export"
_PROJECTS = "Projects"


# A. Project Setup ----------------------------------------------------------
_PROJECT_SETUP = WorkflowTemplate(
    id="project_setup",
    title="Project Setup",
    description="Get a new project ready: title, logline, mode, first structure.",
    category="setup",
    steps=[
        WorkflowStep("title", "Set a project title", kind=KIND_CHECK,
                     section_name=_PROJECTS, completion_check="project_has_title",
                     description="Give the project a real title."),
        WorkflowStep("logline", "Write a one-line description / logline",
                     kind=KIND_CHECK, section_name=_PROJECTS,
                     completion_check="project_has_description",
                     description="A short logline anchors the whole project."),
        WorkflowStep("mode", "Confirm the writing mode", kind=KIND_MANUAL,
                     section_name=_PROJECTS,
                     description="Novel / Screenplay / Graphic Novel / Stage / Series — "
                                 "every section adapts to this."),
        WorkflowStep("first_scenes", "Create your first scene(s)", kind=KIND_CHECK,
                     section_name=_MANUSCRIPT, completion_check="has_scenes",
                     description="Add at least one scene to start drafting."),
    ],
)

# B. PSYKE Story Bible ------------------------------------------------------
_PSYKE_BIBLE = WorkflowTemplate(
    id="psyke_story_bible",
    title="PSYKE Story Bible",
    description="Build out characters, places and objects with notes and relations.",
    category="bible",
    steps=[
        WorkflowStep("create_entries", "Create your core PSYKE entries",
                     kind=KIND_CHECK, section_name=_PSYKE,
                     completion_check="psyke_has_entries",
                     description="Add the key characters / places / objects."),
        WorkflowStep("fill_notes", "Give each entry meaningful notes",
                     kind=KIND_CHECK, section_name=_PSYKE,
                     completion_check="psyke_notes_filled",
                     description="Empty notes weaken continuity and Assistant context."),
        WorkflowStep("relations", "Connect related entries", kind=KIND_CHECK,
                     section_name=_PSYKE, completion_check="psyke_has_relations",
                     description="Relations power continuity and setup/payoff tracking."),
        WorkflowStep("review", "Review the story bible for gaps", kind=KIND_CREATIVE,
                     section_name=_PSYKE,
                     description="A judgement step — only you can mark this done."),
    ],
)

# C. Classical Outline ------------------------------------------------------
_CLASSICAL_OUTLINE = WorkflowTemplate(
    id="classical_outline",
    title="Classical Outline",
    description="Shape act/chapter structure and scene summaries.",
    category="outline",
    steps=[
        WorkflowStep("outline_nodes", "Draft your outline structure",
                     kind=KIND_CHECK, section_name=_OUTLINE,
                     completion_check="has_outline_nodes",
                     description="Create acts / chapters / beats."),
        WorkflowStep("assign_chapters", "Assign scenes to chapters/acts",
                     kind=KIND_CHECK, section_name=_OUTLINE,
                     completion_check="all_scenes_have_chapter",
                     description="Place every scene in the structure."),
        WorkflowStep("summaries", "Summarize every scene", kind=KIND_CHECK,
                     section_name=_MANUSCRIPT, completion_check="all_scenes_have_summary",
                     description="Summaries feed Outline / Plot / Timeline / Assistant."),
        WorkflowStep("arc_check", "Sanity-check the dramatic arc",
                     kind=KIND_CREATIVE, section_name=_OUTLINE,
                     action_id="pi_decision_radar",
                     description="A judgement step — your call when it reads right."),
    ],
)

# D. Scene Drafting ---------------------------------------------------------
_SCENE_DRAFTING = WorkflowTemplate(
    id="scene_drafting",
    title="Scene Drafting",
    description="Draft and summarize scenes with mode-aware craft focus.",
    category="drafting",
    steps=[
        WorkflowStep("draft", "Draft the scene", kind=KIND_CREATIVE,
                     section_name=_MANUSCRIPT,
                     description="The core creative step — never auto-completed."),
        WorkflowStep("sp_economy", "Check screenplay scene economy", kind=KIND_MANUAL,
                     section_name=_MANUSCRIPT, action_id="sp_diagnose_scene_economy",
                     modes=(SCREENPLAY,),
                     description="Run the deterministic economy diagnostic."),
        WorkflowStep("summary", "Write the scene summary", kind=KIND_CHECK,
                     section_name=_MANUSCRIPT, completion_check="all_scenes_have_summary",
                     description="Done when every scene has a summary."),
        WorkflowStep("continuity", "Review continuity against PSYKE",
                     kind=KIND_CREATIVE, section_name=_PSYKE,
                     description="A judgement step — your call."),
    ],
)

# E. Rewrite ----------------------------------------------------------------
_REWRITE = WorkflowTemplate(
    id="rewrite",
    title="Rewrite",
    description="Use the Rewrite Sandbox safely: generate, compare, apply.",
    category="rewrite",
    steps=[
        WorkflowStep("select", "Select the passage to rewrite", kind=KIND_MANUAL,
                     section_name=_MANUSCRIPT,
                     description="Pick the scene/selection you want to improve."),
        WorkflowStep("strategy", "Choose a rewrite strategy", kind=KIND_MANUAL,
                     section_name=_MANUSCRIPT, action_id="rw_suggest_strategy",
                     description="Clarify / compress / intensify / subtext, etc."),
        WorkflowStep("generate", "Generate variants in the Sandbox", kind=KIND_CREATIVE,
                     section_name=_MANUSCRIPT, action_id="rw_score_variants",
                     description="A creative step — generate and read the variants."),
        WorkflowStep("compare", "Compare variants and pick a preferred one",
                     kind=KIND_CREATIVE, section_name=_MANUSCRIPT,
                     action_id="rw_explain_tradeoffs",
                     description="A judgement step — your call which (if any) wins."),
        WorkflowStep("apply", "Apply the chosen variant (Controlled Apply)",
                     kind=KIND_CHECK, section_name=_MANUSCRIPT,
                     completion_check="no_preferred_rewrite",
                     description="Routes through Controlled Apply with confirmation. "
                                 "Done when no preferred variant is left unapplied."),
    ],
)

# F. Screenplay Production Prep (screenplay only) ---------------------------
_PRODUCTION_PREP = WorkflowTemplate(
    id="screenplay_production_prep",
    title="Screenplay Production Prep",
    description="Prepare a production draft: numbering, revision set, validation.",
    category="production",
    modes=(SCREENPLAY,),
    steps=[
        WorkflowStep("activate", "Activate a production draft", kind=KIND_CHECK,
                     section_name=_MANUSCRIPT, completion_check="production_active",
                     action_id="sp_production_status",
                     description="Turn on the production-draft layer."),
        WorkflowStep("numbering", "Assign & validate scene numbers", kind=KIND_MANUAL,
                     section_name=_MANUSCRIPT,
                     action_id="sp_check_duplicate_scene_numbers",
                     description="Number scenes and check for duplicates."),
        WorkflowStep("revision_set", "Create a revision set", kind=KIND_CHECK,
                     section_name=_MANUSCRIPT,
                     completion_check="production_has_revision_set",
                     action_id="sp_summarize_revision_set",
                     description="A revision set is required before issuing pages."),
        WorkflowStep("validate", "Validate the production export", kind=KIND_CHECK,
                     section_name=_EXPORT, completion_check="export_safe",
                     action_id="sp_validate_production",
                     description="Done when the export has no blocking issues."),
    ],
)

# G. Export Readiness -------------------------------------------------------
_EXPORT_READINESS = WorkflowTemplate(
    id="export_readiness",
    title="Export Readiness",
    description="Get the project clean for export (mode-aware).",
    category="export",
    steps=[
        WorkflowStep("validate", "Validate the export", kind=KIND_CHECK,
                     section_name=_EXPORT, completion_check="export_safe",
                     action_id="sp_validate_export",
                     description="Resolve any blocking export issues."),
        WorkflowStep("warnings", "Clear export warnings", kind=KIND_CHECK,
                     section_name=_EXPORT, completion_check="export_no_warnings",
                     action_id="sp_export_readiness_report",
                     description="Review and clear non-blocking warnings."),
        WorkflowStep("preview", "Preview the rendered output", kind=KIND_MANUAL,
                     section_name=_EXPORT, action_id="sp_preview_render",
                     description="Eyeball the rendered result before exporting."),
        WorkflowStep("final_review", "Final read-through", kind=KIND_CREATIVE,
                     section_name=_MANUSCRIPT,
                     description="A judgement step — your final sign-off."),
    ],
)

# H. Decision Radar Fix -----------------------------------------------------
_RADAR_FIX = WorkflowTemplate(
    id="decision_radar_fix",
    title="Decision Radar Fix",
    description="Work down the most important open decisions and risks.",
    category="triage",
    steps=[
        WorkflowStep("review_radar", "Review the Decision Radar", kind=KIND_MANUAL,
                     section_name=_MANUSCRIPT, action_id="pi_decision_radar",
                     description="See the ranked list of open decisions."),
        WorkflowStep("clear_blocking", "Resolve all blocking decisions",
                     kind=KIND_CHECK, section_name=_MANUSCRIPT,
                     completion_check="no_blocking_decisions",
                     description="Done when nothing is flagged blocking."),
        WorkflowStep("clear_apply", "Clear any pending Controlled Apply",
                     kind=KIND_CHECK, section_name=_MANUSCRIPT,
                     completion_check="no_pending_apply",
                     action_id="ca_apply_history",
                     description="Apply or cancel any pending preview."),
        WorkflowStep("radar_clear", "Reduce the radar to no warnings",
                     kind=KIND_CHECK, section_name=_MANUSCRIPT,
                     completion_check="radar_clear",
                     description="Done when no blocking/warning decisions remain."),
    ],
)


# Ordered registry of all built-in templates (A–H).
ALL_TEMPLATES: tuple[WorkflowTemplate, ...] = (
    _PROJECT_SETUP,        # A
    _PSYKE_BIBLE,          # B
    _CLASSICAL_OUTLINE,    # C
    _SCENE_DRAFTING,       # D
    _REWRITE,              # E
    _PRODUCTION_PREP,      # F (screenplay)
    _EXPORT_READINESS,     # G
    _RADAR_FIX,            # H
)
