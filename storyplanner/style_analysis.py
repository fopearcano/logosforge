"""Style analysis for manuscript paragraphs.

Computes per-paragraph style metrics (clarity, concision, rhythm,
tone_consistency, dialogue_naturalness) using heuristic rules.
No external dependencies required.

Primary API: ``analyze_style(text)`` returns cached ``ParagraphStyle``.
Optional: ``StyleRefineWorker`` runs an async LLM call to refine heuristics.
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

_ADVERBS = frozenset({
    "very", "really", "extremely", "incredibly", "absolutely", "totally",
    "completely", "utterly", "thoroughly", "remarkably", "terribly",
    "awfully", "exceedingly", "immensely", "enormously", "vastly",
    "deeply", "highly", "greatly", "strongly", "firmly", "slightly",
    "barely", "hardly", "nearly", "mostly", "largely", "roughly",
    "quickly", "slowly", "suddenly", "immediately", "eventually",
    "finally", "constantly", "frequently", "occasionally", "rarely",
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

def _repeated_word_ratio(words: list[str]) -> float:
    if len(words) < 4:
        return 0.0
    skip = {"the", "a", "an", "and", "or", "but", "in", "on", "of", "to",
            "is", "was", "it", "he", "she", "i", "we", "they", "his", "her"}
    content = [w for w in words if w not in skip and len(w) > 2]
    if not content:
        return 0.0
    from collections import Counter
    counts = Counter(content)
    repeated = sum(c - 1 for c in counts.values() if c > 1)
    return repeated / len(content)


def _clarity(text: str, words: list[str], sentences: list[str]) -> float:
    if not words or not sentences:
        return 1.0
    avg_sentence_len = len(words) / len(sentences)
    long_word_ratio = sum(1 for w in words if len(w) > 12) / len(words)
    subordinate_count = sum(1 for w in words if w in _SUBORDINATE_STARTERS)
    subordinate_ratio = subordinate_count / len(sentences) if sentences else 0
    repeat_ratio = _repeated_word_ratio(words)

    score = 1.0
    if avg_sentence_len > 25:
        score -= min(0.3, (avg_sentence_len - 25) * 0.015)
    if avg_sentence_len > 40:
        score -= 0.2
    score -= long_word_ratio * 1.5
    score -= subordinate_ratio * 0.15
    score -= repeat_ratio * 0.8
    return max(0.0, min(1.0, score))


def _adverb_ratio(words: list[str]) -> float:
    if not words:
        return 0.0
    return sum(1 for w in words if w in _ADVERBS) / len(words)


def _concision(text: str, words: list[str], sentences: list[str]) -> float:
    if not words:
        return 1.0
    filler_count = sum(1 for w in words if w in _FILLER_WORDS)
    filler_ratio = filler_count / len(words)

    weak_verb_count = sum(1 for w in words if w in _WEAK_VERBS)
    weak_ratio = weak_verb_count / len(words)

    prep_count = sum(1 for w in words if w in {"of", "in", "on", "at", "to", "for", "with", "by"})
    prep_ratio = prep_count / len(words)

    adverb_r = _adverb_ratio(words)

    avg_sentence_len = len(words) / max(len(sentences), 1)

    score = 1.0
    score -= filler_ratio * 4.0
    score -= max(0, weak_ratio - 0.08) * 2.0
    score -= max(0, prep_ratio - 0.12) * 1.5
    score -= max(0, adverb_r - 0.05) * 3.0
    if avg_sentence_len > 30:
        score -= min(0.25, (avg_sentence_len - 30) * 0.012)
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
        colons = inner.count(":")
        if colons > 1:
            score -= 0.1
        ellipsis_count = inner.count("...") + inner.count("…")
        if ellipsis_count > 2:
            score -= 0.1
        excl = inner.count("!")
        if excl > 3:
            score -= min(0.2, (excl - 3) * 0.05)
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
        "concision": round(_concision(text, words, sentences), 3),
        "rhythm": round(_rhythm(sentences), 3),
        "tone_consistency": round(_tone_consistency(sentences), 3),
    }

    dialogue = _dialogue_naturalness(text)
    if dialogue is not None:
        metrics["dialogue_naturalness"] = round(dialogue, 3)

    notes: list[str] = []
    if metrics["clarity"] < 0.6:
        notes.append("Sentences may be too complex or long")
    if _repeated_word_ratio(words) > 0.15:
        notes.append("Some words repeat frequently")
    if metrics["concision"] < 0.6:
        notes.append("Consider removing filler words")
    if _adverb_ratio(words) > 0.1:
        notes.append("Excessive adverbs weaken the prose")
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


# ---------------------------------------------------------------------------
# Cache
# ---------------------------------------------------------------------------

_style_cache: dict[str, ParagraphStyle] = {}
_STYLE_CACHE_MAX = 512


def _cache_key(text: str) -> str:
    return hashlib.md5(text.encode("utf-8")).hexdigest()


def _cache_get(text: str) -> ParagraphStyle | None:
    return _style_cache.get(_cache_key(text))


def _cache_put(text: str, style: ParagraphStyle) -> None:
    if len(_style_cache) >= _STYLE_CACHE_MAX:
        _style_cache.clear()
    _style_cache[_cache_key(text)] = style


def clear_cache() -> None:
    """Clear the style analysis cache."""
    _style_cache.clear()


# ---------------------------------------------------------------------------
# Cached public API
# ---------------------------------------------------------------------------

def analyze_style(text: str) -> ParagraphStyle:
    """Compute style metrics with caching. Primary public API."""
    cached = _cache_get(text)
    if cached is not None:
        return cached
    result = analyze_paragraph(0, text)
    _cache_put(text, result)
    return result


# ---------------------------------------------------------------------------
# Optional async LLM refinement
# ---------------------------------------------------------------------------

_STYLE_KEYS = ("clarity", "concision", "rhythm", "tone_consistency")

_REFINE_SYSTEM_PROMPT = (
    "You are a writing style analyst. Given a paragraph of fiction, "
    "rate these metrics on a 0.0–1.0 scale:\n"
    "- clarity: how easy the text is to follow (1.0 = crystal clear)\n"
    "- concision: how economical the word choice is (1.0 = no waste)\n"
    "- rhythm: how well sentence lengths vary (1.0 = great flow)\n"
    "- tone_consistency: how uniform the register is (1.0 = consistent)\n"
    "- dialogue_naturalness: how natural the dialogue sounds "
    "(1.0 = very natural, omit if no dialogue)\n\n"
    "Respond with ONLY a JSON object, e.g.: "
    '{"clarity": 0.8, "concision": 0.7, "rhythm": 0.9, "tone_consistency": 0.8}'
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


def _parse_style_metrics(raw: str) -> dict[str, float] | None:
    """Extract style metrics dict from LLM response text."""
    match = re.search(r"\{[^}]+\}", raw)
    if not match:
        return None
    try:
        data = json.loads(match.group())
    except json.JSONDecodeError:
        return None
    if not set(_STYLE_KEYS).issubset(data):
        return None
    result: dict[str, float] = {}
    for k in (*_STYLE_KEYS, "dialogue_naturalness"):
        if k in data:
            result[k] = max(0.0, min(1.0, float(data[k])))
    return result


try:
    from PySide6.QtCore import QThread, Signal

    class StyleRefineWorker(QThread):
        """Async LLM call to refine heuristic style metrics."""

        completed = Signal(object)  # ParagraphStyle
        failed = Signal(str)

        def __init__(self, style: ParagraphStyle, text: str) -> None:
            super().__init__()
            self._style = style
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
                refined = _parse_style_metrics(result)
                if refined is None:
                    self.failed.emit("LLM returned unparseable response")
                    return

                blended: dict[str, float] = {}
                for key in self._style.metrics:
                    h = self._style.metrics[key]
                    l = refined.get(key)
                    if l is not None:
                        blended[key] = round(h * 0.4 + l * 0.6, 3)
                    else:
                        blended[key] = h

                updated = ParagraphStyle(
                    paragraph_id=self._style.paragraph_id,
                    metrics=blended,
                    notes=list(self._style.notes),
                )
                _cache_put(self._text, updated)
                self.completed.emit(updated)
            except Exception as e:
                log.debug("LLM style refinement failed: %s", e)
                self.failed.emit(str(e))

except ImportError:
    pass
