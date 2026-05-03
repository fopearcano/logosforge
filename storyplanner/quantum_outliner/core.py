"""Quantum Agent Core — receives intent, dispatches to engines.

Caller-facing surface for the Quantum Outliner. Handles structured
output formatting so the UI can render results consistently.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from storyplanner.quantum_outliner.collapse import CollapseError, collapse
from storyplanner.quantum_outliner.possibilities import generate_possibilities
from storyplanner.quantum_outliner.relativity import reframe_scene
from storyplanner.quantum_outliner.state import (
    Branch,
    Wavefunction,
    get_state,
)
from storyplanner.quantum_outliner.uncertainty import (
    WeakScene,
    find_uncertainty_zones,
)

if TYPE_CHECKING:
    from storyplanner.db import Database


@dataclass(frozen=True)
class QuantumResult:
    """Structured output the UI renders."""

    kind: str
    title: str
    body: str
    payload: dict


def generate_outline(
    db: "Database",
    project_id: int,
    premise: str,
    *,
    n: int = 4,
    source_scene_id: int | None = None,
    structure_mode: str | None = None,
) -> QuantumResult:
    """Generate an outline as a wavefunction of opening branches."""
    if not premise.strip():
        return QuantumResult(
            kind="error", title="Outline", body="Provide a premise first.", payload={},
        )
    mode = structure_mode or get_state(project_id).structure_mode
    scene_order = _resolve_scene_order(db, project_id, source_scene_id)
    wf = generate_possibilities(
        anchor=f"Story opening: {premise}",
        db=db, project_id=project_id, n=n,
        source_scene_id=source_scene_id,
        source_scene_order=scene_order,
        structure_mode=mode,
    )
    get_state(project_id).add(wf)
    return _format_wavefunction("Outline", wf)


def generate_branches(
    db: "Database",
    project_id: int,
    situation: str,
    *,
    n: int = 4,
    extra_context: str = "",
    source_scene_id: int | None = None,
    structure_mode: str | None = None,
) -> QuantumResult:
    """Generate possible next moves for a given situation."""
    if not situation.strip():
        return QuantumResult(
            kind="error", title="Possibilities", body="Provide a situation first.", payload={},
        )
    mode = structure_mode or get_state(project_id).structure_mode
    scene_order = _resolve_scene_order(db, project_id, source_scene_id)
    wf = generate_possibilities(
        anchor=situation, db=db, project_id=project_id,
        extra_context=extra_context, n=n,
        source_scene_id=source_scene_id,
        source_scene_order=scene_order,
        structure_mode=mode,
    )
    get_state(project_id).add(wf)
    return _format_wavefunction("Possibilities", wf)


def reframe(
    scene_text: str,
    pov: str,
    db: "Database | None" = None,
    project_id: int | None = None,
) -> QuantumResult:
    body = reframe_scene(scene_text, pov, db=db, project_id=project_id)
    return QuantumResult(
        kind="reframe",
        title=f"Perspective: {pov}",
        body=body,
        payload={"pov": pov},
    )


def detect_weak_scenes(
    db: "Database",
    project_id: int,
    *,
    threshold: float = 0.4,
) -> QuantumResult:
    weak = find_uncertainty_zones(db, project_id, threshold=threshold)
    if not weak:
        return QuantumResult(
            kind="uncertainty",
            title="Uncertainty zones",
            body="No weak scenes detected. The story holds together.",
            payload={"scenes": []},
        )

    lines = ["Scenes flagged for re-exploration:\n"]
    for w in weak:
        bar = "▓" * int(w.weakness * 10) + "░" * (10 - int(w.weakness * 10))
        lines.append(f"#{w.scene_id} — {w.title}")
        lines.append(f"  weakness {bar} {w.weakness:.2f}")
        lines.append(f"  reasons: {', '.join(w.reasons)}")
        lines.append("")
    return QuantumResult(
        kind="uncertainty",
        title="Uncertainty zones",
        body="\n".join(lines).strip(),
        payload={"scenes": [_weak_to_dict(w) for w in weak]},
    )


def collapse_branch(
    db: "Database",
    project_id: int,
    wavefunction_id: str,
    branch_id: str,
) -> QuantumResult:
    try:
        result = collapse(db, project_id, wavefunction_id, branch_id)
    except CollapseError as exc:
        return QuantumResult(
            kind="error", title="Collapse failed", body=str(exc), payload={},
        )

    chosen = result["chosen"]
    summary = result["psyke_summary"]
    archived = result["archived"]
    proposals = result.get("proposals", [])

    lines = [
        f"COLLAPSED: {chosen['title']}",
        "",
        chosen["description"],
    ]
    if chosen["consequence"]:
        lines.append("")
        lines.append(f"Consequence: {chosen['consequence']}")

    psyke_parts: list[str] = []
    if summary["characters_created"]:
        names = ", ".join(c["name"] for c in summary["characters_created"])
        psyke_parts.append(f"Created characters: {names}")
    if summary["characters_updated"]:
        names = ", ".join(c["name"] for c in summary["characters_updated"])
        psyke_parts.append(f"Updated characters: {names}")
    if summary["relations_added"]:
        rels = ", ".join(f"{r['from']} ↔ {r['to']}" for r in summary["relations_added"])
        psyke_parts.append(f"New relations: {rels}")
    if summary["arcs_updated"]:
        names = ", ".join(a["name"] for a in summary["arcs_updated"])
        psyke_parts.append(f"Arc updates: {names}")
    if psyke_parts:
        lines.append("")
        lines.append("PSYKE updates:")
        for p in psyke_parts:
            lines.append(f"  • {p}")

    if proposals:
        lines.append("")
        lines.append("Proposed actions (require confirmation):")
        for prop in proposals:
            lines.append(f"  → {prop['description']}")

    if archived:
        lines.append("")
        lines.append(f"Archived {len(archived)} alternate branch(es).")

    return QuantumResult(
        kind="collapse",
        title="Collapse",
        body="\n".join(lines),
        payload=result,
    )


def list_active_wavefunctions(project_id: int) -> list[dict]:
    state = get_state(project_id)
    return [_wf_summary(w) for w in state.active()]


def _resolve_scene_order(
    db: "Database", project_id: int, scene_id: int | None,
) -> int | None:
    if scene_id is None:
        return None
    scene = db.get_scene_by_id(scene_id)
    if scene is None:
        return None
    return scene.sort_order


def _format_wavefunction(title: str, wf: Wavefunction) -> QuantumResult:
    lines = [f"Wavefunction {wf.id} — {wf.anchor}", ""]
    for i, b in enumerate(wf.branches, 1):
        lines.append(f"Option {i}: {b.title}  [{b.id}]")
        lines.append(f"  {b.description}")
        if b.stakes:
            lines.append(f"  Stakes: {b.stakes}")
        if b.consequence:
            lines.append(f"  Consequence: {b.consequence}")
        lines.append("")
    lines.append(
        f"To collapse: choose a branch by id (e.g. /quantum collapse {wf.id} <branch_id>)."
    )
    return QuantumResult(
        kind="possibilities",
        title=title,
        body="\n".join(lines),
        payload=_wf_summary(wf),
    )


def _wf_summary(wf: Wavefunction) -> dict:
    return {
        "wavefunction_id": wf.id,
        "anchor": wf.anchor,
        "collapsed_branch_id": wf.collapsed_branch_id,
        "source_scene_id": wf.source_scene_id,
        "source_scene_order": wf.source_scene_order,
        "target_scene_id": wf.target_scene_id,
        "branches": [
            {
                "id": b.id,
                "title": b.title,
                "description": b.description,
                "stakes": b.stakes,
                "consequence": b.consequence,
            }
            for b in wf.branches
        ],
    }


def _weak_to_dict(w: WeakScene) -> dict:
    return {
        "scene_id": w.scene_id,
        "title": w.title,
        "weakness": w.weakness,
        "reasons": list(w.reasons),
    }
