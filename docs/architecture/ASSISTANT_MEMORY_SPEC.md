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
