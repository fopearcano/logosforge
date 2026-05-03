"""Collapse Mechanism — choose one branch, archive the rest, update PSYKE."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import TYPE_CHECKING

from storyplanner.quantum_outliner.psyke_adapter import apply_collapse
from storyplanner.settings import CONFIG_DIR
from storyplanner.quantum_outliner.state import (
    Branch,
    Wavefunction,
    get_state,
    serialize,
)

if TYPE_CHECKING:
    from storyplanner.db import Database

logger = logging.getLogger(__name__)


class CollapseError(Exception):
    pass


def collapse(
    db: "Database",
    project_id: int,
    wavefunction_id: str,
    branch_id: str,
    *,
    archive: bool = True,
) -> dict:
    """Commit one branch as canonical. Apply its delta to PSYKE.

    Returns a dict with:
      - chosen: the chosen Branch as dict
      - psyke_summary: what was written to PSYKE
      - archived: list of discarded branches (titles)
    """
    state = get_state(project_id)
    wf = state.get(wavefunction_id)
    if wf is None:
        raise CollapseError(f"Wavefunction '{wavefunction_id}' not found")
    if wf.is_collapsed():
        raise CollapseError(f"Wavefunction '{wavefunction_id}' already collapsed")

    chosen = wf.get_branch(branch_id)
    if chosen is None:
        raise CollapseError(
            f"Branch '{branch_id}' not in wavefunction '{wavefunction_id}'"
        )

    psyke_summary = apply_collapse(db, project_id, chosen)
    wf.collapsed_branch_id = chosen.id

    archived: list[dict] = []
    for b in wf.branches:
        if b.id != chosen.id:
            archived.append({"id": b.id, "title": b.title})

    if archive:
        try:
            _archive_wavefunction(project_id, wf)
        except OSError as exc:
            logger.warning("Failed to archive wavefunction: %s", exc)

    return {
        "chosen": {
            "id": chosen.id,
            "title": chosen.title,
            "description": chosen.description,
            "stakes": chosen.stakes,
            "consequence": chosen.consequence,
        },
        "psyke_summary": psyke_summary,
        "archived": archived,
    }


def _archive_path(project_id: int) -> Path:
    return CONFIG_DIR / "quantum" / f"archive_{project_id}.json"


def _archive_wavefunction(project_id: int, wf: Wavefunction) -> None:
    path = _archive_path(project_id)
    history: list[dict] = []
    if path.exists():
        try:
            history = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(history, list):
                history = []
        except (json.JSONDecodeError, OSError):
            history = []

    history.append(json.loads(serialize(wf)))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(history, indent=2), encoding="utf-8")


def load_archive(project_id: int) -> list[dict]:
    path = _archive_path(project_id)
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, list):
            return data
    except (json.JSONDecodeError, OSError):
        pass
    return []
