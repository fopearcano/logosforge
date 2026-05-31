"""Higher-level continuity issue detectors (Phase 10Q).

Production-continuity (screenplay), character state-drift / unresolved arcs, and
scenes missing PSYKE links. Deterministic, evidence-backed, capped. Conservative
confidence — uncertain signals are ``possible``.
"""

from __future__ import annotations

from storyplanner.continuity import models as M
from storyplanner.continuity.facts import ProjectFacts

_CAP = 40


def detect_production(pf: ProjectFacts, writing_mode: str,
                      ) -> list[M.ContinuityIssueData]:
    if writing_mode != "screenplay":
        return []
    issues: list[M.ContinuityIssueData] = []
    for scene in pf.scenes:
        slug = (getattr(scene, "slugline", "") or "").strip()
        tod = (getattr(scene, "time_of_day", "") or "").strip()
        ie = (getattr(scene, "interior_exterior", "") or "").strip()
        missing = []
        if not slug:
            missing.append("scene heading/slugline")
        if not ie:
            missing.append("INT/EXT")
        if not tod:
            missing.append("time of day")
        if len(missing) >= 2:
            issues.append(M.ContinuityIssueData(
                issue_type=M.IT_PRODUCTION_RISK, dimension=M.DIM_PRODUCTION,
                severity=M.SEV_WARNING, confidence=M.CONF_LIKELY,
                title=f"'{getattr(scene, 'title', '') or 'A scene'}' is missing "
                      f"production heading data.",
                explanation="Missing: " + ", ".join(missing) + ".",
                suggested_action="Set the slugline / INT-EXT / time of day.",
                evidence=missing,
                related_scene_ids=[getattr(scene, "id", None)]))
        if len(issues) >= _CAP:
            break
    return issues[:_CAP]


def detect_character_drift(pf: ProjectFacts) -> list[M.ContinuityIssueData]:
    issues: list[M.ContinuityIssueData] = []
    total = len(pf.scenes)
    if total < 5:
        return []
    last_third_start = int(total * 0.6)
    for e in pf.entries:
        if (getattr(e, "entry_type", "") or "").lower() != "character":
            continue
        if getattr(e, "is_global", False):
            continue
        idxs = pf.scene_appearances.get(e.id, [])
        if not idxs:
            continue
        name = getattr(e, "name", "") or "Character"
        if len(idxs) == 1:
            issues.append(M.ContinuityIssueData(
                issue_type=M.IT_STATE_DRIFT, dimension=M.DIM_CHARACTER,
                severity=M.SEV_SUGGESTION, confidence=M.CONF_POSSIBLE,
                title=f"'{name}' appears in only one scene.",
                explanation="A defined character with a single appearance may be an "
                            "unresolved arc or stray reference.",
                suggested_action="Develop the arc or confirm the brief appearance.",
                related_scene_ids=[]))
        elif len(idxs) >= 3 and max(idxs) < last_third_start:
            issues.append(M.ContinuityIssueData(
                issue_type=M.IT_STATE_DRIFT, dimension=M.DIM_CHARACTER,
                severity=M.SEV_SUGGESTION, confidence=M.CONF_POSSIBLE,
                title=f"'{name}' disappears before the final act.",
                explanation="A recurring character is absent from the last ~40% of "
                            "the project.",
                suggested_action="Resolve or reintroduce the character's arc.",
                related_scene_ids=[]))
        if len(issues) >= _CAP:
            break
    return issues[:_CAP]


def detect_scenes_missing_psyke(pf: ProjectFacts) -> list[M.ContinuityIssueData]:
    if not pf.entries or len(pf.scenes) < 2:
        return []
    issues: list[M.ContinuityIssueData] = []
    appearing_scene_idx = set()
    for idxs in pf.scene_appearances.values():
        appearing_scene_idx.update(idxs)
    for idx, scene in enumerate(pf.scenes):
        if idx in appearing_scene_idx:
            continue
        if not (getattr(scene, "content", "") or "").strip():
            continue
        issues.append(M.ContinuityIssueData(
            issue_type=M.IT_CONTINUITY_GAP, dimension=M.DIM_CHARACTER,
            severity=M.SEV_INFO, confidence=M.CONF_POSSIBLE,
            title=f"'{getattr(scene, 'title', '') or 'A scene'}' references no "
                  f"tracked PSYKE entries.",
            explanation="No defined character/place/object is mentioned in this "
                        "scene's text.",
            suggested_action="Link PSYKE entries or confirm the scene is standalone.",
            related_scene_ids=[getattr(scene, "id", None)]))
        if len(issues) >= _CAP:
            break
    return issues[:_CAP]
