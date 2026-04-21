"""Writing format definitions for the Manuscript editor.

Each format defines element types with their styling rules.
The editor uses these to apply format-specific behavior.

Margin values are in pixels, calibrated for a 720 px text area.
720 px ≈ 6.0 in (standard US-letter text width), so 1 in ≈ 120 px.

Screenplay margins follow industry standard (Final Draft / WGA):
  Scene Heading  — full width, bold, ALL CAPS
  Action         — full width
  Character      — 2.2 in left indent (264 px), ALL CAPS
  Dialogue       — 1.0 in left (120 px), 1.5 in right (180 px)
  Parenthetical  — 1.5 in left (180 px), 2.0 in right (240 px)
  Transition     — right-aligned, ALL CAPS
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ElementStyle:
    """Visual and behavioral rules for one element type."""
    name: str
    shortcut: str = ""
    font_size: int = 15
    bold: bool = False
    italic: bool = False
    all_caps: bool = False
    align: str = "left"
    left_margin: int = 0
    right_margin: int = 0
    top_spacing: int = 0
    bottom_spacing: int = 12
    line_height: float = 1.5
    color_key: str = "text"


@dataclass(frozen=True)
class WritingFormat:
    """Complete format definition."""
    name: str
    label: str
    elements: list[ElementStyle] = field(default_factory=list)
    default_element: str = "action"


# ---------------------------------------------------------------------------
# Novel
# Standard prose: generous line height, paragraph spacing, large chapter heads.
# ---------------------------------------------------------------------------
NOVEL = WritingFormat(
    name="novel",
    label="Novel",
    default_element="body",
    elements=[
        ElementStyle(
            name="chapter",
            shortcut="Ctrl+1",
            font_size=26, bold=True,
            top_spacing=48, bottom_spacing=24,
            line_height=1.4,
        ),
        ElementStyle(
            name="scene_break",
            shortcut="Ctrl+2",
            font_size=15, align="center",
            top_spacing=24, bottom_spacing=24,
            line_height=1.0,
        ),
        ElementStyle(
            name="body",
            shortcut="Ctrl+3",
            font_size=18,
            line_height=1.8,
            bottom_spacing=6,
        ),
    ],
)

# ---------------------------------------------------------------------------
# Screenplay  (WGA / Final Draft standard)
#
# All elements use the same font size (industry: Courier 12 pt).
# Differentiation comes from margins, caps, and alignment.
#
# Page text area = 6.0 in  →  720 px at our scale.
#   Scene Heading : left 0,    right 0    — full width
#   Action        : left 0,    right 0    — full width
#   Character     : left 264,  right 0    — 2.2 in indent, left-aligned
#   Dialogue      : left 120,  right 180  — 1.0 in / 1.5 in
#   Parenthetical : left 180,  right 240  — 1.5 in / 2.0 in
#   Transition    : left 0,    right 0    — right-aligned
# ---------------------------------------------------------------------------
SCREENPLAY = WritingFormat(
    name="screenplay",
    label="Screenplay",
    default_element="action",
    elements=[
        ElementStyle(
            name="scene_heading",
            shortcut="Ctrl+1",
            font_size=15, bold=True, all_caps=True,
            top_spacing=24, bottom_spacing=12,
        ),
        ElementStyle(
            name="action",
            shortcut="Ctrl+2",
            font_size=15,
            bottom_spacing=12,
        ),
        ElementStyle(
            name="character",
            shortcut="Ctrl+3",
            font_size=15, all_caps=True,
            left_margin=264,
            top_spacing=12, bottom_spacing=0,
        ),
        ElementStyle(
            name="dialogue",
            shortcut="Ctrl+4",
            font_size=15,
            left_margin=120, right_margin=180,
            bottom_spacing=0,
        ),
        ElementStyle(
            name="parenthetical",
            shortcut="Ctrl+5",
            font_size=15, italic=True,
            left_margin=180, right_margin=240,
            bottom_spacing=0,
        ),
        ElementStyle(
            name="transition",
            shortcut="Ctrl+6",
            font_size=15, all_caps=True, align="right",
            top_spacing=12, bottom_spacing=12,
        ),
    ],
)

# ---------------------------------------------------------------------------
# Graphic Novel  (Dark Horse / DC "full script" style)
#
# Page headers and panel labels are structural.  Dialogue is indented
# under the character name.  Descriptions sit at full width.
# ---------------------------------------------------------------------------
GRAPHIC_NOVEL = WritingFormat(
    name="graphic_novel",
    label="Graphic Novel",
    default_element="panel",
    elements=[
        ElementStyle(
            name="page",
            shortcut="Ctrl+1",
            font_size=15, bold=True, all_caps=True,
            top_spacing=36, bottom_spacing=12,
        ),
        ElementStyle(
            name="panel",
            shortcut="Ctrl+2",
            font_size=15, bold=True,
            top_spacing=20, bottom_spacing=4,
        ),
        ElementStyle(
            name="description",
            shortcut="Ctrl+3",
            font_size=15,
            left_margin=48,
            bottom_spacing=8,
        ),
        ElementStyle(
            name="character",
            shortcut="Ctrl+4",
            font_size=15, all_caps=True, bold=True,
            left_margin=48,
            top_spacing=8, bottom_spacing=0,
        ),
        ElementStyle(
            name="dialogue",
            shortcut="Ctrl+5",
            font_size=15,
            left_margin=96,
            bottom_spacing=8,
        ),
        ElementStyle(
            name="caption",
            shortcut="Ctrl+6",
            font_size=15, italic=True,
            left_margin=48,
            color_key="muted",
            bottom_spacing=8,
        ),
        ElementStyle(
            name="sfx",
            font_size=15, bold=True, all_caps=True,
            left_margin=48,
            bottom_spacing=8,
        ),
    ],
)

# ---------------------------------------------------------------------------
# Stage Script  (Samuel French / standard playwriting format)
#
# Act and scene headings are centered.  Stage directions are in italics
# and bracketed.  Character names centered, dialogue at narrower margins
# than screenplay.
# ---------------------------------------------------------------------------
STAGE_SCRIPT = WritingFormat(
    name="stage_script",
    label="Stage Script",
    default_element="dialogue",
    elements=[
        ElementStyle(
            name="act",
            shortcut="Ctrl+1",
            font_size=18, bold=True, all_caps=True, align="center",
            top_spacing=36, bottom_spacing=18,
        ),
        ElementStyle(
            name="scene",
            shortcut="Ctrl+2",
            font_size=16, bold=True, align="center",
            top_spacing=24, bottom_spacing=12,
        ),
        ElementStyle(
            name="stage_direction",
            shortcut="Ctrl+3",
            font_size=15, italic=True,
            left_margin=60, right_margin=60,
            bottom_spacing=8,
        ),
        ElementStyle(
            name="character",
            shortcut="Ctrl+4",
            font_size=15, all_caps=True, align="center",
            top_spacing=12, bottom_spacing=0,
        ),
        ElementStyle(
            name="dialogue",
            shortcut="Ctrl+5",
            font_size=15,
            left_margin=120, right_margin=60,
            bottom_spacing=8,
        ),
        ElementStyle(
            name="parenthetical",
            shortcut="Ctrl+6",
            font_size=15, italic=True,
            left_margin=168, right_margin=120,
            bottom_spacing=0,
        ),
    ],
)

# ---------------------------------------------------------------------------
# Series  (TV script — single-cam / multi-cam hybrid)
#
# Follows screenplay rules for scene-level elements, adds episode and
# act structural markers.
# ---------------------------------------------------------------------------
SERIES = WritingFormat(
    name="series",
    label="Series",
    default_element="action",
    elements=[
        ElementStyle(
            name="episode",
            shortcut="Ctrl+1",
            font_size=18, bold=True, all_caps=True, align="center",
            top_spacing=48, bottom_spacing=12,
        ),
        ElementStyle(
            name="cold_open",
            font_size=15, bold=True, all_caps=True, align="center",
            top_spacing=24, bottom_spacing=12,
        ),
        ElementStyle(
            name="act_break",
            shortcut="Ctrl+2",
            font_size=15, bold=True, all_caps=True, align="center",
            top_spacing=24, bottom_spacing=18,
        ),
        ElementStyle(
            name="scene_heading",
            shortcut="Ctrl+3",
            font_size=15, bold=True, all_caps=True,
            top_spacing=24, bottom_spacing=12,
        ),
        ElementStyle(
            name="action",
            shortcut="Ctrl+4",
            font_size=15,
            bottom_spacing=12,
        ),
        ElementStyle(
            name="character",
            shortcut="Ctrl+5",
            font_size=15, all_caps=True,
            left_margin=264,
            top_spacing=12, bottom_spacing=0,
        ),
        ElementStyle(
            name="dialogue",
            shortcut="Ctrl+6",
            font_size=15,
            left_margin=120, right_margin=180,
            bottom_spacing=0,
        ),
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
