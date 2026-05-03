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

from storyplanner.quantum_outliner.collapse import apply_proposal
from storyplanner.quantum_outliner.core import (
    QuantumResult,
    collapse_branch,
    detect_weak_scenes,
    generate_branches,
    generate_outline,
    list_active_wavefunctions,
    reframe,
)
from storyplanner.quantum_outliner.persistence import (
    export_quantum_state,
    import_quantum_state,
    load_state,
    save_state,
)
from storyplanner.quantum_outliner.scoring import (
    CollapseRecommendation,
    FACTOR_LABELS,
    compute_probabilities,
    recommend_collapse,
)
from storyplanner.quantum_outliner.state import (
    OUTLINE_MODES,
    STRUCTURE_MODES,
    Branch,
    NarrativeState,
    OutlineMode,
    QuantumPossibility,
    StateDelta,
    Wavefunction,
    get_outline_mode,
    get_state,
    reset_state,
)

__all__ = [
    "OUTLINE_MODES",
    "OutlineMode",
    "QuantumPossibility",
    "QuantumResult",
    "Branch",
    "NarrativeState",
    "STRUCTURE_MODES",
    "StateDelta",
    "Wavefunction",
    "CollapseRecommendation",
    "FACTOR_LABELS",
    "apply_proposal",
    "collapse_branch",
    "compute_probabilities",
    "recommend_collapse",
    "detect_weak_scenes",
    "export_quantum_state",
    "generate_branches",
    "generate_outline",
    "get_outline_mode",
    "get_state",
    "import_quantum_state",
    "list_active_wavefunctions",
    "load_state",
    "reframe",
    "reset_state",
    "save_state",
]
