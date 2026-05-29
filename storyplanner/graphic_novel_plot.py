"""Plot and Timeline behavior for the Graphic Novel Engine.

Deterministic, pure helpers that make Plot and Timeline page/panel-aware:
they turn the Sequence -> Page -> Panel data into plot blocks, a
reading-flow timeline, page-turn (setup/reveal) pairs, and visual-pacing
classification. No UI / Tauri / filesystem / provider imports — the views
consume these.
"""

from __future__ import annotations

from typing import Any


# Visual-pacing indicators (§4).
PACING_INDICATORS: tuple[str, ...] = (
    "quiet",
    "dense",
    "explosive",
    "exposition-heavy",
    "cinematic",
)

# Page-rhythm vocabulary derived from a page's density level.
_DENSITY_TO_RHYTHM: dict[str, str] = {
    "silent": "held",
    "light": "slow",
    "medium": "steady",
    "dense": "fast",
    "explosive": "chaotic",
}

# Density levels treated as "silence" vs "action" for alternation analysis.
_SILENCE_DENSITIES = frozenset({"silent", "light"})
_ACTION_DENSITIES = frozenset({"dense", "explosive"})


# ---------------------------------------------------------------------------
# Pacing classification (§4)
# ---------------------------------------------------------------------------

def _page_text_load(db: Any, page_id: int) -> int:
    """Approximate text load on a page from panel dialogue references."""
    total = 0
    for panel in db.get_gn_panels_for_page(page_id):
        total += len(db.csv_split(panel.dialogue_refs))
    return total


def _page_action_density(db: Any, page_id: int) -> float:
    """Fraction of a page's panels that carry concrete action (0..1)."""
    panels = db.get_gn_panels_for_page(page_id)
    if not panels:
        return 0.0
    with_action = sum(1 for p in panels if (p.action or "").strip())
    return with_action / len(panels)


def classify_page_pacing(db: Any, page: Any) -> str:
    """Return a visual-pacing indicator for a page (one of PACING_INDICATORS)."""
    density = (page.density_level or "").lower()
    panels = db.get_gn_panels_for_page(page.id)
    n = len(panels)
    text_load = _page_text_load(db, page.id)

    if page.splash_page or density == "explosive":
        return "explosive"
    # Heavy text relative to panel count reads as exposition.
    if n and text_load >= 2 * n:
        return "exposition-heavy"
    if (page.reveal_type or "").strip():
        return "cinematic"
    if density in _SILENCE_DENSITIES:
        return "quiet"
    if density == "dense":
        return "dense"
    return "quiet"


def page_rhythm(density_level: str) -> str:
    return _DENSITY_TO_RHYTHM.get((density_level or "").lower(), "steady")


def _page_motifs(db: Any, page_id: int) -> list[str]:
    motifs: list[str] = []
    for panel in db.get_gn_panels_for_page(page_id):
        for m in db.csv_split(panel.visual_motifs):
            if m not in motifs:
                motifs.append(m)
    return motifs


# ---------------------------------------------------------------------------
# Plot grid (§1):  Act/Issue -> Sequence -> Page
# ---------------------------------------------------------------------------

def get_gn_plot_blocks(
    db: Any, project_id: int, unit: str = "sequence",
) -> list[dict]:
    """Plot blocks for the Graphic Novel grid.

    unit="sequence": one block per sequence (with aggregate page count /
    density / reveal markers / motifs). unit="page": one block per page.
    Pages with no sequence are grouped under a synthetic block.
    """
    if unit == "page":
        return [_page_block(db, page) for page in db.get_gn_pages(project_id)]

    blocks: list[dict] = []
    for seq in db.get_gn_sequences(project_id):
        pages = db.get_gn_pages_for_sequence(seq.id)
        blocks.append(_sequence_block(db, seq, pages))

    # Pages not assigned to any sequence → a trailing synthetic block.
    orphan = [pg for pg in db.get_gn_pages(project_id) if pg.sequence_id is None]
    if orphan:
        blocks.append({
            "type": "sequence",
            "id": None,
            "title": "(unassigned pages)",
            "group": "",
            "page_count": len(orphan),
            "density": _aggregate_density(orphan),
            "reveal_markers": sum(1 for p in orphan if (p.reveal_type or "").strip()),
            "emotional_beat": "",
            "motif_markers": _collect_motifs(db, orphan),
            "page_ids": [p.id for p in orphan],
        })
    return blocks


def _sequence_block(db: Any, seq: Any, pages: list) -> dict:
    return {
        "type": "sequence",
        "id": seq.id,
        "title": seq.title or f"Sequence {seq.id}",
        "group": seq.issue or seq.chapter or "",   # Act/Issue level (§1)
        "page_count": len(pages),
        "density": _aggregate_density(pages),
        "reveal_markers": sum(1 for p in pages if (p.reveal_type or "").strip()),
        "emotional_beat": seq.emotional_beat or "",
        "motif_markers": _collect_motifs(db, pages),
        "page_ids": [p.id for p in pages],
    }


def _page_block(db: Any, page: Any) -> dict:
    return {
        "type": "page",
        "id": page.id,
        "title": f"Page {page.page_number}",
        "page_number": page.page_number,
        "sequence_id": page.sequence_id,
        "density": page.density_level or "",
        "reveal_marker": (page.reveal_type or "").strip(),
        "emotional_beat": page.emotional_beat or "",
        "motif_markers": _page_motifs(db, page.id),
        "splash_page": bool(page.splash_page),
        "pacing": classify_page_pacing(db, page),
    }


def _aggregate_density(pages: list) -> str:
    """Strongest density across a set of pages (for a sequence block)."""
    order = ["silent", "light", "medium", "dense", "explosive"]
    best = ""
    best_idx = -1
    for p in pages:
        d = (p.density_level or "").lower()
        if d in order and order.index(d) > best_idx:
            best_idx = order.index(d)
            best = d
    return best


def _collect_motifs(db: Any, pages: list) -> list[str]:
    motifs: list[str] = []
    for p in pages:
        for m in _page_motifs(db, p.id):
            if m not in motifs:
                motifs.append(m)
    return motifs


# ---------------------------------------------------------------------------
# Timeline (§2):  reading flow / rhythm / reveal timing / action density
# ---------------------------------------------------------------------------

def get_gn_timeline(db: Any, project_id: int) -> list[dict]:
    """Ordered reading-flow rows, one per page."""
    rows: list[dict] = []
    for page in db.get_gn_pages(project_id):
        density = (page.density_level or "").lower()
        rows.append({
            "page_id": page.id,
            "page_number": page.page_number,
            "sequence_id": page.sequence_id,
            "density": density,
            "rhythm": page_rhythm(density),
            "reveal_timing": (page.reveal_type or "").strip(),
            "action_density": _page_action_density(db, page.id),
            "text_load": _page_text_load(db, page.id),
            "pacing": classify_page_pacing(db, page),
            "is_silence": density in _SILENCE_DENSITIES,
            "is_action": density in _ACTION_DENSITIES or bool(page.splash_page),
        })
    return rows


def get_silence_action_pattern(db: Any, project_id: int) -> list[str]:
    """Reading-order pattern of 'silence' / 'action' / 'mixed' per page."""
    pattern: list[str] = []
    for row in get_gn_timeline(db, project_id):
        if row["is_action"]:
            pattern.append("action")
        elif row["is_silence"]:
            pattern.append("silence")
        else:
            pattern.append("mixed")
    return pattern


# ---------------------------------------------------------------------------
# Page-turn logic (§3):  setup before turn, reveal after turn
# ---------------------------------------------------------------------------

def get_page_turn_map(db: Any, project_id: int) -> list[dict]:
    """Pairs where a page sets up a reveal delivered on the next page.

    A page carrying a reveal_type is a page-turn SETUP; the following page
    in reading order is the REVEAL.
    """
    pages = db.get_gn_pages(project_id)
    pairs: list[dict] = []
    for i in range(len(pages) - 1):
        setup, reveal = pages[i], pages[i + 1]
        if (setup.reveal_type or "").strip():
            pairs.append({
                "setup_page_id": setup.id,
                "setup_page_number": setup.page_number,
                "reveal_page_id": reveal.id,
                "reveal_page_number": reveal.page_number,
                "reveal_type": setup.reveal_type,
            })
    return pairs


# ---------------------------------------------------------------------------
# Assistant context (§3):  page rhythm / visual motifs / density / continuity
# ---------------------------------------------------------------------------

def _recurring_motifs(db: Any, project_id: int) -> dict[str, int]:
    counts: dict[str, int] = {}
    for page in db.get_gn_pages(project_id):
        for motif in _page_motifs(db, page.id):
            counts[motif] = counts.get(motif, 0) + 1
    return counts


def _continuity_summary(db: Any, project_id: int) -> list[str]:
    summary: list[str] = []
    for item in db.get_gn_continuity_items(project_id):
        apps = db.get_gn_continuity_appearances(item.id)
        status = apps[-1].continuity_status if apps else "unknown"
        summary.append(f"{item.name} [{item.item_type}]: {status}")
    return summary


def build_graphic_novel_context(
    db: Any, project_id: int, page_id: int | None = None,
) -> str:
    """Compact ``[Graphic Novel Context]`` block for the Assistant (§3).

    Surfaces page rhythm, recurring visual motifs, panel density, and
    visual-continuity state. Returns "" when there is no GN data.
    """
    pages = db.get_gn_pages(project_id)
    if not pages:
        return ""

    lines: list[str] = ["[Graphic Novel Context]"]

    if page_id is not None:
        page = db.get_gn_page_by_id(page_id)
        if page is not None:
            n_panels = len(db.get_gn_panels_for_page(page.id))
            lines.append(
                f"Page {page.page_number}: rhythm={page_rhythm(page.density_level)}"
                f", density={page.density_level or 'n/a'}"
                f", panels={n_panels}, pacing={classify_page_pacing(db, page)}"
            )
            if (page.reveal_type or "").strip():
                lines.append(f"Reveal: {page.reveal_type}")
    else:
        rhythms = [page_rhythm(p.density_level) for p in pages]
        lines.append("Page rhythm: " + " → ".join(rhythms[:12]))
        density = ", ".join(
            f"p{p.page_number}:{len(db.get_gn_panels_for_page(p.id))}"
            for p in pages[:8]
        )
        lines.append("Panel density: " + density)

    motifs = _recurring_motifs(db, project_id)
    recurring = [f"{m} (×{c})" for m, c in motifs.items() if c >= 2]
    if recurring:
        lines.append("Recurring motifs: " + ", ".join(recurring[:10]))

    continuity = _continuity_summary(db, project_id)
    if continuity:
        lines.append("Continuity: " + "; ".join(continuity[:8]))

    if len(lines) == 1:
        return ""
    return "\n".join(lines)
