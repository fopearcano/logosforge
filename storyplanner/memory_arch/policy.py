"""Memory writer policy (Phase 2 stub — conservative by default).

Encodes `docs/architecture/ASSISTANT_MEMORY_SPEC.md` §memory writer policy:
what to save, what not to blindly save, scope/status defaults, and the
forbidden-content guard (secrets, raw audio paths, debug logs). Decisions
only — this never writes memory itself.
"""

from __future__ import annotations

import re
from enum import Enum

from storyplanner.memory_arch.contradictions import contradicts
from storyplanner.memory_arch.schema import (
    MemoryObject,
    MemoryScope,
    MemoryStatus,
    MemoryType,
)


class PolicyDecision(str, Enum):
    """What the automatic, policy-governed pipeline does with a candidate.

    **The model generates; LogosForge remembers automatically when confidence
    and policy allow it, and asks the user only when memory is uncertain,
    sensitive, contradictory, or scope-ambiguous.**
    """
    AUTO_SAVE_ACTIVE = "auto_save_active"          # safe + high-confidence → active now
    SAVE_PROPOSED = "save_proposed"               # medium confidence → proposed
    SAVE_SPECULATIVE = "save_speculative"         # clearly a maybe/idea
    REQUIRE_REVIEW = "require_review"             # low confidence / needs a human
    IGNORE = "ignore"                            # duplicate / transient → no object
    REJECT = "reject"                            # secret / raw audio / unsafe
    FLAG_CONTRADICTION = "flag_contradiction"     # conflicts with ACTIVE memory
    FLAG_SENSITIVE = "flag_sensitive"            # sensitive-looking (not a hard secret)
    NEEDS_SCOPE_CONFIRMATION = "needs_scope_confirmation"  # scope/ownership unclear

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

# Stable, durable, low-ambiguity types that MAY auto-save as active when
# confidence is high and all safety gates pass (see `decide`).
_AUTO_SAVABLE_TYPES = {
    MemoryType.PREFERENCE, MemoryType.MODEL_PREFERENCE,
    MemoryType.PROJECT_DECISION, MemoryType.ARCHITECTURE_DECISION,
    MemoryType.REPO_DECISION, MemoryType.WORKFLOW_RULE,
    MemoryType.PROCEDURAL_RULE, MemoryType.ASSISTANT_RULE,
    MemoryType.MISTAKE_CORRECTION, MemoryType.CORRECTION,
    MemoryType.RELEASE_BLOCKER_RULE, MemoryType.CHARACTER_FACT,
    MemoryType.CONTINUITY_FACT, MemoryType.DEFERRED_FEATURE,
    MemoryType.LIMITATION,
}

# Confidence tiers for auto-save vs propose vs review.
_AUTO_SAVE_THRESHOLD = 0.85
_MEDIUM_CONFIDENCE = 0.5

# Sensitive-looking content (NOT a hard secret, but high-risk → review, never
# silently auto-saved). Hard secrets/raw-audio are handled by _FORBIDDEN_PATTERNS.
_SENSITIVE_PATTERNS = (
    re.compile(r"\b(ssn|social security|credit card|passport number|"
               r"bank account|routing number|password|passphrase|pin code)\b",
               re.IGNORECASE),
    re.compile(r"\b(medical|diagnosis|prescription|mental health|"
               r"lawsuit|legal case|salary|net worth)\b", re.IGNORECASE),
)

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

    def is_sensitive(self, text: str) -> bool:
        """Sensitive-looking (but not a hard secret) → route to review, never
        auto-save. Hard secrets/raw-audio are caught by check_forbidden_content."""
        return any(p.search(text or "") for p in _SENSITIVE_PATTERNS)

    def decide(self, candidate: MemoryObject,
               existing: list[MemoryObject] | None = None,
               context=None) -> PolicyDecision:
        """The automatic, policy-governed decision for a classified candidate.

        Auto-saves safe, high-confidence, durable memory as **active**; asks the
        user only when memory is uncertain, sensitive, contradictory, or
        scope-ambiguous. Pure decision — performs no write, no model call.
        """
        existing = existing or []
        text = candidate.content or ""

        # 1. Hard-unsafe content → never store.
        if self.check_forbidden_content_text(text):
            return PolicyDecision.REJECT
        # 2. Sensitive-looking → human review.
        if self.is_sensitive(text):
            return PolicyDecision.FLAG_SENSITIVE
        # 3. Collaborative/ambiguous scope → review.
        if candidate.scope is MemoryScope.WORKSPACE:
            if not candidate.workspace_id:
                return PolicyDecision.NEEDS_SCOPE_CONFIRMATION
            return PolicyDecision.REQUIRE_REVIEW          # affects collaborators
        if candidate.scope is MemoryScope.PROJECT and not candidate.project_id:
            return PolicyDecision.NEEDS_SCOPE_CONFIRMATION
        if candidate.scope is MemoryScope.USER and not candidate.user_id:
            return PolicyDecision.NEEDS_SCOPE_CONFIRMATION

        actives = [m for m in existing if m.status is MemoryStatus.ACTIVE]
        # 4. Exact duplicate of an active memory → ignore (don't re-store).
        norm = text.strip().lower()
        if any(m.scope is candidate.scope and (m.content or "").strip().lower()
               == norm for m in actives):
            return PolicyDecision.IGNORE
        # 5. Conflicts with an ACTIVE memory → human review.
        if any(contradicts(candidate, m) for m in actives):
            return PolicyDecision.FLAG_CONTRADICTION
        # 6. Clearly a maybe/idea → speculative.
        if (candidate.status is MemoryStatus.SPECULATIVE
                or candidate.type is MemoryType.SPECULATIVE_IDEA):
            return PolicyDecision.SAVE_SPECULATIVE

        # 7. Confidence/type gating.
        conf = candidate.confidence or 0.0
        if conf >= _AUTO_SAVE_THRESHOLD and candidate.type in _AUTO_SAVABLE_TYPES:
            return PolicyDecision.AUTO_SAVE_ACTIVE       # safe + high-confidence
        if conf >= _MEDIUM_CONFIDENCE:
            return PolicyDecision.SAVE_PROPOSED
        return PolicyDecision.REQUIRE_REVIEW              # low confidence

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
