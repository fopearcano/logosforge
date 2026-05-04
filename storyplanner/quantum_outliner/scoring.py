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

SCORING_PRESETS: dict[str, dict[str, float]] = {
    "Balanced": {
        "structure_fit": 0.25,
        "psyke_consistency": 0.25,
        "tension_gain": 0.20,
        "novelty": 0.15,
        "goal_alignment": 0.15,
    },
    "Conservative": {
        "structure_fit": 0.35,
        "psyke_consistency": 0.35,
        "tension_gain": 0.10,
        "novelty": 0.10,
        "goal_alignment": 0.10,
    },
    "Bold": {
        "structure_fit": 0.10,
        "psyke_consistency": 0.10,
        "tension_gain": 0.35,
        "novelty": 0.35,
        "goal_alignment": 0.10,
    },
    "Character-driven": {
        "structure_fit": 0.10,
        "psyke_consistency": 0.35,
        "tension_gain": 0.10,
        "novelty": 0.10,
        "goal_alignment": 0.35,
    },
    "Plot-driven": {
        "structure_fit": 0.35,
        "psyke_consistency": 0.10,
        "tension_gain": 0.35,
        "novelty": 0.10,
        "goal_alignment": 0.10,
    },
}

PRESET_NAMES: list[str] = list(SCORING_PRESETS.keys())


# ---------------------------------------------------------------------------
# Beat-phase bias: adjust weights by story position
# ---------------------------------------------------------------------------

BEAT_PHASE_MAP: dict[str, str] = {
    # Setup — establishing the world
    "opening image": "setup",
    "theme stated": "setup",
    "set-up": "setup",
    "setup": "setup",
    "ordinary world": "setup",
    "hook": "setup",
    "ki": "setup",
    "you": "setup",
    # Catalyst — call to action
    "catalyst": "catalyst",
    "call to adventure": "catalyst",
    "refusal of the call": "catalyst",
    "crossing the first threshold": "catalyst",
    "need": "catalyst",
    "go": "catalyst",
    "plot turn 1": "catalyst",
    "break into two": "catalyst",
    # Development — exploring the new world
    "fun and games": "development",
    "b story": "development",
    "tests/allies/enemies": "development",
    "debate": "development",
    "search": "development",
    "shō": "development",
    "meeting the mentor": "development",
    "pinch 1": "development",
    # Midpoint — reversal territory
    "midpoint": "midpoint",
    "midpoint reversal": "midpoint",
    "approach to the inmost cave": "midpoint",
    "find": "midpoint",
    "ten": "midpoint",
    # Crisis — darkest hour
    "bad guys close in": "crisis",
    "all is lost": "crisis",
    "dark night of the soul": "crisis",
    "ordeal": "crisis",
    "pinch 2": "crisis",
    "take": "crisis",
    # Climax — peak confrontation
    "break into three": "climax",
    "finale": "climax",
    "resurrection": "climax",
    "plot turn 2": "climax",
    "climax": "climax",
    "confrontation": "climax",
    # Resolution — wrapping up
    "final image": "resolution",
    "return with the elixir": "resolution",
    "resolution": "resolution",
    "the road back": "resolution",
    "return": "resolution",
    "change": "resolution",
    "ketsu": "resolution",
    "reward": "resolution",
}

PHASE_MULTIPLIERS: dict[str, dict[str, float]] = {
    "setup": {
        "structure_fit": 1.4,
        "psyke_consistency": 1.0,
        "tension_gain": 0.8,
        "novelty": 1.0,
        "goal_alignment": 1.0,
    },
    "catalyst": {
        "structure_fit": 1.0,
        "psyke_consistency": 1.0,
        "tension_gain": 1.0,
        "novelty": 1.4,
        "goal_alignment": 1.0,
    },
    "development": {
        "structure_fit": 1.0,
        "psyke_consistency": 1.3,
        "tension_gain": 0.9,
        "novelty": 1.0,
        "goal_alignment": 1.3,
    },
    "midpoint": {
        "structure_fit": 1.0,
        "psyke_consistency": 1.0,
        "tension_gain": 1.4,
        "novelty": 1.3,
        "goal_alignment": 0.9,
    },
    "crisis": {
        "structure_fit": 0.9,
        "psyke_consistency": 1.4,
        "tension_gain": 1.0,
        "novelty": 0.9,
        "goal_alignment": 1.3,
    },
    "climax": {
        "structure_fit": 1.3,
        "psyke_consistency": 1.0,
        "tension_gain": 1.4,
        "novelty": 0.9,
        "goal_alignment": 1.0,
    },
    "resolution": {
        "structure_fit": 1.3,
        "psyke_consistency": 1.0,
        "tension_gain": 0.8,
        "novelty": 0.9,
        "goal_alignment": 1.4,
    },
}


def get_beat_phase(beat: str | None) -> str | None:
    """Map a beat name to its narrative phase, or None if unrecognized."""
    if not beat:
        return None
    return BEAT_PHASE_MAP.get(beat.strip().lower())


def apply_beat_bias(
    weights: dict[str, float], beat: str | None,
) -> dict[str, float]:
    """Apply phase-based multipliers to weights and renormalize to sum=1."""
    phase = get_beat_phase(beat)
    if not phase:
        return weights

    multipliers = PHASE_MULTIPLIERS.get(phase)
    if not multipliers:
        return weights

    biased = {k: weights.get(k, 0.0) * multipliers.get(k, 1.0) for k in weights}
    total = sum(biased.values())
    if total <= 0:
        return weights
    return {k: round(v / total, 4) for k, v in biased.items()}


# ---------------------------------------------------------------------------
# Weight adaptation — learn from user collapse choices
# ---------------------------------------------------------------------------

LEARNING_RATE: float = 0.05


def adapt_weights(
    current_weights: dict[str, float],
    chosen_factors: dict[str, float],
    unchosen_factors: list[dict[str, float]],
    learning_rate: float = LEARNING_RATE,
) -> dict[str, float]:
    """Nudge weights toward the factor pattern of the chosen branch.

    For each factor, the signal is (chosen - mean_unchosen). Positive signal
    means the user preferred a branch strong on that factor, so we increase
    its weight. Result is clamped to [0, 1] and renormalized to sum = 1.
    """
    if not unchosen_factors or not chosen_factors:
        return current_weights

    n = len(unchosen_factors)
    updated = {}
    for k, w in current_weights.items():
        chosen_val = chosen_factors.get(k, 0.0)
        mean_unchosen = sum(f.get(k, 0.0) for f in unchosen_factors) / n
        signal = chosen_val - mean_unchosen
        updated[k] = max(0.0, min(w + learning_rate * signal, 1.0))

    total = sum(updated.values())
    if total <= 0:
        return current_weights
    return {k: round(v / total, 4) for k, v in updated.items()}


FACTOR_LABELS: dict[str, str] = {
    "structure_fit": "aligns with structural beat",
    "psyke_consistency": "consistent with story bible",
    "tension_gain": "raises narrative tension",
    "novelty": "offers fresh direction",
    "goal_alignment": "advances protagonist's goal",
}

_FACTOR_LABELS = FACTOR_LABELS


def _factor_descriptor(value: float) -> str:
    if value >= 0.7:
        return "high"
    if value >= 0.4:
        return "strong"
    if value >= 0.2:
        return "moderate"
    return "some"


def explain_factors(
    factors: dict[str, float] | list[tuple[str, float]],
    top_n: int = 2,
) -> str:
    """Concise explanation from the top contributing factors.

    >>> explain_factors({"tension_gain": 0.9, "novelty": 0.5, "structure_fit": 0.1})
    'high tension_gain + strong novelty'
    """
    if isinstance(factors, dict):
        items = sorted(factors.items(), key=lambda kv: kv[1], reverse=True)[:top_n]
    else:
        items = list(factors)[:top_n]
    parts = [f"{_factor_descriptor(v)} {k}" for k, v in items if v > 0]
    return " + ".join(parts) if parts else "balanced across all factors"


@dataclass(frozen=True)
class CollapseRecommendation:
    branch_id: str
    title: str
    probability: float
    reason: str
    top_factors: list[tuple[str, float]]

    def explain(self) -> str:
        """Format as 'Recommended: Title (pct)\\n  because: ...'."""
        return format_recommendation(self)


def format_recommendation(rec: CollapseRecommendation) -> str:
    """Format a recommendation with factor-based explanation."""
    explanation = explain_factors(rec.top_factors)
    return (
        f"Recommended: {rec.title}  ({rec.probability:.0%})\n"
        f"  because: {explanation}"
    )


def explain_wavefunction(wf: "Wavefunction") -> str:
    """Per-branch factor explanation, sorted by probability."""
    branches = sorted(wf.branches, key=lambda b: b.probability, reverse=True)
    scored = [b for b in branches if b.factors]
    if not scored:
        return "No scoring data available. Generate branches first."

    lines: list[str] = []
    for b in scored:
        explanation = explain_factors(b.factors)
        lines.append(f"{b.title}  [{b.id}]  ({b.probability:.0%})")
        lines.append(f"  because: {explanation}")
    return "\n".join(lines)


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
    w = apply_beat_bias(weights or DEFAULT_WEIGHTS, wf.structure_beat)

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


def recommend_collapse(wf: Wavefunction) -> CollapseRecommendation | None:
    """Pick the highest-probability branch as collapse recommendation.

    Returns None if fewer than 2 branches or none are scored.
    """
    candidates = [b for b in wf.branches if b.probability > 0]
    if len(candidates) < 2:
        return None

    best = max(candidates, key=lambda b: b.probability)

    runner_up = max(
        (b for b in candidates if b.id != best.id),
        key=lambda b: b.probability,
    )
    is_tie = abs(best.probability - runner_up.probability) < 0.01

    top_factors = sorted(best.factors.items(), key=lambda kv: kv[1], reverse=True)[:2]

    parts = [_FACTOR_LABELS.get(k, k) for k, _ in top_factors if _ > 0]
    if is_tie:
        parts = [f"near-tie with {runner_up.title}"] + parts[:1]
    reason = "; ".join(parts) if parts else "highest overall score"

    return CollapseRecommendation(
        branch_id=best.id,
        title=best.title,
        probability=best.probability,
        reason=reason,
        top_factors=top_factors,
    )


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
    if branch.structure_beat and wf.structure_beat:
        if branch.structure_beat == wf.structure_beat:
            score += 0.5
        else:
            b_words = set(branch.structure_beat.lower().split())
            w_words = set(wf.structure_beat.lower().split())
            if b_words and w_words:
                overlap = len(b_words & w_words) / max(len(b_words | w_words), 1)
                score += overlap * 0.3
    if branch.structure_method and wf.structure_method:
        if branch.structure_method == wf.structure_method:
            score += 0.3
        elif branch.structure_method.lower() in wf.structure_method.lower():
            score += 0.15
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
    _stop = {"the", "a", "an", "is", "of", "to", "and", "in", "for"}

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
        arc_words = set(arc["arc"].lower().split()) - _stop
        if arc_words & words:
            score += 0.15
            break

    for prog in psyke.progressions:
        prog_words = set(prog["text"].lower().split()) - _stop
        if prog_words & words:
            score += min(len(prog_words & words) * 0.1, 0.2)
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
