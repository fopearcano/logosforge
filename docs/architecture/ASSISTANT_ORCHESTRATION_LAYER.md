# Assistant Orchestration Layer (Assistant Engine)

> Phase 1 — direction only. The Alpha seeds this in `assistant.py`,
> `assistant_context_policy.py`, `context_assistant.py`, `memory_context.py`,
> `memory_manager.py`, `story_memory.py`. This document defines the target
> shape; it implements nothing.

The Assistant Engine is the orchestration layer between the user, LogosForge
memory, and the selected model backend. **It always uses LogosForge
memory/context tools before calling the model.**

## Components

- **prompt builder** — assembles the final prompt/context bundle.
- **context selector** — picks relevant document + memory.
- **memory retriever** — reads Project/User/Workspace/Assistant memory.
- **memory writer** — proposes/writes durable memory per policy.
- **contradiction checker** — detects conflicts before active writes.
- **model router** — selects the provider/model for the task.
- **tool caller** — executes LogosForge assistant tools.
- **provider capability selector** — matches task needs to provider
  capabilities (`MODEL_GATEWAY_SPEC.md`).
- **session summarizer** — produces session summaries.
- **memory candidate extractor** — turns events into proposed memory.
- **safety / privacy guard** — blocks secrets/raw-audio/out-of-scope leaks.
- **sync coordinator** — local/cloud/GitHub per settings (`SYNC_STRATEGY.md`).

## Request flow

1. User asks something.
2. LogosForge reads current document/editor state.
3. Retrieve relevant **Project Memory**.
4. Retrieve relevant **User Memory**.
5. Retrieve relevant **Assistant Meta-Memory**.
6. Retrieve applicable **assistant rules** (externalized self-model).
7. Check **provider capabilities**.
8. Build the **prompt/context bundle**.
9. The **selected model backend generates** the response.
10. LogosForge receives the response.
11. LogosForge **proposes/extracts memory candidates**.
12. LogosForge **updates local memory per policy** (no destructive writes;
    contradictions checked).
13. LogosForge **syncs** memory per settings.
14. **Optional GitHub export** happens only if enabled.

## Final target

A user opens LogosForge on any device (local or cloud). The assistant
retrieves: current document context · project memory · user memory ·
assistant meta-memory · relevant previous decisions · model/provider
capabilities. It answers through the **selected** model backend. After the
interaction, LogosForge decides what should become durable memory and syncs
it locally / cloud / GitHub depending on settings — the backend can be
swapped at any time without losing assistant memory.

## Roadmap (mirrors `MEMORY_ARCHITECTURE.md`)

- **Early MVP:** local-first memory; structured tables; optional vector
  store (pgvector/Chroma/Qdrant); local models via LM Studio/Ollama; cloud
  via gateway; candidate-extraction + retrieval **placeholders**; no
  destructive writes; no GitHub auto-commit.
- **SaaS/Pro:** accounts; cloud sync; project/workspace memory; permissions;
  shared memory; cloud index; optional GitHub export.
- **Team/Studio:** workspace memory; role-based permissions; shared project
  assistant; project-level assistant history; versioned memory; audit.

## Implementation phases (Claude Code)

1. Architecture docs (this set). 2. Minimal interfaces/stubs (provider
abstraction, schema, local store interface, context-builder interface,
retrieval + candidate-extraction placeholders; no destructive writes; no
GitHub auto-commit). 3. Local MVP. 4. Cloud sync. 5. Optional GitHub export
(manual push only). No runtime/assistant behavior changes in Phase 1–2.


## Phase 2 — implemented interface locations

Interfaces/stubs only (no DB, no cloud sync, no GitHub commits, no vector runtime, no external provider calls, no UI wiring, no automatic durable writes). New isolated packages:

- `storyplanner/memory_arch/` — `schema.py` (MemoryObject, EventLogEntry, enums), `store.py` (`MemoryStore` ABC + `InMemoryMemoryStore`), `policy.py` (`MemoryWriterPolicy`), `retrieval.py`, `contradictions.py`, `sync.py` (disabled), `github_export.py` (disabled).
- `storyplanner/assistant_arch/` — `model_gateway.py` (`ProviderCapability`/`ModelRequest`/`ModelResponse`/`ModelProvider`/`ModelGateway` + `DummyModelProvider`), `context_builder.py` (`AssistantContextBuilder`, `ContextBundle`, `MemoryCandidateExtractor`), `orchestration.py` (`AssistantOrchestrator`), `tools.py` (`AssistantTools`).

Tests: `tests/test_memory_architecture_stubs.py` (21). The Alpha assistant (`assistant.py`, Billy/Logos/Dexter) and `providers.py` are unchanged.
