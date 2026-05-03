"""Branch scoring engine — compute weighted score per quantum possibility.

Each branch is evaluated on five factors (0–1 each), combined via
configurable weights into a final score and probability.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from storyplanner.quantum_outliner.psyke_adapter import PsykeSignals
from storyplanner.quantum_outliner.state import Branch, QuantumPossibility, Wavefunction

if TYPE_CHECKING:
    pass

_TENSION_KEYWORDS = frozenset({
    "but", "however", "suddenly", "fight", "argued", "shouted",
    "betray", "lie", "secret", "fear", "afraid", "danger",
    "must", "cannot", "refused", "demanded", "conflict", "risk",
    "threat", "desperate", "sacrifice", "loss", "pain", "war",
})

DEFAULT_WEIGHTS: dict[str, float] = {
    "structure_fit": 0.25,
    "psyke_consistency": 0.25,
    "tension_gain": 0.20,
    "novelty": 0.15,
    "goal_alignment": 0.15,
}


@dataclass(frozen=True)
class ScoredBranch:
    branch_id: str
    score: float
    probability: float
    factors: dict[str, float]


def score_branches(
    wf: Wavefunction,
    *,
    psyke: PsykeSignals | None = None,
    protagonist_goal: str = "",
    weights: dict[str, float] | None = None,
) -> list[ScoredBranch]:
    """Score all branches in a wavefunction. Returns sorted high-to-low."""
    w = weights or DEFAULT_WEIGHTS

    scored: list[ScoredBranch] = []
    existing_titles = {b.title.lower() for b in wf.branches}

    for b in wf.branches:
        others = existing_titles - {b.title.lower()}
        factors = compute_factors(
            b, wf,
            psyke=psyke,
            protagonist_goal=protagonist_goal,
            sibling_titles=others,
        )
        raw = sum(factors[k] * w.get(k, 0.0) for k in factors)
        score = max(0.0, min(raw, 1.0))
        scored.append(ScoredBranch(
            branch_id=b.id,
            score=round(score, 4),
            probability=0.0,
            factors={k: round(v, 4) for k, v in factors.items()},
        ))

    probs = _softmax([s.score for s in scored])
    scored = [
        ScoredBranch(
            branch_id=s.branch_id,
            score=s.score,
            probability=p,
            factors=s.factors,
        )
        for s, p in zip(scored, probs)
    ]

    scored.sort(key=lambda s: s.score, reverse=True)
    return scored


def apply_scores(wf: Wavefunction, scored: list[ScoredBranch]) -> None:
    """Write scoring results back onto the Branch objects."""
    by_id = {s.branch_id: s for s in scored}
    for b in wf.branches:
        s = by_id.get(b.id)
        if s:
            b.score = s.score
            b.probability = s.probability
            b.factors = dict(s.factors)


def compute_probabilities(
    possibilities: list[QuantumPossibility],
    *,
    temperature: float = 1.0,
) -> None:
    """Normalize scores to probabilities via softmax. Mutates in place."""
    probs = _softmax([p.score for p in possibilities], temperature=temperature)
    for p, prob in zip(possibilities, probs):
        p.probability = prob


def _softmax(
    scores: list[float], *, temperature: float = 1.0,
) -> list[float]:
    """Softmax normalization returning probabilities that sum to 1."""
    if not scores:
        return []

    n = len(scores)
    if all(s == 0.0 for s in scores):
        uniform = round(1.0 / n, 4)
        return [uniform] * n

    t = max(temperature, 1e-9)
    max_s = max(scores)
    exps = [math.exp((s - max_s) / t) for s in scores]
    total = sum(exps)
    return [round(e / total, 4) for e in exps]


def compute_factors(
    branch: Branch,
    wf: Wavefunction,
    *,
    psyke: PsykeSignals | None = None,
    protagonist_goal: str = "",
    sibling_titles: set[str] | None = None,
) -> dict[str, float]:
    """Compute individual factor scores (0–1) for a single branch."""
    return {
        "structure_fit": _score_structure_fit(branch, wf),
        "psyke_consistency": _score_psyke_consistency(branch, psyke),
        "tension_gain": _score_tension_gain(branch),
        "novelty": _score_novelty(branch, sibling_titles or set()),
        "goal_alignment": _score_goal_alignment(branch, protagonist_goal),
    }


def _score_structure_fit(branch: Branch, wf: Wavefunction) -> float:
    score = 0.0
    if branch.structure_beat and branch.structure_beat == wf.structure_beat:
        score += 0.5
    if branch.structure_method and branch.structure_method == wf.structure_method:
        score += 0.3
    if branch.branch_type == "intensification":
        score += 0.2
    elif branch.branch_type in ("alternative", "resolution"):
        score += 0.1
    return min(score, 1.0)


def _score_psyke_consistency(
    branch: Branch, psyke: PsykeSignals | None,
) -> float:
    if not psyke or not psyke.keywords:
        return 0.5

    text = f"{branch.title} {branch.description} {branch.stakes} {branch.consequence}".lower()
    words = set(text.split())

    score = 0.0

    char_names = {c["name"].lower() for c in psyke.characters}
    name_hits = char_names & words
    if name_hits:
        score += min(len(name_hits) * 0.2, 0.4)

    kw_hits = psyke.keywords & words
    if kw_hits:
        score += min(len(kw_hits) * 0.05, 0.3)

    for rel in psyke.relations:
        pair = {rel["from"].lower(), rel["to"].lower()}
        if pair & words:
            score += 0.15
            break

    for arc in psyke.unresolved_arcs:
        arc_words = set(arc["arc"].lower().split())
        if arc_words & words - {"the", "a", "an", "is", "of"}:
            score += 0.15
            break

    return min(score, 1.0)


def _score_tension_gain(branch: Branch) -> float:
    text = f"{branch.description} {branch.stakes} {branch.consequence}".lower()
    words = set(text.split())
    hits = _TENSION_KEYWORDS & words
    if not hits:
        return 0.1
    return min(len(hits) * 0.15, 1.0)


def _score_novelty(branch: Branch, sibling_titles: set[str]) -> float:
    if not sibling_titles:
        return 0.8

    title_words = set(branch.title.lower().split())
    desc_words = set(branch.description.lower().split())
    branch_words = title_words | desc_words

    max_overlap = 0.0
    for sib in sibling_titles:
        sib_words = set(sib.split())
        if not sib_words:
            continue
        overlap = len(branch_words & sib_words) / max(len(sib_words), 1)
        if overlap > max_overlap:
            max_overlap = overlap

    return max(1.0 - max_overlap, 0.0)


def _score_goal_alignment(branch: Branch, goal: str) -> float:
    if not goal.strip():
        return 0.5

    goal_words = set(goal.lower().split()) - {"the", "a", "an", "is", "to", "of"}
    text = f"{branch.title} {branch.description} {branch.consequence}".lower()
    branch_words = set(text.split())

    if not goal_words:
        return 0.5

    hits = goal_words & branch_words
    return min(len(hits) / len(goal_words), 1.0)
