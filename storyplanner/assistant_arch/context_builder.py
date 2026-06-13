"""Assistant context builder + candidate extractor (Phase 2 stubs).

Mirrors `docs/architecture/ASSISTANT_ORCHESTRATION_LAYER.md`. Builds the
read-only context bundle that the prompt builder would consume. Degrades
safely (empty memory) when no store is configured; never mutates memory and
never calls a model.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from storyplanner.assistant_arch.model_gateway import ProviderCapability
from storyplanner.memory_arch.retrieval import MemoryRetriever
from storyplanner.memory_arch.schema import MemoryObject, MemoryScope
from storyplanner.memory_arch.store import MemoryStore


@dataclass
class ContextBundle:
    current_document_context: str = ""
    project_memory: list[MemoryObject] = field(default_factory=list)
    user_memory: list[MemoryObject] = field(default_factory=list)
    assistant_meta_memory: list[MemoryObject] = field(default_factory=list)
    assistant_rules: list[MemoryObject] = field(default_factory=list)
    provider_capabilities: ProviderCapability | None = None
    retrieved_at: float = field(default_factory=time.time)
    token_budget: int = 0
    warnings: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)


class AssistantContextBuilder:
    """Read-only context assembly. Optional store/gateway; safe when absent."""

    def __init__(self, store: MemoryStore | None = None,
                 gateway=None) -> None:
        self._store = store
        self._retriever = MemoryRetriever(store)
        self._gateway = gateway

    def build_context(self, user_request: str, project_id: str | None = None,
                      user_id: str | None = None,
                      workspace_id: str | None = None,
                      provider_id: str | None = None) -> ContextBundle:
        bundle = ContextBundle(token_budget=0)
        # Document context is supplied by the caller/editor in a later phase;
        # Phase 2 leaves it empty and never reaches into UI.
        bundle.project_memory = self.retrieve_relevant_memory(
            user_request, [MemoryScope.PROJECT], project_id, user_id,
            workspace_id)
        bundle.user_memory = self.retrieve_relevant_memory(
            user_request, [MemoryScope.USER], project_id, user_id,
            workspace_id)
        bundle.assistant_meta_memory = self.retrieve_relevant_memory(
            user_request, [MemoryScope.ASSISTANT], project_id, user_id,
            workspace_id)
        bundle.assistant_rules = list(bundle.assistant_meta_memory)
        if self._gateway is not None and provider_id:
            for cap in self._gateway.list_providers():
                if cap.provider_id == provider_id:
                    bundle.provider_capabilities = cap
                    break
        if self._store is None:
            bundle.warnings.append("no memory store configured (empty memory).")
        return bundle

    def retrieve_project_context(self, project_id: str) -> dict:
        # Placeholder: the real builder reads editor/project state. Phase 2
        # returns an empty, non-mutating snapshot.
        return {"project_id": project_id, "document_context": "",
                "structure": []}

    def retrieve_relevant_memory(self, query: str,
                                 scopes: list[MemoryScope],
                                 project_id: str | None = None,
                                 user_id: str | None = None,
                                 workspace_id: str | None = None
                                 ) -> list[MemoryObject]:
        return self._retriever.retrieve(query, scopes, project_id, user_id,
                                        workspace_id)

    def select_context(self, memory_items: list[MemoryObject],
                       token_budget: int) -> list[MemoryObject]:
        # Stub: no token estimation yet; return as-is (caller may slice).
        return list(memory_items)


class MemoryCandidateExtractor:
    """Turns a session/event into proposed memory candidates.

    Phase 2 placeholder: **returns an empty list**, calls no model, writes no
    memory. No automatic durable writes; no auto-saving raw chat spam."""

    def extract_candidates(self, session_or_event,
                           context=None) -> list[MemoryObject]:
        return []
