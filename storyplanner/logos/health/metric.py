"""NarrativeHealthMetric — one explainable health reading for a category.

A metric is always evidence-based: its status is derived from the diagnostics
that fed it. When a category has no analyzable data the status is ``unknown``
(never a false negative). No fake percentages — confidence is the max diagnostic
confidence behind the metric, shown only as supporting detail.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any

# -- Categories (12) ---------------------------------------------------------
CAT_STRUCTURE = "structure"
CAT_CHARACTER = "character"
CAT_RELATIONSHIP = "relationship"
CAT_THEME = "theme"
CAT_CONTINUITY = "continuity"
CAT_TIMELINE = "timeline"
CAT_PACING = "pacing"
CAT_SCENE_PURPOSE = "scene_purpose"
CAT_SETUP_PAYOFF = "setup_payoff"
CAT_PSYKE = "psyke"
CAT_GRAPH = "graph"
CAT_NOTES = "notes"

ALL_CATEGORIES = (
    CAT_STRUCTURE, CAT_CHARACTER, CAT_RELATIONSHIP, CAT_THEME, CAT_CONTINUITY,
    CAT_TIMELINE, CAT_PACING, CAT_SCENE_PURPOSE, CAT_SETUP_PAYOFF, CAT_PSYKE,
    CAT_GRAPH, CAT_NOTES,
)

_CATEGORY_NAMES = {
    CAT_STRUCTURE: "Structure",
    CAT_CHARACTER: "Character",
    CAT_RELATIONSHIP: "Relationships",
    CAT_THEME: "Theme / Motif",
    CAT_CONTINUITY: "Continuity",
    CAT_TIMELINE: "Timeline",
    CAT_PACING: "Pacing",
    CAT_SCENE_PURPOSE: "Scene Purpose",
    CAT_SETUP_PAYOFF: "Setup / Payoff",
    CAT_PSYKE: "PSYKE Completeness",
    CAT_GRAPH: "Graph Connectivity",
    CAT_NOTES: "Notes Integration",
}

# -- Status ------------------------------------------------------------------
STATUS_UNKNOWN = "unknown"
STATUS_STABLE = "stable"
STATUS_WATCH = "watch"
STATUS_WEAK = "weak"
STATUS_CRITICAL = "critical"

# Worse statuses rank higher.
STATUS_RANK = {
    STATUS_UNKNOWN: -1,
    STATUS_STABLE: 0,
    STATUS_WATCH: 1,
    STATUS_WEAK: 2,
    STATUS_CRITICAL: 3,
}

# User-facing wording (no fake percentages).
STATUS_LABEL = {
    STATUS_UNKNOWN: "Not Enough Data",
    STATUS_STABLE: "Stable",
    STATUS_WATCH: "Needs Attention",
    STATUS_WEAK: "Weak Area",
    STATUS_CRITICAL: "Critical Risk",
}


def category_name(category: str) -> str:
    return _CATEGORY_NAMES.get(category, category.title())


@dataclass
class NarrativeHealthMetric:
    category: str
    status: str = STATUS_UNKNOWN
    name: str = ""
    confidence: float = 0.0
    evidence: str = ""
    related_diagnostics: list[str] = field(default_factory=list)
    target_type: str = ""
    target_id: str = ""
    suggested_actions: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.name:
            self.name = category_name(self.category)

    @property
    def id(self) -> str:
        raw = f"{self.category}:{self.status}:{self.evidence}"
        return "m_" + hashlib.sha1(raw.encode("utf-8")).hexdigest()[:12]

    @property
    def status_label(self) -> str:
        return STATUS_LABEL.get(self.status, self.status)

    @property
    def status_rank(self) -> int:
        return STATUS_RANK.get(self.status, -1)

    @property
    def is_known(self) -> bool:
        return self.status != STATUS_UNKNOWN

    @property
    def is_problem(self) -> bool:
        return self.status in (STATUS_WEAK, STATUS_CRITICAL)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "category": self.category,
            "name": self.name,
            "status": self.status,
            "status_label": self.status_label,
            "confidence": self.confidence,
            "evidence": self.evidence,
            "related_diagnostics": list(self.related_diagnostics),
            "target_type": self.target_type,
            "target_id": self.target_id,
            "suggested_actions": list(self.suggested_actions),
        }
