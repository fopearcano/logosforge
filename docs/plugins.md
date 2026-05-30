# Logosforge Plugin Development Guide

Logosforge has **two kinds of plugins**:

1. **External menu plugins** — folders under `plugins/` with a `plugin.json`
   manifest and a `register(api)` entry point. They add menu actions and read
   project data through a small, read-only `PluginAPI`. This is what most of this
   guide covers, and how the bundled Go McKee, Idea di Controllo, and PSYKE Outline
   Templates plugins are built.
2. **Internal analysis plugins** — Python classes subclassing `LogosforgePlugin`
   that receive a rich, immutable narrative snapshot (`PluginContext`) and return
   structured `PluginResult` suggestions. They live in `storyplanner/plugins/` and
   are documented under [Analysis plugins](#analysis-plugins-internal-api) below.

Both kinds are read-only: a plugin can never access the database or mutate project
state directly.

## Plugin Folder Structure

Each plugin lives in its own folder inside `plugins/` at the project root:

```
plugins/
  my_plugin/
    plugin.json
    plugin.py
```

A plugin is valid when both `plugin.json` and `plugin.py` exist.

## Manifest (`plugin.json`)

Required fields:

```json
{
  "id": "my_plugin",
  "name": "My Plugin",
  "version": "1.0.0",
  "author": "Your Name",
  "description": "What this plugin does."
}
```

Optional fields:

| Field | Default | Description |
|---|---|---|
| `entry_point` | `"plugin.py"` | Python file to load |
| `enabled_by_default` | `true` | Whether the plugin starts enabled |

## Entry Point (`plugin.py`)

Your plugin module must define a `register(api)` function:

```python
def register(api):
    api.log("My plugin loaded.")

    def my_action():
        api.show_message("Hello", "Plugin action triggered.")

    api.register_menu_action("My Action", my_action)
```

The `api` object is a `PluginAPI` instance with the methods listed below.

## Plugin API Reference

### `api.register_menu_action(name, callback)`
Adds an item to the **Plugins** menu in the menu bar. `callback` is called when the user clicks it.

### `api.log(message)`
Records a log line visible in the Plugins view details panel.

### `api.show_message(title, message)`
Shows a simple information dialog.

### `api.get_project_title() -> str`
Returns the current project title (read-only).

### `api.get_scene_titles() -> list[str]`
Returns a list of all scene titles in the current project (read-only).

### `api.get_scene_count() -> int`
Returns the number of scenes in the current project.

## Minimal Example

`plugins/example_plugin/plugin.json`:
```json
{
  "id": "example_plugin",
  "name": "Example Plugin",
  "version": "1.0.0",
  "author": "Logosforge",
  "description": "A minimal example plugin."
}
```

`plugins/example_plugin/plugin.py`:
```python
def register(api):
    api.log("Example plugin loaded.")

    def greet():
        title = api.get_project_title()
        count = api.get_scene_count()
        api.show_message(
            "Hello from Plugin",
            f"Project: {title}\nScenes: {count}",
        )

    api.register_menu_action("Hello from Plugin", greet)
```

## Enable / Disable

Plugins can be enabled or disabled from the **Plugins** view in the sidebar. State changes take effect on next launch.

Enabled state is stored in `~/.storyplanner/settings.json` under `"plugin_states"`.

## Limitations

- Plugins run in the same process as the app (no sandboxing).
- The API is read-only — plugins cannot modify project data directly.
- No dependency resolution between plugins.
- No hot reloading — restart the app after adding or modifying plugins.
- A broken plugin is caught at load time and marked as errored without crashing the app.

---

## Analysis plugins (internal API)

Analysis plugins are a second, richer plugin type used for read-only narrative
*analysis*. Instead of `register(api)`, they subclass `LogosforgePlugin`
(`storyplanner/plugin_base.py`) and implement `execute(context)`:

```python
from storyplanner.plugin_base import LogosforgePlugin, PluginResult, Suggestion

class MyAnalysisPlugin(LogosforgePlugin):
    @property
    def name(self) -> str:
        return "my_analysis"

    @property
    def description(self) -> str:
        return "Flags something interesting about the story."

    requires_scene = False  # set True if the plugin needs an active scene

    def execute(self, context) -> PluginResult:
        suggestions = [
            Suggestion(text="…", category="pacing", severity="warning", target="…"),
        ]
        return PluginResult(plugin_name=self.name, suggestions=suggestions,
                            summary="…", metadata={})
```

The plugin registers itself with `plugin_registry.register_plugin(MyAnalysisPlugin())`
and is run by `plugin_executor.run_plugin(db, project_id, name, scene_id)`, which
builds the context, calls `execute()`, and validates the result (errors are caught
and returned as an error `PluginResult`, never raised).

### `PluginContext` (read-only snapshot)

`execute()` receives an immutable `PluginContext` assembled by
`plugin_executor.build_plugin_context()`:

| Field | Contents |
|-------|----------|
| `project_id`, `project_title` | Identity. |
| `active_scene` | `SceneSnapshot` of the current scene (or `None`). |
| `scenes` | All scenes as `SceneSnapshot`s (title, chapter, plotline, act, goal, conflict, outcome, content, character names, order). |
| `characters` | `CharacterSnapshot`s with `scene_count` and balance `flag`. |
| `psyke_entries` | `PsykeSnapshot`s resolved at the current temporal position (incl. `progression_text`). |
| `memories` | Scored `MemorySnapshot`s (type, target, value, scene label, relevance, superseded). |
| `*_context_text` | Pre-formatted `scene` / `psyke` / `memory` / `graph` / `outline` text blocks for plugins that want raw context. |

### `PluginResult` & `Suggestion`

`PluginResult` carries `plugin_name`, a list of `Suggestion`s, a `summary`, and a
free-form `metadata` dict. Each `Suggestion` has `text`, `category` (grouping
label), `severity` (`info` / `warning` / `critical`), an optional `target`, and an
optional `detail`.

### Bundled analysis plugins

| Plugin | Module | What it does |
|--------|--------|--------------|
| **Character Presence** | `storyplanner/plugins/character_presence.py` | Project-level distribution analysis — disappearances, clustering, dominance, underuse, and character-less scenes. |
| **Dialogue Tension** | `storyplanner/plugins/dialogue_tension.py` | Active-scene analysis of dialogue density, tension signals, line-length rhythm, and silent characters. |

---

## Architecture

Three modules cooperate, plus the two plugin base types:

| Module | Role |
|--------|------|
| `plugin_manager.py` | Discovers external plugins (`discover()`), parses `plugin.json`, loads enabled ones (`load_enabled()`), tracks enable/disable state (`is_enabled` / `set_enabled`, persisted to `plugin_states`), and collects menu actions (`get_all_menu_actions`). Provides the `PluginAPI` handed to `register(api)`. A process-global instance is returned by `get_plugin_manager()`. |
| `plugin_registry.py` | An in-memory registry of internal `LogosforgePlugin` instances — `register_plugin`, `get_plugin`, `list_plugins`, `list_plugins_by_category`, `describe_plugin`. |
| `plugin_executor.py` | Builds a `PluginContext` from the database and runs an analysis plugin safely (`build_plugin_context`, `run_plugin`). |

The **Plugins** view (`ui/plugins_view.py`) lists discovered external plugins,
shows load logs/errors, and toggles their enabled state.

---

## Bundled external plugins

Logosforge ships several reference plugins under `plugins/`:

### Go McKee (`plugins/gomckee/`)
Encodes Robert McKee's craft as automated, **invisible constraints** rather than
quoted advice. It loads three canonical JSON systems unchanged —
`story_system.json`, `character_system.json`, `dialogue_system.json` — each a set
of principles, methods (with rules, applicability, and priority), triggers, and
diagnostic checks, plus a conflict table deciding which method wins when two
collide. A request is classified into the `story` / `character` / `dialogue`
domains (preserving domain purity and nesting order), the matching methods are
activated and rendered as constraints, conflicts are resolved, and checks are run
in revision/diagnosis mode. It is PSYKE-aware when the host exposes project state.
Menu actions toggle it on/off and force a domain focus; the engine also understands
`/gomckee on|off|story|character|dialogue|all|check|explain` commands. See
`plugins/gomckee/README.md`.

### Idea di Controllo (`plugins/idea_di_controllo/`)
A PSYKE-aware narrative compass built on McKee's **Controlling Idea**
(VALUE + CAUSE). It manages the project's controlling idea, marks scene/PSYKE
alignment, can mirror the idea as a PSYKE *theme* entry, and injects an
`[Idea di Controllo]` block into the assistant context. It pairs with the core
`controlling_idea.py` module and the `/idea` command — see
[structure-and-plot.md](structure-and-plot.md#controlling-idea).

### PSYKE Outline Templates (`plugins/psyke_outline_templates/`)
Registers a large catalogue of structure templates beyond the built-ins — across
classical (Hero's Journey, Three-Act, Freytag, Fichtean), modern (Save the Cat,
Story Circle, Seven-Point, 27-chapter), non-Western/alternative (Kishōtenketsu,
Heroine's Journey, In Medias Res, Snowflake), and genre (Mystery, Rom-Com, Quest)
methods. It can infer the best template from the story's genre, conflict, arc,
scope, and pacing, and emit a PSYKE-annotated outline. It feeds the Outline
section's template picker — see
[structure-and-plot.md](structure-and-plot.md#outline).

### Example Plugin (`plugins/example_plugin/`)
The minimal reference implementation shown above.
