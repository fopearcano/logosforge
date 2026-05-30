# Configuration & Settings

Logosforge is configured through a JSON settings file, an AI-provider setup, and a
handful of dialogs. This page is the reference for every setting and where it lives.

> Source: `storyplanner/settings.py` (the settings manager and defaults),
> `storyplanner/preferences.py`, `storyplanner/providers.py`, and the UI in
> `ui/settings_dialog.py`, `ui/provider_settings.py`, `ui/project_settings_dialog.py`,
> `ui/new_project_dialog.py`.

---

## Settings file

A single global settings file is loaded once and auto-saved on change:

```
~/.storyplanner/settings.json
```

`SettingsManager` (`settings.py`) is a singleton (`get_manager()`); `get(key)` /
`set(key, value)` read and persist immediately. A second, simpler store —
`~/.storyplanner/preferences.json` (`preferences.py`) — holds small boolean/string
flags.

### Setting keys

| Key | Default | Purpose |
|-----|---------|---------|
| `appearance` | `"Dark"` | Active theme palette. |
| `ai_provider` | `"LM Studio"` | Selected AI provider. |
| `ai_model` | `""` | Selected model. |
| `ai_api_key` | `""` | API key (or use the provider's env var). |
| `ai_base_url` | `""` | Override endpoint URL. |
| `assistant_api_timeout` | `0` | Request timeout override (0 = provider default). |
| `sidebar_collapsed` | `false` | Sidebar collapsed to icons. |
| `sidebar_groups_expanded` | `{}` | Per-group expand/collapse state. |
| `assistant_open` | `false` | Assistant panel visible. |
| `assistant_panel_mode` | `"assistant"` | Assistant / Counterpart / Quantum. |
| `assistant_include_outline` | `false` | Include outline in AI context. |
| `assistant_include_memory` | `false` | Include story memory in AI context. |
| `assistant_include_bible` | `false` | Include PSYKE in AI context. |
| `assistant_include_notes` | `true` | Include notes in AI context. |
| `assistant_irrational` | `false` | IRRATIONAL mode toggle. |
| `last_project_path` | `""` | Project file reopened on launch. |
| `plugin_states` | `{}` | Per-plugin enabled flags. |
| `auto_link_ignored` | `[]` | Permanently ignored Auto-Link suggestions. |
| `context_assistant_enabled` | `true` | Proactive Context Assistant on/off. |
| `context_assistant_ignored` | `[]` | Permanently ignored hint types. |
| `connector_enabled` | `false` | Allow AI to run Connector actions. |
| `connector_allow_writes` | `false` | Allow Connector **write** actions. |
| `connector_confirm_writes` | `true` | Require confirmation before writes. |
| `connector_disabled_actions` | `[]` | Specific Connector actions to disable. |
| `default_projects_folder` | `""` | Default location for new/saved projects. |
| `open_anyway_on_lock` | `false` | Open a project despite a lock sidecar. |
| `graph_state` | `{}` | Persisted Graph lens/layers/zoom/focus. |
| `graph_presets` | `{}` | Saved Graph filter sets. |

Per-project settings (engine, writing format, Controlling Idea, quantum weights/
goals/constraints, GN style profile, …) are stored separately inside
`Project.settings_json` — see [data-model.md](data-model.md).

---

## AI providers

The **Settings → AI Provider** section (and the provider widget embedded in the
assistant panels) configures the model. Five providers are supported
(`providers.py`):

| Provider | Endpoint | Key | Notes |
|----------|----------|-----|-------|
| LM Studio | `http://localhost:1234/v1` | — | Local; no key. |
| Ollama | `http://localhost:11434/v1` | — | Local; model selectable. |
| OpenAI | `https://api.openai.com/v1` | `OPENAI_API_KEY` | Cloud. |
| Anthropic | `https://api.anthropic.com` | `ANTHROPIC_API_KEY` | Cloud; native Messages API. |
| OpenRouter | `https://openrouter.ai/api/v1` | `OPENROUTER_API_KEY` | Cloud aggregator. |

For each provider you can set the base URL, model, and API key, or leave the key
blank to use the environment variable. A **Test** button validates the connection;
**Defaults** resets to the provider's defaults. Keys resolve from the settings
value first, then the provider's environment variable (`resolve_api_key`). Local
providers get a longer default timeout than cloud ones.

> Logosforge is local-first: with a local provider (LM Studio / Ollama) **no data
> leaves your machine**. With a cloud provider, only the assembled prompt context
> for a given request is sent to that provider.

---

## The Connector

The **Connector** lets the AI perform structured, non-destructive writes
(create scene / note / PSYKE entry, update scene title) — always
propose-then-confirm. It is **off by default** and gated by four settings:
`connector_enabled`, `connector_allow_writes`, `connector_confirm_writes`, and
`connector_disabled_actions` (a per-action opt-out list shown as checkboxes in the
Settings dialog). No delete actions are ever exposed. See
[ai-assistant.md](ai-assistant.md#the-connector--safe-write-actions).

---

## Appearance / themes

Three palettes ship (`ui/theme.py`): **Dark**, **Light (Green)**, and
**Light (Warm)**. Choose one in Settings → Appearance, the View → Appearance menu,
or the buttons at the bottom of the sidebar. The selection persists in
`appearance` and is applied as a global Qt stylesheet at startup.

---

## Project settings & new projects

- **New Project** (`ui/new_project_dialog.py`) — set the title, the
  [Narrative Engine](narrative-engines.md), and the default
  [Writing Format](writing-formats.md) (the engine auto-suggests a matching format).
- **Project Settings** (`ui/project_settings_dialog.py`) — change the engine or
  format later; changing the engine re-enters the project so every view rebuilds
  against the new reasoning model.
- **Default projects folder** and cloud-folder detection make it easy to keep
  projects in a synced directory; see [data-model.md](data-model.md) for the
  cloud-safety model.

---

## Remote / web execution

When run via Claude Code on the web (in a managed cloud container rather than your
machine), outbound network access is governed by the environment's network policy
chosen at creation time, and the container is ephemeral — anything worth keeping
must be committed and pushed. This affects whether cloud AI providers are reachable
during such a session, but does not change any of the settings above. See the
[Claude Code on the web docs](https://code.claude.com/docs/en/claude-code-on-the-web).
