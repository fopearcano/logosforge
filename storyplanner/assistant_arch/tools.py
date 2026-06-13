"""LogosForge-internal assistant tools (Phase 2 stubs).

The 13 tools from `docs/architecture/ASSISTANT_TOOLS_SPEC.md`, bound to a
`MemoryStore`. These are **LogosForge internal functions, not
provider-specific tools**. Read tools never persist; write tools only ever
create proposed/speculative candidates; cloud/GitHub sync are disabled
placeholders. Nothing here is wired into the running assistant.
"""

from __future__ import annotations

from storyplanner.assistant_arch.context_builder import MemoryCandidateExtractor
from storyplanner.memory_arch.github_export import GitHubMemoryExportService
from storyplanner.memory_arch.policy import MemoryWriterPolicy
from storyplanner.memory_arch.schema import (
    MemoryObject,
    MemoryScope,
    MemoryStatus,
    MemoryType,
)
from storyplanner.memory_arch.store import InMemoryMemoryStore, MemoryStore
from storyplanner.memory_arch.sync import MemorySyncService


class AssistantTools:
    """Tool surface over a single memory store. Defaults to an in-memory
    store so the tools are importable/testable without any backend."""

    def __init__(self, store: MemoryStore | None = None) -> None:
        self.store = store or InMemoryMemoryStore()
        self.policy = MemoryWriterPolicy()
        self._sync = MemorySyncService()
        self._github = GitHubMemoryExportService(self.store)
        self._extractor = MemoryCandidateExtractor()

    # -- read tools (never persist) -------------------------------------
    def search_memory(self, query: str, scope=None, project_id=None,
                      filters=None) -> list[MemoryObject]:
        return self.store.search(query, scope=scope, project_id=project_id,
                                 filters=filters)

    def retrieve_project_state(self, project_id: str) -> dict:
        items = self.store.search("", scope=MemoryScope.PROJECT,
                                  project_id=project_id)
        return {"project_id": project_id, "memory": items}

    def retrieve_user_preferences(self, task_type: str | None = None
                                  ) -> list[MemoryObject]:
        return self.store.search("", scope=MemoryScope.USER)

    def retrieve_assistant_rules(self, context=None) -> list[MemoryObject]:
        return self.store.search("", scope=MemoryScope.ASSISTANT)

    # -- write tools (candidates only; explicit approval) ---------------
    def write_memory_candidate(self, content: str, type: MemoryType,
                               scope: MemoryScope, confidence: float = 0.0,
                               source: str | None = None,
                               project_id: str | None = None,
                               user_id: str | None = None) -> MemoryObject:
        forbidden = self.policy.check_forbidden_content_text(content)
        if forbidden:
            raise ValueError(f"refused forbidden content: {forbidden}")
        mem = MemoryObject(
            scope=scope, type=type, content=content, confidence=confidence,
            source_event=source, project_id=project_id, user_id=user_id,
            status=MemoryStatus.PROPOSED)        # candidate only, never active
        self.policy.validate_scope(mem)
        return self.store.write_candidate(mem)

    def approve_memory_candidate(self, memory_id: str) -> MemoryObject:
        return self.store.approve_candidate(memory_id)

    def update_memory(self, memory_id: str, patch: dict,
                      reason: str) -> MemoryObject:
        return self.store.update(memory_id, patch, reason)

    def supersede_memory(self, old_id: str, new_id: str, reason: str):
        return self.store.supersede(old_id, new_id, reason)

    def find_contradictions(self, topic: str, project_id=None
                            ) -> list[MemoryObject]:
        return self.store.find_contradictions(topic, project_id=project_id)

    def summarize_session(self, session_id: str) -> dict:
        # Placeholder: real summarization is a later phase (no model call).
        return {"status": "not_implemented", "session_id": session_id,
                "summary": ""}

    def export_memory_to_markdown(self, scope=None, project_id=None) -> str:
        return self.store.export_markdown(scope=scope, project_id=project_id)

    # -- sync / github (disabled placeholders) --------------------------
    def sync_memory_to_cloud(self) -> dict:
        return self._sync.sync_memory_to_cloud()

    def optional_sync_memory_to_github(self) -> dict:
        return self._github.optional_sync_memory_to_github()
