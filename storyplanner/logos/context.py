"""LogosContext — a lightweight, serializable description of *where* the user
is working.

Rules (Phase 0):
* no ORM objects, no Qt widget references, no provider secrets;
* every field is a primitive or a list of ids, so the context is trivially
  serializable / debuggable;
* it only *describes* a location — it does not perform any work.

The UI captures the raw pieces (selection, active scene/section, …) and hands
them to :func:`build_logos_context`, which fills in the narrative
engine/writing format from the project. No database mutation occurs.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# Excerpt cap so the context object stays lightweight / debuggable.
_EXCERPT_LIMIT = 600


@dataclass
class LogosContext:
    project_id: int
    section_name: str = ""
    current_scene_id: int | None = None
    current_outline_node_id: int | None = None
    current_psyke_entry_id: int | None = None
    selected_text: str = ""
    cursor_text_excerpt: str = ""
    active_block_type: str = ""
    narrative_engine: str = ""
    writing_format: str = ""
    outline_template: str = ""
    # The outline item the user acted on (PlanView is scene-derived, so these
    # describe an Act / Chapter / Scene "node" rather than an OutlineNode row).
    outline_node_label: str = ""
    outline_node_kind: str = ""
    relevant_psyke_entry_ids: list[int] = field(default_factory=list)
    relevant_note_ids: list[int] = field(default_factory=list)

    def has_selection(self) -> bool:
        return bool(self.selected_text.strip())

    def to_dict(self) -> dict[str, Any]:
        return {
            "project_id": self.project_id,
            "section_name": self.section_name,
            "current_scene_id": self.current_scene_id,
            "current_outline_node_id": self.current_outline_node_id,
            "current_psyke_entry_id": self.current_psyke_entry_id,
            "selected_text": self.selected_text,
            "cursor_text_excerpt": self.cursor_text_excerpt,
            "active_block_type": self.active_block_type,
            "narrative_engine": self.narrative_engine,
            "writing_format": self.writing_format,
            "outline_template": self.outline_template,
            "outline_node_label": self.outline_node_label,
            "outline_node_kind": self.outline_node_kind,
            "relevant_psyke_entry_ids": list(self.relevant_psyke_entry_ids),
            "relevant_note_ids": list(self.relevant_note_ids),
        }

    def debug_summary(self) -> str:
        """One-line, secret-free summary for safe diagnostics/logging."""
        sel = (self.selected_text or "").strip()
        sel_preview = (sel[:40] + "…") if len(sel) > 40 else sel
        return (
            f"Logos[{self.section_name or '?'}] project={self.project_id} "
            f"scene={self.current_scene_id} engine={self.narrative_engine or '-'} "
            f"sel={len(sel)}c '{sel_preview}'"
        )


def build_logos_context(
    db,
    project_id: int,
    *,
    section_name: str = "",
    current_scene_id: int | None = None,
    current_outline_node_id: int | None = None,
    current_psyke_entry_id: int | None = None,
    selected_text: str = "",
    cursor_text_excerpt: str = "",
    active_block_type: str = "",
    outline_template: str = "",
    outline_node_label: str = "",
    outline_node_kind: str = "",
) -> LogosContext:
    """Build a :class:`LogosContext`, resolving engine/format from the project.

    *db* is read-only here (only :func:`project_compat` lookups) — no mutation.
    """
    engine = ""
    writing_format = ""
    try:
        from storyplanner.project_compat import (
            get_project_narrative_engine,
            get_project_writing_format,
        )
        project = db.get_project_by_id(project_id)
        engine = get_project_narrative_engine(project)
        writing_format = get_project_writing_format(project)
    except Exception:
        pass

    return LogosContext(
        project_id=project_id,
        section_name=section_name,
        current_scene_id=current_scene_id,
        current_outline_node_id=current_outline_node_id,
        current_psyke_entry_id=current_psyke_entry_id,
        selected_text=(selected_text or ""),
        cursor_text_excerpt=(cursor_text_excerpt or "")[:_EXCERPT_LIMIT],
        active_block_type=active_block_type,
        narrative_engine=engine,
        writing_format=writing_format,
        outline_template=outline_template,
        outline_node_label=outline_node_label,
        outline_node_kind=outline_node_kind,
    )
