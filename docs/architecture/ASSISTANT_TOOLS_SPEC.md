# Assistant Tools Spec

> Phase 1 — interface **direction** for LogosForge-internal assistant tools.
> These are **LogosForge tools, not provider-specific tools** — the model
> may *request* them, but LogosForge owns and executes them. No
> implementation here.

Conventions for every tool below: **purpose · inputs · outputs · scope
rules · safety rules · persistence rules · MVP behavior · future SaaS
behavior.**

---

### `search_memory(query, scope, project_id, filters)`
- **Purpose:** retrieve curated memory objects relevant to a query.
- **Inputs:** query text; `scope`; `project_id`; `filters` (type, status,
  tags, date).
- **Outputs:** ranked memory objects (active by default).
- **Scope:** never returns another project's/user's objects unless
  `visibility` permits; `assistant` scope excluded from creative output.
- **Safety:** read-only; no secrets returned.
- **Persistence:** none (read).
- **MVP:** keyword/structured filter over the local DB.
- **SaaS:** + cloud semantic index, permission-filtered.

### `retrieve_project_state(project_id)`
- **Purpose:** current Project Memory snapshot (structure + key facts).
- **Inputs:** `project_id`. **Outputs:** scenes/chapters/PSYKE/continuity
  summary. **Scope:** project only. **Safety:** read-only.
- **MVP:** read from project DB. **SaaS:** + synced project memory.

### `retrieve_user_preferences(task_type)`
- **Purpose:** user-scope preferences relevant to a task.
- **Inputs:** `task_type`. **Outputs:** preference objects. **Scope:** user.
- **Safety:** read-only; no secrets. **MVP:** local. **SaaS:** synced.

### `retrieve_assistant_rules(context)`
- **Purpose:** operating rules / known mistakes / corrections for the
  current context (the externalized self-model — `JORDAN_EXTERNALIZED_SELF_MODEL.md`).
- **Inputs:** `context`. **Outputs:** `assistant_rule` / `mistake_correction`
  / `workflow_rule` objects. **Scope:** assistant. **Safety:** read-only.

### `write_memory_candidate(content, type, scope, confidence, source)`
- **Purpose:** propose a durable memory (does not become active by itself).
- **Inputs:** content; `type`; `scope`; `confidence`; `source` event id.
- **Outputs:** candidate id with `status = proposed` (or `speculative`).
- **Scope:** defaults per `ASSISTANT_MEMORY_SPEC.md`. **Safety:** rejects
  secrets/raw-audio/debug; runs contradiction check.
- **Persistence:** writes a **proposed** object only. **MVP:** local table,
  manual approval. **SaaS:** + policy auto-approve for high-confidence ops.

### `approve_memory_candidate(memory_id)`
- **Purpose:** promote a candidate to `active`.
- **Safety:** re-runs contradiction detection; supersedes conflicts.
- **Persistence:** flips status to `active`, bumps `version`.

### `update_memory(memory_id, patch, reason)`
- **Purpose:** revise an object with an audit reason.
- **Persistence:** new `version`; `updated_at`; keeps history.

### `supersede_memory(old_id, new_id, reason)`
- **Purpose:** mark `old_id` `superseded` by `new_id` (never silent delete).
- **Persistence:** sets `supersedes`/`contradicted_by` + reason; old object
  retained for audit.

### `find_contradictions(topic, project_id)`
- **Purpose:** detect conflicting active memory on a topic.
- **Outputs:** conflicting object pairs. **Safety:** read-only; must run
  before any active write. **MVP:** heuristic/keyword. **SaaS:** semantic.

### `summarize_session(session_id)`
- **Purpose:** produce a `session_summary` candidate from an event-log
  session. **Persistence:** writes a **proposed** summary only.

### `export_memory_to_markdown(scope)`
- **Purpose:** human-readable export of a memory scope. **Safety:** strips
  secrets; labels scope. **Persistence:** none (returns/export only).

### `sync_memory_to_cloud()`
- **Purpose:** push/pull durable memory to the cloud account/workspace.
- **Scope:** respects permissions. **Safety:** no secrets; conflict →
  contradiction handling (`SYNC_STRATEGY.md`). **MVP:** no-op/disabled.
  **SaaS:** full sync.

### `optional_sync_memory_to_github()`
- **Purpose:** opt-in export/commit of memory snapshots to a repo.
- **Safety:** **explicit opt-in, manual push only, no secrets, no raw chat
  by default** (`GITHUB_EXPORT_STRATEGY.md`). **MVP:** disabled.

---

**Global tool rules:** read tools never persist; write tools only ever
create `proposed`/`speculative` unless policy explicitly auto-approves;
every active write is contradiction-checked; nothing writes secrets, raw
audio paths, or transient logs.


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
