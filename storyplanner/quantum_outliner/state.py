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

    @classmethod
    def new(
        cls,
        title: str,
        description: str,
        stakes: str = "",
        consequence: str = "",
        state_delta: StateDelta | None = None,
    ) -> "Branch":
        return cls(
            id=uuid.uuid4().hex[:8],
            title=title,
            description=description,
            stakes=stakes,
            consequence=consequence,
            state_delta=state_delta or StateDelta(),
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

    @classmethod
    def new(cls, anchor: str, branches: list[Branch] | None = None) -> "Wavefunction":
        return cls(
            id=uuid.uuid4().hex[:8],
            anchor=anchor,
            branches=branches or [],
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
