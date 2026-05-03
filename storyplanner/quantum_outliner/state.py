"""Narrative state engine — represents story as nodes, branches, wavefunctions.

The metaphor is borrowed from quantum mechanics but the implementation is
purely a data model. There is no math, only structured story possibilities.
"""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import asdict, dataclass, field


@dataclass
class StateDelta:
    """What changes in the story world if a branch is taken."""

    character_changes: list[dict] = field(default_factory=list)
    new_relations: list[dict] = field(default_factory=list)
    arc_updates: list[dict] = field(default_factory=list)
    notes: str = ""


@dataclass
class Branch:
    """One possible narrative direction within a wavefunction."""

    id: str
    title: str
    description: str
    stakes: str
    consequence: str
    state_delta: StateDelta = field(default_factory=StateDelta)
    structure_method: str | None = None
    structure_beat: str | None = None
    branch_type: str | None = None

    @classmethod
    def new(
        cls,
        title: str,
        description: str,
        stakes: str = "",
        consequence: str = "",
        state_delta: StateDelta | None = None,
        structure_method: str | None = None,
        structure_beat: str | None = None,
        branch_type: str | None = None,
    ) -> "Branch":
        return cls(
            id=uuid.uuid4().hex[:8],
            title=title,
            description=description,
            stakes=stakes,
            consequence=consequence,
            state_delta=state_delta or StateDelta(),
            structure_method=structure_method,
            structure_beat=structure_beat,
            branch_type=branch_type,
        )


@dataclass
class Wavefunction:
    """A superposition of possible next states for a single anchor.

    Branches stay alive in memory until the writer collapses one. Collapsed
    wavefunctions are archived for history but never block new work.
    """

    id: str
    anchor: str
    branches: list[Branch] = field(default_factory=list)
    collapsed_branch_id: str | None = None
    created_at: float = field(default_factory=time.time)
    source_scene_id: int | None = None
    source_scene_order: int | None = None
    target_scene_id: int | None = None
    structure_method: str | None = None
    structure_beat: str | None = None
    expected_function: str | None = None

    @classmethod
    def new(
        cls,
        anchor: str,
        branches: list[Branch] | None = None,
        source_scene_id: int | None = None,
        source_scene_order: int | None = None,
    ) -> "Wavefunction":
        return cls(
            id=uuid.uuid4().hex[:8],
            anchor=anchor,
            branches=branches or [],
            source_scene_id=source_scene_id,
            source_scene_order=source_scene_order,
        )

    def is_collapsed(self) -> bool:
        return self.collapsed_branch_id is not None

    def get_branch(self, branch_id: str) -> Branch | None:
        for b in self.branches:
            if b.id == branch_id:
                return b
        return None

    def collapsed_branch(self) -> Branch | None:
        if self.collapsed_branch_id is None:
            return None
        return self.get_branch(self.collapsed_branch_id)


@dataclass
class NarrativeState:
    """In-memory store of all live wavefunctions for a project."""

    project_id: int
    wavefunctions: dict[str, Wavefunction] = field(default_factory=dict)
    selected_pov: str = ""
    linked_scene_id: int | None = None

    def add(self, wf: Wavefunction) -> None:
        self.wavefunctions[wf.id] = wf

    def get(self, wf_id: str) -> Wavefunction | None:
        return self.wavefunctions.get(wf_id)

    def remove(self, wf_id: str) -> bool:
        return self.wavefunctions.pop(wf_id, None) is not None

    def active(self) -> list[Wavefunction]:
        return [w for w in self.wavefunctions.values() if not w.is_collapsed()]

    def collapsed(self) -> list[Wavefunction]:
        return [w for w in self.wavefunctions.values() if w.is_collapsed()]


_STATES: dict[int, NarrativeState] = {}


def get_state(project_id: int) -> NarrativeState:
    """Per-process narrative state for a project — created on first access."""
    if project_id not in _STATES:
        _STATES[project_id] = NarrativeState(project_id=project_id)
    return _STATES[project_id]


def reset_state(project_id: int) -> None:
    _STATES.pop(project_id, None)


def serialize(wf: Wavefunction) -> str:
    return json.dumps(asdict(wf), indent=2)


def serialize_state(state: NarrativeState) -> str:
    data = {
        "project_id": state.project_id,
        "selected_pov": state.selected_pov,
        "linked_scene_id": state.linked_scene_id,
        "wavefunctions": [asdict(wf) for wf in state.wavefunctions.values()],
    }
    return json.dumps(data)


def deserialize_state(raw: str, project_id: int) -> NarrativeState | None:
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return None
    if not isinstance(data, dict):
        return None

    state = NarrativeState(
        project_id=project_id,
        selected_pov=str(data.get("selected_pov", "")),
        linked_scene_id=data.get("linked_scene_id"),
    )

    for wf_raw in data.get("wavefunctions", []):
        if not isinstance(wf_raw, dict):
            continue
        branches = []
        for b_raw in wf_raw.get("branches", []):
            if not isinstance(b_raw, dict):
                continue
            delta_raw = b_raw.get("state_delta") or {}
            delta = StateDelta(
                character_changes=delta_raw.get("character_changes", []),
                new_relations=delta_raw.get("new_relations", []),
                arc_updates=delta_raw.get("arc_updates", []),
                notes=delta_raw.get("notes", ""),
            )
            branches.append(Branch(
                id=b_raw.get("id", ""),
                title=b_raw.get("title", ""),
                description=b_raw.get("description", ""),
                stakes=b_raw.get("stakes", ""),
                consequence=b_raw.get("consequence", ""),
                state_delta=delta,
                structure_method=b_raw.get("structure_method"),
                structure_beat=b_raw.get("structure_beat"),
                branch_type=b_raw.get("branch_type"),
            ))

        wf = Wavefunction(
            id=wf_raw.get("id", ""),
            anchor=wf_raw.get("anchor", ""),
            branches=branches,
            collapsed_branch_id=wf_raw.get("collapsed_branch_id"),
            created_at=wf_raw.get("created_at", time.time()),
            source_scene_id=wf_raw.get("source_scene_id"),
            source_scene_order=wf_raw.get("source_scene_order"),
            target_scene_id=wf_raw.get("target_scene_id"),
            structure_method=wf_raw.get("structure_method"),
            structure_beat=wf_raw.get("structure_beat"),
            expected_function=wf_raw.get("expected_function"),
        )
        state.wavefunctions[wf.id] = wf

    return state
