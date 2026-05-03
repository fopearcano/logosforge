"""QUANTUM Outliner — physics-inspired story plotting agent.

Public API. The metaphors (relativity, uncertainty, wavefunction) are
abstract narrative models, not physics simulation.

Quick reference:
    generate_outline(db, pid, premise)            → starting branches
    generate_branches(db, pid, situation)         → next-move options
    reframe(scene_text, pov, db, pid)             → POV-shifted reading
    detect_weak_scenes(db, pid)                   → uncertainty zones
    collapse_branch(db, pid, wf_id, branch_id)    → commit, update PSYKE
    list_active_wavefunctions(pid)                → live branches
"""

from storyplanner.quantum_outliner.core import (
    QuantumResult,
    collapse_branch,
    detect_weak_scenes,
    generate_branches,
    generate_outline,
    list_active_wavefunctions,
    reframe,
)
from storyplanner.quantum_outliner.state import (
    Branch,
    NarrativeState,
    StateDelta,
    Wavefunction,
    get_state,
    reset_state,
)

__all__ = [
    "QuantumResult",
    "Branch",
    "NarrativeState",
    "StateDelta",
    "Wavefunction",
    "collapse_branch",
    "detect_weak_scenes",
    "generate_branches",
    "generate_outline",
    "get_state",
    "list_active_wavefunctions",
    "reframe",
    "reset_state",
]
