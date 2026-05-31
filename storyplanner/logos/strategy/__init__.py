"""Logos Strategy Layer (Phase 7) — medium-aware narrative router.

A deterministic decision layer that tells Assistant and Logos which reasoning
should dominate in a given situation, based on project mode, writing format,
plugins (Go McKee, Idea di Controllo), Quantum/Lambda mode, the selected outline
template, the active section, and Narrative Health. It does not create a new AI
backend, never calls an LLM to route, and never mutates project data. It does
not modify the Assistant — it only *informs* it.
"""

from storyplanner.logos.strategy.medium_profiles import (
    MediumProfile,
    all_profiles,
    get_profile,
)
from storyplanner.logos.strategy.registry import (
    MEDIUM_STRATEGY,
    get_strategy,
    list_strategies,
    register,
)
from storyplanner.logos.strategy.router import StrategyRouter
from storyplanner.logos.strategy.strategy import NarrativeStrategy, StrategyDecision
from storyplanner.logos.strategy.strategy_context import gather_strategy_context

__all__ = [
    "StrategyRouter",
    "NarrativeStrategy",
    "StrategyDecision",
    "MediumProfile",
    "get_profile",
    "all_profiles",
    "get_strategy",
    "list_strategies",
    "register",
    "MEDIUM_STRATEGY",
    "gather_strategy_context",
]
