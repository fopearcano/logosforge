"""Relativity Engine — reframe a scene from a different POV.

Each character is a "reference frame". The same event reads as betrayal
from one frame, mercy from another. The engine re-prompts the LLM with
the chosen frame as anchor.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from storyplanner.assistant import chat_completion
from storyplanner.providers import ProviderConfig
from storyplanner.quantum_outliner.psyke_adapter import find_entry_by_name
from storyplanner.settings import get_manager as get_settings

if TYPE_CHECKING:
    from storyplanner.db import Database

logger = logging.getLogger(__name__)

_NEUTRAL_POV = "neutral"
_TIMEOUT = 60

_SYSTEM_PROMPT = (
    "You are QUANTUM, applying narrative relativity. Each character is a "
    "reference frame; meaning depends on perspective.\n\n"
    "Given a scene and a chosen perspective, return how the scene reads "
    "from that frame. Be brief and direct.\n\n"
    "Format your response as:\n"
    "PERSPECTIVE: <name>\n"
    "MEANING: <how the events read to this character — 2-3 sentences>\n"
    "STAKES: <what is at risk for this character>\n"
    "SHIFT: <what changes vs. the neutral reading — one sentence>"
)


def _build_provider() -> ProviderConfig:
    settings = get_settings()
    return ProviderConfig(
        name=str(settings.get("ai_provider") or "LM Studio"),
        base_url=str(settings.get("ai_base_url") or "http://localhost:1234/v1"),
        model=str(settings.get("ai_model") or ""),
        api_key=str(settings.get("ai_api_key") or ""),
    )


def reframe_scene(
    scene_text: str,
    pov: str,
    db: "Database | None" = None,
    project_id: int | None = None,
) -> str:
    """Return the scene's reading from a chosen POV.

    `pov` can be a character name, "protagonist"/"antagonist", or "neutral".
    Returns a textual reframing. Returns an offline note if LLM is unreachable.
    """
    if not scene_text.strip():
        return "(no scene text to reframe)"

    pov = (pov or _NEUTRAL_POV).strip()
    pov_brief = ""
    if db is not None and project_id is not None and pov.lower() not in (
        _NEUTRAL_POV, "protagonist", "antagonist",
    ):
        entry = find_entry_by_name(db, project_id, pov)
        if entry and entry.notes:
            pov_brief = f"Background on {pov}: {entry.notes.strip()[:400]}"

    user_parts = [f"SCENE:\n{scene_text.strip()}"]
    if pov_brief:
        user_parts.append(pov_brief)
    user_parts.append(f"Reframe from this perspective: {pov}")

    messages = [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user", "content": "\n\n".join(user_parts)},
    ]

    try:
        response, _cached = chat_completion(
            messages, provider=_build_provider(), timeout=_TIMEOUT, use_cache=True,
        )
        return response.strip() or _stub_reframe(pov)
    except (ConnectionError, RuntimeError, OSError) as exc:
        logger.debug("Relativity LLM unavailable: %s", exc)
        return _stub_reframe(pov)


def _stub_reframe(pov: str) -> str:
    return (
        f"PERSPECTIVE: {pov}\n"
        "MEANING: (LLM unavailable — connect a model to reframe.)\n"
        "STAKES: unknown\n"
        "SHIFT: cannot compute offline"
    )
