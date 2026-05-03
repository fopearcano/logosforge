"""Possibility Generator — produces 3–5 plausible narrative branches.

Calls the LLM with a strict JSON-output prompt, parses, validates,
and returns Branch objects. Falls back to a stub list if the LLM is
unreachable so the UI never shows "blank".
"""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING

from storyplanner.assistant import chat_completion
from storyplanner.providers import ProviderConfig
from storyplanner.quantum_outliner.psyke_adapter import gather_psyke_brief
from storyplanner.quantum_outliner.state import Branch, StateDelta, Wavefunction
from storyplanner.settings import get_manager as get_settings

if TYPE_CHECKING:
    from storyplanner.db import Database

logger = logging.getLogger(__name__)

_MIN_BRANCHES = 3
_MAX_BRANCHES = 5
_TIMEOUT = 60

_SYSTEM_PROMPT = (
    "You are QUANTUM, a story plotting agent. You see story moments as a "
    "superposition of possible directions, each with distinct stakes and "
    "consequences.\n\n"
    "Return ONLY JSON, no markdown, no explanation. Schema:\n"
    "{\n"
    '  "branches": [\n'
    '    {\n'
    '      "title": "short label (3-6 words)",\n'
    '      "description": "what happens (1-3 sentences)",\n'
    '      "stakes": "what is at risk",\n'
    '      "consequence": "what changes if this path is taken",\n'
    '      "state_delta": {\n'
    '        "character_changes": [{"name": "...", "note": "..."}],\n'
    '        "new_relations": [{"from": "...", "to": "..."}],\n'
    '        "arc_updates": [{"name": "...", "note": "..."}]\n'
    "      }\n"
    "    }\n"
    "  ]\n"
    "}\n\n"
    "Generate 3-5 branches. Each MUST be distinct in trajectory — not "
    "variations of the same outcome. Cover different emotional registers "
    "(conflict, alliance, deception, retreat, escalation)."
)


def _build_provider() -> ProviderConfig:
    settings = get_settings()
    return ProviderConfig(
        name=str(settings.get("ai_provider") or "LM Studio"),
        base_url=str(settings.get("ai_base_url") or "http://localhost:1234/v1"),
        model=str(settings.get("ai_model") or ""),
        api_key=str(settings.get("ai_api_key") or ""),
    )


def generate_possibilities(
    anchor: str,
    db: "Database | None" = None,
    project_id: int | None = None,
    *,
    extra_context: str = "",
    n: int = 4,
) -> Wavefunction:
    """Generate a wavefunction of N branches for a narrative anchor.

    `anchor` is the situation prompt: "Hero meets enemy", "Scene 3 ends".
    PSYKE characters are folded in for grounding when db+project_id given.
    """
    n = max(_MIN_BRANCHES, min(n, _MAX_BRANCHES))

    psyke_brief = ""
    if db is not None and project_id is not None:
        psyke_brief = gather_psyke_brief(db, project_id)

    user_parts = []
    if psyke_brief:
        user_parts.append("Story bible:\n" + psyke_brief)
    if extra_context:
        user_parts.append("Context:\n" + extra_context)
    user_parts.append(f"Anchor situation: {anchor}")
    user_parts.append(f"Generate {n} distinct branches.")

    messages = [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user", "content": "\n\n".join(user_parts)},
    ]

    try:
        response, _cached = chat_completion(
            messages, provider=_build_provider(), timeout=_TIMEOUT, use_cache=True,
        )
        branches = _parse_branches(response)
    except (ConnectionError, RuntimeError, OSError) as exc:
        logger.debug("Possibility LLM unavailable: %s", exc)
        branches = []

    if not branches:
        branches = _stub_branches(anchor, n)

    return Wavefunction.new(anchor=anchor, branches=branches)


def _parse_branches(response: str) -> list[Branch]:
    """Extract Branch list from LLM JSON. Returns [] on any failure."""
    text = response.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[-1]
        if text.endswith("```"):
            text = text[:-3].strip()

    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        logger.debug("Possibility LLM returned invalid JSON: %s", text[:200])
        return []

    raw_branches = data.get("branches") if isinstance(data, dict) else data
    if not isinstance(raw_branches, list):
        return []

    out: list[Branch] = []
    for raw in raw_branches:
        if not isinstance(raw, dict):
            continue
        title = str(raw.get("title", "")).strip()
        description = str(raw.get("description", "")).strip()
        if not title or not description:
            continue
        delta_raw = raw.get("state_delta") or {}
        delta = StateDelta(
            character_changes=_clean_dict_list(delta_raw.get("character_changes")),
            new_relations=_clean_dict_list(delta_raw.get("new_relations")),
            arc_updates=_clean_dict_list(delta_raw.get("arc_updates")),
        )
        out.append(Branch.new(
            title=title,
            description=description,
            stakes=str(raw.get("stakes", "")).strip(),
            consequence=str(raw.get("consequence", "")).strip(),
            state_delta=delta,
        ))
    return out


def _clean_dict_list(value) -> list[dict]:
    if not isinstance(value, list):
        return []
    return [v for v in value if isinstance(v, dict)]


_STUB_TEMPLATES = [
    ("Conflict", "Open hostility breaks out.", "Trust", "A relationship is severed."),
    ("Alliance", "An unexpected agreement forms.", "Independence", "Sides must compromise."),
    ("Deception", "One side conceals their real intent.", "Truth", "A future betrayal seeds itself."),
    ("Retreat", "The confrontation is postponed.", "Momentum", "Pressure builds elsewhere."),
    ("Escalation", "A small spark grows uncontrollably.", "Stability", "The story shifts gears."),
]


def _stub_branches(anchor: str, n: int) -> list[Branch]:
    """Offline fallback so the UI is never empty when LLM is down."""
    return [
        Branch.new(
            title=f"{title} — {anchor[:30]}",
            description=desc,
            stakes=stakes,
            consequence=cons,
        )
        for (title, desc, stakes, cons) in _STUB_TEMPLATES[:n]
    ]
