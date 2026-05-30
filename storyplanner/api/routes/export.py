"""Export endpoint — structured story/project data export.

Reuses :mod:`storyplanner.data_export` (the same code path the desktop File ▸
Export menu uses) so the API never re-implements export logic.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from storyplanner.api import schemas
from storyplanner.api.deps import get_db, get_project
from storyplanner.api.errors import bad_request
from storyplanner.db import Database

router = APIRouter(tags=["export"])

_VALID_TYPES = {"story_elements", "psyke_data", "full_project"}
_VALID_FORMATS = {"json", "markdown", "csv"}


@router.post(
    "/projects/{project_id}/export",
    response_model=schemas.ExportResponseDTO,
)
def export_project(
    body: schemas.ExportRequestDTO,
    project=Depends(get_project),
    db: Database = Depends(get_db),
):
    from storyplanner import data_export as de

    if body.export_type not in _VALID_TYPES:
        raise bad_request(f"Unknown export_type: {body.export_type}")
    if body.format not in _VALID_FORMATS:
        raise bad_request(f"Unknown format: {body.format}")

    if body.export_type == "full_project":
        data = de.build_full_export(db, project.id)
    else:
        if body.export_type == "psyke_data":
            opts = de.psyke_data_options()
        else:
            opts = de.story_elements_options()
        # Apply optional per-request overrides.
        for field in (
            "include_outline", "include_plot", "include_timeline",
            "include_scenes", "include_psyke_entries", "include_psyke_relations",
            "include_psyke_progressions", "include_notes",
            "include_project_metadata", "include_ids",
            "include_internal_metadata", "summaries_only",
        ):
            value = getattr(body, field)
            if value is not None:
                setattr(opts, field, value)
        opts.fmt = body.format
        data = de.gather_export(db, project.id, opts)

    response = schemas.ExportResponseDTO(
        export_type=body.export_type, format=body.format,
    )
    if body.format == "json":
        response.payload = data
    elif body.format == "markdown":
        response.content = de.to_markdown(data)
    else:  # csv -> map of filename -> text
        response.files = de.to_csv_files(data)
    return response
