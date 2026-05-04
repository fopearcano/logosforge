"""Style analysis for manuscript paragraphs.

Computes per-paragraph style metrics (clarity, concision, rhythm,
tone_consistency, dialogue_naturalness) using heuristic rules.
No external dependencies required.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field


@dataclass
class ParagraphStyle:
    """Style metrics for a single paragraph."""

    paragraph_id: int
    metrics: dict[str, float] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)
    last_updated: float = 0.0

    def __post_init__(self) -> None:
        if not self.last_updated:
            self.last_updated = time.time()


# ---------------------------------------------------------------------------
# Heuristic helpers
# ---------------------------------------------------------------------------

_FILLER_WORDS = frozenset({
    "very", "really", "just", "quite", "rather", "somewhat", "basically",
    "actually", "literally", "honestly", "simply", "totally", "completely",
    "absolutely", "definitely", "certainly", "perhaps", "maybe",
})

_WEAK_VERBS = frozenset({
    "is", "was", "were", "are", "am", "been", "being",
    "has", "have", "had", "do", "does", "did",
    "seem", "seems", "seemed", "appear", "appears", "appeared",
})

_SUBORDINATE_STARTERS = frozenset({
    "which", "that", "who", "whom", "whose", "where", "when",
    "although", "because", "since", "while", "whereas",
})

_DIALOGUE_RE = re.compile(
    r'["“][^"”]*["”]'
    r"|"
    r"['‘][^'’]*['’]",
)


def _words(text: str) -> list[str]:
    return re.findall(r"[a-zA-Z']+", text.lower())


def _sentences(text: str) -> list[str]:
    parts = re.split(r'[.!?]+', text)
    return [s.strip() for s in parts if s.strip()]


# ---------------------------------------------------------------------------
# Metric computations
# ---------------------------------------------------------------------------

def _clarity(text: str, words: list[str], sentences: list[str]) -> float:
    if not words or not sentences:
        return 1.0
    avg_sentence_len = len(words) / len(sentences)
    long_word_ratio = sum(1 for w in words if len(w) > 12) / len(words)
    subordinate_count = sum(1 for w in words if w in _SUBORDINATE_STARTERS)
    subordinate_ratio = subordinate_count / len(sentences) if sentences else 0

    score = 1.0
    if avg_sentence_len > 25:
        score -= min(0.3, (avg_sentence_len - 25) * 0.015)
    if avg_sentence_len > 40:
        score -= 0.2
    score -= long_word_ratio * 1.5
    score -= subordinate_ratio * 0.15
    return max(0.0, min(1.0, score))


def _concision(text: str, words: list[str]) -> float:
    if not words:
        return 1.0
    filler_count = sum(1 for w in words if w in _FILLER_WORDS)
    filler_ratio = filler_count / len(words)

    weak_verb_count = sum(1 for w in words if w in _WEAK_VERBS)
    weak_ratio = weak_verb_count / len(words)

    prep_count = sum(1 for w in words if w in {"of", "in", "on", "at", "to", "for", "with", "by"})
    prep_ratio = prep_count / len(words)

    score = 1.0
    score -= filler_ratio * 4.0
    score -= max(0, weak_ratio - 0.08) * 2.0
    score -= max(0, prep_ratio - 0.12) * 1.5
    return max(0.0, min(1.0, score))


def _rhythm(sentences: list[str]) -> float:
    if len(sentences) < 2:
        return 1.0
    lengths = [len(s.split()) for s in sentences]
    avg = sum(lengths) / len(lengths)
    if avg == 0:
        return 1.0

    variance = sum((l - avg) ** 2 for l in lengths) / len(lengths)
    cv = (variance ** 0.5) / avg

    if cv < 0.1:
        return 0.5
    if cv > 1.5:
        return 0.5
    if 0.3 <= cv <= 0.8:
        return 1.0
    if cv < 0.3:
        return 0.5 + (cv - 0.1) * 2.5
    return 1.0 - (cv - 0.8) * 0.7


def _tone_consistency(sentences: list[str]) -> float:
    if len(sentences) < 2:
        return 1.0

    def _sentence_register(s: str) -> str:
        w = s.lower().split()
        exclaim = s.endswith("!")
        question = s.endswith("?")
        has_contraction = any("'" in word for word in w)
        avg_word_len = sum(len(word) for word in w) / max(len(w), 1)
        if exclaim or has_contraction or avg_word_len < 4.5:
            return "informal"
        if avg_word_len > 6.0:
            return "formal"
        return "neutral"

    registers = [_sentence_register(s) for s in sentences]
    unique = set(registers)
    if len(unique) <= 1:
        return 1.0
    if "formal" in unique and "informal" in unique:
        return 0.5
    return 0.8


def _dialogue_naturalness(text: str) -> float | None:
    matches = _DIALOGUE_RE.findall(text)
    if not matches:
        return None

    scores: list[float] = []
    for quote in matches:
        inner = quote[1:-1].strip()
        words = inner.split()
        if not words:
            continue
        score = 1.0
        if len(words) > 50:
            score -= 0.3
        if len(words) > 80:
            score -= 0.2
        semicolons = inner.count(";")
        if semicolons > 0:
            score -= semicolons * 0.15
        long_words = sum(1 for w in words if len(w) > 10)
        if long_words / max(len(words), 1) > 0.15:
            score -= 0.2
        has_contraction = any("'" in w or "’" in w for w in words)
        if has_contraction:
            score += 0.05
        scores.append(max(0.0, min(1.0, score)))

    return sum(scores) / len(scores) if scores else None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def analyze_paragraph(paragraph_id: int, text: str) -> ParagraphStyle:
    """Compute style metrics for a paragraph of text."""
    words = _words(text)
    sentences = _sentences(text)

    metrics: dict[str, float] = {
        "clarity": round(_clarity(text, words, sentences), 3),
        "concision": round(_concision(text, words), 3),
        "rhythm": round(_rhythm(sentences), 3),
        "tone_consistency": round(_tone_consistency(sentences), 3),
    }

    dialogue = _dialogue_naturalness(text)
    if dialogue is not None:
        metrics["dialogue_naturalness"] = round(dialogue, 3)

    notes: list[str] = []
    if metrics["clarity"] < 0.6:
        notes.append("Sentences may be too complex or long")
    if metrics["concision"] < 0.6:
        notes.append("Consider removing filler words")
    if metrics["rhythm"] < 0.6:
        notes.append("Sentence lengths are too uniform")
    if metrics["tone_consistency"] < 0.7:
        notes.append("Tone shifts between formal and informal")
    if dialogue is not None and dialogue < 0.6:
        notes.append("Dialogue may sound unnatural")

    return ParagraphStyle(
        paragraph_id=paragraph_id,
        metrics=metrics,
        notes=notes,
    )


def analyze_paragraphs(text: str) -> list[ParagraphStyle]:
    """Analyze all paragraphs in a block of text."""
    paragraphs = [p.strip() for p in text.split("\n") if p.strip()]
    return [analyze_paragraph(i, p) for i, p in enumerate(paragraphs)]
