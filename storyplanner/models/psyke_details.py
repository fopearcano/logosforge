"""PSYKE detail field schemas per entry type."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FieldSpec:
    key: str
    label: str
    widget: str  # "line" | "multiline"
    max_chars: int


_SCHEMAS: dict[str, list[FieldSpec]] = {
    "character": [
        FieldSpec("appearance", "Appearance", "multiline", 400),
        FieldSpec("voice", "Voice", "multiline", 300),
        FieldSpec("goals", "Goals", "multiline", 300),
        FieldSpec("background", "Background", "multiline", 500),
    ],
    "place": [
        FieldSpec("climate", "Climate", "line", 150),
        FieldSpec("politics", "Politics", "multiline", 300),
        FieldSpec("atmosphere", "Atmosphere", "multiline", 300),
    ],
    "object": [
        FieldSpec("appearance", "Appearance", "multiline", 300),
        FieldSpec("properties", "Properties", "multiline", 300),
        FieldSpec("history", "History", "multiline", 300),
    ],
    "lore": [
        FieldSpec("summary", "Summary", "multiline", 500),
        FieldSpec("rules", "Rules", "multiline", 500),
    ],
    "theme": [
        FieldSpec("statement", "Statement", "line", 200),
        FieldSpec("manifestations", "Manifestations", "multiline", 400),
    ],
    "other": [],
}


def get_detail_schema(entry_type: str) -> list[FieldSpec]:
    return _SCHEMAS.get(entry_type, [])
