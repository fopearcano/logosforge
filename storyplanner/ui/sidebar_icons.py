"""Centralized left-panel icon map (flat / terminal / minimal-cyber style).

The sidebar renders each item's icon as a leading glyph inside the button text,
so the icon inherits the button's QSS ``color`` automatically — muted gray when
idle, off-white on hover, and the accent (``SIDEBAR_ACTIVE_TEXT``) when the
section is active. That only works for **monochrome text-presentation** glyphs;
colorful emoji render in their own colors and ignore the theme.

This module replaces the previous scattered colorful-emoji strings with a single
consistent monochrome set: geometric shapes, technical symbols, a terminal
prompt and a lambda — flat, dark-mode friendly, no gradients/3D/texture/emoji.

Where a glyph has an emoji presentation by default, U+FE0E (VARIATION SELECTOR-15)
is appended to force the flat text rendering. For glyphs that are already
text-default it is a harmless no-op, so the set renders consistently across the
Dark / Green / Warm themes without any per-theme work.
"""

from __future__ import annotations

_VS15 = "︎"  # force text (monochrome) presentation

# name -> monochrome glyph. Kept visually consistent (single-cell, similar weight).
SIDEBAR_ICONS: dict[str, str] = {
    "Projects": "▦",          # ▦  orthogonal-fill square (project grid)
    "Dashboard": "▤",         # ▤  horizontal-fill square (dashboard rows)
    "Notes": "✎" + _VS15,     # ✎  pencil
    "Manuscript": "≡",        # ≡  three lines (prose)
    "Outline": "☰" + _VS15,   # ☰  trigram (hierarchy)
    "Scenes": "▣",            # ▣  square with centre (frame)
    "Timeline": "◷",          # ◷  clock-quadrant circle
    "Plot": "⊠",              # ⊠  squared times (plot grid)
    "Structure": "▥",         # ▥  vertical-fill square (blocks)
    "Acts": "▷" + _VS15,      # ▷  play / act
    "Beats": "⋮",             # ⋮  vertical ellipsis (beat list)
    "Tags": "⌗",              # ⌗  viewdata / hash
    "Graph": "⌬",             # ⌬  benzene ring (node graph)
    "Arcs": "⌒",              # ⌒  arc
    "PSYKE": "◉",             # ◉  fisheye (mind/eye)
    "Grid": "⊞",              # ⊞  squared plus
    "Health": "✚" + _VS15,    # ✚  heavy cross
    "Balance": "⚖" + _VS15,   # ⚖  scales
    "Pacing": "♪",            # ♪  eighth note (rhythm)
    "Adapt": "⟳",             # ⟳  clockwise arrow (transform)
    "Narrative": "¶",         # ¶  pilcrow (prose flow)
    "Plugins": "⊕",           # ⊕  circled plus (add-on)
    "Assistant": "❯",         # ❯  terminal prompt
    "Logos": "λ",             # λ  lambda (logic / logos)
    "Chat": "✉" + _VS15,      # ✉  envelope (message)
    "Stages": "⊟",            # ⊟  squared minus (layered stage)
    "Pages": "▭",             # ▭  rectangle (page)
    # Footer actions (kept centralized so no emoji strings are scattered).
    "Import": "⇣",            # ⇣  download
    "Export": "⇡",            # ⇡  upload
    "Settings": "⚙" + _VS15,  # ⚙  gear
}


def sidebar_icon(name: str) -> str:
    """Return the monochrome glyph for *name* (empty string if unknown)."""
    return SIDEBAR_ICONS.get(name, "")
