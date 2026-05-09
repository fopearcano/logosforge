"""Paragraph-level energy analysis — tension, pacing, conflict, emotional shift.

Computes lightweight per-paragraph writing dynamics from content text.
Paragraphs are positional text blocks within scene content, split by newlines.
All structures are in-memory dataclasses — no database persistence.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field


@dataclass
class ParagraphEnergy:
    """Energy metrics for a single paragraph."""

    paragraph_id: int
    scene_id: int
    metrics: dict[str, float] = field(default_factory=dict)
    last_updated: float = 0.0

    def __post_init__(self) -> None:
        if not self.last_updated:
            self.last_updated = time.time()

    @property
    def tension(self) -> float:
        return self.metrics.get("tension", 0.0)

    @property
    def pacing(self) -> float:
        return self.metrics.get("pacing", 0.0)

    @property
    def conflict(self) -> float:
        return self.metrics.get("conflict", 0.0)

    @property
    def emotional_shift(self) -> float:
        return self.metrics.get("emotional_shift", 0.0)


_TENSION_WORDS = frozenset({
    "feared", "trembled", "dreaded", "panicked", "froze", "screamed",
    "gasped", "shuddered", "tightened", "clenched", "braced", "whispered",
    "lurked", "crept", "stalked", "loomed", "threatened", "cornered",
    "trapped", "suffocated", "strangled", "choked", "darkness", "shadow",
    "danger", "risk", "death", "blood", "pain", "agony",
})

_CONFLICT_WORDS = frozenset({
    "fought", "argued", "screamed", "attacked", "refused", "clash",
    "struggle", "battle", "confronted", "threat", "danger", "enemy",
    "betrayed", "lied", "deceived", "trapped", "killed", "opposed",
    "resisted", "defied", "challenged", "denied", "demanded", "accused",
    "blamed", "shouted", "slammed", "smashed", "rage", "fury",
})

_EMOTION_WORDS: dict[str, float] = {
    "laughed": 0.8, "smiled": 0.7, "grinned": 0.7, "cheered": 0.9,
    "rejoiced": 0.9, "loved": 0.8, "hoped": 0.6, "delighted": 0.8,
    "cried": 0.2, "wept": 0.2, "sobbed": 0.1, "mourned": 0.1,
    "grieved": 0.1, "feared": 0.2, "dreaded": 0.15, "raged": 0.15,
    "hated": 0.1, "despaired": 0.05, "panicked": 0.2, "trembled": 0.25,
    "sighed": 0.4, "shrugged": 0.5, "wondered": 0.5, "pondered": 0.5,
}

_ACTION_WORDS = frozenset({
    "ran", "jumped", "fell", "grabbed", "slammed", "sprinted",
    "crashed", "exploded", "chased", "dodged", "struck", "threw",
    "kicked", "punched", "fired", "shot", "fled", "escaped",
    "leaped", "dashed", "lunged", "charged", "hurled", "swung",
})


def _words(text: str) -> list[str]:
    return re.findall(r"[a-zA-Z']+", text.lower())


def _sentences(text: str) -> list[str]:
    parts = re.split(r'[.!?]+', text)
    return [s.strip() for s in parts if s.strip()]


def _compute_tension(words: list[str]) -> float:
    if not words:
        return 0.0
    hits = sum(1 for w in words if w in _TENSION_WORDS)
    return min(1.0, round(hits / max(len(words), 1) * 15, 3))


def _compute_pacing(text: str, words: list[str], sentences: list[str]) -> float:
    if not words:
        return 0.5
    avg_sentence_len = len(words) / max(len(sentences), 1)
    action_hits = sum(1 for w in words if w in _ACTION_WORDS)
    action_ratio = action_hits / len(words)
    exclamations = text.count("!")
    excl_ratio = exclamations / max(len(sentences), 1)

    score = 0.5
    if avg_sentence_len < 8:
        score += 0.25
    elif avg_sentence_len < 15:
        score += 0.1
    elif avg_sentence_len > 25:
        score -= 0.2
    score += action_ratio * 5
    score += min(excl_ratio * 0.2, 0.2)
    return min(1.0, max(0.0, round(score, 3)))


def _compute_conflict(words: list[str]) -> float:
    if not words:
        return 0.0
    hits = sum(1 for w in words if w in _CONFLICT_WORDS)
    return min(1.0, round(hits / max(len(words), 1) * 12, 3))


def _compute_emotional_shift(words: list[str]) -> float:
    vals = [_EMOTION_WORDS[w] for w in words if w in _EMOTION_WORDS]
    if len(vals) < 2:
        return 0.0
    max_diff = max(
        abs(vals[i] - vals[i + 1]) for i in range(len(vals) - 1)
    )
    return min(1.0, round(max_diff, 3))


def compute_paragraph_energy(
    paragraph_id: int,
    scene_id: int,
    text: str,
) -> ParagraphEnergy:
    """Compute energy metrics for a single paragraph."""
    words = _words(text)
    sentences = _sentences(text)

    metrics = {
        "tension": _compute_tension(words),
        "pacing": _compute_pacing(text, words, sentences),
        "conflict": _compute_conflict(words),
        "emotional_shift": _compute_emotional_shift(words),
    }

    return ParagraphEnergy(
        paragraph_id=paragraph_id,
        scene_id=scene_id,
        metrics=metrics,
    )


def analyze_scene_energy(scene_id: int, content: str) -> list[ParagraphEnergy]:
    """Compute energy metrics for all paragraphs in scene content."""
    paragraphs = [p.strip() for p in content.split("\n") if p.strip()]
    return [
        compute_paragraph_energy(i, scene_id, p)
        for i, p in enumerate(paragraphs)
    ]
