# Assistant Memory Spec

> Phase 1 — direction only. Defines the two memory systems, the memory
> scopes, and the **memory writer policy**. Implements nothing.

Core principle: **the model generates; LogosForge remembers, retrieves,
structures, updates, and syncs.** (`MEMORY_ARCHITECTURE.md`.)

## Two separate memory systems

LogosForge keeps **two** memory systems that must never be mixed.

### A. Project Memory — belongs to the writing project

The content and structure of one creative work. Examples:

- scenes, chapters, drafts, notes
- characters, locations
- codex / story bible (PSYKE)
- plotlines, continuity, themes
- screenplay structure
- graphic novel pages / panels
- series seasons / episodes

In the current Alpha this lives in the project database + PSYKE; it is the
canonical creative content.

### B. Assistant Meta-Memory — belongs to the collaboration layer

How the assistant has worked with this user / project. Examples:

- "user prefers a GitHub-first workflow"
- "desktop alpha first, cloud later"
- "local Whisper buffering for desktop voice"
- Claude Code prompts that worked or failed
- architecture decisions; repo structure
- known mistakes and their corrections
- model / backend preferences
- workflow rules
- assistant self-description and operating rules
- previous implementation choices
- release-blocker rules; deferred features
- repeated user corrections

### Hard separation rule

**Do not mix Project Memory and Assistant Meta-Memory.**

- Project facts must **not** be written into global user memory unless they
  are explicitly reusable across projects.
- Assistant workflow rules must **not** be stored as fiction/codex facts.
- A project fact defaults to **project** scope; a workflow rule defaults to
  **assistant** scope; a user preference defaults to **user** scope.

## Memory scopes

1. **Personal / User Memory** — follows the user across projects and devices.
2. **Project Memory** — belongs to one writing project.
3. **Workspace / Team Memory** — shared across collaborators or a writing
   room.
4. **Assistant Meta-Memory** — how the assistant has worked with the
   user/project.
5. **Device-local Cache** — fast offline access and local-first UX.

(The canonical `scope` enum is in `MEMORY_OBJECT_SCHEMA.md`:
`user | project | workspace | assistant | device`.)

## Memory writer policy

The assistant **does not save everything automatically as fact.** Durable
writes follow this policy.

### Save (candidates for durable memory)

- stable preferences
- project decisions
- technical constraints
- user corrections
- reusable workflows
- long-term project facts
- assistant mistakes and corrections
- repo / architecture decisions
- release rules
- mode-specific structural decisions
- model / backend preferences
- durable workflow decisions

### Do not blindly save

- temporary moods
- random chat fragments
- speculative ideas **as facts** (store them with `status = speculative`)
- outdated implementation assumptions
- project facts into the wrong project namespace
- one-off phrasing unless explicitly requested
- private/sensitive material without explicit reason and scope
- cloud/API secrets
- raw audio paths
- transient debug logs

### Rules

1. Memory candidates are usually **proposed before** becoming durable.
2. High-confidence operational facts may be saved automatically **only if
   policy allows** it.
3. Project facts default to **project** scope.
4. User preferences default to **user** scope.
5. Assistant operating rules default to **assistant** scope.
6. Device-only facts default to **device** scope.
7. **Contradictions must be detected before writing active memory.**
8. Superseded memory **remains available** for audit/history — it is marked
   `superseded`, never silently deleted.

## Retrieval expectation

Before calling the model, the Assistant Engine retrieves, in order: current
document/editor state → relevant Project Memory → relevant User Memory →
relevant Assistant Meta-Memory → applicable assistant rules
(`ASSISTANT_ORCHESTRATION_LAYER.md`). The assistant uses LogosForge
memory/context tools (`ASSISTANT_TOOLS_SPEC.md`) **before** the model call,
never instead of LogosForge memory.


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

**Implemented now** (`storyplanner/memory_arch/candidates.py`, `review.py`; `contradictions.py` upgraded to a heuristic; `assistant_arch/tools.py` extended) — deterministic, local-only, **no model call / no embeddings / no network**:

- **Extract → classify → propose.** `extract_candidates(...)` and `process_event_for_memory_candidates(store, event)` turn an interaction event into candidates via an ordered **marker** heuristic (correction → release_blocker → architecture → deferred → workflow → project_decision → preference → speculative). Only *marked* spans become candidates — **raw chat is never auto-saved as fact**; per-event and per-candidate caps add anti-spam guards.
- **Candidates only.** Every write is `proposed` (or `speculative` for speculative ideas) — **never active without explicit approval**. Confidence is tiered low/medium/high → 0.3 / 0.6 / 0.9.
- **Scope integrity.** Project-scope spans without a `project_id` (and user-scope spans without a `user_id`) are **skipped with a warning**, never mis-filed; Project Memory and Assistant Meta-Memory stay separate.
- **Safety.** Secrets / raw-audio / debug spans are dropped by the writer policy before any write; the session summary redacts forbidden excerpts.
- **Review service** (`MemoryCandidateReviewService`): `list_candidates` / `get` / `approve` / `reject` / `edit` / `supersede` / `mark_speculative` / `mark_contradicted`. **No destructive delete** — `reject` (new `MemoryStatus.REJECTED`) and `supersede` preserve the object for audit; transitions require a reason; `edit` refuses to change status.
- **Deterministic `summarize_session(session_id)`** — event counts + redacted excerpts → **one proposed** `session_summary` candidate at **assistant** scope (no model).
- **Heuristic contradiction surface** — `contradicts()` / `pairwise_contradictions()` flag same-scope statements with high keyword overlap + opposing polarity; surfaced as warnings/metadata only, **never auto-superseded**.

Tests: `tests/test_memory_candidate_workflow.py` (31). Dev demo: `scripts/memory_candidates_demo.py`.

**Still NOT implemented:** model-driven extraction/classification; semantic (embedding) contradiction or retrieval; auto-approval; cloud sync; GitHub auto-export; memory-approval UI; any wiring into the running Alpha assistant/providers.

**Reaffirmed (Phase 4):** the model generates, LogosForge remembers, retrieves, structures, updates, and syncs; nothing becomes durable/active without explicit approval; GitHub is optional only; Project Memory and Assistant Meta-Memory stay separate; Jordan has an externalized self-model, not consciousness.


## Phase 5 — Context Builder Retrieval MVP

**Implemented now** (`storyplanner/assistant_arch/context_builder.py`; `assistant_arch/tools.py` retrieval refined) — local-only, provider-agnostic, **no provider call / no memory write / no embeddings**:

- **Local scoped memory retrieval** from the `MemoryStore`, composed into **separate** sections — Project / User / Workspace / Assistant memory are never merged into one generic blob.
- **Assistant rules** retrieved as a focused sub-view (`assistant_rule` / `procedural_rule` / `workflow_rule`); `tools.retrieve_user_preferences` / `retrieve_assistant_rules` now return **active** memory of the relevant types by default.
- **Provider capability inclusion** (size / tool-strategy hints) — capabilities are *not* memory and are never stored.
- **Deterministic selection/ranking** (keyword/tag/entity match, project match, active status, confidence, type/mode/entity signals; recency tiebreak) — no embeddings, no vector DB.
- **Character-budget placeholder** with safe truncation and over-budget exclusions (objects never mutated).
- **Prompt-section serialization** — every scope labeled; secrets / raw-audio paths redacted; archived statuses hidden unless diagnostic; no raw source events, no provider keys.
- Status policy: **active by default**; `include_proposed` / `review_mode` surface candidates; `diagnostic` surfaces archived **with labels**; every exclusion carries a reason.

Tests: `tests/test_assistant_context_builder.py` (26).

**Still NOT implemented:** embeddings/vector retrieval; cloud sync; GitHub export automation; full UI memory review; active assistant-runtime integration; LLM-based extraction; full contradiction reasoning.

**Reaffirmed (Phase 5):** the model generates; LogosForge remembers and retrieves; **providers are not memory** (LM Studio / Ollama / vLLM / OpenAI / Anthropic / OpenRouter are generation backends only); Project Memory and Assistant Meta-Memory stay separate; Jordan is memory-grounded through LogosForge's externalized memory system, not conscious.
