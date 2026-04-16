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

    # -- Places --------------------------------------------------------------

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

    # -- Notes ---------------------------------------------------------------

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

    # -- Scenes --------------------------------------------------------------

    def get_scene_by_id(self, scene_id: int) -> Scene | None:
        with Session(self._engine) as session:
            return session.get(Scene, scene_id)

    def get_all_scenes(self, project_id: int) -> list[Scene]:
        with Session(self._engine) as session:
            stmt = (
                select(Scene)
                .where(Scene.project_id == project_id)
                .order_by(Scene.sort_order)
            )
            return list(session.exec(stmt).all())

    def create_scene(
        self,
        project_id: int,
        title: str,
        summary: str = "",
        character_ids: list[int] | None = None,
        place_ids: list[int] | None = None,
    ) -> Scene:
        with Session(self._engine) as session:
            scene = Scene(
                project_id=project_id, title=title, summary=summary
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
        character_ids: list[int] | None = None,
        place_ids: list[int] | None = None,
    ) -> Scene:
        with Session(self._engine) as session:
            scene = session.get(Scene, scene_id)
            scene.title = title
            scene.summary = summary

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
