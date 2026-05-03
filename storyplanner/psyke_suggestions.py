"""PSYKE Console suggestion engine — context-aware, mixed results."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from storyplanner.psyke_intents import detect_intent, intent_to_command

if TYPE_CHECKING:
    from storyplanner.db import Database
    from storyplanner.psyke_command_registry import CommandRegistry
    from storyplanner.psyke_search import PsykeSearchIndex

_ENTITY_ACTIONS = ("insert", "open")

_COMMAND_SUBARGS: dict[str, list[str]] = {
    "create": ["character", "place", "object", "lore", "theme"],
    "open": ["scene", "psyke"],
    "go": ["scene next", "scene previous"],
    "ai": ["rewrite", "expand", "summarize", "dialogue", "tension", "pacing"],
}


@dataclass(frozen=True)
class Suggestion:
    text: str
    description: str
    icon: str
    category: str
    score: float
    entry_id: int = 0


def suggest(
    query: str,
    search_index: PsykeSearchIndex,
    registry: CommandRegistry | None = None,
    scene_entry_ids: set[int] | None = None,
    max_results: int = 8,
) -> list[Suggestion]:
    query = query.strip()
    if not query:
        return []

    if query.startswith("/"):
        return _suggest_command(
            query[1:], search_index, registry, scene_entry_ids, max_results,
        )

    return _suggest_search(query, search_index, scene_entry_ids, max_results)


def _suggest_search(
    query: str,
    search_index: PsykeSearchIndex,
    scene_entry_ids: set[int] | None,
    max_results: int,
) -> list[Suggestion]:
    suggestions: list[Suggestion] = []

    intent = detect_intent(query)
    if intent is not None:
        cmd_str = intent_to_command(intent)
        if cmd_str is not None:
            suggestions.append(Suggestion(
                text=cmd_str,
                description=f"Run: {query}",
                icon="⚡",
                category="intent",
                score=1.0 + intent.confidence,
                entry_id=0,
            ))

    results = search_index.search(query, max_results=max_results + 4)
    for r in results:
        boost = 0.05 if (scene_entry_ids and r.entry_id in scene_entry_ids) else 0.0
        icon = _type_icon(r.entry_type)
        suggestions.append(Suggestion(
            text=r.name,
            description=r.entry_type,
            icon=icon,
            category="entity",
            score=r.score + boost,
            entry_id=r.entry_id,
        ))

    suggestions.sort(key=lambda s: s.score, reverse=True)
    return suggestions[:max_results]


def _suggest_command(
    body: str,
    search_index: PsykeSearchIndex,
    registry: CommandRegistry | None,
    scene_entry_ids: set[int] | None,
    max_results: int,
) -> list[Suggestion]:
    if not body:
        return _list_all_commands(registry, max_results)

    parts = body.split(None, 1)
    head = parts[0].lower()
    tail = parts[1].strip() if len(parts) > 1 else ""

    suggestions: list[Suggestion] = []

    if not tail:
        suggestions.extend(_match_commands(head, registry))
        suggestions.extend(_match_entities_with_actions(head, search_index, scene_entry_ids))
    else:
        suggestions.extend(_match_subargs(head, tail, registry))
        suggestions.extend(_match_entity_action(head, tail, search_index, scene_entry_ids))

    suggestions.sort(key=lambda s: s.score, reverse=True)
    return suggestions[:max_results]


def _list_all_commands(registry: CommandRegistry | None, max_results: int) -> list[Suggestion]:
    results: list[Suggestion] = []
    if registry:
        for entry in registry.all_commands():
            results.append(Suggestion(
                text=f"/{entry.name}",
                description=entry.description,
                icon="⌘",
                category="command",
                score=0.5,
            ))
    results.sort(key=lambda s: s.text)
    return results[:max_results]


def _match_commands(prefix: str, registry: CommandRegistry | None) -> list[Suggestion]:
    results: list[Suggestion] = []
    if not registry:
        return results
    for entry in registry.all_commands():
        name = entry.name
        if name == prefix:
            for sub in _COMMAND_SUBARGS.get(name, []):
                results.append(Suggestion(
                    text=f"/{name} {sub}",
                    description=entry.description,
                    icon="⌘",
                    category="command",
                    score=0.95,
                ))
            if not results:
                results.append(Suggestion(
                    text=f"/{name}",
                    description=entry.description,
                    icon="⌘",
                    category="command",
                    score=0.95,
                ))
        elif name.startswith(prefix):
            results.append(Suggestion(
                text=f"/{name}",
                description=entry.description,
                icon="⌘",
                category="command",
                score=0.8 + 0.1 * (len(prefix) / len(name)),
            ))
        for alias in entry.aliases:
            alias_lower = alias.lower()
            if alias_lower.startswith(prefix) and alias_lower != prefix:
                results.append(Suggestion(
                    text=f"/{alias_lower}",
                    description=f"alias for /{name}",
                    icon="⌘",
                    category="command",
                    score=0.7 + 0.1 * (len(prefix) / len(alias_lower)),
                ))
    return results


def _match_subargs(
    command: str,
    tail: str,
    registry: CommandRegistry | None,
) -> list[Suggestion]:
    results: list[Suggestion] = []
    subs = _COMMAND_SUBARGS.get(command, [])
    if not subs:
        return results
    desc = ""
    if registry:
        entry = registry.resolve(command)
        if entry:
            desc = entry.description

    tail_lower = tail.lower()
    for sub in subs:
        if sub.lower().startswith(tail_lower):
            results.append(Suggestion(
                text=f"/{command} {sub}",
                description=desc,
                icon="⌘",
                category="command",
                score=0.9 + 0.05 * (len(tail_lower) / max(len(sub), 1)),
            ))
    return results


def _match_entities_with_actions(
    prefix: str,
    search_index: PsykeSearchIndex,
    scene_entry_ids: set[int] | None,
) -> list[Suggestion]:
    results = search_index.search(prefix, max_results=4)
    suggestions: list[Suggestion] = []
    for r in results:
        if r.score < 0.6:
            continue
        boost = 0.03 if (scene_entry_ids and r.entry_id in scene_entry_ids) else 0.0
        icon = _type_icon(r.entry_type)
        suggestions.append(Suggestion(
            text=f"/{r.name.lower().split()[0]}",
            description=f"{r.name} — insert",
            icon=icon,
            category="entity",
            score=r.score * 0.85 + boost,
            entry_id=r.entry_id,
        ))
        for action in _ENTITY_ACTIONS:
            suggestions.append(Suggestion(
                text=f"/{r.name.lower().split()[0]} {action}",
                description=f"{r.name} — {action}",
                icon=icon,
                category="entity_action",
                score=r.score * 0.80 + boost,
                entry_id=r.entry_id,
            ))
    return suggestions


def _match_entity_action(
    entity_prefix: str,
    action_prefix: str,
    search_index: PsykeSearchIndex,
    scene_entry_ids: set[int] | None,
) -> list[Suggestion]:
    results = search_index.search(entity_prefix, max_results=3)
    suggestions: list[Suggestion] = []
    action_lower = action_prefix.lower()
    for r in results:
        if r.score < 0.6:
            continue
        boost = 0.03 if (scene_entry_ids and r.entry_id in scene_entry_ids) else 0.0
        icon = _type_icon(r.entry_type)
        for action in _ENTITY_ACTIONS:
            if action.startswith(action_lower):
                suggestions.append(Suggestion(
                    text=f"/{entity_prefix} {action}",
                    description=f"{r.name} — {action}",
                    icon=icon,
                    category="entity_action",
                    score=r.score * 0.85 + boost,
                    entry_id=r.entry_id,
                ))
    return suggestions


def _type_icon(entry_type: str) -> str:
    return {
        "character": "\U0001F464",
        "place": "\U0001F3DB",
        "object": "\U0001F48E",
        "lore": "\U0001F4DC",
        "theme": "\U0001F3AD",
    }.get(entry_type, "\U0001F4CC")
