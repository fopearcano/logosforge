# Sync Strategy

> Phase 1 — direction only. **Local-first is the default; cloud sync is
> future/pro.** No sync is implemented here. Cloud/infra ownership lives in
> future repos (per `CLAUDE.md`); this repo owns the durable contracts
> (schema, sync_state, conflict semantics).

## Tier hierarchy

**Local memory** — the default and the source of immediate UX:
- active working memory; fast offline access; immediate UX.
- SQLite (desktop) / Postgres (server) in MVP.

**Cloud account memory** *(future / pro)*:
- sync; multi-device continuation; shared project memory.
- canonical shared state for an account/workspace; permissions;
  embeddings/index updates.

**GitHub** *(optional, power-user)*:
- archive / export / versioning layer; **not** the default backend for all
  users; useful for developers, backups, markdown memory archives, Claude
  Code workflows, repository-linked projects (`GITHUB_EXPORT_STRATEGY.md`).

**Model providers** — replaceable reasoning/generation engines; never a sync
target for memory.

## Multi-device flow

**Device A:** edits project → talks to assistant → memory candidates
extracted → **local memory updates immediately** → cloud sync uploads
durable changes.

**Cloud:** stores account/project/workspace memory → keeps canonical shared
state → updates/searches embeddings → resolves sync state.

**Device B:** opens same account/project → downloads latest state →
rebuilds local cache → assistant continues with the **same** memory context.

## Conflict handling

- **Last-write-wins** only for safe, non-semantic fields (e.g. cosmetic
  tags, `updated_at`).
- **Semantic memory conflicts** require **contradiction detection**
  (`find_contradictions`, `MEMORY_OBJECT_SCHEMA.md`) — never a blind
  overwrite.
- **Supersede rather than silently delete** old decisions (`supersedes` /
  `contradicted_by`, `status = superseded`).
- **Keep audit / history** (`version`, event log).
- `sync_state` (`local_only` · `pending_sync` · `synced` · `conflict`)
  tracks each object; `conflict` blocks active use until reconciled.

## Defaults

Local-first everywhere; cloud sync **off** until accounts exist; GitHub
export **off** and opt-in. Nothing about sync is required for the desktop
Alpha to function offline.


## Phase 2 — implemented interface locations

Interfaces/stubs only (no DB, no cloud sync, no GitHub commits, no vector runtime, no external provider calls, no UI wiring, no automatic durable writes). New isolated packages:

- `storyplanner/memory_arch/` — `schema.py` (MemoryObject, EventLogEntry, enums), `store.py` (`MemoryStore` ABC + `InMemoryMemoryStore`), `policy.py` (`MemoryWriterPolicy`), `retrieval.py`, `contradictions.py`, `sync.py` (disabled), `github_export.py` (disabled).
- `storyplanner/assistant_arch/` — `model_gateway.py` (`ProviderCapability`/`ModelRequest`/`ModelResponse`/`ModelProvider`/`ModelGateway` + `DummyModelProvider`), `context_builder.py` (`AssistantContextBuilder`, `ContextBundle`, `MemoryCandidateExtractor`), `orchestration.py` (`AssistantOrchestrator`), `tools.py` (`AssistantTools`).

Tests: `tests/test_memory_architecture_stubs.py` (21). The Alpha assistant (`assistant.py`, Billy/Logos/Dexter) and `providers.py` are unchanged.
