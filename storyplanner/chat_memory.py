"""Chat memory and personality helpers for the project Chat section.

Pure-logic module — no Qt, no DB session management. The Database layer
calls these helpers to summarize old messages, build personality
prompts, and parse structured action proposals from LLM output.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass

from storyplanner.models.models import CHAT_PERSONALITIES


# ---------------------------------------------------------------------------
# Personality presets
# ---------------------------------------------------------------------------

_PERSONALITY_PROMPTS: dict[str, str] = {
    "default": (
        "You are a thoughtful writing collaborator for the user's story "
        "project. Be concise, specific, and grounded in the project's "
        "details when answering."
    ),
    "mentor": (
        "You are a patient, encouraging mentor. Ask clarifying questions, "
        "offer gentle redirects, and help the user think through choices "
        "rather than handing them solutions."
    ),
    "skeptic": (
        "You are a sharp skeptic. Push back on weak premises, name "
        "logical gaps, and never agree just to be agreeable. Be polite "
        "but unflinching."
    ),
    "editor": (
        "You are a senior fiction editor. Focus on clarity, pacing, "
        "characterization, and continuity. Be specific — quote lines "
        "and suggest concrete revisions."
    ),
    "brutal": (
        "You are a brutally honest critic. No flattery, no padding. "
        "If something doesn't work, say so plainly and explain why. "
        "If it does, say that briefly too."
    ),
    "whimsical": (
        "You are a playful, whimsical co-writer. Lean into metaphor, "
        "wordplay, and unexpected angles. Stay useful, but never dull."
    ),
    "minimalist": (
        "You are a minimalist. Use the fewest words that fully answer. "
        "Prefer lists and short sentences. Skip pleasantries."
    ),
    "philosopher": (
        "You are a literary philosopher. Treat narrative choices as "
        "questions about meaning. Connect specifics to broader themes "
        "without losing the concrete detail."
    ),
}


def personality_prompt(name: str) -> str:
    """Return the system-prompt fragment for a personality preset."""
    return _PERSONALITY_PROMPTS.get(name, _PERSONALITY_PROMPTS["default"])


def is_valid_personality(name: str) -> bool:
    return name in CHAT_PERSONALITIES


# ---------------------------------------------------------------------------
# Memory window + summarization
# ---------------------------------------------------------------------------

# Most recent N messages always sent verbatim.
RECENT_WINDOW = 12

# Once unsummarized count exceeds this, fold the older ones into the summary.
SUMMARIZE_THRESHOLD = 20


@dataclass(slots=True)
class MemoryFrame:
    """What gets sent to the LLM: a summary plus recent verbatim messages."""

    summary: str
    recent: list[dict]  # [{"role": ..., "content": ...}, ...]


def _to_role_dict(msg) -> dict:
    return {"role": msg.role, "content": msg.content}


def build_memory_frame(
    all_messages: list,
    summary_text: str,
    last_summarized_id: int,
) -> MemoryFrame:
    """Slice messages into (summary, recent) for the next LLM call.

    *all_messages* are in chronological order. The recent window is
    the last RECENT_WINDOW messages regardless of summary state — the
    summary covers everything older.
    """
    if not all_messages:
        return MemoryFrame(summary=summary_text, recent=[])
    recent = all_messages[-RECENT_WINDOW:]
    return MemoryFrame(
        summary=summary_text,
        recent=[_to_role_dict(m) for m in recent],
    )


def needs_summary_update(
    all_messages: list, last_summarized_id: int,
) -> bool:
    """True when there are enough older-than-recent messages to fold in."""
    if len(all_messages) <= RECENT_WINDOW:
        return False
    older = all_messages[:-RECENT_WINDOW]
    unsummarized = [m for m in older if m.id and m.id > last_summarized_id]
    return len(unsummarized) >= (SUMMARIZE_THRESHOLD - RECENT_WINDOW)


def heuristic_summary(
    previous_summary: str, new_messages: list,
) -> tuple[str, int]:
    """Append a terse heuristic summary line for *new_messages*.

    Returns (new_summary_text, last_message_id). This avoids a second
    LLM call — the summary just lists the topics covered. If the LLM
    is wired in later, replace this function's body; the caller
    contract stays the same.
    """
    if not new_messages:
        return previous_summary, 0
    bullets: list[str] = []
    for m in new_messages:
        text = m.content.strip().replace("\n", " ")
        if len(text) > 120:
            text = text[:117] + "..."
        bullets.append(f"- [{m.role}] {text}")
    new_block = "\n".join(bullets)
    if previous_summary:
        combined = previous_summary.rstrip() + "\n" + new_block
    else:
        combined = "Earlier conversation:\n" + new_block
    return combined, new_messages[-1].id or 0


# ---------------------------------------------------------------------------
# Action proposal parsing
# ---------------------------------------------------------------------------

_ACTION_TAG_RE = re.compile(
    r"<action>\s*(\{.*?\})\s*</action>", re.DOTALL,
)
_ACTION_FENCE_RE = re.compile(
    r"```(?:json)?\s*(\{[^`]*?\"action\"[^`]*?\})\s*```", re.DOTALL,
)


@dataclass(slots=True)
class ActionProposal:
    """A structured action the assistant has proposed but not executed."""

    action: str
    args: dict
    label: str
    raw: str  # the original tag/fence so we can strip it from the visible text


def parse_action_proposals(text: str) -> list[ActionProposal]:
    """Extract any ``<action>{...}</action>`` blocks from the LLM reply.

    Falls back to a JSON code fence containing an ``"action"`` key when
    the explicit tag isn't used. Invalid JSON is silently ignored — the
    text still renders, just without an action card.
    """
    proposals: list[ActionProposal] = []
    seen_raws: set[str] = set()

    for match in _ACTION_TAG_RE.finditer(text):
        raw = match.group(0)
        if raw in seen_raws:
            continue
        seen_raws.add(raw)
        payload = match.group(1)
        try:
            data = json.loads(payload)
        except (json.JSONDecodeError, TypeError):
            continue
        proposal = _proposal_from_dict(data, raw)
        if proposal is not None:
            proposals.append(proposal)

    if not proposals:
        for match in _ACTION_FENCE_RE.finditer(text):
            raw = match.group(0)
            if raw in seen_raws:
                continue
            seen_raws.add(raw)
            payload = match.group(1)
            try:
                data = json.loads(payload)
            except (json.JSONDecodeError, TypeError):
                continue
            proposal = _proposal_from_dict(data, raw)
            if proposal is not None:
                proposals.append(proposal)

    return proposals


def _proposal_from_dict(data: dict, raw: str) -> ActionProposal | None:
    action = data.get("action")
    if not isinstance(action, str) or not action:
        return None
    args = data.get("args", {})
    if not isinstance(args, dict):
        args = {}
    label = data.get("label") or _humanize_action(action)
    return ActionProposal(action=action, args=args, label=label, raw=raw)


def _humanize_action(name: str) -> str:
    return name.replace("_", " ").strip().capitalize()


def strip_action_blocks(text: str) -> str:
    """Remove action tags/fences so the visible reply doesn't show JSON."""
    cleaned = _ACTION_TAG_RE.sub("", text)
    cleaned = _ACTION_FENCE_RE.sub("", cleaned)
    return cleaned.strip()


# ---------------------------------------------------------------------------
# System prompt assembly
# ---------------------------------------------------------------------------

_ACTIONS_HINT = (
    "When you want to perform a project change (create a scene, "
    "create a PSYKE entry, add a note, etc.), do NOT execute it "
    "yourself. Instead, propose it as a structured action the user "
    "can accept or decline. Format proposals as:\n"
    "<action>{\"action\": \"<name>\", \"args\": {...}, "
    "\"label\": \"<short label>\"}</action>\n"
    "Available write actions: create_scene, create_psyke_entry, "
    "create_note, update_scene_title.\n"
    "Never produce destructive proposals (delete_*). The user must "
    "always confirm before any change is made."
)


def build_system_prompt(personality: str, project_context: str) -> str:
    """Assemble the system message: personality + context + action rules."""
    parts = [personality_prompt(personality)]
    if project_context.strip():
        parts.append("Project context:\n" + project_context.strip())
    parts.append(_ACTIONS_HINT)
    return "\n\n".join(parts)
