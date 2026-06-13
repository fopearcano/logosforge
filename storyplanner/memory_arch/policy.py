"""Memory writer policy (Phase 2 stub — conservative by default).

Encodes `docs/architecture/ASSISTANT_MEMORY_SPEC.md` §memory writer policy:
what to save, what not to blindly save, scope/status defaults, and the
forbidden-content guard (secrets, raw audio paths, debug logs). Decisions
only — this never writes memory itself.
"""

from __future__ import annotations

import re

from storyplanner.memory_arch.schema import (
    MemoryObject,
    MemoryScope,
    MemoryStatus,
    MemoryType,
)

# Types that are reusable workflow/assistant knowledge → assistant scope.
_ASSISTANT_TYPES = {
    MemoryType.ARCHITECTURE_DECISION, MemoryType.REPO_DECISION,
    MemoryType.WORKFLOW_RULE, MemoryType.ASSISTANT_RULE,
    MemoryType.MISTAKE_CORRECTION, MemoryType.RELEASE_BLOCKER_RULE,
    MemoryType.PROCEDURAL_RULE, MemoryType.DEFERRED_FEATURE,
    MemoryType.LIMITATION,
}
_USER_TYPES = {MemoryType.PREFERENCE, MemoryType.MODEL_PREFERENCE}
_PROJECT_TYPES = {
    MemoryType.PROJECT_DECISION, MemoryType.CHARACTER_FACT,
    MemoryType.CONTINUITY_FACT,
}

# Obvious secrets / raw audio / transient debug that must never be stored.
_FORBIDDEN_PATTERNS = (
    (re.compile(r"\bsk-[A-Za-z0-9]{8,}\b"), "openai-style api key"),
    (re.compile(r"\b(api[_-]?key|secret|token|password|bearer)\b"
                r"\s*[:=]", re.IGNORECASE), "credential assignment"),
    (re.compile(r"\.(wav|mp3|m4a|flac|ogg)\b", re.IGNORECASE),
     "raw audio path"),
    (re.compile(r"\b(traceback|stack trace|debug log)\b", re.IGNORECASE),
     "transient debug log"),
)


class MemoryWriterPolicy:
    """Conservative-by-default policy. Prefers `proposed`, requires user
    approval for most memory, and rejects obvious secrets/raw-audio."""

    def should_save_candidate(self, event_or_content, context=None) -> bool:
        text = _text(event_or_content)
        if not text.strip():
            return False
        # Never propose obviously-forbidden content.
        if self.check_forbidden_content_text(text):
            return False
        return True

    def classify_memory_type(self, content, context=None) -> MemoryType:
        # Stub heuristic; real classification is a later phase.
        return MemoryType.OTHER

    def infer_scope(self, content, context=None,
                    mtype: MemoryType | None = None) -> MemoryScope:
        if mtype in _ASSISTANT_TYPES:
            return MemoryScope.ASSISTANT
        if mtype in _USER_TYPES:
            return MemoryScope.USER
        if mtype in _PROJECT_TYPES:
            return MemoryScope.PROJECT
        return MemoryScope.PROJECT  # conservative default for facts

    def default_status(self, content, context=None) -> MemoryStatus:
        return MemoryStatus.PROPOSED  # never active by default

    def requires_user_approval(self, memory: MemoryObject) -> bool:
        # Conservative: approve everything except already-active high-conf ops.
        return not (memory.status is MemoryStatus.ACTIVE
                    and memory.confidence >= 0.9)

    def validate_scope(self, memory: MemoryObject) -> None:
        # Enforce the Project↔Assistant separation: assistant-scope objects
        # must not carry fiction/codex fact types, and project facts must not
        # be filed at assistant scope.
        if memory.scope is MemoryScope.ASSISTANT and memory.type in _PROJECT_TYPES:
            raise ValueError(
                "assistant scope must not hold project fiction/codex facts.")
        if memory.scope is MemoryScope.PROJECT and not memory.project_id:
            raise ValueError("project scope requires project_id.")

    def check_forbidden_content(self, memory: MemoryObject) -> list[str]:
        return self.check_forbidden_content_text(memory.content)

    def check_forbidden_content_text(self, text: str) -> list[str]:
        hits = []
        for pattern, label in _FORBIDDEN_PATTERNS:
            if pattern.search(text or ""):
                hits.append(label)
        return hits


def _text(event_or_content) -> str:
    if isinstance(event_or_content, str):
        return event_or_content
    return getattr(event_or_content, "content", "") or ""
