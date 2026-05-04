"""Quantum Agent Core — receives intent, dispatches to engines.

Caller-facing surface for the Quantum Outliner. Handles structured
output formatting so the UI can render results consistently.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from storyplanner.quantum_outliner.collapse import CollapseError, collapse
from storyplanner.quantum_outliner.possibilities import generate_possibilities
from storyplanner.quantum_outliner.psyke_adapter import PsykeSignals, gather_psyke_signals
from storyplanner.quantum_outliner.scoring import (
    adapt_weights,
    apply_scores,
    explain_wavefunction,
    format_branch_chips,
    format_recommendation,
    recommend_collapse,
    score_branches,
)
from storyplanner.quantum_outliner.relativity import reframe_scene
from storyplanner.quantum_outliner.state import (
    Branch,
    OutlineMode,
    Wavefunction,
    get_state,
)
from storyplanner.quantum_outliner.uncertainty import (
    WeakScene,
    find_uncertainty_zones,
)
from storyplanner.quantum_outliner.writing_methods_rag import (
    MethodResult,
    extract_beats,
    get_relevant_writing_methods,
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

    state = get_state(project_id)
    if state.outline_mode is OutlineMode.CLASSICAL:
        return _generate_classical_outline(
            db, project_id, premise, source_scene_id=source_scene_id,
        )

    mode = structure_mode or state.structure_mode
    scene_order = _resolve_scene_order(db, project_id, source_scene_id)
    wf = generate_possibilities(
        anchor=f"Story opening: {premise}",
        db=db, project_id=project_id, n=n,
        source_scene_id=source_scene_id,
        source_scene_order=scene_order,
        structure_mode=mode,
    )
    state.add(wf)
    return _format_wavefunction("Outline", wf, db=db, project_id=project_id)


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

    state = get_state(project_id)
    if state.outline_mode is OutlineMode.CLASSICAL:
        return _generate_classical_outline(
            db, project_id, situation, source_scene_id=source_scene_id,
        )

    mode = structure_mode or state.structure_mode
    scene_order = _resolve_scene_order(db, project_id, source_scene_id)
    wf = generate_possibilities(
        anchor=situation, db=db, project_id=project_id,
        extra_context=extra_context, n=n,
        source_scene_id=source_scene_id,
        source_scene_order=scene_order,
        structure_mode=mode,
    )
    state.add(wf)
    return _format_wavefunction("Possibilities", wf, db=db, project_id=project_id)


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

    adapted = _adapt_weights_on_collapse(
        db, project_id, wavefunction_id, branch_id,
    )
    if adapted:
        lines.append("")
        lines.append("Weights adjusted (learning ON).")

    return QuantumResult(
        kind="collapse",
        title="Collapse",
        body="\n".join(lines),
        payload=result,
    )


def _adapt_weights_on_collapse(
    db: "Database",
    project_id: int,
    wavefunction_id: str,
    branch_id: str,
) -> bool:
    """Adapt scoring weights from the user's collapse choice. Returns True if adapted."""
    if not db.get_weight_learning(project_id):
        return False

    state = get_state(project_id)
    wf = state.get(wavefunction_id)
    if wf is None:
        return False

    chosen = wf.get_branch(branch_id)
    if chosen is None or not chosen.factors:
        return False

    unchosen = [b for b in wf.branches if b.id != branch_id and b.factors]
    if not unchosen:
        return False

    current = db.get_scoring_weights(project_id)
    updated = adapt_weights(current, chosen.factors, [b.factors for b in unchosen])
    if updated == current:
        return False

    db.set_scoring_weights(project_id, updated)
    db.set_scoring_preset(project_id, "Custom")
    return True


def explain_branches(
    project_id: int,
    wavefunction_id: str,
) -> QuantumResult:
    """Return factor-based explanation for all branches in a wavefunction."""
    state = get_state(project_id)
    wf = state.get(wavefunction_id)
    if wf is None:
        return QuantumResult(
            kind="explain", title="Explain",
            body="Wavefunction not found.", payload={},
        )
    body = explain_wavefunction(wf)
    return QuantumResult(
        kind="explain", title="Explain",
        body=body, payload={"wavefunction_id": wf.id},
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


def _generate_classical_outline(
    db: "Database",
    project_id: int,
    premise: str,
    *,
    source_scene_id: int | None = None,
) -> QuantumResult:
    """Produce a deterministic linear outline from Writing Methods RAG."""
    methods = get_relevant_writing_methods(premise, max_results=1)
    if not methods:
        methods = get_relevant_writing_methods("three-act structure", max_results=1)

    if methods:
        method = methods[0]
        beats = extract_beats(method.snippet)
        method_title = method.title
    else:
        method_title = "Three-Act Structure"
        beats = ["Setup", "Confrontation", "Resolution"]

    scene_order = _resolve_scene_order(db, project_id, source_scene_id)

    branch = Branch.new(
        title=f"{method_title} Outline",
        description=f"Linear outline for: {premise}",
        structure_method=method_title,
        structure_beat=beats[0] if beats else None,
    )
    wf = Wavefunction.new(
        anchor=premise,
        branches=[branch],
        source_scene_id=source_scene_id,
        source_scene_order=scene_order,
    )
    wf.structure_method = method_title
    wf.structure_beat = beats[0] if beats else None
    wf.effective_mode = "classical"
    get_state(project_id).add(wf)

    body = _format_classical(method_title, beats, premise)
    return QuantumResult(
        kind="classical_outline",
        title="Outline",
        body=body,
        payload={
            "structure_method": method_title,
            "beats": beats,
            "anchor": premise,
            "wavefunction_id": wf.id,
            "source_scene_id": source_scene_id,
        },
    )


def _format_classical(method_title: str, beats: list[str], anchor: str) -> str:
    lines = [f"Classical Outline — {anchor}", ""]
    lines.append(f"Method: {method_title}")
    lines.append("")
    if beats:
        lines.append("Beats:")
        for i, beat in enumerate(beats, 1):
            lines.append(f"  {i}. {beat}")
    else:
        lines.append("(No beats extracted — use a specific method name.)")
    lines.append("")
    lines.append(
        "This is a stable structure outline. "
        "Switch to Lambda Mode for branching possibilities."
    )
    return "\n".join(lines)


def _format_wavefunction(
    title: str,
    wf: Wavefunction,
    *,
    db: "Database | None" = None,
    project_id: int | None = None,
) -> QuantumResult:
    psyke = None
    if db is not None and project_id is not None:
        psyke = gather_psyke_signals(db, project_id)

    weights = None
    constraints = None
    show_tradeoffs = False
    if db is not None and project_id is not None:
        weights = db.get_scoring_weights(project_id)
        constraints = db.get_constraints(project_id)
        show_tradeoffs = db.get_show_tradeoffs(project_id)

    if wf.branches:
        scored = score_branches(
            wf, psyke=psyke, weights=weights, constraints=constraints,
        )
        apply_scores(wf, scored)
        wf.branches.sort(key=lambda b: b.probability, reverse=True)

    body = _format_lambda(wf, psyke=psyke, show_tradeoffs=show_tradeoffs)
    return QuantumResult(
        kind="possibilities",
        title=title,
        body=body,
        payload=_wf_summary(wf),
    )


def _format_lambda(
    wf: Wavefunction,
    *,
    psyke: PsykeSignals | None = None,
    show_tradeoffs: bool = False,
) -> str:
    n = len(wf.branches)
    lines = [
        f"═══ QUANTUM FIELD ═══",
        f"Wavefunction {wf.id} — {wf.anchor}",
        f"Superposition: {n} possible futures",
        "",
    ]

    if wf.structure_method or wf.structure_beat:
        gravity = wf.structure_method or ""
        if wf.structure_beat:
            gravity = f"{gravity} → {wf.structure_beat}" if gravity else wf.structure_beat
        lines.append(f"Gravity: {gravity}")
        lines.append("")

    all_factors = [b.factors for b in wf.branches if b.factors and not b.violations]

    for i, b in enumerate(wf.branches, 1):
        label = f"▸ Option {i}: {b.title}  [{b.id}]"
        if b.branch_type:
            label += f"  ({b.branch_type})"
        if b.probability > 0:
            label += f"  {b.probability:.0%}"
        if show_tradeoffs and b.is_pareto_optimal and not b.violations:
            label += "  ●"
        lines.append(label)
        lines.append(f"  {b.description}")
        if b.structure_beat:
            lines.append(f"  Beat: {b.structure_beat}")
        if b.stakes:
            lines.append(f"  Stakes: {b.stakes}")
        if b.consequence:
            lines.append(f"  Consequence: {b.consequence}")
        if b.state_delta and b.state_delta.character_changes:
            names = [c.get("name", "") for c in b.state_delta.character_changes if c.get("name")]
            if names:
                lines.append(f"  Affects: {', '.join(names[:4])}")
        if b.violations:
            for v in b.violations:
                lines.append(f"  ⚠ BLOCKED: violates \"{v}\"")
        elif show_tradeoffs and b.factors and all_factors:
            chips = format_branch_chips(b.factors, all_factors, is_pareto=False)
            if chips:
                lines.append(f"  {chips}")
        lines.append("")

    pov_names = _extract_pov_frames(wf, psyke)
    if pov_names:
        lines.append(f"POV Frames: {', '.join(pov_names)}")
        lines.append("  Use /quantum reframe <name> to shift perspective.")
        lines.append("")

    rec = recommend_collapse(wf)
    if rec:
        lines.append(format_recommendation(rec))
        lines.append("")

    lines.append(
        f"Uncertainty: {n} branches in superposition — "
        f"all futures coexist until collapsed."
    )
    lines.append("")
    lines.append(
        f"To collapse: choose a branch by id "
        f"(e.g. /quantum collapse {wf.id} <branch_id>)."
    )
    lines.append(
        f"To explain: /quantum explain {wf.id}"
    )
    return "\n".join(lines)


def _extract_pov_frames(
    wf: Wavefunction, psyke: PsykeSignals | None,
) -> list[str]:
    """Collect character names available for POV reframing."""
    names: list[str] = []
    seen: set[str] = set()

    if psyke:
        for c in psyke.characters:
            n = c.get("name", "")
            if n and n.lower() not in seen:
                seen.add(n.lower())
                names.append(n)

    for b in wf.branches:
        if not b.state_delta:
            continue
        for c in b.state_delta.character_changes:
            n = (c.get("name") or "").strip()
            if n and n.lower() not in seen:
                seen.add(n.lower())
                names.append(n)

    return names[:6]


_format_quantum = _format_lambda


def _format_hybrid(wf: Wavefunction, *, psyke: PsykeSignals | None = None) -> str:
    lines = [f"Wavefunction {wf.id} — {wf.anchor}", ""]

    lines.append("Classical Axis:")
    lines.append(f"  Method: {wf.structure_method}")
    if wf.structure_beat:
        lines.append(f"  Beat: {wf.structure_beat}")
    if wf.expected_function:
        lines.append(f"  Function: {wf.expected_function}")
    lines.append("")

    lines.append("Quantum Branches:")
    for i, b in enumerate(wf.branches, 1):
        label = f"{i}. {b.title}  [{b.id}]"
        if b.branch_type:
            label += f"  ({b.branch_type})"
        lines.append(label)
        lines.append(f"   {b.description}")
        if b.structure_beat:
            lines.append(f"   Beat: {b.structure_beat}")
        if b.stakes:
            lines.append(f"   Stakes: {b.stakes}")
        if b.consequence:
            lines.append(f"   Consequence: {b.consequence}")
        lines.append("")

    recommended = _pick_collapse_candidate(wf, psyke=psyke)
    lines.append("Collapse Candidates:")
    if recommended:
        lines.append(f"  Recommended: {recommended[0]}  [{recommended[1]}]")
        lines.append(f"  Reason: {recommended[2]}")
        if recommended[3]:
            lines.append(f"  Signals: {recommended[3]}")
    else:
        lines.append("  No recommendation — all branches are viable.")
    lines.append("")

    lines.append(
        f"To collapse: choose a branch by id (e.g. /quantum collapse {wf.id} <branch_id>)."
    )
    return "\n".join(lines)


def _pick_collapse_candidate(
    wf: Wavefunction,
    *,
    psyke: PsykeSignals | None = None,
) -> tuple[str, str, str, str] | None:
    """Return (title, id, reason, signals) for the best collapse candidate.

    Scoring considers: branch_type alignment, structural beat match,
    PSYKE character relevance, relationship tension, and unresolved arcs.
    """
    if not wf.branches:
        return None

    scores: list[tuple[float, str, list[str]]] = []

    for b in wf.branches:
        score = 0.0
        signals: list[str] = []

        if b.branch_type == "intensification":
            score += 3.0
            signals.append("intensifies structural beat")
        elif b.branch_type == "resolution":
            score += 1.5
        elif b.branch_type == "alternative":
            score += 1.0

        if b.structure_beat and b.structure_beat == wf.structure_beat:
            score += 2.0
            signals.append(f"aligned with {b.structure_beat}")

        if wf.expected_function and b.description:
            func_words = set(wf.expected_function.lower().split())
            desc_words = set(b.description.lower().split())
            overlap = func_words & desc_words - {"the", "a", "an", "is", "of"}
            if overlap:
                score += 1.5
                signals.append(f"matches expected function")

        if psyke and psyke.keywords:
            branch_text = f"{b.title} {b.description} {b.stakes} {b.consequence}".lower()
            branch_words = set(branch_text.split())
            char_overlap = psyke.keywords & branch_words
            if char_overlap:
                names = [
                    c["name"] for c in psyke.characters
                    if c["name"].lower() in char_overlap
                ]
                score += min(len(char_overlap) * 0.5, 3.0)
                if names:
                    signals.append(f"involves {', '.join(names[:3])}")

            for rel in psyke.relations:
                rel_names = {rel["from"].lower(), rel["to"].lower()}
                if rel_names & branch_words:
                    score += 1.0
                    signals.append(f"{rel['from']} ↔ {rel['to']} tension")
                    break

            for arc in psyke.unresolved_arcs:
                arc_words = set(arc["arc"].lower().split())
                if arc_words & branch_words - {"the", "a", "an", "is"}:
                    score += 1.5
                    signals.append(f"advances {arc['name']}'s arc")
                    break

        scores.append((score, b.id, signals))

    if not scores:
        return None

    scores.sort(key=lambda x: x[0], reverse=True)
    best_score, best_id, best_signals = scores[0]

    best_branch = wf.get_branch(best_id)
    if best_branch is None:
        return None

    if best_signals:
        reason = "; ".join(best_signals[:2])
    elif best_branch.branch_type == "intensification":
        reason = "follows the structural beat most closely"
    elif best_branch.structure_beat:
        reason = f"anchored to {best_branch.structure_beat}"
    else:
        reason = "first generated option"

    signals_str = ", ".join(best_signals) if best_signals else ""
    return (best_branch.title, best_branch.id, reason, signals_str)


def _wf_summary(wf: Wavefunction) -> dict:
    rec = recommend_collapse(wf)
    rec_data = None
    if rec:
        rec_data = {
            "branch_id": rec.branch_id,
            "title": rec.title,
            "probability": rec.probability,
            "reason": rec.reason,
            "top_factors": rec.top_factors,
        }
    return {
        "wavefunction_id": wf.id,
        "anchor": wf.anchor,
        "collapsed_branch_id": wf.collapsed_branch_id,
        "source_scene_id": wf.source_scene_id,
        "source_scene_order": wf.source_scene_order,
        "target_scene_id": wf.target_scene_id,
        "structure_method": wf.structure_method,
        "recommendation": rec_data,
        "branches": [
            {
                "id": b.id,
                "title": b.title,
                "description": b.description,
                "stakes": b.stakes,
                "consequence": b.consequence,
                "structure_method": b.structure_method,
                "structure_beat": b.structure_beat,
                "branch_type": b.branch_type,
                "score": b.score,
                "probability": b.probability,
                "factors": b.factors,
                "is_pareto_optimal": b.is_pareto_optimal,
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
