"""Persistence layer — wraps SQLite via SQLModel.

Usage:
    db = Database("my_story.db")  # file-based
    db = Database()               # in-memory (for tests)

All public methods open their own session so callers don't manage sessions.
"""

from pathlib import Path
from typing import Optional, Type, TypeVar

from sqlmodel import Session, SQLModel, create_engine, select

T = TypeVar("T", bound=SQLModel)


class Database:
    def __init__(self, path: Optional[str] = None) -> None:
        if path:
            # Ensure parent directories exist
            Path(path).parent.mkdir(parents=True, exist_ok=True)
            url = f"sqlite:///{path}"
        else:
            url = "sqlite://"  # in-memory

        self._engine = create_engine(url, echo=False)
        SQLModel.metadata.create_all(self._engine)

    # -- Generic CRUD helpers ------------------------------------------------

    def add(self, instance: SQLModel) -> SQLModel:
        """Insert a new record and return it with its generated id."""
        with Session(self._engine) as session:
            session.add(instance)
            session.commit()
            session.refresh(instance)
            return instance

    def get_by_id(self, model: Type[T], record_id: int) -> Optional[T]:
        """Fetch a single record by primary key."""
        with Session(self._engine) as session:
            return session.get(model, record_id)

    def get_all(self, model: Type[T], **filters: object) -> list[T]:
        """Return all rows of *model*, optionally filtered by column values."""
        with Session(self._engine) as session:
            stmt = select(model)
            for col, val in filters.items():
                stmt = stmt.where(getattr(model, col) == val)
            return list(session.exec(stmt).all())

    def update(self, instance: SQLModel, **values: object) -> SQLModel:
        """Update fields on an existing record."""
        with Session(self._engine) as session:
            session.add(instance)
            for key, val in values.items():
                setattr(instance, key, val)
            session.commit()
            session.refresh(instance)
            return instance

    def delete(self, instance: SQLModel) -> None:
        """Delete a record."""
        with Session(self._engine) as session:
            session.delete(instance)
            session.commit()
