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
    Place,
    Project,
    Scene,
    SceneCharacterLink,
    ScenePlaceLink,
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

    # -- Projects ------------------------------------------------------------

    def get_project_by_id(self, project_id: int) -> Project | None:
        with Session(self._engine) as session:
            return session.get(Project, project_id)

    def get_all_projects(self) -> list[Project]:
        with Session(self._engine) as session:
            return list(session.exec(select(Project)).all())

    def create_project(self, title: str) -> Project:
        with Session(self._engine) as session:
            project = Project(title=title)
            session.add(project)
            session.commit()
            session.refresh(project)
            return project

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
        chapter: str = "",
        plotline: str = "",
        character_ids: list[int] | None = None,
        place_ids: list[int] | None = None,
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
                chapter=chapter,
                plotline=plotline,
                sort_order=next_order,
            )
            session.add(scene)
            session.flush()  # get scene.id before creating links

            for cid in character_ids or []:
                session.add(SceneCharacterLink(scene_id=scene.id, character_id=cid))
            for pid in place_ids or []:
                session.add(ScenePlaceLink(scene_id=scene.id, place_id=pid))

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
        chapter: str = "",
        plotline: str = "",
        character_ids: list[int] | None = None,
        place_ids: list[int] | None = None,
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

        return results

    def resolve_link(
        self, project_id: int, name: str
    ) -> tuple[str, int] | None:
        name_lower = name.strip().lower()
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

    @staticmethod
    def _matches(query_lower: str, *fields: str) -> bool:
        for field in fields:
            if field and query_lower in field.lower():
                return True
        return False
