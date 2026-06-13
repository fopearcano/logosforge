# LogosForge Memory Architecture

> **Phase 1 — architecture direction only.** No database tables, migrations,
> vector search, provider clients, sync, GitHub automation, or UI are
> implemented by this document. It defines the direction the LogosForge
> core (this repo) and its future frontends/services must follow.

## Core principle

> **The model generates. LogosForge remembers, retrieves, structures,
> updates, and syncs.**

Model providers are **replaceable generation/reasoning backends**. They are
**not** the memory system. The memory system is implemented inside
LogosForge and is owned by the Python core (`fopearcano/storyplanner`).

1. **Model providers are not the memory system.** LM Studio, Ollama, vLLM,
   OpenAI, Anthropic, OpenRouter and any future provider produce tokens;
   they do not own, persist, or retrieve LogosForge memory.
2. **Memory is implemented inside LogosForge.** It is the core's
   responsibility, exposed through the API layer that frontends consume.
3. **LogosForge is model-agnostic.** The selected backend can change at any
   time without losing a single memory object.
4. **The assistant works with local or cloud models** through one gateway.
5. **Memory is externalized and persistent** — it lives in LogosForge
   stores, never inside model weights.
6. **Memory is structured, scoped, versioned, and sync-capable** (see
   `MEMORY_OBJECT_SCHEMA.md`).
7. **Memory is not raw chat spam.** Durable memory is curated, not a
   transcript dump (see the memory writer policy in `ASSISTANT_MEMORY_SPEC.md`).
8. **GitHub is optional**, never the default backend for every user (see
   `GITHUB_EXPORT_STRATEGY.md`).

## Ownership boundary (per `CLAUDE.md`)

This repo (the Python core) owns: the **Memory Store**, the **Assistant
Engine / orchestration**, the **Model Gateway**, and the **API surface**
that exposes them. It does **not** own React/Electron UI, web hosting/auth,
or cloud deployment — those are future scaffolds in other repos
(`logosforge-desktop`, cloud/infra repos) that consume this core's API.
Cloud sync and GitHub export below describe **direction**; the durable
contracts (schema, tools, gateway) are what this repo implements.

## Component hierarchy

```
LogosForge App
├─ Editor / Whiteboard / Outline / Codex (PSYKE)        [UI: this repo's
│                                                          Qt app today;
│                                                          React later]
├─ Project Database                                      [core, this repo]
├─ Assistant Engine                                      [core, this repo]
│   ├─ prompt builder
│   ├─ context selector
│   ├─ memory retriever
│   ├─ memory writer
│   ├─ contradiction checker
│   ├─ model router
│   └─ tool caller
├─ Memory Store                                          [core + future svc]
│   ├─ local structured DB        (active working memory)
│   ├─ local vector index         (semantic retrieval)
│   ├─ cloud sync layer           (future / pro)
│   └─ optional GitHub export     (opt-in power-user)
└─ Model Providers                                       [replaceable backends]
    ├─ LM Studio · Ollama · vLLM   (local / self-hosted)
    ├─ OpenAI · Anthropic · OpenRouter (cloud)
    └─ future providers
```

## Memory tier hierarchy

| Tier | Role |
|------|------|
| **Local memory** | Active working memory. Fast, offline, local-first UX. SQLite (desktop) / Postgres (server) in MVP. |
| **Cloud account memory** | Sync, multi-device continuation, shared project memory. Canonical shared state for an account/workspace. *(future / pro)* |
| **GitHub** | Optional power-user archive / export / versioning layer. Not the default backend for any user. |
| **Model providers** | Replaceable reasoning/generation engines. Hold no durable LogosForge memory. |

## Roadmap (summary; full phases in §Implementation direction below and `ASSISTANT_ORCHESTRATION_LAYER.md`)

- **Early MVP:** local-first memory (SQLite/Postgres); simple structured
  memory tables; optional vector store (pgvector / Chroma / Qdrant); local
  models via LM Studio/Ollama; cloud models via the model gateway; memory
  candidate extraction + retrieval **placeholders**; no destructive memory
  writes; no GitHub auto-commit.
- **SaaS / Pro:** user accounts; cloud sync; project/workspace memory;
  permissions; shared memory; cloud embeddings/index; optional GitHub export.
- **Team / Studio:** workspace memory; role-based permissions; shared
  project assistant; project-level assistant history; versioned memory;
  audit/history.

## Implementation direction (Claude Code)

Do **not** implement the full system at once. Build in phases:

1. **Phase 1 — Architecture docs only** (this set under `docs/architecture/`).
2. **Phase 2 — Minimal interfaces/stubs:** model-provider abstraction,
   memory-object schema, local memory-store interface, assistant
   context-builder interface, retrieval placeholder, candidate-extraction
   placeholder. No destructive writes; no GitHub auto-commit.
3. **Phase 3 — Local MVP:** SQLite/Postgres-backed local memory; event log;
   curated memory table; manual approve/reject of candidates; basic
   semantic index if safe.
4. **Phase 4 — Cloud sync:** account/project/workspace memory; conflict
   resolution; permissions; cloud index.
5. **Phase 5 — Optional GitHub export:** markdown export; architecture
   decision log; assistant memory snapshot; **manual push/commit only**.

## How the current Alpha relates to this direction

The Alpha already seeds parts of this architecture (see the cited modules
in each spec): `storyplanner/providers.py` (`ProviderCapabilities` — the
Model Gateway seed), `assistant.py` / `assistant_context_policy.py` /
`context_assistant.py` / `memory_context.py` / `memory_manager.py` /
`story_memory.py` / `chat_memory.py` (Assistant Engine + context seeds),
and the project database + PSYKE (Project Memory). These are partial and
project-context-oriented; the scoped, versioned, sync-capable memory system
described here is future work layered over them — **not** a rewrite of the
Alpha.

See: `ASSISTANT_MEMORY_SPEC.md`, `MEMORY_OBJECT_SCHEMA.md`,
`ASSISTANT_TOOLS_SPEC.md`, `MODEL_GATEWAY_SPEC.md`,
`ASSISTANT_ORCHESTRATION_LAYER.md`, `SYNC_STRATEGY.md`,
`GITHUB_EXPORT_STRATEGY.md`, `JORDAN_EXTERNALIZED_SELF_MODEL.md`.


## Phase 2 — implemented interface locations

Interfaces/stubs only (no DB, no cloud sync, no GitHub commits, no vector runtime, no external provider calls, no UI wiring, no automatic durable writes). New isolated packages:

- `storyplanner/memory_arch/` — `schema.py` (MemoryObject, EventLogEntry, enums), `store.py` (`MemoryStore` ABC + `InMemoryMemoryStore`), `policy.py` (`MemoryWriterPolicy`), `retrieval.py`, `contradictions.py`, `sync.py` (disabled), `github_export.py` (disabled).
- `storyplanner/assistant_arch/` — `model_gateway.py` (`ProviderCapability`/`ModelRequest`/`ModelResponse`/`ModelProvider`/`ModelGateway` + `DummyModelProvider`), `context_builder.py` (`AssistantContextBuilder`, `ContextBundle`, `MemoryCandidateExtractor`), `orchestration.py` (`AssistantOrchestrator`), `tools.py` (`AssistantTools`).

Tests: `tests/test_memory_architecture_stubs.py` (21). The Alpha assistant (`assistant.py`, Billy/Logos/Dexter) and `providers.py` are unchanged.


## Phase 3 — Local MVP Memory Store

**Implemented now** (`storyplanner/memory_arch/local_store.py` — isolated stdlib `sqlite3`, separate from the app's SQLModel project DB):

- `LocalSQLiteMemoryStore(path)` implementing the full `MemoryStore` ABC; tables `memory_events`, `memory_objects`, `memory_relations` (JSON-as-text columns for lists).
- local structured memory persistence + event log; explicit approval workflow (candidates stay proposed/speculative; `approve_candidate` activates); `update` requires a reason; `supersede` preserves the old object (marked superseded + linked) — **no destructive delete**.
- simple substring/scope/project/type/status search; safe scoped/grouped markdown export (no secrets / raw audio / DB internals).
- writer-policy enforcement on write (rejects obvious secrets + raw-audio paths; enforces explicit scope, project/user ids, and the Project↔Assistant separation).
- DB path is opt-in (`:memory:` default; `default_memory_db_path()` → `~/.storyplanner/logosforge_memory.sqlite3`). **No DB is created on import or app startup**; nothing is wired into the running app/UI/providers; the file is git-ignored.

**Still NOT implemented:** automatic memory extraction from chats; vector embeddings; cloud sync; GitHub auto-export; memory-approval UI; model-provider memory; provider calls; full contradiction reasoning (`find_contradictions` only surfaces already-flagged `contradicted` rows).

**Reaffirmed:** the model generates, LogosForge remembers; GitHub is optional only; Project Memory and Assistant Meta-Memory stay separate; Jordan has an externalized self-model, not consciousness.


## Phase 4 — Memory Candidate Workflow MVP

Phase 4 builds the curated-memory layer (layer 2) on top of the Phase 3 store: a deterministic, local-only pipeline that turns interaction events into **reviewable candidates** — extract, classify, review, approve, reject, supersede, and export — **without destructive writes** and **without a model call, embeddings, or network**.

- **Anti-spam by construction:** only spans carrying an explicit memory **marker** become candidates; raw chat is discarded. Nothing is durable or active without explicit human approval.
- **Conservative defaults:** every candidate is `proposed` (or `speculative`); confidence is tiered (0.3 / 0.6 / 0.9); secrets / raw-audio / debug are dropped; scope/id integrity is enforced so Project Memory and Assistant Meta-Memory never mix.
- **Non-destructive lifecycle:** the new `MemoryStatus.REJECTED`, plus `superseded` / `contradicted`, are auditable status transitions that preserve the object and its history — **no delete**.
- **Heuristic, not magical:** contradiction detection is keyword-overlap + opposing-polarity and only *surfaces* conflicts; the deterministic `summarize_session` produces a redaction-safe proposed summary. Semantic/model-driven versions remain future work.

New code: `storyplanner/memory_arch/candidates.py`, `review.py`; upgraded `contradictions.py`; extended `assistant_arch/tools.py`. Tests: `tests/test_memory_candidate_workflow.py` (31). Dev demo: `scripts/memory_candidates_demo.py`. Nothing is wired into the running Alpha; importing creates no DB and touches no provider.

**Reaffirmed (Phase 4):** the model generates, LogosForge remembers, retrieves, structures, updates, and syncs; nothing becomes durable/active without explicit approval; GitHub is optional only; Project Memory and Assistant Meta-Memory stay separate; Jordan has an externalized self-model, not consciousness.


## Phase 5 — Context Builder Retrieval MVP

Phase 5 implements the **retrieve / structure** half of the principle: the `AssistantContextBuilder` reads scoped memory from the local store (layer 2) and composes a provider-agnostic `ContextBundle` for the model gateway — **without calling any provider and without writing any memory**.

- **Local scoped retrieval** into **separate** sections (Project / User / Workspace / Assistant + a focused Assistant Rules view) — never one generic memory blob.
- **Deterministic ranking/selection** (keyword/tag/entity + project/active/confidence/type/mode/entity signals; recency tiebreak) — no embeddings, no vector DB.
- **Character-budget placeholder** with safe truncation; **prompt-section serialization** that labels every scope and strips secrets / raw-audio paths.
- **Provider capabilities** (context window, tool/JSON/stream/vision/audio support, privacy/offline) are surfaced as size/strategy hints only — **providers are not memory and store nothing**.
- Status policy: active by default; proposed/speculative only on request; deprecated/superseded/contradicted/rejected excluded with reasons (diagnostic mode can include them, labeled).
- A generic, **test-only `DocumentContext` adapter** carries current document/editor state; no UI or active-editor code is touched.

New/updated code: `storyplanner/assistant_arch/context_builder.py`, `tools.py`. Tests: `tests/test_assistant_context_builder.py` (26). Nothing wired into the running Alpha; importing creates no DB and touches no provider.

**Still NOT implemented:** embeddings/vector retrieval; cloud sync; GitHub export automation; full UI memory review; active assistant-runtime integration; LLM-based extraction; full contradiction reasoning.

**Reaffirmed (Phase 5):** the model generates; LogosForge remembers and retrieves; **providers are not memory** (LM Studio / Ollama / vLLM / OpenAI / Anthropic / OpenRouter are generation backends only); Project Memory and Assistant Meta-Memory stay separate; Jordan is memory-grounded through LogosForge's externalized memory system, not conscious.


## Phase 6 — Passive Assistant Context Integration MVP

Phase 6 connects the retrieval layer to the **live assistant prompt** — passively. When the **default-OFF** flag `assistant_memory_context_enabled` is on and a memory store is available, `storyplanner/assistant.build_messages` may append a read-only LogosForge ContextBundle (via `assistant_arch/passive_context.py`) — **without any provider call and without writing memory**.

- **Opt-in / fail-safe:** gated by a per-call param + the settings flag + an available store; off → byte-identical prompt; failures degrade to no block; the default path imports no memory packages.
- **Separate labelled sections** (Project / User / Workspace / Assistant Meta-Memory + Assistant Rules + Provider Capabilities) — never one blob; archived + proposed/speculative excluded; secrets / raw-audio / raw events never injected.
- **Read-only:** the memory layers (event log → curated objects) are only *read*; the candidate workflow remains the sole, explicit path to durable memory.
- Production note: no concrete store is wired yet — the seam is in place and tested; wiring a store is a later explicit step.

New code: `storyplanner/assistant_arch/passive_context.py`; opt-in param on `assistant.build_messages`; 2 settings flags. Tests: `tests/test_assistant_passive_context_integration.py` (22).

**Still NOT implemented:** automatic durable memory writing; full memory approval UI; embeddings/vector retrieval; cloud sync; GitHub export automation; provider-specific memory; LLM-based memory extraction; full assistant-runtime replacement.

**Reaffirmed (Phase 6):** the model generates; LogosForge remembers and retrieves; **providers are replaceable backends, not memory**; Jordan is memory-grounded through LogosForge's externalized memory system — **not provider memory or model weights**.
