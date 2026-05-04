"""LLM branch evaluator — brief critique-to-score via chat completion.

Returns factor scores (0–1) for each of the five scoring objectives.
Falls back to None on any LLM or parse failure so the caller can use
heuristic-only scoring.
"""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING

from storyplanner.assistant import chat_completion
from storyplanner.providers import ProviderConfig
from storyplanner.settings import get_manager as get_settings

if TYPE_CHECKING:
    from storyplanner.quantum_outliner.state import Branch

logger = logging.getLogger(__name__)

_TIMEOUT = 30

_SYSTEM_PROMPT = (
    "You evaluate narrative branches. Score each factor 0.0–1.0.\n"
    "Return ONLY JSON, no markdown, no explanation.\n"
    '{"structure_fit":0.0,"psyke_consistency":0.0,'
    '"tension_gain":0.0,"novelty":0.0,"goal_alignment":0.0}'
)

_FACTOR_KEYS = frozenset({
    "structure_fit", "psyke_consistency", "tension_gain",
    "novelty", "goal_alignment",
})


def _build_provider() -> ProviderConfig:
    settings = get_settings()
    return ProviderConfig(
        name=str(settings.get("ai_provider") or "LM Studio"),
        base_url=str(settings.get("ai_base_url") or "http://localhost:1234/v1"),
        model=str(settings.get("ai_model") or ""),
        api_key=str(settings.get("ai_api_key") or ""),
    )


def _format_branch_prompt(branch: "Branch", context: str) -> str:
    parts = []
    if context:
        parts.append(f"Context: {context}")
    parts.append(f"Title: {branch.title}")
    parts.append(f"Description: {branch.description}")
    if branch.stakes:
        parts.append(f"Stakes: {branch.stakes}")
    if branch.consequence:
        parts.append(f"Consequence: {branch.consequence}")
    return "\n".join(parts)


def _parse_factors(response: str) -> dict[str, float] | None:
    text = response.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[-1]
        if text.endswith("```"):
            text = text[:-3].strip()

    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        logger.debug("LLM evaluator returned invalid JSON: %s", text[:200])
        return None

    if not isinstance(data, dict):
        return None

    factors: dict[str, float] = {}
    for key in _FACTOR_KEYS:
        val = data.get(key)
        if val is None:
            return None
        try:
            f = float(val)
        except (TypeError, ValueError):
            return None
        factors[key] = max(0.0, min(f, 1.0))
    return factors


def score_with_llm(
    branch: "Branch",
    context: str = "",
    *,
    provider: ProviderConfig | None = None,
) -> dict[str, float] | None:
    """Call LLM to score a single branch. Returns None on any failure."""
    prov = provider or _build_provider()
    user_msg = _format_branch_prompt(branch, context)
    messages = [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user", "content": user_msg},
    ]
    try:
        response, _ = chat_completion(
            messages, provider=prov, timeout=_TIMEOUT, use_cache=True,
        )
    except Exception:
        logger.debug("LLM evaluator call failed for branch %s", branch.id)
        return None
    return _parse_factors(response)


def evaluate_branches(
    branches: list["Branch"],
    context: str = "",
    *,
    provider: ProviderConfig | None = None,
) -> dict[str, dict[str, float]]:
    """Score multiple branches via LLM. Returns {branch_id: factors} for successes only."""
    prov = provider or _build_provider()
    results: dict[str, dict[str, float]] = {}
    for b in branches:
        factors = score_with_llm(b, context, provider=prov)
        if factors is not None:
            results[b.id] = factors
    return results
