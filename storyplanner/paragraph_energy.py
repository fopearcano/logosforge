"""Paragraph-level energy analysis — tension, pacing, conflict, emotional shift.

Computes lightweight per-paragraph writing dynamics from content text.
Paragraphs are positional text blocks within scene content, split by newlines.
All structures are in-memory dataclasses — no database persistence.

Primary API: ``analyze_paragraph(text)`` returns cached ``ParagraphEnergy``.
Optional: ``EnergyRefineWorker`` runs an async LLM call to refine heuristics.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
import time
from dataclasses import dataclass, field

log = logging.getLogger(__name__)


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


# ---------------------------------------------------------------------------
# Word sets
# ---------------------------------------------------------------------------

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

_CONTRAST_WORDS = frozenset({
    "but", "however", "yet", "suddenly", "instead", "nevertheless",
    "although", "despite", "whereas", "unlike", "unexpectedly",
    "still", "nonetheless", "conversely", "ironically",
})

_DIALOGUE_RE = re.compile(
    r'["“][^”"]*["”]'
    r"|"
    r"['‘][^’']*['’]",
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _words(text: str) -> list[str]:
    return re.findall(r"[a-zA-Z']+", text.lower())


def _sentences(text: str) -> list[str]:
    parts = re.split(r'[.!?]+', text)
    return [s.strip() for s in parts if s.strip()]


def _dialogue_ratio(text: str) -> float:
    matches = _DIALOGUE_RE.findall(text)
    if not matches or not text.strip():
        return 0.0
    dialogue_chars = sum(len(m) for m in matches)
    return dialogue_chars / len(text)


# ---------------------------------------------------------------------------
# Metric computations
# ---------------------------------------------------------------------------

def _compute_tension(words: list[str], dialogue_r: float) -> float:
    if not words:
        return 0.0
    hits = sum(1 for w in words if w in _TENSION_WORDS)
    score = hits / max(len(words), 1) * 15
    score += dialogue_r * 0.15
    return min(1.0, round(score, 3))


def _compute_pacing(
    text: str, words: list[str], sentences: list[str], dialogue_r: float,
) -> float:
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
    score += dialogue_r * 0.1
    return min(1.0, max(0.0, round(score, 3)))


def _compute_conflict(words: list[str]) -> float:
    if not words:
        return 0.0
    hits = sum(1 for w in words if w in _CONFLICT_WORDS)
    return min(1.0, round(hits / max(len(words), 1) * 12, 3))


def _compute_emotional_shift(words: list[str]) -> float:
    vals = [_EMOTION_WORDS[w] for w in words if w in _EMOTION_WORDS]

    contrast_hits = sum(1 for w in words if w in _CONTRAST_WORDS)
    contrast_boost = min(contrast_hits * 0.1, 0.3)

    if len(vals) < 2:
        return min(1.0, round(contrast_boost, 3))
    max_diff = max(
        abs(vals[i] - vals[i + 1]) for i in range(len(vals) - 1)
    )
    return min(1.0, round(max_diff + contrast_boost, 3))


# ---------------------------------------------------------------------------
# Cache
# ---------------------------------------------------------------------------

_energy_cache: dict[str, ParagraphEnergy] = {}
_ENERGY_CACHE_MAX = 512


def _cache_key(text: str) -> str:
    return hashlib.md5(text.encode("utf-8")).hexdigest()


def _cache_get(text: str) -> ParagraphEnergy | None:
    return _energy_cache.get(_cache_key(text))


def _cache_put(text: str, energy: ParagraphEnergy) -> None:
    if len(_energy_cache) >= _ENERGY_CACHE_MAX:
        _energy_cache.clear()
    _energy_cache[_cache_key(text)] = energy


def clear_cache() -> None:
    """Clear the energy analysis cache."""
    _energy_cache.clear()


# ---------------------------------------------------------------------------
# Core computation
# ---------------------------------------------------------------------------

def compute_paragraph_energy(
    paragraph_id: int,
    scene_id: int,
    text: str,
) -> ParagraphEnergy:
    """Compute energy metrics for a single paragraph (no cache)."""
    words = _words(text)
    sentences = _sentences(text)
    dialogue_r = _dialogue_ratio(text)

    metrics = {
        "tension": _compute_tension(words, dialogue_r),
        "pacing": _compute_pacing(text, words, sentences, dialogue_r),
        "conflict": _compute_conflict(words),
        "emotional_shift": _compute_emotional_shift(words),
    }

    return ParagraphEnergy(
        paragraph_id=paragraph_id,
        scene_id=scene_id,
        metrics=metrics,
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def analyze_paragraph(text: str) -> ParagraphEnergy:
    """Compute energy metrics with caching. Primary public API."""
    cached = _cache_get(text)
    if cached is not None:
        return cached
    result = compute_paragraph_energy(0, 0, text)
    _cache_put(text, result)
    return result


@dataclass
class FlowHint:
    """A light flow issue detected across a span of paragraphs."""

    start: int
    end: int
    kind: str
    message: str


_FLAT_WINDOW = 4
_FLAT_TENSION_CEIL = 0.15
_FLAT_CONFLICT_CEIL = 0.1

_PACING_WINDOW = 3
_PACING_SPIKE_DELTA = 0.4

_EMOTION_WINDOW = 5
_EMOTION_SHIFT_CEIL = 0.05


def detect_flow_hints(energies: list[ParagraphEnergy]) -> list[FlowHint]:
    """Detect flow issues from a sequence of paragraph energies.

    Returns at most one hint per detected region.  Keeps thresholds
    strict so hints only fire on unambiguous patterns.
    """
    hints: list[FlowHint] = []
    n = len(energies)

    # -- flat sequence: low tension + low conflict for FLAT_WINDOW+ paragraphs
    if n >= _FLAT_WINDOW:
        run_start: int | None = None
        for i, e in enumerate(energies):
            flat = e.tension <= _FLAT_TENSION_CEIL and e.conflict <= _FLAT_CONFLICT_CEIL
            if flat:
                if run_start is None:
                    run_start = i
            else:
                if run_start is not None and i - run_start >= _FLAT_WINDOW:
                    hints.append(FlowHint(
                        start=run_start, end=i - 1,
                        kind="flat",
                        message="This section may feel flat — tension and conflict are low across several paragraphs",
                    ))
                run_start = None
        if run_start is not None and n - run_start >= _FLAT_WINDOW:
            hints.append(FlowHint(
                start=run_start, end=n - 1,
                kind="flat",
                message="This section may feel flat — tension and conflict are low across several paragraphs",
            ))

    # -- pacing spike/drop: sudden jump between adjacent paragraphs
    if n >= _PACING_WINDOW:
        for i in range(1, n):
            delta = energies[i].pacing - energies[i - 1].pacing
            if abs(delta) >= _PACING_SPIKE_DELTA:
                word = "spike" if delta > 0 else "drop"
                hints.append(FlowHint(
                    start=i, end=i,
                    kind=f"pacing_{word}",
                    message=f"Pacing {word}s sharply here",
                ))

    # -- no emotional shift: long stretch with zero emotional_shift
    if n >= _EMOTION_WINDOW:
        run_start = None
        for i, e in enumerate(energies):
            if e.emotional_shift <= _EMOTION_SHIFT_CEIL:
                if run_start is None:
                    run_start = i
            else:
                if run_start is not None and i - run_start >= _EMOTION_WINDOW:
                    hints.append(FlowHint(
                        start=run_start, end=i - 1,
                        kind="no_emotion",
                        message="Emotional tone stays constant through this stretch",
                    ))
                run_start = None
        if run_start is not None and n - run_start >= _EMOTION_WINDOW:
            hints.append(FlowHint(
                start=run_start, end=n - 1,
                kind="no_emotion",
                message="Emotional tone stays constant through this stretch",
            ))

    return hints


def analyze_scene_energy(scene_id: int, content: str) -> list[ParagraphEnergy]:
    """Compute energy metrics for all paragraphs in scene content."""
    paragraphs = [p.strip() for p in content.split("\n") if p.strip()]
    results: list[ParagraphEnergy] = []
    for i, p in enumerate(paragraphs):
        cached = _cache_get(p)
        if cached is not None:
            result = ParagraphEnergy(
                paragraph_id=i,
                scene_id=scene_id,
                metrics=dict(cached.metrics),
                last_updated=cached.last_updated,
            )
        else:
            result = compute_paragraph_energy(i, scene_id, p)
            _cache_put(p, result)
        results.append(result)
    return results


# ---------------------------------------------------------------------------
# Optional async LLM refinement
# ---------------------------------------------------------------------------

_REFINE_SYSTEM_PROMPT = (
    "You are a literary analysis assistant. Given a paragraph of fiction, "
    "rate these four metrics on a 0.0–1.0 scale:\n"
    "- tension: how much suspense or anxiety the reader feels\n"
    "- pacing: how fast events move (1.0 = very fast)\n"
    "- conflict: how much opposition or struggle is present\n"
    "- emotional_shift: how much the emotional tone changes within the paragraph\n\n"
    "Respond with ONLY a JSON object: "
    '{"tension": 0.0, "pacing": 0.0, "conflict": 0.0, "emotional_shift": 0.0}'
)


def _build_provider():
    from storyplanner.providers import ProviderConfig
    from storyplanner.settings import get_manager
    settings = get_manager()
    return ProviderConfig(
        name=str(settings.get("ai_provider") or "LM Studio"),
        base_url=str(settings.get("ai_base_url") or "http://localhost:1234/v1"),
        model=str(settings.get("ai_model") or ""),
        api_key=str(settings.get("ai_api_key") or ""),
    )


def _parse_llm_metrics(raw: str) -> dict[str, float] | None:
    """Extract metrics dict from LLM response text."""
    match = re.search(r"\{[^}]+\}", raw)
    if not match:
        return None
    try:
        data = json.loads(match.group())
    except json.JSONDecodeError:
        return None
    keys = {"tension", "pacing", "conflict", "emotional_shift"}
    if not keys.issubset(data):
        return None
    return {k: max(0.0, min(1.0, float(data[k]))) for k in keys}


try:
    from PySide6.QtCore import QThread, Signal

    class EnergyRefineWorker(QThread):
        """Async LLM call to refine heuristic energy metrics."""

        completed = Signal(object)  # ParagraphEnergy
        failed = Signal(str)

        def __init__(self, energy: ParagraphEnergy, text: str) -> None:
            super().__init__()
            self._energy = energy
            self._text = text

        def run(self) -> None:
            from storyplanner.assistant import chat_completion
            try:
                provider = _build_provider()
                messages = [
                    {"role": "system", "content": _REFINE_SYSTEM_PROMPT},
                    {"role": "user", "content": self._text},
                ]
                result, _ = chat_completion(
                    messages, provider=provider, timeout=15,
                    use_cache=True, response_language="en",
                )
                refined = _parse_llm_metrics(result)
                if refined is None:
                    self.failed.emit("LLM returned unparseable response")
                    return

                blended: dict[str, float] = {}
                for key in ("tension", "pacing", "conflict", "emotional_shift"):
                    h = self._energy.metrics.get(key, 0.0)
                    l = refined[key]
                    blended[key] = round(h * 0.4 + l * 0.6, 3)

                updated = ParagraphEnergy(
                    paragraph_id=self._energy.paragraph_id,
                    scene_id=self._energy.scene_id,
                    metrics=blended,
                )
                _cache_put(self._text, updated)
                self.completed.emit(updated)
            except Exception as e:
                log.debug("LLM energy refinement failed: %s", e)
                self.failed.emit(str(e))

except ImportError:
    pass
