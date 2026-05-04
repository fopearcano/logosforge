"""Persistence layer — wraps SQLite via SQLModel.

Usage:
    db = Database("my_story.db")  # file-based
    db = Database()               # in-memory (for tests)

UI code should only call the public methods below (e.g. create_character,
get_all_places). All session management stays inside this module.
"""

from pathlib import Path
from typing import Optional

from sqlmodel import Session, SQLModel, create_engine, select

from storyplanner.models import (
    Character,
    Note,
    OutlineNode,
    Place,
    Project,
    PsykeEntry,
    PsykeProgression,
    PsykeRelation,
    QuantumStateRecord,
    Scene,
    SceneCharacterLink,
    SceneCharacterState,
    ScenePlaceLink,
    StoryMemoryEntry,
)


class Database:
    def __init__(self, path: Optional[str] = None) -> None:
        if path:
            Path(path).parent.mkdir(parents=True, exist_ok=True)
            url = f"sqlite:///{path}"
        else:
            url = "sqlite://"  # in-memory

        self._engine = create_engine(url, echo=False)
        SQLModel.metadata.create_all(self._engine)
        self._migrate()

    def _migrate(self) -> None:
        from sqlalchemy import text
        with self._engine.connect() as conn:
            rows = conn.execute(text("PRAGMA table_info(psykeentry)")).fetchall()
            columns = {row[1] for row in rows}
            if rows and "details_json" not in columns:
                conn.execute(
                    text("ALTER TABLE psykeentry ADD COLUMN details_json TEXT DEFAULT ''")
                )
                conn.commit()

            rows = conn.execute(text("PRAGMA table_info(project)")).fetchall()
            columns = {row[1] for row in rows}
            if rows and "format_mode" not in columns:
                conn.execute(
                    text("ALTER TABLE project ADD COLUMN format_mode TEXT DEFAULT 'novel'")
                )
                conn.commit()
            if rows and "settings_json" not in columns:
                conn.execute(
                    text("ALTER TABLE project ADD COLUMN settings_json TEXT DEFAULT ''")
                )
                conn.commit()

    # -- Projects ------------------------------------------------------------

    def get_project_by_id(self, project_id: int) -> Project | None:
        with Session(self._engine) as session:
            return session.get(Project, project_id)

    def get_all_projects(self) -> list[Project]:
        with Session(self._engine) as session:
            return list(session.exec(select(Project)).all())

    def create_project(self, title: str, format_mode: str = "novel") -> Project:
        with Session(self._engine) as session:
            project = Project(title=title, format_mode=format_mode)
            session.add(project)
            session.commit()
            session.refresh(project)
            return project

    def update_project_format(self, project_id: int, format_mode: str) -> None:
        with Session(self._engine) as session:
            project = session.get(Project, project_id)
            if project:
                project.format_mode = format_mode
                session.commit()

    def get_project_settings(self, project_id: int) -> dict:
        import json
        with Session(self._engine) as session:
            project = session.get(Project, project_id)
            if project and project.settings_json:
                try:
                    return json.loads(project.settings_json)
                except (json.JSONDecodeError, TypeError):
                    return {}
            return {}

    def save_project_settings(self, project_id: int, settings: dict) -> None:
        import json
        with Session(self._engine) as session:
            project = session.get(Project, project_id)
            if project:
                project.settings_json = json.dumps(settings)
                session.commit()

    def get_scoring_weights(self, project_id: int) -> dict[str, float]:
        from storyplanner.quantum_outliner.scoring import DEFAULT_WEIGHTS
        settings = self.get_project_settings(project_id)
        stored = settings.get("scoring_weights")
        if isinstance(stored, dict) and all(k in stored for k in DEFAULT_WEIGHTS):
            return {k: float(stored[k]) for k in DEFAULT_WEIGHTS}
        return dict(DEFAULT_WEIGHTS)

    def set_scoring_weights(self, project_id: int, weights: dict[str, float]) -> None:
        settings = self.get_project_settings(project_id)
        settings["scoring_weights"] = weights
        self.save_project_settings(project_id, settings)

    def get_scoring_preset(self, project_id: int) -> str:
        settings = self.get_project_settings(project_id)
        return settings.get("scoring_preset", "Balanced")

    def set_scoring_preset(self, project_id: int, preset: str) -> None:
        settings = self.get_project_settings(project_id)
        settings["scoring_preset"] = preset
        self.save_project_settings(project_id, settings)

    def get_weight_learning(self, project_id: int) -> bool:
        settings = self.get_project_settings(project_id)
        return settings.get("weight_learning", True)

    def set_weight_learning(self, project_id: int, enabled: bool) -> None:
        settings = self.get_project_settings(project_id)
        settings["weight_learning"] = enabled
        self.save_project_settings(project_id, settings)

    def get_constraints(self, project_id: int) -> list[str]:
        settings = self.get_project_settings(project_id)
        raw = settings.get("constraints")
        if isinstance(raw, list):
            return [str(c) for c in raw if c]
        return []

    def set_constraints(self, project_id: int, constraints: list[str]) -> None:
        settings = self.get_project_settings(project_id)
        settings["constraints"] = constraints
        self.save_project_settings(project_id, settings)

    def add_constraint(self, project_id: int, constraint: str) -> None:
        constraints = self.get_constraints(project_id)
        constraint = constraint.strip()
        if constraint and constraint not in constraints:
            constraints.append(constraint)
            self.set_constraints(project_id, constraints)

    def remove_constraint(self, project_id: int, constraint: str) -> None:
        constraints = self.get_constraints(project_id)
        constraint = constraint.strip()
        if constraint in constraints:
            constraints.remove(constraint)
            self.set_constraints(project_id, constraints)

    def get_show_tradeoffs(self, project_id: int) -> bool:
        settings = self.get_project_settings(project_id)
        return settings.get("show_tradeoffs", False)

    def set_show_tradeoffs(self, project_id: int, enabled: bool) -> None:
        settings = self.get_project_settings(project_id)
        settings["show_tradeoffs"] = enabled
        self.save_project_settings(project_id, settings)

    def get_selection_mode(self, project_id: int) -> str:
        settings = self.get_project_settings(project_id)
        mode = settings.get("selection_mode", "weighted")
        if mode not in ("weighted", "pareto"):
            return "weighted"
        return mode

    def set_selection_mode(self, project_id: int, mode: str) -> None:
        if mode not in ("weighted", "pareto"):
            mode = "weighted"
        settings = self.get_project_settings(project_id)
        settings["selection_mode"] = mode
        self.save_project_settings(project_id, settings)

    def get_ensemble_alpha(self, project_id: int) -> float:
        settings = self.get_project_settings(project_id)
        val = settings.get("ensemble_alpha", 0.7)
        try:
            return max(0.0, min(float(val), 1.0))
        except (TypeError, ValueError):
            return 0.7

    def set_ensemble_alpha(self, project_id: int, alpha: float) -> None:
        settings = self.get_project_settings(project_id)
        settings["ensemble_alpha"] = max(0.0, min(float(alpha), 1.0))
        self.save_project_settings(project_id, settings)

    # -- Characters ----------------------------------------------------------

    def get_character_by_id(self, character_id: int) -> Character | None:
        with Session(self._engine) as session:
            return session.get(Character, character_id)

    def get_all_characters(self, project_id: int) -> list[Character]:
        with Session(self._engine) as session:
            stmt = select(Character).where(Character.project_id == project_id)
            return list(session.exec(stmt).all())

    def create_character(
        self, project_id: int, name: str, description: str = ""
    ) -> Character:
        with Session(self._engine) as session:
            character = Character(
                project_id=project_id, name=name, description=description
            )
            session.add(character)
            session.commit()
            session.refresh(character)
            return character

    def update_character(
        self, character_id: int, name: str, description: str = ""
    ) -> Character:
        with Session(self._engine) as session:
            character = session.get(Character, character_id)
            character.name = name
            character.description = description
            session.commit()
            session.refresh(character)
            return character

    def delete_character(self, character_id: int) -> None:
        with Session(self._engine) as session:
            # Remove scene links
            for link in session.exec(
                select(SceneCharacterLink).where(
                    SceneCharacterLink.character_id == character_id
                )
            ).all():
                session.delete(link)
            character = session.get(Character, character_id)
            if character:
                session.delete(character)
            session.commit()

    # -- Places --------------------------------------------------------------

    def get_place_by_id(self, place_id: int) -> Place | None:
        with Session(self._engine) as session:
            return session.get(Place, place_id)

    def get_all_places(self, project_id: int) -> list[Place]:
        with Session(self._engine) as session:
            stmt = select(Place).where(Place.project_id == project_id)
            return list(session.exec(stmt).all())

    def create_place(
        self, project_id: int, name: str, description: str = ""
    ) -> Place:
        with Session(self._engine) as session:
            place = Place(
                project_id=project_id, name=name, description=description
            )
            session.add(place)
            session.commit()
            session.refresh(place)
            return place

    def update_place(
        self, place_id: int, name: str, description: str = ""
    ) -> Place:
        with Session(self._engine) as session:
            place = session.get(Place, place_id)
            place.name = name
            place.description = description
            session.commit()
            session.refresh(place)
            return place

    def delete_place(self, place_id: int) -> None:
        with Session(self._engine) as session:
            # Remove scene links
            for link in session.exec(
                select(ScenePlaceLink).where(
                    ScenePlaceLink.place_id == place_id
                )
            ).all():
                session.delete(link)
            place = session.get(Place, place_id)
            if place:
                session.delete(place)
            session.commit()

    # -- Notes ---------------------------------------------------------------

    def get_note_by_id(self, note_id: int) -> Note | None:
        with Session(self._engine) as session:
            return session.get(Note, note_id)

    def get_all_notes(self, project_id: int) -> list[Note]:
        with Session(self._engine) as session:
            stmt = select(Note).where(Note.project_id == project_id)
            return list(session.exec(stmt).all())

    def create_note(
        self, project_id: int, title: str, content: str = ""
    ) -> Note:
        with Session(self._engine) as session:
            note = Note(
                project_id=project_id, title=title, content=content
            )
            session.add(note)
            session.commit()
            session.refresh(note)
            return note

    def update_note(
        self, note_id: int, title: str, content: str = ""
    ) -> Note:
        with Session(self._engine) as session:
            note = session.get(Note, note_id)
            note.title = title
            note.content = content
            session.commit()
            session.refresh(note)
            return note

    def delete_note(self, note_id: int) -> None:
        with Session(self._engine) as session:
            note = session.get(Note, note_id)
            if note:
                session.delete(note)
            session.commit()

    # -- Scenes --------------------------------------------------------------

    def get_scene_by_id(self, scene_id: int) -> Scene | None:
        with Session(self._engine) as session:
            return session.get(Scene, scene_id)

    def get_all_scenes(
        self,
        project_id: int,
        chapter: str | None = None,
        plotline: str | None = None,
        tag: str | None = None,
    ) -> list[Scene]:
        with Session(self._engine) as session:
            stmt = select(Scene).where(Scene.project_id == project_id)
            if chapter is not None:
                stmt = stmt.where(Scene.chapter == chapter)
            if plotline is not None:
                stmt = stmt.where(Scene.plotline == plotline)
            stmt = stmt.order_by(Scene.sort_order, Scene.id)
            scenes = list(session.exec(stmt).all())
            if tag is not None:
                tag_lower = tag.lower()
                scenes = [
                    s for s in scenes
                    if any(t.strip().lower() == tag_lower for t in s.tags.split(","))
                ]
            return scenes

    def get_scene_chapters(self, project_id: int) -> list[str]:
        with Session(self._engine) as session:
            stmt = (
                select(Scene.chapter)
                .where(Scene.project_id == project_id)
                .where(Scene.chapter != "")
                .distinct()
            )
            return list(session.exec(stmt).all())

    def get_scene_plotlines(self, project_id: int) -> list[str]:
        with Session(self._engine) as session:
            stmt = (
                select(Scene.plotline)
                .where(Scene.project_id == project_id)
                .where(Scene.plotline != "")
                .distinct()
            )
            return list(session.exec(stmt).all())

    def get_scene_tags(self, project_id: int) -> list[str]:
        with Session(self._engine) as session:
            stmt = (
                select(Scene.tags)
                .where(Scene.project_id == project_id)
                .where(Scene.tags != "")
            )
            raw = list(session.exec(stmt).all())
        tags: set[str] = set()
        for csv_tags in raw:
            for tag in csv_tags.split(","):
                tag = tag.strip()
                if tag:
                    tags.add(tag)
        return sorted(tags)

    def create_scene(
        self,
        project_id: int,
        title: str,
        summary: str = "",
        synopsis: str = "",
        goal: str = "",
        conflict: str = "",
        outcome: str = "",
        beat: str = "",
        tags: str = "",
        act: str = "",
        content: str = "",
        chapter: str = "",
        plotline: str = "",
        character_ids: list[int] | None = None,
        place_ids: list[int] | None = None,
        character_states: list[tuple[int, str]] | None = None,
    ) -> Scene:
        with Session(self._engine) as session:
            # Assign next sort_order
            from sqlalchemy import func

            max_order = session.exec(
                select(func.max(Scene.sort_order)).where(
                    Scene.project_id == project_id
                )
            ).one()
            next_order = (max_order or 0) + 1

            scene = Scene(
                project_id=project_id,
                title=title,
                summary=summary,
                synopsis=synopsis,
                goal=goal,
                conflict=conflict,
                outcome=outcome,
                beat=beat,
                tags=tags,
                act=act,
                content=content,
                chapter=chapter,
                plotline=plotline,
                sort_order=next_order,
            )
            session.add(scene)
            session.flush()

            for cid in character_ids or []:
                session.add(SceneCharacterLink(scene_id=scene.id, character_id=cid))
            for pid in place_ids or []:
                session.add(ScenePlaceLink(scene_id=scene.id, place_id=pid))
            for char_id, state in character_states or []:
                session.add(SceneCharacterState(
                    scene_id=scene.id, character_id=char_id, state=state,
                ))

            session.commit()
            session.refresh(scene)
            return scene

    def update_scene(
        self,
        scene_id: int,
        title: str,
        summary: str = "",
        synopsis: str = "",
        goal: str = "",
        conflict: str = "",
        outcome: str = "",
        beat: str = "",
        tags: str = "",
        act: str = "",
        content: str = "",
        chapter: str = "",
        plotline: str = "",
        character_ids: list[int] | None = None,
        place_ids: list[int] | None = None,
        character_states: list[tuple[int, str]] | None = None,
    ) -> Scene:
        with Session(self._engine) as session:
            scene = session.get(Scene, scene_id)
            scene.title = title
            scene.summary = summary
            scene.synopsis = synopsis
            scene.goal = goal
            scene.conflict = conflict
            scene.outcome = outcome
            scene.beat = beat
            scene.tags = tags
            scene.act = act
            scene.content = content
            scene.chapter = chapter
            scene.plotline = plotline

            # Replace character links
            old_char_links = session.exec(
                select(SceneCharacterLink).where(
                    SceneCharacterLink.scene_id == scene_id
                )
            ).all()
            for link in old_char_links:
                session.delete(link)
            for cid in character_ids or []:
                session.add(SceneCharacterLink(scene_id=scene_id, character_id=cid))

            # Replace place links
            old_place_links = session.exec(
                select(ScenePlaceLink).where(
                    ScenePlaceLink.scene_id == scene_id
                )
            ).all()
            for link in old_place_links:
                session.delete(link)
            for pid in place_ids or []:
                session.add(ScenePlaceLink(scene_id=scene_id, place_id=pid))

            # Replace character states
            old_states = session.exec(
                select(SceneCharacterState).where(
                    SceneCharacterState.scene_id == scene_id
                )
            ).all()
            for st in old_states:
                session.delete(st)
            for char_id, state in character_states or []:
                session.add(SceneCharacterState(
                    scene_id=scene_id, character_id=char_id, state=state,
                ))

            session.commit()
            session.refresh(scene)
            return scene

    def delete_scene(self, scene_id: int) -> None:
        with Session(self._engine) as session:
            # Delete links first
            for link in session.exec(
                select(SceneCharacterLink).where(
                    SceneCharacterLink.scene_id == scene_id
                )
            ).all():
                session.delete(link)
            for link in session.exec(
                select(ScenePlaceLink).where(
                    ScenePlaceLink.scene_id == scene_id
                )
            ).all():
                session.delete(link)
            for st in session.exec(
                select(SceneCharacterState).where(
                    SceneCharacterState.scene_id == scene_id
                )
            ).all():
                session.delete(st)

            # Delete the scene
            scene = session.get(Scene, scene_id)
            if scene:
                session.delete(scene)
            session.commit()

    def move_scene_up(self, scene_id: int) -> None:
        """Swap sort_order with the scene directly above (lower sort_order)."""
        with Session(self._engine) as session:
            scene = session.get(Scene, scene_id)
            if scene is None:
                return

            # Find the scene just before this one
            stmt = (
                select(Scene)
                .where(Scene.project_id == scene.project_id)
                .where(
                    (Scene.sort_order < scene.sort_order)
                    | (
                        (Scene.sort_order == scene.sort_order)
                        & (Scene.id < scene.id)
                    )
                )
                .order_by(Scene.sort_order.desc(), Scene.id.desc())
            )
            prev_scene = session.exec(stmt).first()
            if prev_scene is None:
                return  # already first

            # Swap sort_order values
            scene.sort_order, prev_scene.sort_order = (
                prev_scene.sort_order,
                scene.sort_order,
            )
            session.commit()

    def move_scene_down(self, scene_id: int) -> None:
        """Swap sort_order with the scene directly below (higher sort_order)."""
        with Session(self._engine) as session:
            scene = session.get(Scene, scene_id)
            if scene is None:
                return

            # Find the scene just after this one
            stmt = (
                select(Scene)
                .where(Scene.project_id == scene.project_id)
                .where(
                    (Scene.sort_order > scene.sort_order)
                    | (
                        (Scene.sort_order == scene.sort_order)
                        & (Scene.id > scene.id)
                    )
                )
                .order_by(Scene.sort_order, Scene.id)
            )
            next_scene = session.exec(stmt).first()
            if next_scene is None:
                return  # already last

            # Swap sort_order values
            scene.sort_order, next_scene.sort_order = (
                next_scene.sort_order,
                scene.sort_order,
            )
            session.commit()

    def update_scene_plotline(self, scene_id: int, plotline: str) -> None:
        with Session(self._engine) as session:
            scene = session.get(Scene, scene_id)
            if scene is None:
                return
            scene.plotline = plotline
            session.commit()

    def update_scene_content(self, scene_id: int, content: str) -> None:
        with Session(self._engine) as session:
            scene = session.get(Scene, scene_id)
            if scene is None:
                return
            scene.content = content
            session.commit()

    def update_scene_synopsis(self, scene_id: int, synopsis: str) -> None:
        with Session(self._engine) as session:
            scene = session.get(Scene, scene_id)
            if scene is None:
                return
            scene.synopsis = synopsis
            session.commit()

    def update_scene_summary(self, scene_id: int, summary: str) -> None:
        with Session(self._engine) as session:
            scene = session.get(Scene, scene_id)
            if scene is None:
                return
            scene.summary = summary
            session.commit()

    def reorder_scene(self, scene_id: int, new_index: int) -> None:
        """Move a scene to a new position (0-based) among all project scenes."""
        with Session(self._engine) as session:
            scene = session.get(Scene, scene_id)
            if scene is None:
                return

            stmt = (
                select(Scene)
                .where(Scene.project_id == scene.project_id)
                .order_by(Scene.sort_order, Scene.id)
            )
            all_scenes = list(session.exec(stmt).all())

            old_index = next(
                (i for i, s in enumerate(all_scenes) if s.id == scene_id), None
            )
            if old_index is None:
                return

            moved = all_scenes.pop(old_index)
            new_index = max(0, min(new_index, len(all_scenes)))
            all_scenes.insert(new_index, moved)

            for i, s in enumerate(all_scenes):
                s.sort_order = i
            session.commit()

    def get_scene_character_ids(self, scene_id: int) -> list[int]:
        with Session(self._engine) as session:
            stmt = select(SceneCharacterLink.character_id).where(
                SceneCharacterLink.scene_id == scene_id
            )
            return list(session.exec(stmt).all())

    def get_scene_place_ids(self, scene_id: int) -> list[int]:
        with Session(self._engine) as session:
            stmt = select(ScenePlaceLink.place_id).where(
                ScenePlaceLink.scene_id == scene_id
            )
            return list(session.exec(stmt).all())

    def get_scene_character_states(
        self, scene_id: int
    ) -> list[tuple[int, str]]:
        with Session(self._engine) as session:
            stmt = select(SceneCharacterState).where(
                SceneCharacterState.scene_id == scene_id
            )
            return [
                (s.character_id, s.state)
                for s in session.exec(stmt).all()
            ]

    def get_character_arc(
        self, project_id: int, character_id: int
    ) -> list[tuple[int, str, int, str]]:
        scenes = self.get_all_scenes(project_id)
        arc: list[tuple[int, str, int, str]] = []
        for idx, scene in enumerate(scenes):
            for cid, state in self.get_scene_character_states(scene.id):
                if cid == character_id:
                    arc.append((scene.id, scene.title, idx + 1, state))
        return arc

    # -- PSYKE (Story Bible) ------------------------------------------------

    def get_psyke_entry_by_id(self, entry_id: int) -> PsykeEntry | None:
        with Session(self._engine) as session:
            return session.get(PsykeEntry, entry_id)

    def get_all_psyke_entries(self, project_id: int) -> list[PsykeEntry]:
        with Session(self._engine) as session:
            stmt = select(PsykeEntry).where(
                PsykeEntry.project_id == project_id
            )
            return list(session.exec(stmt).all())

    def create_psyke_entry(
        self,
        project_id: int,
        name: str,
        entry_type: str = "other",
        aliases: str = "",
        notes: str = "",
        is_global: bool = False,
        details: dict | None = None,
    ) -> PsykeEntry:
        import json
        with Session(self._engine) as session:
            entry = PsykeEntry(
                project_id=project_id,
                name=name,
                entry_type=entry_type,
                aliases=aliases,
                notes=notes,
                is_global=is_global,
                details_json=json.dumps(details) if details else "",
            )
            session.add(entry)
            session.commit()
            session.refresh(entry)
            return entry

    def update_psyke_entry(
        self,
        entry_id: int,
        name: str,
        entry_type: str = "other",
        aliases: str = "",
        notes: str = "",
        is_global: bool = False,
        details: dict | None = None,
    ) -> PsykeEntry:
        import json
        with Session(self._engine) as session:
            entry = session.get(PsykeEntry, entry_id)
            entry.name = name
            entry.entry_type = entry_type
            entry.aliases = aliases
            entry.notes = notes
            entry.is_global = is_global
            if details is not None:
                entry.details_json = json.dumps(details)
            session.commit()
            session.refresh(entry)
            return entry

    def get_psyke_entry_details(self, entry_id: int) -> dict:
        import json
        entry = self.get_psyke_entry_by_id(entry_id)
        if entry is None:
            return {}
        try:
            return json.loads(entry.details_json) if entry.details_json else {}
        except (json.JSONDecodeError, TypeError):
            return {}

    def delete_psyke_entry(self, entry_id: int) -> None:
        with Session(self._engine) as session:
            for rel in session.exec(
                select(PsykeRelation).where(
                    (PsykeRelation.entry_id == entry_id)
                    | (PsykeRelation.related_entry_id == entry_id)
                )
            ).all():
                session.delete(rel)
            for prog in session.exec(
                select(PsykeProgression).where(
                    PsykeProgression.entry_id == entry_id
                )
            ).all():
                session.delete(prog)
            entry = session.get(PsykeEntry, entry_id)
            if entry:
                session.delete(entry)
            session.commit()

    # -- PSYKE Relations -----------------------------------------------------

    def get_related_psyke_entries(self, entry_id: int) -> list[PsykeEntry]:
        with Session(self._engine) as session:
            stmt = select(PsykeRelation.related_entry_id).where(
                PsykeRelation.entry_id == entry_id
            )
            related_ids = list(session.exec(stmt).all())
            if not related_ids:
                return []
            return list(
                session.exec(
                    select(PsykeEntry).where(PsykeEntry.id.in_(related_ids))
                ).all()
            )

    def add_psyke_relation(self, entry_id: int, related_entry_id: int) -> None:
        if entry_id == related_entry_id:
            return
        with Session(self._engine) as session:
            existing = session.get(PsykeRelation, (entry_id, related_entry_id))
            if existing:
                return
            session.add(PsykeRelation(entry_id=entry_id, related_entry_id=related_entry_id))
            session.add(PsykeRelation(entry_id=related_entry_id, related_entry_id=entry_id))
            session.commit()

    def remove_psyke_relation(self, entry_id: int, related_entry_id: int) -> None:
        with Session(self._engine) as session:
            for a, b in [(entry_id, related_entry_id), (related_entry_id, entry_id)]:
                rel = session.get(PsykeRelation, (a, b))
                if rel:
                    session.delete(rel)
            session.commit()

    # -- PSYKE Progressions --------------------------------------------------

    def get_psyke_progression_by_id(self, progression_id: int) -> PsykeProgression | None:
        with Session(self._engine) as session:
            return session.get(PsykeProgression, progression_id)

    def get_psyke_progressions(self, entry_id: int) -> list[PsykeProgression]:
        with Session(self._engine) as session:
            stmt = (
                select(PsykeProgression)
                .where(PsykeProgression.entry_id == entry_id)
                .order_by(PsykeProgression.sort_order, PsykeProgression.id)
            )
            return list(session.exec(stmt).all())

    def create_psyke_progression(
        self,
        entry_id: int,
        text: str,
        scene_id: int | None = None,
    ) -> PsykeProgression:
        with Session(self._engine) as session:
            from sqlalchemy import func

            max_order = session.exec(
                select(func.max(PsykeProgression.sort_order)).where(
                    PsykeProgression.entry_id == entry_id
                )
            ).one()
            next_order = (max_order or 0) + 1

            prog = PsykeProgression(
                entry_id=entry_id,
                text=text,
                scene_id=scene_id,
                sort_order=next_order,
            )
            session.add(prog)
            session.commit()
            session.refresh(prog)
            return prog

    def update_psyke_progression(
        self,
        progression_id: int,
        text: str,
        scene_id: int | None = None,
    ) -> PsykeProgression:
        with Session(self._engine) as session:
            prog = session.get(PsykeProgression, progression_id)
            prog.text = text
            prog.scene_id = scene_id
            session.commit()
            session.refresh(prog)
            return prog

    def delete_psyke_progression(self, progression_id: int) -> None:
        with Session(self._engine) as session:
            prog = session.get(PsykeProgression, progression_id)
            if prog:
                session.delete(prog)
            session.commit()

    # -- Search --------------------------------------------------------------

    def search_project(
        self, project_id: int, query: str
    ) -> list[dict]:
        query_lower = query.lower()
        results: list[dict] = []

        for char in self.get_all_characters(project_id):
            if self._matches(query_lower, char.name, char.description):
                results.append(
                    {"type": "Character", "id": char.id, "label": char.name,
                     "preview": char.description}
                )

        for place in self.get_all_places(project_id):
            if self._matches(query_lower, place.name, place.description):
                results.append(
                    {"type": "Place", "id": place.id, "label": place.name,
                     "preview": place.description}
                )

        for note in self.get_all_notes(project_id):
            if self._matches(query_lower, note.title, note.content):
                results.append(
                    {"type": "Note", "id": note.id, "label": note.title,
                     "preview": note.content}
                )

        for scene in self.get_all_scenes(project_id):
            if self._matches(
                query_lower, scene.title, scene.summary,
                scene.chapter, scene.plotline, scene.beat, scene.tags,
            ):
                results.append(
                    {"type": "Scene", "id": scene.id, "label": scene.title,
                     "preview": scene.summary,
                     "chapter": scene.chapter, "plotline": scene.plotline,
                     "tags": scene.tags}
                )

        for entry in self.get_all_psyke_entries(project_id):
            if self._matches(query_lower, entry.name, entry.aliases, entry.notes):
                results.append(
                    {"type": "PSYKE", "id": entry.id, "label": entry.name,
                     "preview": entry.notes}
                )

        return results

    def resolve_link(
        self, project_id: int, name: str
    ) -> tuple[str, int] | None:
        name_lower = name.strip().lower()
        for entry in self.get_all_psyke_entries(project_id):
            if entry.name.lower() == name_lower:
                return ("PsykeEntry", entry.id)
            if entry.aliases:
                for alias in entry.aliases.split(","):
                    if alias.strip().lower() == name_lower:
                        return ("PsykeEntry", entry.id)
        for char in self.get_all_characters(project_id):
            if char.name.lower() == name_lower:
                return ("Character", char.id)
        for place in self.get_all_places(project_id):
            if place.name.lower() == name_lower:
                return ("Place", place.id)
        for scene in self.get_all_scenes(project_id):
            if scene.title.lower() == name_lower:
                return ("Scene", scene.id)
        for note in self.get_all_notes(project_id):
            if note.title.lower() == name_lower:
                return ("Note", note.id)
        return None

    def find_backlinks(
        self, project_id: int, name: str
    ) -> list[tuple[str, int, str]]:
        import re
        pattern = re.compile(
            r"\[\[" + re.escape(name) + r"\]\]", re.IGNORECASE
        )
        results: list[tuple[str, int, str]] = []

        for scene in self.get_all_scenes(project_id):
            fields = (
                scene.summary, scene.synopsis, scene.goal,
                scene.conflict, scene.outcome,
            )
            if any(pattern.search(f) for f in fields if f):
                results.append(("Scene", scene.id, scene.title))

        for note in self.get_all_notes(project_id):
            if note.content and pattern.search(note.content):
                results.append(("Note", note.id, note.title))

        return results

    def build_link_graph(
        self, project_id: int
    ) -> tuple[list[tuple[str, int, str]], list[tuple[str, str]]]:
        import re
        link_pat = re.compile(r"\[\[(.+?)\]\]")

        entity_info: dict[str, tuple[str, int, str]] = {}
        for char in self.get_all_characters(project_id):
            entity_info[char.name.lower()] = ("Character", char.id, char.name)
        for place in self.get_all_places(project_id):
            entity_info[place.name.lower()] = ("Place", place.id, place.name)
        for scene in self.get_all_scenes(project_id):
            entity_info[scene.title.lower()] = ("Scene", scene.id, scene.title)
        for note in self.get_all_notes(project_id):
            entity_info[note.title.lower()] = ("Note", note.id, note.title)

        edges: list[tuple[str, str]] = []
        connected: set[str] = set()

        def _scan(source_name: str, *fields: str) -> None:
            for field in fields:
                if not field:
                    continue
                for match in link_pat.finditer(field):
                    target = match.group(1)
                    if target.lower() in entity_info:
                        edges.append((source_name, target))
                        connected.add(source_name.lower())
                        connected.add(target.lower())

        for scene in self.get_all_scenes(project_id):
            _scan(
                scene.title,
                scene.summary, scene.synopsis, scene.goal,
                scene.conflict, scene.outcome,
            )
        for note in self.get_all_notes(project_id):
            _scan(note.title, note.content)

        nodes: list[tuple[str, int, str]] = []
        for key in sorted(connected):
            if key in entity_info:
                nodes.append(entity_info[key])

        return nodes, edges

    # -- Story Memory -----------------------------------------------------------

    def add_memory(
        self,
        project_id: int,
        scene_id: int,
        memory_type: str,
        target: str,
        value: str,
    ) -> StoryMemoryEntry:
        with Session(self._engine) as session:
            entry = StoryMemoryEntry(
                project_id=project_id,
                scene_id=scene_id,
                memory_type=memory_type,
                target=target,
                value=value,
            )
            session.add(entry)
            session.commit()
            session.refresh(entry)
            return entry

    def get_memories(
        self, project_id: int, scene_id: int | None = None
    ) -> list[StoryMemoryEntry]:
        with Session(self._engine) as session:
            stmt = select(StoryMemoryEntry).where(
                StoryMemoryEntry.project_id == project_id
            )
            if scene_id is not None:
                stmt = stmt.where(StoryMemoryEntry.scene_id == scene_id)
            stmt = stmt.order_by(StoryMemoryEntry.scene_id, StoryMemoryEntry.id)
            return list(session.exec(stmt).all())

    def get_memories_by_type(
        self, project_id: int, memory_type: str
    ) -> list[StoryMemoryEntry]:
        with Session(self._engine) as session:
            stmt = (
                select(StoryMemoryEntry)
                .where(StoryMemoryEntry.project_id == project_id)
                .where(StoryMemoryEntry.memory_type == memory_type)
                .order_by(StoryMemoryEntry.scene_id, StoryMemoryEntry.id)
            )
            return list(session.exec(stmt).all())

    def delete_memories_for_scene(self, scene_id: int) -> None:
        with Session(self._engine) as session:
            stmt = select(StoryMemoryEntry).where(
                StoryMemoryEntry.scene_id == scene_id
            )
            for entry in session.exec(stmt).all():
                session.delete(entry)
            session.commit()

    def memory_exists(
        self, scene_id: int, memory_type: str, target: str
    ) -> bool:
        with Session(self._engine) as session:
            stmt = (
                select(StoryMemoryEntry)
                .where(StoryMemoryEntry.scene_id == scene_id)
                .where(StoryMemoryEntry.memory_type == memory_type)
                .where(StoryMemoryEntry.target == target)
            )
            return session.exec(stmt).first() is not None

    # -- Outline Nodes -------------------------------------------------------

    def get_outline_nodes(self, project_id: int) -> list[OutlineNode]:
        with Session(self._engine) as session:
            stmt = (
                select(OutlineNode)
                .where(OutlineNode.project_id == project_id)
                .order_by(OutlineNode.sort_order, OutlineNode.id)
            )
            return list(session.exec(stmt).all())

    def get_outline_node_by_id(self, node_id: int) -> OutlineNode | None:
        with Session(self._engine) as session:
            return session.get(OutlineNode, node_id)

    def get_outline_children(
        self, project_id: int, parent_id: int | None,
    ) -> list[OutlineNode]:
        with Session(self._engine) as session:
            stmt = (
                select(OutlineNode)
                .where(OutlineNode.project_id == project_id)
                .where(OutlineNode.parent_id == parent_id)
                .order_by(OutlineNode.sort_order, OutlineNode.id)
            )
            return list(session.exec(stmt).all())

    def create_outline_node(
        self,
        project_id: int,
        title: str,
        description: str = "",
        parent_id: int | None = None,
        sort_order: int = 0,
    ) -> OutlineNode:
        with Session(self._engine) as session:
            node = OutlineNode(
                project_id=project_id,
                parent_id=parent_id,
                title=title,
                description=description,
                sort_order=sort_order,
            )
            session.add(node)
            session.commit()
            session.refresh(node)
            return node

    def update_outline_node(
        self,
        node_id: int,
        title: str | None = None,
        description: str | None = None,
        sort_order: int | None = None,
    ) -> None:
        with Session(self._engine) as session:
            node = session.get(OutlineNode, node_id)
            if node is None:
                return
            if title is not None:
                node.title = title
            if description is not None:
                node.description = description
            if sort_order is not None:
                node.sort_order = sort_order
            session.commit()

    def delete_outline_node(self, node_id: int) -> None:
        with Session(self._engine) as session:
            children = session.exec(
                select(OutlineNode).where(OutlineNode.parent_id == node_id)
            ).all()
            for child in children:
                self.delete_outline_node(child.id)
            node = session.get(OutlineNode, node_id)
            if node:
                session.delete(node)
                session.commit()

    def delete_all_outline_nodes(self, project_id: int) -> None:
        with Session(self._engine) as session:
            nodes = session.exec(
                select(OutlineNode)
                .where(OutlineNode.project_id == project_id)
            ).all()
            for node in nodes:
                session.delete(node)
            session.commit()

    # -- Decision Log --------------------------------------------------------

    def get_decision_log(self, project_id: int) -> list[dict]:
        settings = self.get_project_settings(project_id)
        raw = settings.get("decision_log")
        if isinstance(raw, list):
            return raw
        return []

    def append_decision(self, project_id: int, entry: dict) -> None:
        settings = self.get_project_settings(project_id)
        log = settings.get("decision_log")
        if not isinstance(log, list):
            log = []
        log.append(entry)
        settings["decision_log"] = log
        self.save_project_settings(project_id, settings)

    def clear_decision_log(self, project_id: int) -> None:
        settings = self.get_project_settings(project_id)
        settings["decision_log"] = []
        self.save_project_settings(project_id, settings)

    # -- Quantum State --------------------------------------------------------

    def get_quantum_state_json(self, project_id: int) -> str:
        with Session(self._engine) as session:
            record = session.get(QuantumStateRecord, project_id)
            return record.state_json if record else ""

    def save_quantum_state_json(self, project_id: int, state_json: str) -> None:
        from datetime import datetime, timezone
        with Session(self._engine) as session:
            record = session.get(QuantumStateRecord, project_id)
            if record is None:
                record = QuantumStateRecord(
                    project_id=project_id,
                    state_json=state_json,
                    updated_at=datetime.now(timezone.utc),
                )
                session.add(record)
            else:
                record.state_json = state_json
                record.updated_at = datetime.now(timezone.utc)
            session.commit()

    @staticmethod
    def _matches(query_lower: str, *fields: str) -> bool:
        for field in fields:
            if field and query_lower in field.lower():
                return True
        return False
