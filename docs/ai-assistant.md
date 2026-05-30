# AI Assistant

Logosforge's AI layer is built around one principle: **the model reasons with deep
narrative context, and never mutates your story without confirmation.** It works
with any OpenAI-compatible endpoint — fully local (LM Studio, Ollama) or cloud
(OpenAI, Anthropic, OpenRouter) — and degrades gracefully to a deterministic app
when no provider is configured.

> Source: `storyplanner/assistant.py` (transport), `context_builder.py` (the
> layered prompt), `providers.py` (provider catalog), `orchestration.py`,
> `adaptive_mode.py`, `counterpart.py`, `chat_memory.py`, the `connector_*`
> modules, and the UI in `ui/assistant_view.py`, `inline_assistant.py`,
> `inline_edit_bar.py`, `chat_view.py`.

---

## Providers & transport

`providers.py` defines five providers, each with capabilities (local vs cloud,
API-key requirement, default model list, API format, environment-variable key
name):

| Provider | Default endpoint | Auth | API format |
|----------|------------------|------|-----------|
| **LM Studio** | `http://localhost:1234/v1` | none | OpenAI |
| **Ollama** | `http://localhost:11434/v1` | none | OpenAI |
| **OpenAI** | `https://api.openai.com/v1` | `OPENAI_API_KEY` | OpenAI |
| **Anthropic** | `https://api.anthropic.com` | `ANTHROPIC_API_KEY` | Anthropic Messages |
| **OpenRouter** | `https://openrouter.ai/api/v1` | `OPENROUTER_API_KEY` | OpenAI |

`assistant.chat_completion(messages, …)` is the single entry point. It:

- selects the OpenAI-compatible or native Anthropic request shape per
  `get_api_format()`,
- resolves the API key from settings or the provider's environment variable,
- applies a provider-appropriate **timeout** (longer for local, shorter for
  cloud; overridable in settings),
- retries once on transient network errors (timeouts, connection resets) but
  raises immediately on HTTP/JSON errors with a helpful message,
- uses a small **LRU response cache** (keyed on messages + provider + model) so
  repeated identical calls are instant,
- can auto-detect the user's language and instruct the model to reply in it.

Every UI call runs on a `QThread` worker, so the interface never blocks.

---

## The layered context pipeline

The heart of the assistant is `context_builder.py` together with
`assistant.build_messages()`, which assemble a sequence of clearly-labelled
context blocks into the prompt. Blocks are included only when relevant and within
size caps, in roughly this order:

1. **`[Narrative Engine]`** — the engine profile and its `system_prompt_overlay`
   (reason as novelist / screenwriter / playwright / comics author / showrunner).
2. **`[AI Mode]`** — the adaptive mode (Structure / Balance / Refinement), story
   stage, and health guidance (see below).
3. **`[IRRATIONAL MODE]`** — optional surreal provocations, only when toggled on
   (see [irrational_mode.md](irrational_mode.md)).
4. **`[Story Memory]`** — continuity facts (character states, key events,
   relationships, decisions) scored by relevance, recency, and proximity to the
   active scene.
5. **`[Idea di Controllo]`** — the [Controlling Idea](structure-and-plot.md#controlling-idea)
   thematic spine and any scene/PSYKE alignment, when defined.
6. **`[PSYKE Context]`** — global entries, scene-relevant entries (with temporal
   progression state), and their one/two-hop related entries.
7. **`[Notes]`** — pinned and scene-/PSYKE-/tag-relevant notes, scored and ranked.
8. **`[Graph]`** — the active scene's graph neighbourhood (directly connected,
   high-influence, and weakly-connected nodes).
9. **`[Structural Analysis]`** — top structural issues (see
   [structural_intelligence.md](structural_intelligence.md)); screenplay
   continuity/setup-payoff context where applicable.
10. **`[Outline]`** — a numbered scene list with chapter/plotline/summary.
11. **`[Scene Context]`** — the current scene's full detail: content, summary,
    goal/conflict/outcome, character memory, places, continuity, screenplay fields,
    and story position.
12. **Action prompt + user note** — the specific instruction.

This is why the assistant's suggestions are grounded in *your* story rather than
generic advice — the relevant slice of the entire project is in the prompt.

### Orchestration

`orchestration.py` tailors the PSYKE slice to the *action* being performed. A
**Rewrite** uses only entries mentioned in the selection and their latest
progressions; **Dialogue** focuses on characters and their relations; **Expand**
adds globals and conservative relations; **Brainstorm** widens to active entries
and broader relations. Each run reports which entries were included and why
(visible in the context-inspector panel).

---

## Assistant modes

The Assistant panel (`ui/assistant_view.py`) offers several distinct modes:

- **Assistant** — generative help that can propose actions. Context scope is
  selectable: selection, current scene, outline, acts, or whole project. Toggles
  control whether outline, story memory, Story Bible, notes, and IRRATIONAL mode
  are included; a "show context" view reveals the exact assembled prompt.
- **COUNTERPART** (`counterpart.py`) — a reflective literary critic that **never
  rewrites and never proposes actions**. Its dialogic sub-modes are *Feedback*,
  *Critique*, *Interpret*, *Ask Back* (reflective questions), and *Compare*
  (alternative approaches with trade-offs, no rewrites). Every observation is
  grounded in the actual text.
- **Quantum** — drives the [QUANTUM Outliner](quantum-outliner.md) (generate
  branches, score, collapse).
- **Outline mode** — generates a structured outline and routes it into the Outline
  section (see [structure-and-plot.md](structure-and-plot.md)).

### Inline editing

- **Inline edit bar** (`ui/inline_edit_bar.py`) — a floating bar on text selection
  with quick **Rewrite / Expand / Dialogue** actions, then **Replace / Insert
  below / Cancel**.
- **Inline assistant** (`ui/inline_assistant.py`) — an in-editor panel with preset
  and custom actions, **Suggest Beats**, a session memory of recent actions, a
  context inspector, and **Replace / Insert / Compare (diff)** application. A
  replace only lands if the original text hasn't moved — the propose-then-confirm
  guarantee.

---

## Adaptive mode

`adaptive_mode.py` picks a guidance mode automatically from the story's maturity
and health:

| Story stage | Health | AI mode |
|-------------|--------|---------|
| Early | — | **Structure** — scaffold outline, establish acts, introduce characters |
| Mid / Late | Fragmented | **Structure** |
| Mid / Late | Uneven | **Balance** — even out character usage, develop thin arcs, fix pacing |
| Mid / Late | Balanced | **Refinement** — polish prose, sharpen dialogue, deepen themes |

The chosen mode appears in the **mode strip**, is injected as the `[AI Mode]`
block, and seeds the **Adapt** view's concrete suggestions
(`mode_suggestions.py`). You can always override it.

---

## Chat

The **Chat** view (`ui/chat_view.py`) is a persistent, project-scoped conversation
backed by `ChatMessage` / `ChatSummary` rows. `chat_memory.py` keeps a rolling
window of recent messages verbatim and folds older ones into a running summary, so
long conversations stay within the context budget. You can choose a **personality**
(`CHAT_PERSONALITIES`): *default, mentor, skeptic, editor, brutal, whimsical,
minimalist, philosopher.* The model can embed **action proposals** in its replies,
which render as cards with **Apply / Discard** buttons.

---

## The Connector — safe write actions

The **Connector** is how the AI performs structured writes — always
propose-then-confirm, never silent.

- `connector_registry.py` declares the available actions and their typed
  parameters, split into **read** actions (get project, list/get scenes,
  characters, PSYKE entries, notes; search) and a small allow-list of
  **non-destructive write** actions (create scene, update scene title, create
  PSYKE entry, create note). **No delete actions are ever exposed.**
- `connector_executor.execute_action()` validates the action name, enforces
  settings (connector enabled, writes allowed, action not disabled), coerces and
  checks parameters against the schema, dispatches to the handler
  (`connector_actions.py`), and on a successful write emits a project event so the
  UI refreshes. It never raises — failures come back as `{"ok": false, "error": …}`.
- In Chat and the Assistant, a proposed action is shown as a card; it executes only
  when the user clicks **Apply**.

The Connector is gated by the `connector_enabled`, `connector_allow_writes`,
`connector_confirm_writes`, and `connector_disabled_actions` settings — see
[configuration.md](configuration.md).

---

## Memory subsystem

- `story_memory.py` extracts low-level continuity facts from scenes
  (character_state, key_event, relationship, decision), de-duplicated before
  insert.
- `memory_manager.py` scores memories by type priority, recency decay, and
  supersession (a newer character state marks the older one "(past)").
- `memory_context.py` boosts memories near the active scene and overlapping its
  characters, then renders the `[Story Memory]` block.

Together these give the assistant a compact, scene-aware sense of what has already
happened — without dumping the whole manuscript into the prompt.
