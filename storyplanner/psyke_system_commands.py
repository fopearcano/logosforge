"""PSYKE system command handlers — /create, /open, /go."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from storyplanner.psyke_command_registry import CommandContext, CommandRegistry

if TYPE_CHECKING:
    from storyplanner.db import Database


class SystemCommandHandlers:
    """Stateful handler set that holds references to db and UI callbacks."""

    def __init__(
        self,
        db: Database,
        project_id: int,
        *,
        open_scene: Any | None = None,
        open_psyke_entry: Any | None = None,
        navigate_section: Any | None = None,
        get_active_scene_id: Any | None = None,
        on_data_changed: Any | None = None,
    ) -> None:
        self._db = db
        self._project_id = project_id
        self._open_scene = open_scene
        self._open_psyke_entry = open_psyke_entry
        self._navigate_section = navigate_section
        self._get_active_scene_id = get_active_scene_id
        self._on_data_changed = on_data_changed

    def register_all(self, registry: CommandRegistry) -> None:
        registry.register("create", self.handle_create, description="Create a PSYKE entry")
        registry.register("open", self.handle_open, description="Open a scene or entry")
        registry.register("go", self.handle_go, description="Navigate scenes", aliases=["goto"])

    def handle_create(self, ctx: CommandContext) -> dict:
        entry_type = ctx.first_arg.lower() if ctx.first_arg else "other"
        valid_types = ("character", "place", "object", "lore", "theme", "other")
        if entry_type not in valid_types:
            return {"ok": False, "error": f"Unknown type '{entry_type}'. Use: {', '.join(valid_types)}"}

        name = ctx.arg_text_after(1) if len(ctx.args) > 1 else ""
        if not name:
            name = f"New {entry_type.title()}"

        entry = self._db.create_psyke_entry(self._project_id, name, entry_type)
        if self._on_data_changed:
            self._on_data_changed()
        if self._open_psyke_entry:
            self._open_psyke_entry(entry.id)
        return {"ok": True, "entry_id": entry.id, "name": entry.name, "type": entry.entry_type}

    def handle_open(self, ctx: CommandContext) -> dict:
        if not ctx.args:
            return {"ok": False, "error": "Usage: /open scene <id> | /open psyke <name>"}

        target = ctx.args[0].lower()
        rest = ctx.args[1:]

        if target == "scene":
            return self._open_scene_by_arg(rest)

        if target == "psyke":
            return self._open_psyke_by_arg(rest)

        return {"ok": False, "error": f"Unknown target '{target}'. Use: scene, psyke"}

    def handle_go(self, ctx: CommandContext) -> dict:
        if not ctx.args:
            return {"ok": False, "error": "Usage: /go scene next|previous|<id>"}

        target = ctx.args[0].lower()
        rest = ctx.args[1:]

        if target == "scene":
            return self._go_scene(rest)

        return {"ok": False, "error": f"Unknown target '{target}'. Use: scene"}

    def _open_scene_by_arg(self, args: list[str]) -> dict:
        if not args:
            return {"ok": False, "error": "Usage: /open scene <id>"}

        try:
            scene_id = int(args[0])
        except ValueError:
            return {"ok": False, "error": f"Invalid scene id: '{args[0]}'"}

        scene = self._db.get_scene_by_id(scene_id)
        if scene is None or scene.project_id != self._project_id:
            return {"ok": False, "error": f"Scene {scene_id} not found"}

        if self._open_scene:
            self._open_scene(scene_id)
        return {"ok": True, "scene_id": scene_id}

    def _open_psyke_by_arg(self, args: list[str]) -> dict:
        if not args:
            return {"ok": False, "error": "Usage: /open psyke <name>"}

        query = " ".join(args).strip()
        from storyplanner.psyke_search import PsykeSearchIndex

        index = PsykeSearchIndex(self._db, self._project_id)
        result = index.resolve_entity(query)
        if result is None:
            return {"ok": False, "error": f"No entry matching '{query}'"}

        if self._open_psyke_entry:
            self._open_psyke_entry(result.entry_id)
        return {"ok": True, "entry_id": result.entry_id, "name": result.name}

    def _go_scene(self, args: list[str]) -> dict:
        if not args:
            return {"ok": False, "error": "Usage: /go scene next|previous|<id>"}

        direction = args[0].lower()

        if direction not in ("next", "previous", "prev"):
            try:
                scene_id = int(direction)
            except ValueError:
                return {"ok": False, "error": f"Unknown direction '{direction}'. Use: next, previous, or a scene id"}
            scene = self._db.get_scene_by_id(scene_id)
            if scene is None or scene.project_id != self._project_id:
                return {"ok": False, "error": f"Scene {scene_id} not found"}
            if self._open_scene:
                self._open_scene(scene_id)
            return {"ok": True, "scene_id": scene_id}

        scenes = self._db.get_all_scenes(self._project_id)
        if not scenes:
            return {"ok": False, "error": "No scenes in project"}

        current_id = self._get_active_scene_id() if self._get_active_scene_id else None
        if current_id is None:
            target = scenes[0]
        else:
            ids = [s.id for s in scenes]
            try:
                idx = ids.index(current_id)
            except ValueError:
                target = scenes[0]
                idx = -1

            if direction == "next":
                idx = min(idx + 1, len(scenes) - 1)
            else:
                idx = max(idx - 1, 0)
            target = scenes[idx]

        if self._open_scene:
            self._open_scene(target.id)
        return {"ok": True, "scene_id": target.id}
