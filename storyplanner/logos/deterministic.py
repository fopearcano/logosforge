"""Deterministic Logos action handlers (Phase 10C).

Some Logos actions are *diagnostic* and must run without an LLM — they compute a
rule-based result and return it directly. ``LogosController.run`` consults this
registry first; if an action has a handler here, the controller never resolves a
provider or calls the chat backend. Handlers are read-only (no DB writes) and
return a :class:`LogosResult` (preview-only — never auto-applies).
"""

from __future__ import annotations

from collections.abc import Callable

from storyplanner.logos.context import LogosContext
from storyplanner.logos.result import LogosResult

# action_name -> handler(db, context) -> LogosResult
_HANDLERS: dict[str, Callable[[object, LogosContext], LogosResult]] = {}


def register(action_name: str, handler: Callable[[object, LogosContext], LogosResult]) -> None:
    _HANDLERS[action_name] = handler


def get_handler(action_name: str):
    return _HANDLERS.get(action_name)


def is_deterministic(action_name: str) -> bool:
    return action_name in _HANDLERS


# -- Handlers ----------------------------------------------------------------


def _diagnose_scene_economy(db, context: LogosContext) -> LogosResult:
    """Run the deterministic screenplay scene-economy diagnostics for the scene."""
    action = "sp_diagnose_scene_economy"
    scene_id = context.current_scene_id
    if scene_id is None:
        return LogosResult(
            ok=True, action=action, title="Diagnose Scene Economy",
            message="Open a scene in the Manuscript to run screenplay diagnostics.",
            suggestions=[], proposed_operations=[],
        )
    try:
        from storyplanner.screenplay_diagnostics import analyze_scene_by_id
        report = analyze_scene_by_id(db, context.project_id, scene_id)
    except Exception as exc:  # never crash the UI
        return LogosResult.failure(action, f"Diagnostics failed: {exc}")

    lines = [report.summary, ""]
    lines.append(
        f"Blocks: {report.block_count}  ·  Action: {report.action_block_count}  ·  "
        f"Dialogue: {report.dialogue_block_count}  ·  Characters: "
        f"{', '.join(report.unique_characters) or '—'}"
    )
    if report.estimated_minutes:
        lines.append(f"Approx. length: ~{report.estimated_minutes} min (rough).")
    suggestions: list[str] = []
    if report.issues:
        lines.append("")
        lines.append("Issues:")
        for i in report.top_issues(8):
            lines.append(f"- [{i.severity}] {i.label} — {i.evidence}")
            if i.suggested_action:
                suggestions.append(f"{i.label}: {i.suggested_action}")
    if report.strengths:
        lines.append("")
        lines.append("Strengths: " + "; ".join(report.strengths))

    return LogosResult(
        ok=True, action=action, title="Diagnose Scene Economy",
        message="\n".join(lines), suggestions=suggestions,
        proposed_operations=[],  # diagnostic only — no mutation
    )


register("sp_diagnose_scene_economy", _diagnose_scene_economy)
