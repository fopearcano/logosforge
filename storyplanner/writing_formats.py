"""Writing format definitions for the Manuscript editor.

Each format defines element types with their styling rules.
The editor uses these to apply format-specific behavior.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ElementStyle:
    """Visual and behavioral rules for one element type."""
    name: str
    shortcut: str = ""
    font_size: int = 18
    bold: bool = False
    italic: bool = False
    all_caps: bool = False
    align: str = "left"
    left_margin: int = 0
    right_margin: int = 0
    top_spacing: int = 0
    bottom_spacing: int = 12
    line_height: float = 1.6
    color_key: str = "text"


@dataclass(frozen=True)
class WritingFormat:
    """Complete format definition."""
    name: str
    label: str
    elements: list[ElementStyle] = field(default_factory=list)
    default_element: str = "action"


NOVEL = WritingFormat(
    name="novel",
    label="Novel",
    default_element="body",
    elements=[
        ElementStyle(name="chapter", font_size=24, bold=True, top_spacing=40, bottom_spacing=20, shortcut="Ctrl+1"),
        ElementStyle(name="scene_break", font_size=14, align="center", top_spacing=20, bottom_spacing=20, shortcut="Ctrl+2"),
        ElementStyle(name="body", font_size=18, line_height=1.65, bottom_spacing=10, shortcut="Ctrl+3"),
    ],
)

SCREENPLAY = WritingFormat(
    name="screenplay",
    label="Screenplay",
    default_element="action",
    elements=[
        ElementStyle(name="scene_heading", font_size=16, bold=True, all_caps=True, top_spacing=24, bottom_spacing=8, shortcut="Ctrl+1"),
        ElementStyle(name="action", font_size=15, bottom_spacing=12, shortcut="Ctrl+2"),
        ElementStyle(name="character", font_size=15, all_caps=True, align="center", left_margin=160, top_spacing=12, bottom_spacing=0, shortcut="Ctrl+3"),
        ElementStyle(name="dialogue", font_size=15, left_margin=100, right_margin=100, bottom_spacing=0, shortcut="Ctrl+4"),
        ElementStyle(name="parenthetical", font_size=14, italic=True, left_margin=130, right_margin=130, bottom_spacing=0, shortcut="Ctrl+5"),
        ElementStyle(name="transition", font_size=15, all_caps=True, align="right", top_spacing=12, bottom_spacing=12, shortcut="Ctrl+6"),
    ],
)

GRAPHIC_NOVEL = WritingFormat(
    name="graphic_novel",
    label="Graphic Novel",
    default_element="panel",
    elements=[
        ElementStyle(name="page", font_size=16, bold=True, all_caps=True, top_spacing=30, bottom_spacing=12, shortcut="Ctrl+1"),
        ElementStyle(name="panel", font_size=15, bold=True, top_spacing=16, bottom_spacing=4, shortcut="Ctrl+2"),
        ElementStyle(name="description", font_size=15, italic=True, bottom_spacing=8, shortcut="Ctrl+3"),
        ElementStyle(name="character", font_size=15, all_caps=True, bottom_spacing=0, shortcut="Ctrl+4"),
        ElementStyle(name="dialogue", font_size=15, left_margin=40, bottom_spacing=8, shortcut="Ctrl+5"),
        ElementStyle(name="caption", font_size=14, italic=True, left_margin=40, color_key="muted", bottom_spacing=8, shortcut="Ctrl+6"),
        ElementStyle(name="sfx", font_size=16, bold=True, all_caps=True, align="center", bottom_spacing=8),
    ],
)

STAGE_SCRIPT = WritingFormat(
    name="stage_script",
    label="Stage Script",
    default_element="dialogue",
    elements=[
        ElementStyle(name="act", font_size=20, bold=True, all_caps=True, align="center", top_spacing=30, bottom_spacing=16, shortcut="Ctrl+1"),
        ElementStyle(name="scene", font_size=16, bold=True, top_spacing=20, bottom_spacing=8, shortcut="Ctrl+2"),
        ElementStyle(name="stage_direction", font_size=15, italic=True, left_margin=40, bottom_spacing=8, shortcut="Ctrl+3"),
        ElementStyle(name="character", font_size=15, all_caps=True, align="center", top_spacing=12, bottom_spacing=0, shortcut="Ctrl+4"),
        ElementStyle(name="dialogue", font_size=15, left_margin=80, right_margin=40, bottom_spacing=8, shortcut="Ctrl+5"),
        ElementStyle(name="parenthetical", font_size=14, italic=True, left_margin=100, bottom_spacing=0, shortcut="Ctrl+6"),
    ],
)

SERIES = WritingFormat(
    name="series",
    label="Series",
    default_element="action",
    elements=[
        ElementStyle(name="episode", font_size=20, bold=True, all_caps=True, top_spacing=40, bottom_spacing=8, shortcut="Ctrl+1"),
        ElementStyle(name="cold_open", font_size=16, bold=True, all_caps=True, top_spacing=24, bottom_spacing=8),
        ElementStyle(name="act_break", font_size=16, bold=True, all_caps=True, align="center", top_spacing=24, bottom_spacing=16, shortcut="Ctrl+2"),
        ElementStyle(name="scene_heading", font_size=15, bold=True, all_caps=True, top_spacing=20, bottom_spacing=8, shortcut="Ctrl+3"),
        ElementStyle(name="action", font_size=15, bottom_spacing=12, shortcut="Ctrl+4"),
        ElementStyle(name="character", font_size=15, all_caps=True, align="center", left_margin=160, top_spacing=12, bottom_spacing=0, shortcut="Ctrl+5"),
        ElementStyle(name="dialogue", font_size=15, left_margin=100, right_margin=100, bottom_spacing=0, shortcut="Ctrl+6"),
    ],
)

ALL_FORMATS: dict[str, WritingFormat] = {
    "novel": NOVEL,
    "screenplay": SCREENPLAY,
    "graphic_novel": GRAPHIC_NOVEL,
    "stage_script": STAGE_SCRIPT,
    "series": SERIES,
}

FORMAT_ORDER = ["novel", "screenplay", "graphic_novel", "stage_script", "series"]
