"""Contradiction checker (Phase 2 placeholder — non-destructive).

Future behavior (`docs/architecture/MEMORY_OBJECT_SCHEMA.md` writer
invariants): detect conflicting active memory, mark the loser
`contradicted`/`superseded`, and ask the user to reconcile. For now it
returns empty results and makes no changes.
"""

from __future__ import annotations

from storyplanner.memory_arch.schema import MemoryObject


class ContradictionChecker:
    def find_contradictions(self, memory_candidate: MemoryObject,
                            existing_memory: list[MemoryObject]
                            ) -> list[MemoryObject]:
        # Placeholder: returns no contradictions. Real semantic/heuristic
        # detection lands in a later phase; nothing is mutated here.
        return []

    def propose_resolution(self, memory_candidate: MemoryObject,
                           contradictions: list[MemoryObject]) -> dict:
        # Placeholder resolution descriptor (no side effects). Future:
        # mark contradicted / supersede old decisions / request user input.
        return {
            "action": "none",
            "candidate_id": memory_candidate.id,
            "contradictions": [m.id for m in contradictions],
            "note": "ContradictionChecker is a Phase-2 placeholder.",
        }
