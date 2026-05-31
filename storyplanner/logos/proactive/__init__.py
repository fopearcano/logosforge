"""Logos proactive suggestion layer (Phase 4).

A non-intrusive, rule-based engine that *notices* possible narrative issues
while the user works and surfaces lightweight, dismissible suggestions. It never
mutates data, never calls an LLM in the background, and never touches the
Assistant. Acting on a suggestion routes through the existing Logos actions
(preview + confirm).
"""

from storyplanner.logos.proactive.engine import ProactiveConfig, ProactiveEngine
from storyplanner.logos.proactive.suggestion import (
    LogosSuggestion,
    SEVERITY_IMPORTANT,
    SEVERITY_INFO,
    SEVERITY_WARNING,
)
from storyplanner.logos.proactive.suppression import SuppressionStore

__all__ = [
    "ProactiveEngine",
    "ProactiveConfig",
    "LogosSuggestion",
    "SuppressionStore",
    "SEVERITY_INFO",
    "SEVERITY_WARNING",
    "SEVERITY_IMPORTANT",
]
