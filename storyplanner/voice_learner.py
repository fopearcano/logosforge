"""Voice profile learning — infers traits from a character's dialogue.

Collects dialogue segments per speaker, computes style metrics
(sentence length, contraction rate, punctuation habits, vocabulary
level), and merges inferred traits into the stored VoiceProfile
without overwriting user-defined values.

Primary API:
    ``analyze_voice(segments)``  — pure analysis, returns ``VoiceAnalysis``
    ``learn_voice_profile(db, character_id, segments, user_locked=())``
        — analyzes + merges into the DB profile
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

from storyplanner.dialogue_attribution import DialogueSegment


@dataclass(slots=True)
class VoiceAnalysis:
    """Inferred voice traits from dialogue samples."""

    sentence_length: str
    vocabulary_level: str
    tone: str
    punctuation_style: dict[str, float]
    quirks: list[str]
    dialogue_markers: list[str]
    confidence: float
    sample_count: int


_CONTRACTION_RE = re.compile(
    r"\b(?:i'm|i'll|i've|i'd|"
    r"you're|you'll|you've|you'd|"
    r"he's|she's|it's|we're|they're|"
    r"he'll|she'll|we'll|they'll|"
    r"he'd|she'd|we'd|they'd|"
    r"isn't|aren't|wasn't|weren't|"
    r"don't|doesn't|didn't|"
    r"won't|wouldn't|couldn't|shouldn't|"
    r"can't|haven't|hasn't|hadn't|"
    r"let's|that's|there's|who's|what's|"
    r"ain't|gonna|wanna|gotta)\b",
    re.IGNORECASE,
)

_SENTENCE_RE = re.compile(r"[^.!?]+[.!?]+|[^.!?]+$")

_ELEVATED_WORDS = frozenset((
    "nevertheless", "furthermore", "consequently", "henceforth",
    "moreover", "notwithstanding", "aforementioned", "pursuant",
    "whereby", "wherein", "therefore", "thus", "hence",
    "whilst", "amongst", "perhaps", "indeed", "certainly",
    "precisely", "undoubtedly", "exceedingly", "remarkably",
    "shall", "whom", "ought", "endeavour", "endeavor",
))

_SIMPLE_INDICATORS = frozenset((
    "yeah", "yep", "nah", "nope", "huh", "wow", "dude",
    "cool", "stuff", "kinda", "sorta", "totally", "like",
    "ok", "okay", "hey", "yo", "damn", "hell", "crap",
    "gotta", "gonna", "wanna", "ain't", "dunno", "lemme",
))

_MARKER_RE = re.compile(
    r"^(well|look|listen|hey|so|right|okay|oh|ah|hmm|"
    r"indeed|actually|honestly|seriously|basically|"
    r"y'know|you see|I mean|I say)\b",
    re.IGNORECASE,
)

_EXISTING_WEIGHT = 0.7
_LEARNED_WEIGHT = 0.3

_MIN_SAMPLES = 3


def _collect_speaker_text(
    segments: list[DialogueSegment],
    character_id: int,
) -> list[str]:
    return [s.text for s in segments if s.speaker_id == character_id and s.text.strip()]


def _avg_sentence_length(lines: list[str]) -> float:
    word_counts: list[int] = []
    for line in lines:
        for sent_m in _SENTENCE_RE.finditer(line):
            words = sent_m.group().split()
            if words:
                word_counts.append(len(words))
    return sum(word_counts) / max(len(word_counts), 1)


def _classify_sentence_length(avg: float) -> str:
    if avg <= 6:
        return "short"
    if avg <= 14:
        return "medium"
    return "long"


def _contraction_rate(lines: list[str]) -> float:
    total_words = sum(len(line.split()) for line in lines)
    if total_words == 0:
        return 0.0
    contraction_count = sum(len(_CONTRACTION_RE.findall(line)) for line in lines)
    return contraction_count / total_words


def _classify_tone(contraction_rate: float, avg_sent_len: float) -> str:
    if contraction_rate >= 0.08 and avg_sent_len <= 8:
        return "casual"
    if contraction_rate <= 0.02 and avg_sent_len >= 10:
        return "formal"
    return "neutral"


def _punctuation_usage(lines: list[str]) -> dict[str, float]:
    total = max(len(lines), 1)
    counts: dict[str, int] = {
        "exclamations": 0,
        "questions": 0,
        "ellipses": 0,
        "dashes": 0,
    }
    for line in lines:
        if "!" in line:
            counts["exclamations"] += 1
        if "?" in line:
            counts["questions"] += 1
        if "..." in line or "…" in line:
            counts["ellipses"] += 1
        if "—" in line or "--" in line:
            counts["dashes"] += 1
    return {k: round(v / total, 3) for k, v in counts.items()}


def _classify_vocabulary(lines: list[str]) -> str:
    words: list[str] = []
    for line in lines:
        words.extend(re.findall(r"[a-z']+", line.lower()))
    if not words:
        return "standard"
    total = len(words)
    elevated = sum(1 for w in words if w in _ELEVATED_WORDS)
    simple = sum(1 for w in words if w in _SIMPLE_INDICATORS)
    if elevated / total >= 0.03:
        return "elevated"
    if simple / total >= 0.05:
        return "simple"
    return "standard"


def _detect_quirks(lines: list[str], contraction_rate: float) -> list[str]:
    quirks: list[str] = []
    if contraction_rate < 0.01 and len(lines) >= _MIN_SAMPLES:
        quirks.append("avoids contractions")
    if contraction_rate >= 0.10:
        quirks.append("heavy contraction use")

    ellipsis_count = sum(1 for l in lines if "..." in l or "…" in l)
    if len(lines) >= _MIN_SAMPLES and ellipsis_count / len(lines) >= 0.4:
        quirks.append("trails off frequently")

    excl_count = sum(1 for l in lines if "!" in l)
    if len(lines) >= _MIN_SAMPLES and excl_count / len(lines) >= 0.5:
        quirks.append("exclamatory speaker")

    return quirks


def _detect_markers(lines: list[str]) -> list[str]:
    counts: dict[str, int] = {}
    for line in lines:
        m = _MARKER_RE.match(line.strip())
        if m:
            marker = m.group(1)
            normalised = marker[0].upper() + marker[1:].lower()
            counts[normalised] = counts.get(normalised, 0) + 1
    threshold = max(2, len(lines) // 5)
    return [m for m, c in sorted(counts.items(), key=lambda x: -x[1]) if c >= threshold]


def _confidence(sample_count: int) -> float:
    if sample_count < _MIN_SAMPLES:
        return round(sample_count / _MIN_SAMPLES * 0.3, 2)
    return round(min(0.3 + (sample_count - _MIN_SAMPLES) * 0.07, 1.0), 2)


def analyze_voice(
    segments: list[DialogueSegment],
    character_id: int,
) -> VoiceAnalysis:
    """Analyze dialogue segments for one character, returning inferred traits."""
    lines = _collect_speaker_text(segments, character_id)
    sample_count = len(lines)
    if sample_count == 0:
        return VoiceAnalysis(
            sentence_length="medium",
            vocabulary_level="standard",
            tone="neutral",
            punctuation_style={},
            quirks=[],
            dialogue_markers=[],
            confidence=0.0,
            sample_count=0,
        )

    avg_sl = _avg_sentence_length(lines)
    cr = _contraction_rate(lines)

    return VoiceAnalysis(
        sentence_length=_classify_sentence_length(avg_sl),
        vocabulary_level=_classify_vocabulary(lines),
        tone=_classify_tone(cr, avg_sl),
        punctuation_style=_punctuation_usage(lines),
        quirks=_detect_quirks(lines, cr),
        dialogue_markers=_detect_markers(lines),
        confidence=_confidence(sample_count),
        sample_count=sample_count,
    )


def _merge_field(existing: str, learned: str, locked: bool) -> str:
    if locked or existing == learned:
        return existing
    return learned


def _merge_list(
    existing: list[str],
    learned: list[str],
    locked: bool,
) -> list[str]:
    if locked:
        return existing
    seen: set[str] = set()
    merged: list[str] = []
    for item in existing + learned:
        if item not in seen:
            seen.add(item)
            merged.append(item)
    return merged


def _merge_punctuation(
    existing: dict,
    learned: dict[str, float],
    locked: bool,
) -> dict:
    if locked or not learned:
        return existing
    merged = dict(existing)
    for k, v in learned.items():
        if k in merged:
            merged[k] = round(
                merged[k] * _EXISTING_WEIGHT + v * _LEARNED_WEIGHT, 3,
            )
        else:
            merged[k] = v
    return merged


def learn_voice_profile(
    db,
    character_id: int,
    segments: list[DialogueSegment],
    *,
    user_locked: tuple[str, ...] = (),
) -> VoiceAnalysis:
    """Analyze dialogue and merge inferred traits into the stored profile.

    *user_locked* names fields the user has explicitly set — these are
    never overwritten by inference (e.g. ``("tone", "vocabulary_level")``).

    Creates a new profile if one doesn't exist yet.
    """
    analysis = analyze_voice(segments, character_id)

    if analysis.confidence == 0.0:
        return analysis

    existing = db.get_voice_profile_data(character_id)

    if existing is None:
        db.create_voice_profile(
            character_id,
            tone=analysis.tone,
            sentence_length=analysis.sentence_length,
            vocabulary_level=analysis.vocabulary_level,
            quirks=analysis.quirks,
            punctuation_style=analysis.punctuation_style,
            dialogue_markers=analysis.dialogue_markers,
        )
        return analysis

    db.update_voice_profile(
        character_id,
        tone=_merge_field(
            existing["tone"], analysis.tone, "tone" in user_locked,
        ),
        sentence_length=_merge_field(
            existing["sentence_length"],
            analysis.sentence_length,
            "sentence_length" in user_locked,
        ),
        vocabulary_level=_merge_field(
            existing["vocabulary_level"],
            analysis.vocabulary_level,
            "vocabulary_level" in user_locked,
        ),
        quirks=_merge_list(
            existing["quirks"], analysis.quirks, "quirks" in user_locked,
        ),
        punctuation_style=_merge_punctuation(
            existing["punctuation_style"],
            analysis.punctuation_style,
            "punctuation_style" in user_locked,
        ),
        dialogue_markers=_merge_list(
            existing["dialogue_markers"],
            analysis.dialogue_markers,
            "dialogue_markers" in user_locked,
        ),
    )
    return analysis
