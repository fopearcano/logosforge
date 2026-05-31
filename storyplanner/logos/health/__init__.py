"""Logos Narrative Health Engine (Phase 6).

Turns Logos PSYKE diagnostics into an explainable, project-level health report:
per-category status (Stable / Needs Attention / Weak Area / Critical Risk / Not
Enough Data), top risks, strengths, and prioritized recommendations that link to
existing Logos actions. Rule-based, evidence-driven, no fake scores, no
background LLM, no DB mutation. Does not touch the Assistant.
"""

from storyplanner.logos.health.engine import HealthEngine
from storyplanner.logos.health.health_context import top_risks_text
from storyplanner.logos.health.metric import (
    ALL_CATEGORIES,
    STATUS_CRITICAL,
    STATUS_STABLE,
    STATUS_UNKNOWN,
    STATUS_WATCH,
    STATUS_WEAK,
    NarrativeHealthMetric,
    category_name,
)
from storyplanner.logos.health.report import (
    HealthRecommendation,
    NarrativeHealthReport,
)

__all__ = [
    "HealthEngine",
    "NarrativeHealthReport",
    "NarrativeHealthMetric",
    "HealthRecommendation",
    "top_risks_text",
    "category_name",
    "ALL_CATEGORIES",
    "STATUS_UNKNOWN",
    "STATUS_STABLE",
    "STATUS_WATCH",
    "STATUS_WEAK",
    "STATUS_CRITICAL",
]
