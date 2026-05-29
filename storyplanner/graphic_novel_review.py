"""Graphic Novel review checks — data-driven visual-storytelling feedback.

When the GraphicNovelEngine is active, these checks evaluate the actual
Sequence/Page/Panel data (not prose heuristics) and surface concrete
notes about page turns, dialogue load, panel flow, visual clutter, motif
recurrence, emotional pacing, and splash-page justification.

Pure core/app logic: no UI / Tauri / filesystem / provider imports.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from storyplanner.graphic_novel_plot import (
    _page_text_load,
    classify_page_pacing,
    get_page_turn_map,
    page_rhythm,
)

# Panels-per-page above this reads as visual clutter.
_CLUTTER_PANELS = 9
# Dialogue refs per panel above this reads as balloon overload.
_BALLOON_OVERLOAD_PER_PANEL = 3


@dataclass
class GraphicNovelCheck:
    """One review finding. page_id is None for project-level checks."""

    check_type: str
    message: str
    severity: str = "info"      # "info" | "warning"
    page_id: int | None = None


def review_graphic_novel(
    db: Any, project_id: int, page_id: int | None = None,
) -> list[GraphicNovelCheck]:
    """Run graphic-novel review checks (§2).

    With *page_id*, runs page-scoped checks only; otherwise runs page
    checks for every page plus project-level checks.
    """
    checks: list[GraphicNovelCheck] = []
    pages = db.get_gn_pages(project_id)
    if not pages:
        return checks

    target_pages = (
        [p for p in pages if p.id == page_id] if page_id is not None else pages
    )
    for page in target_pages:
        checks.extend(_page_checks(db, page))

    if page_id is None:
        checks.extend(_project_checks(db, project_id, pages))
    return checks


def _page_checks(db: Any, page: Any) -> list[GraphicNovelCheck]:
    out: list[GraphicNovelCheck] = []
    panels = db.get_gn_panels_for_page(page.id)
    n = len(panels)

    # Too much dialogue / balloon overload.
    text_load = _page_text_load(db, page.id)
    if n and text_load >= _BALLOON_OVERLOAD_PER_PANEL * n:
        out.append(GraphicNovelCheck(
            "too_much_dialogue",
            f"Page {page.page_number}: heavy dialogue load "
            f"({text_load} balloons across {n} panels) — risk of balloon overload",
            "warning", page.id,
        ))

    # Visual clutter.
    if n > _CLUTTER_PANELS:
        out.append(GraphicNovelCheck(
            "visual_clutter",
            f"Page {page.page_number}: {n} panels — visual clutter risk; "
            "consider fewer, stronger panels",
            "warning", page.id,
        ))

    # Panel flow readable — a panel with no description/action reads unclearly.
    if n:
        empty = sum(
            1 for p in panels
            if not (p.description or "").strip() and not (p.action or "").strip()
        )
        if empty:
            out.append(GraphicNovelCheck(
                "panel_flow",
                f"Page {page.page_number}: {empty} panel(s) lack description/action "
                "— panel flow may be unreadable",
                "warning", page.id,
            ))

    # Splash page justified — a splash should land a beat/reveal/high energy.
    if page.splash_page:
        density = (page.density_level or "").lower()
        justified = (
            (page.reveal_type or "").strip()
            or (page.emotional_beat or "").strip()
            or density in ("dense", "explosive")
        )
        if not justified:
            out.append(GraphicNovelCheck(
                "splash_unjustified",
                f"Page {page.page_number}: splash page with no reveal, beat, or "
                "high energy — is the full-page real estate earned?",
                "warning", page.id,
            ))
    return out


def _project_checks(
    db: Any, project_id: int, pages: list,
) -> list[GraphicNovelCheck]:
    out: list[GraphicNovelCheck] = []

    # Page turn effective? — reveal setups should land on a non-empty page.
    turns = get_page_turn_map(db, project_id)
    if not turns and len(pages) >= 4:
        out.append(GraphicNovelCheck(
            "page_turn_effective",
            "No page-turn reveals set up across the book — page turns "
            "are not being leveraged for tension",
            "warning",
        ))
    for turn in turns:
        reveal_panels = db.get_gn_panels_for_page(turn["reveal_page_id"])
        if not reveal_panels:
            out.append(GraphicNovelCheck(
                "page_turn_effective",
                f"Page {turn['setup_page_number']} sets up a "
                f"'{turn['reveal_type']}' but the reveal page "
                f"{turn['reveal_page_number']} is empty",
                "warning", turn["reveal_page_id"],
            ))

    # Motif recurrence — a motif seen once is decor, not theme.
    counts: dict[str, int] = {}
    for page in pages:
        seen: set[str] = set()
        for panel in db.get_gn_panels_for_page(page.id):
            for m in db.csv_split(panel.visual_motifs):
                seen.add(m)
        for m in seen:
            counts[m] = counts.get(m, 0) + 1
    for motif, c in counts.items():
        if c == 1:
            out.append(GraphicNovelCheck(
                "motif_recurrence",
                f"Motif '{motif}' appears once — introduced but never recurs",
                "info",
            ))

    # Emotional pacing balanced — flag a monotonous rhythm across the book.
    rhythms = {page_rhythm(p.density_level) for p in pages if (p.density_level or "")}
    if len(pages) >= 4 and len(rhythms) <= 1:
        out.append(GraphicNovelCheck(
            "emotional_pacing",
            "Emotional pacing is monotonous — every page shares the same "
            "rhythm; vary density to breathe",
            "warning",
        ))
    return out
