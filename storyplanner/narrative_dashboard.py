"""Narrative dashboard data engine — computes tension, presence, structure,
and theme-continuity data from scenes and PSYKE entries.

All computation is read-only; nothing is written to the database.
Results are lightweight dataclasses suitable for direct rendering.
"""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass, field

from storyplanner.db import Database

# -- Tension keywords (lower-cased) ------------------------------------------

_TENSION_KEYWORDS: frozenset[str] = frozenset({
    "fight", "fought", "attack", "battle", "war",
    "scream", "screamed", "shout", "yell",
    "betrayal", "betrayed", "lied", "deceived",
    "death", "dead", "killed", "murder", "died",
    "secret", "reveal", "revealed", "truth",
    "danger", "threat", "threatened", "fear", "afraid",
    "escape", "fled", "chase", "pursued",
    "explosion", "crash", "collapsed",
    "blood", "wound", "pain", "agony",
    "anger", "rage", "fury", "furious",
    "desperate", "panic", "terror",
    "confrontation", "conflict", "duel",
    "arrest", "trial", "accused",
    "sacrifice", "loss", "grief",
})

_KEYWORD_RE = re.compile(
    r"\b(" + "|".join(re.escape(k) for k in _TENSION_KEYWORDS) + r")\b",
    re.IGNORECASE,
)


@dataclass
class SceneTension:
    scene_id: int
    scene_order: int
    scene_title: str
    score: float
    char_count: int
    relation_pairs: int
    keyword_hits: int
    progression_count: int


@dataclass
class TensionCurve:
    points: list[SceneTension]
    flags: list[str] = field(default_factory=list)


@dataclass
class CharacterPresence:
    entry_id: int
    name: str
    present_scenes: list[int]
    total_scenes: int
    flags: list[str] = field(default_factory=list)


@dataclass
class ActSegment:
    label: str
    scene_count: int
    word_count: int


@dataclass
class StructureDistribution:
    segments: list[ActSegment]
    total_scenes: int
    total_words: int
    flags: list[str] = field(default_factory=list)


@dataclass
class ThemePresence:
    entry_id: int
    name: str
    present_scenes: list[int]
    total_scenes: int
    flags: list[str] = field(default_factory=list)


@dataclass
class NarrativeDashboardData:
    tension: TensionCurve
    characters: list[CharacterPresence]
    structure: StructureDistribution
    themes: list[ThemePresence]


def compute_dashboard(db: Database, project_id: int) -> NarrativeDashboardData:
    """Compute all dashboard panels in a single pass."""
    scenes = db.get_all_scenes(project_id)
    entries = db.get_all_psyke_entries(project_id)

    char_entries = [e for e in entries if e.entry_type == "character"]
    theme_entries = [e for e in entries if e.entry_type == "theme"]

    term_map: dict[str, int] = {}
    for e in entries:
        if e.name.strip():
            term_map[e.name.lower()] = e.id
        if e.aliases:
            for alias in e.aliases.split(","):
                a = alias.strip().lower()
                if a:
                    term_map[a] = e.id

    char_ids = {e.id for e in char_entries}
    theme_ids = {e.id for e in theme_entries}

    all_relations: set[tuple[int, int]] = set()
    for e in entries:
        for related in db.get_related_psyke_entries(e.id):
            pair = tuple(sorted([e.id, related.id]))
            all_relations.add(pair)

    scene_progressions: dict[int, int] = defaultdict(int)
    for e in entries:
        for prog in db.get_psyke_progressions(e.id):
            if prog.scene_id is not None:
                scene_progressions[prog.scene_id] += 1

    terms_pattern = _build_terms_pattern(list(term_map.keys()))

    scene_entity_presence: dict[int, set[int]] = {}
    for scene in scenes:
        text = (scene.content or "").lower()
        present: set[int] = set()
        if terms_pattern and text:
            for m in terms_pattern.finditer(text):
                eid = term_map.get(m.group().lower())
                if eid is not None:
                    present.add(eid)
        scene_entity_presence[scene.id] = present

    tension = _compute_tension(
        scenes, scene_entity_presence, char_ids,
        all_relations, scene_progressions,
    )

    characters = _compute_character_presence(
        char_entries, scenes, scene_entity_presence,
    )

    structure = _compute_structure(scenes)
    themes = _compute_theme_presence(
        theme_entries, scenes, scene_entity_presence,
    )

    return NarrativeDashboardData(
        tension=tension,
        characters=characters,
        structure=structure,
        themes=themes,
    )


# -- Internal -----------------------------------------------------------------

def _build_terms_pattern(terms: list[str]) -> re.Pattern | None:
    if not terms:
        return None
    escaped = sorted((re.escape(t) for t in terms if t.strip()), key=len, reverse=True)
    if not escaped:
        return None
    return re.compile(r"\b(?:" + "|".join(escaped) + r")\b", re.IGNORECASE)


def _compute_tension(
    scenes,
    presence: dict[int, set[int]],
    char_ids: set[int],
    relations: set[tuple[int, int]],
    progressions: dict[int, int],
) -> TensionCurve:
    points: list[SceneTension] = []
    for scene in scenes:
        present = presence.get(scene.id, set())
        chars_here = present & char_ids
        char_count = len(chars_here)

        char_list = sorted(chars_here)
        rel_pairs = 0
        for i, a in enumerate(char_list):
            for b in char_list[i + 1:]:
                if tuple(sorted([a, b])) in relations:
                    rel_pairs += 1

        text = (scene.content or "").lower()
        keyword_hits = len(_KEYWORD_RE.findall(text))
        prog_count = progressions.get(scene.id, 0)

        score = (
            min(char_count / 4, 1.0) * 25
            + min(rel_pairs / 3, 1.0) * 25
            + min(keyword_hits / 5, 1.0) * 25
            + min(prog_count / 3, 1.0) * 25
        )
        points.append(SceneTension(
            scene_id=scene.id,
            scene_order=scene.sort_order,
            scene_title=scene.title or f"Scene {scene.sort_order}",
            score=round(score, 1),
            char_count=char_count,
            relation_pairs=rel_pairs,
            keyword_hits=keyword_hits,
            progression_count=prog_count,
        ))

    flags: list[str] = []
    if len(points) >= 3:
        for i in range(len(points) - 2):
            window = [points[j].score for j in range(i, i + 3)]
            if max(window) - min(window) <= 5:
                flags.append(
                    f"Flat section: scenes {points[i].scene_order}"
                    f"–{points[i+2].scene_order}"
                )
                break

    for i, p in enumerate(points):
        if i == 0 or i == len(points) - 1:
            continue
        prev_s = points[i - 1].score
        next_s = points[i + 1].score
        if p.score - prev_s > 30 and p.score - next_s > 30:
            flags.append(
                f"Spike at scene {p.scene_order} (score {p.score})"
            )

    if len(points) >= 3:
        third = max(1, len(points) // 3)
        first_avg = sum(p.score for p in points[:third]) / third
        if first_avg < 20:
            flags.append("Weak buildup in first third")

    return TensionCurve(points=points, flags=flags)


def _compute_character_presence(
    char_entries, scenes, presence: dict[int, set[int]],
) -> list[CharacterPresence]:
    total = len(scenes)
    results: list[CharacterPresence] = []
    for entry in char_entries:
        present_in: list[int] = []
        for scene in scenes:
            if entry.id in presence.get(scene.id, set()):
                present_in.append(scene.sort_order)

        flags: list[str] = []
        if total > 0 and present_in:
            ratio = len(present_in) / total
            if ratio > 0.8:
                flags.append("Over-dominant")
            consecutive_absent = _max_consecutive_absent(
                present_in, total,
            )
            if consecutive_absent >= 3:
                flags.append(f"Absent for {consecutive_absent} consecutive scenes")

        results.append(CharacterPresence(
            entry_id=entry.id,
            name=entry.name,
            present_scenes=present_in,
            total_scenes=total,
            flags=flags,
        ))
    return results


def _max_consecutive_absent(present_orders: list[int], total: int) -> int:
    if not present_orders or total == 0:
        return 0
    present_set = set(present_orders)
    max_gap = 0
    current = 0
    for i in range(total):
        if i in present_set:
            current = 0
        else:
            current += 1
            max_gap = max(max_gap, current)
    return max_gap


def _compute_structure(scenes) -> StructureDistribution:
    if not scenes:
        return StructureDistribution(
            segments=[], total_scenes=0, total_words=0,
        )

    act_groups: dict[str, list] = defaultdict(list)
    has_acts = False
    for scene in scenes:
        act = (scene.act or "").strip()
        if act:
            has_acts = True
        label = act or "Unassigned"
        act_groups[label].append(scene)

    if not has_acts:
        n = len(scenes)
        cut1 = max(1, n // 4)
        cut2 = max(cut1 + 1, n - n // 4)
        act_groups = {
            "Act 1 (Setup)": scenes[:cut1],
            "Act 2 (Confrontation)": scenes[cut1:cut2],
            "Act 3 (Resolution)": scenes[cut2:],
        }

    segments: list[ActSegment] = []
    total_words = 0
    for label, group in act_groups.items():
        wc = sum(
            len((s.content or "").split()) for s in group
        )
        total_words += wc
        segments.append(ActSegment(
            label=label,
            scene_count=len(group),
            word_count=wc,
        ))

    flags: list[str] = []
    if len(segments) >= 3:
        word_counts = [seg.word_count for seg in segments]
        if word_counts:
            avg = sum(word_counts) / len(word_counts)
            for seg in segments:
                if avg > 0 and seg.word_count < avg * 0.3:
                    flags.append(f"Weak section: {seg.label}")

    mid_idx = len(segments) // 2
    if len(segments) >= 3:
        mid = segments[mid_idx]
        others_avg = (
            sum(s.word_count for i, s in enumerate(segments) if i != mid_idx)
            / max(1, len(segments) - 1)
        )
        if others_avg > 0 and mid.word_count < others_avg * 0.4:
            flags.append("Weak middle")

    return StructureDistribution(
        segments=segments,
        total_scenes=len(scenes),
        total_words=total_words,
        flags=flags,
    )


def _compute_theme_presence(
    theme_entries, scenes, presence: dict[int, set[int]],
) -> list[ThemePresence]:
    total = len(scenes)
    results: list[ThemePresence] = []
    for entry in theme_entries:
        present_in: list[int] = []
        for scene in scenes:
            if entry.id in presence.get(scene.id, set()):
                present_in.append(scene.sort_order)

        flags: list[str] = []
        if total > 0 and present_in:
            if len(present_in) < total * 0.2:
                flags.append("Underused")
            consecutive_absent = _max_consecutive_absent(present_in, total)
            if consecutive_absent >= 3:
                flags.append(f"Disappears for {consecutive_absent} scenes")

        results.append(ThemePresence(
            entry_id=entry.id,
            name=entry.name,
            present_scenes=present_in,
            total_scenes=total,
            flags=flags,
        ))
    return results
