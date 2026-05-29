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
    ChatMessage,
    ChatSummary,
    Character,
    Note,
    NotePsykeLink,
    NoteSceneLink,
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
    Stage,
    StageBranch,
    StageSnapshot,
    StoryMemoryEntry,
    VoiceProfile,
)


# Inverse mapping for PSYKE typed relations. A "payoff" from A→B is stored as
# a "supports_setup" on B→A so direction is preserved when traversing.
_INVERSE_RELATION_TYPE: dict[str, str] = {
    "supports_setup": "payoff",
    "payoff": "supports_setup",
    # Symmetric relation types map to themselves
    "thematic_echo": "thematic_echo",
    "visual_motif": "visual_motif",
    "subtext_opposition": "subtext_opposition",
}


# Continuity memory_type values for StoryMemoryEntry — track per-scene
# physical and mental state for continuity audits.
CONTINUITY_MEMORY_TYPES = (
    "continuity_wound",
    "continuity_prop",
    "continuity_costume",
    "continuity_emotional_state",
    "continuity_knowledge_state",
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
            if rows and "narrative_engine" not in columns:
                conn.execute(text(
                    "ALTER TABLE project ADD COLUMN"
                    " narrative_engine TEXT DEFAULT ''"
                ))
                conn.commit()
            if rows and "default_writing_format" not in columns:
                conn.execute(text(
                    "ALTER TABLE project ADD COLUMN"
                    " default_writing_format TEXT DEFAULT ''"
                ))
                conn.commit()
            # Backfill engine + format from legacy format_mode for rows
            # that haven't been touched by the new UI yet.
            from storyplanner.project_compat import resolve_legacy_format
            existing = conn.execute(text(
                "SELECT id, format_mode, narrative_engine,"
                " default_writing_format FROM project"
            )).fetchall()
            for pid, fmode, engine, fmt in existing:
                if not (engine or "").strip() or not (fmt or "").strip():
                    e2, f2 = resolve_legacy_format(fmode or "")
                    conn.execute(
                        text(
                            "UPDATE project SET narrative_engine=:e,"
                            " default_writing_format=:f WHERE id=:i"
                        ),
                        {"e": engine or e2, "f": fmt or f2, "i": pid},
                    )
            conn.commit()

            rows = conn.execute(text("PRAGMA table_info(scene)")).fetchall()
            columns = {row[1] for row in rows}
            if rows and "color_label" not in columns:
                conn.execute(
                    text("ALTER TABLE scene ADD COLUMN color_label TEXT DEFAULT ''")
                )
                conn.commit()

            # Screenplay-engine fields — added safely; existing rows pick up
            # the defaults and Novel projects simply ignore them.
            _screenplay_text_fields = (
                "slugline", "location", "interior_exterior", "time_of_day",
                "visual_objective", "dramatic_turn", "blocking_notes",
                "subtext_notes", "setup_payoff_links", "montage_group",
                "cinematic_pacing", "continuity_notes",
                # PSYKE-screenplay extensions (cinematic + performative)
                "visible_conflict", "hidden_conflict", "emotional_turn",
                "who_knows_what", "physical_action", "visual_symbolism",
            )
            if rows:
                columns = {row[1] for row in conn.execute(
                    text("PRAGMA table_info(scene)")).fetchall()}
                for col in _screenplay_text_fields:
                    if col not in columns:
                        conn.execute(text(
                            f"ALTER TABLE scene ADD COLUMN {col} TEXT DEFAULT ''"
                        ))
                if "estimated_duration_minutes" not in columns:
                    conn.execute(text(
                        "ALTER TABLE scene ADD COLUMN"
                        " estimated_duration_minutes INTEGER DEFAULT 0"
                    ))
                conn.commit()

            # PSYKE relation typing — adds relation_type for screenplay
            # extensions (setup/payoff/thematic_echo/visual_motif/etc.)
            rel_rows = conn.execute(
                text("PRAGMA table_info(psykerelation)"),
            ).fetchall()
            rel_columns = {row[1] for row in rel_rows}
            if rel_rows and "relation_type" not in rel_columns:
                conn.execute(text(
                    "ALTER TABLE psykerelation ADD COLUMN"
                    " relation_type TEXT DEFAULT ''"
                ))
                conn.commit()

    # -- Projects ------------------------------------------------------------

    def get_project_by_id(self, project_id: int) -> Project | None:
        with Session(self._engine) as session:
            return session.get(Project, project_id)

    def get_all_projects(self) -> list[Project]:
        with Session(self._engine) as session:
            return list(session.exec(select(Project)).all())

    def create_project(
        self,
        title: str,
        format_mode: str | None = None,
        *,
        narrative_engine: str = "",
        default_writing_format: str = "",
    ) -> Project:
        from storyplanner.project_compat import (
            default_format_for_engine,
            resolve_legacy_format,
        )
        engine = (narrative_engine or "").strip()
        fmt = (default_writing_format or "").strip()
        legacy_provided = format_mode is not None
        legacy = (format_mode or "novel").strip()

        # Derive whichever new field is missing.
        if not engine and not fmt:
            engine, fmt = resolve_legacy_format(legacy)
        elif not engine:
            engine = resolve_legacy_format(legacy)[0]
        elif not fmt:
            fmt = default_format_for_engine(engine)

        # When the caller explicitly passed a legacy format_mode (e.g.
        # imports, legacy tests, or `_make_project(db, "series")`), keep
        # it exactly so round-trips stay faithful. Otherwise mirror the
        # chosen writing format into format_mode so back-compat readers
        # see the new selection.
        stored_format_mode = legacy if legacy_provided else fmt

        with Session(self._engine) as session:
            project = Project(
                title=title,
                format_mode=stored_format_mode,
                narrative_engine=engine,
                default_writing_format=fmt,
            )
            session.add(project)
            session.commit()
            session.refresh(project)
            return project

    def update_project_format(self, project_id: int, format_mode: str) -> None:
        """Legacy: change the writing format and keep new fields in sync."""
        with Session(self._engine) as session:
            project = session.get(Project, project_id)
            if project:
                project.format_mode = format_mode
                if format_mode:
                    project.default_writing_format = format_mode
                session.commit()

    def update_project_narrative_engine(
        self, project_id: int, engine: str,
    ) -> None:
        with Session(self._engine) as session:
            project = session.get(Project, project_id)
            if project and engine:
                project.narrative_engine = engine
                session.commit()

    def update_project_writing_format(
        self, project_id: int, writing_format: str,
    ) -> None:
        with Session(self._engine) as session:
            project = session.get(Project, project_id)
            if project and writing_format:
                project.default_writing_format = writing_format
                # Keep legacy format_mode in sync so the manuscript editor
                # and exporters that still read format_mode keep working.
                project.format_mode = writing_format
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

    def get_quantum_goals(self, project_id: int) -> "QuantumGoals":
        from storyplanner.quantum_outliner.scoring import QuantumGoals
        settings = self.get_project_settings(project_id)
        raw = settings.get("quantum_goals")
        if isinstance(raw, dict):
            return QuantumGoals(
                objectives=raw.get("objectives", {}),
                min_constraints=raw.get("min_constraints", {}),
                horizon=raw.get("horizon", 1),
            ).validate()
        return QuantumGoals()

    def set_quantum_goals(self, project_id: int, goals: "QuantumGoals") -> None:
        goals.validate()
        settings = self.get_project_settings(project_id)
        settings["quantum_goals"] = {
            "objectives": goals.objectives,
            "min_constraints": goals.min_constraints,
            "horizon": goals.horizon,
        }
        self.save_project_settings(project_id, settings)
        from storyplanner.quantum_outliner.lookahead_cache import invalidate_lookahead
        invalidate_lookahead()

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

    # -- Voice Profiles --------------------------------------------------------

    def get_voice_profile(self, character_id: int) -> VoiceProfile | None:
        with Session(self._engine) as session:
            stmt = select(VoiceProfile).where(
                VoiceProfile.character_id == character_id,
            )
            return session.exec(stmt).first()

    def create_voice_profile(
        self,
        character_id: int,
        *,
        tone: str = "neutral",
        sentence_length: str = "medium",
        vocabulary_level: str = "standard",
        quirks: list[str] | None = None,
        punctuation_style: dict | None = None,
        dialogue_markers: list[str] | None = None,
    ) -> VoiceProfile:
        import json
        with Session(self._engine) as session:
            profile = VoiceProfile(
                character_id=character_id,
                tone=tone,
                sentence_length=sentence_length,
                vocabulary_level=vocabulary_level,
                quirks_json=json.dumps(quirks or []),
                punctuation_style_json=json.dumps(punctuation_style or {}),
                dialogue_markers_json=json.dumps(dialogue_markers or []),
            )
            session.add(profile)
            session.commit()
            session.refresh(profile)
            return profile

    def update_voice_profile(
        self,
        character_id: int,
        *,
        tone: str | None = None,
        sentence_length: str | None = None,
        vocabulary_level: str | None = None,
        quirks: list[str] | None = None,
        punctuation_style: dict | None = None,
        dialogue_markers: list[str] | None = None,
    ) -> VoiceProfile | None:
        import json
        from datetime import datetime, timezone
        with Session(self._engine) as session:
            stmt = select(VoiceProfile).where(
                VoiceProfile.character_id == character_id,
            )
            profile = session.exec(stmt).first()
            if profile is None:
                return None
            if tone is not None:
                profile.tone = tone
            if sentence_length is not None:
                profile.sentence_length = sentence_length
            if vocabulary_level is not None:
                profile.vocabulary_level = vocabulary_level
            if quirks is not None:
                profile.quirks_json = json.dumps(quirks)
            if punctuation_style is not None:
                profile.punctuation_style_json = json.dumps(punctuation_style)
            if dialogue_markers is not None:
                profile.dialogue_markers_json = json.dumps(dialogue_markers)
            profile.updated_at = datetime.now(timezone.utc)
            session.commit()
            session.refresh(profile)
            return profile

    def delete_voice_profile(self, character_id: int) -> None:
        with Session(self._engine) as session:
            stmt = select(VoiceProfile).where(
                VoiceProfile.character_id == character_id,
            )
            profile = session.exec(stmt).first()
            if profile:
                session.delete(profile)
                session.commit()

    def get_voice_profile_data(self, character_id: int) -> dict | None:
        """Return deserialized voice profile as a plain dict, or None."""
        import json
        profile = self.get_voice_profile(character_id)
        if profile is None:
            return None
        return {
            "character_id": profile.character_id,
            "tone": profile.tone,
            "sentence_length": profile.sentence_length,
            "vocabulary_level": profile.vocabulary_level,
            "quirks": json.loads(profile.quirks_json),
            "punctuation_style": json.loads(profile.punctuation_style_json),
            "dialogue_markers": json.loads(profile.dialogue_markers_json),
            "last_updated": profile.updated_at.isoformat(),
        }

    def sync_voice_to_psyke(self, character_id: int, project_id: int) -> None:
        """Write a voice-profile summary into the character's PSYKE entry."""
        import json
        from storyplanner.voice_learner import voice_profile_summary

        data = self.get_voice_profile_data(character_id)
        if data is None:
            return
        summary = voice_profile_summary(data)
        if not summary:
            return
        char = self.get_character_by_id(character_id)
        if char is None:
            return
        entry = self._find_character_psyke_entry(project_id, char.name)
        if entry is None:
            return
        details = self.get_psyke_entry_details(entry.id)
        details["voice"] = summary
        self.update_psyke_entry(
            entry.id,
            name=entry.name,
            entry_type=entry.entry_type,
            aliases=entry.aliases,
            notes=entry.notes,
            is_global=entry.is_global,
            details=details,
        )

    def _find_character_psyke_entry(
        self, project_id: int, character_name: str,
    ) -> PsykeEntry | None:
        with Session(self._engine) as session:
            stmt = (
                select(PsykeEntry)
                .where(PsykeEntry.project_id == project_id)
                .where(PsykeEntry.entry_type == "character")
                .where(PsykeEntry.name == character_name)
            )
            return session.exec(stmt).first()

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
        self,
        project_id: int,
        title: str,
        content: str = "",
        tags: str = "",
        pinned: bool = False,
    ) -> Note:
        with Session(self._engine) as session:
            note = Note(
                project_id=project_id,
                title=title,
                content=content,
                tags=tags,
                pinned=pinned,
            )
            session.add(note)
            session.commit()
            session.refresh(note)
            return note

    def update_note(
        self,
        note_id: int,
        title: str,
        content: str = "",
        tags: str = "",
        pinned: bool = False,
    ) -> Note:
        with Session(self._engine) as session:
            note = session.get(Note, note_id)
            note.title = title
            note.content = content
            note.tags = tags
            note.pinned = pinned
            session.commit()
            session.refresh(note)
            return note

    def delete_note(self, note_id: int) -> None:
        with Session(self._engine) as session:
            note = session.get(Note, note_id)
            if note:
                stmt = select(NotePsykeLink).where(NotePsykeLink.note_id == note_id)
                for link in session.exec(stmt).all():
                    session.delete(link)
                stmt = select(NoteSceneLink).where(NoteSceneLink.note_id == note_id)
                for link in session.exec(stmt).all():
                    session.delete(link)
                session.delete(note)
            session.commit()

    # -- Note linking ----------------------------------------------------------

    def link_note_to_psyke(self, note_id: int, psyke_entry_id: int) -> None:
        with Session(self._engine) as session:
            existing = session.get(NotePsykeLink, (note_id, psyke_entry_id))
            if existing:
                return
            session.add(NotePsykeLink(note_id=note_id, psyke_entry_id=psyke_entry_id))
            session.commit()

    def unlink_note_from_psyke(self, note_id: int, psyke_entry_id: int) -> None:
        with Session(self._engine) as session:
            link = session.get(NotePsykeLink, (note_id, psyke_entry_id))
            if link:
                session.delete(link)
                session.commit()

    def get_note_psyke_links(self, note_id: int) -> list[int]:
        with Session(self._engine) as session:
            stmt = select(NotePsykeLink.psyke_entry_id).where(
                NotePsykeLink.note_id == note_id,
            )
            return list(session.exec(stmt).all())

    def get_psyke_note_links(self, psyke_entry_id: int) -> list[int]:
        with Session(self._engine) as session:
            stmt = select(NotePsykeLink.note_id).where(
                NotePsykeLink.psyke_entry_id == psyke_entry_id,
            )
            return list(session.exec(stmt).all())

    def link_note_to_scene(self, note_id: int, scene_id: int) -> None:
        with Session(self._engine) as session:
            existing = session.get(NoteSceneLink, (note_id, scene_id))
            if existing:
                return
            session.add(NoteSceneLink(note_id=note_id, scene_id=scene_id))
            session.commit()

    def unlink_note_from_scene(self, note_id: int, scene_id: int) -> None:
        with Session(self._engine) as session:
            link = session.get(NoteSceneLink, (note_id, scene_id))
            if link:
                session.delete(link)
                session.commit()

    def get_note_scene_links(self, note_id: int) -> list[int]:
        with Session(self._engine) as session:
            stmt = select(NoteSceneLink.scene_id).where(
                NoteSceneLink.note_id == note_id,
            )
            return list(session.exec(stmt).all())

    def get_scene_note_links(self, scene_id: int) -> list[int]:
        with Session(self._engine) as session:
            stmt = select(NoteSceneLink.note_id).where(
                NoteSceneLink.scene_id == scene_id,
            )
            return list(session.exec(stmt).all())

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
        color_label: str = "",
        # -- Screenplay-engine fields ------------------------------------
        slugline: str = "",
        location: str = "",
        interior_exterior: str = "",
        time_of_day: str = "",
        estimated_duration_minutes: int = 0,
        visual_objective: str = "",
        dramatic_turn: str = "",
        blocking_notes: str = "",
        subtext_notes: str = "",
        setup_payoff_links: str = "",
        montage_group: str = "",
        cinematic_pacing: str = "",
        continuity_notes: str = "",
        # -- Screenplay PSYKE extensions --------------------------------
        visible_conflict: str = "",
        hidden_conflict: str = "",
        emotional_turn: str = "",
        who_knows_what: str = "",
        physical_action: str = "",
        visual_symbolism: str = "",
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
                color_label=color_label,
                slugline=slugline,
                location=location,
                interior_exterior=interior_exterior,
                time_of_day=time_of_day,
                estimated_duration_minutes=estimated_duration_minutes,
                visual_objective=visual_objective,
                dramatic_turn=dramatic_turn,
                blocking_notes=blocking_notes,
                subtext_notes=subtext_notes,
                setup_payoff_links=setup_payoff_links,
                montage_group=montage_group,
                cinematic_pacing=cinematic_pacing,
                continuity_notes=continuity_notes,
                visible_conflict=visible_conflict,
                hidden_conflict=hidden_conflict,
                emotional_turn=emotional_turn,
                who_knows_what=who_knows_what,
                physical_action=physical_action,
                visual_symbolism=visual_symbolism,
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
        color_label: str | None = None,
        # -- Screenplay-engine fields (None = leave unchanged) -----------
        slugline: str | None = None,
        location: str | None = None,
        interior_exterior: str | None = None,
        time_of_day: str | None = None,
        estimated_duration_minutes: int | None = None,
        visual_objective: str | None = None,
        dramatic_turn: str | None = None,
        blocking_notes: str | None = None,
        subtext_notes: str | None = None,
        setup_payoff_links: str | None = None,
        montage_group: str | None = None,
        cinematic_pacing: str | None = None,
        continuity_notes: str | None = None,
        # -- Screenplay PSYKE extensions (None = leave unchanged) -------
        visible_conflict: str | None = None,
        hidden_conflict: str | None = None,
        emotional_turn: str | None = None,
        who_knows_what: str | None = None,
        physical_action: str | None = None,
        visual_symbolism: str | None = None,
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
            if color_label is not None:
                scene.color_label = color_label
            if slugline is not None:
                scene.slugline = slugline
            if location is not None:
                scene.location = location
            if interior_exterior is not None:
                scene.interior_exterior = interior_exterior
            if time_of_day is not None:
                scene.time_of_day = time_of_day
            if estimated_duration_minutes is not None:
                scene.estimated_duration_minutes = estimated_duration_minutes
            if visual_objective is not None:
                scene.visual_objective = visual_objective
            if dramatic_turn is not None:
                scene.dramatic_turn = dramatic_turn
            if blocking_notes is not None:
                scene.blocking_notes = blocking_notes
            if subtext_notes is not None:
                scene.subtext_notes = subtext_notes
            if setup_payoff_links is not None:
                scene.setup_payoff_links = setup_payoff_links
            if montage_group is not None:
                scene.montage_group = montage_group
            if cinematic_pacing is not None:
                scene.cinematic_pacing = cinematic_pacing
            if continuity_notes is not None:
                scene.continuity_notes = continuity_notes
            if visible_conflict is not None:
                scene.visible_conflict = visible_conflict
            if hidden_conflict is not None:
                scene.hidden_conflict = hidden_conflict
            if emotional_turn is not None:
                scene.emotional_turn = emotional_turn
            if who_knows_what is not None:
                scene.who_knows_what = who_knows_what
            if physical_action is not None:
                scene.physical_action = physical_action
            if visual_symbolism is not None:
                scene.visual_symbolism = visual_symbolism

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
            for nsl in session.exec(
                select(NoteSceneLink).where(
                    NoteSceneLink.scene_id == scene_id,
                )
            ).all():
                session.delete(nsl)

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

    def update_scene_color(self, scene_id: int, color_label: str) -> None:
        with Session(self._engine) as session:
            scene = session.get(Scene, scene_id)
            if scene is None:
                return
            scene.color_label = color_label or ""
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

    def get_character_arc_by_name(
        self, project_id: int, name: str
    ) -> list[tuple[int, str, int, str]]:
        """Arc for a character identified by name.

        The Arcs selector is sourced from PSYKE character entries (the
        source of truth), but scene character-states are keyed by
        Character-table id. This resolves the PSYKE entry name to any
        matching Character rows (case-insensitive) and returns their
        combined arc. Returns [] when the character has no recorded scene
        states yet.
        """
        name_l = (name or "").strip().lower()
        if not name_l:
            return []
        char_ids = {
            c.id for c in self.get_all_characters(project_id)
            if (c.name or "").strip().lower() == name_l
        }
        if not char_ids:
            return []
        scenes = self.get_all_scenes(project_id)
        arc: list[tuple[int, str, int, str]] = []
        for idx, scene in enumerate(scenes):
            for cid, state in self.get_scene_character_states(scene.id):
                if cid in char_ids:
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
            from storyplanner.quantum_outliner.lookahead_cache import invalidate_lookahead
            invalidate_lookahead()
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
            from storyplanner.quantum_outliner.lookahead_cache import invalidate_lookahead
            invalidate_lookahead()
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
            for npl in session.exec(
                select(NotePsykeLink).where(
                    NotePsykeLink.psyke_entry_id == entry_id,
                )
            ).all():
                session.delete(npl)
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

    def add_psyke_relation(
        self,
        entry_id: int,
        related_entry_id: int,
        relation_type: str = "",
    ) -> None:
        """Add a bidirectional PSYKE relation.

        Screenplay extensions use typed relations to express
        setup/payoff/echo/motif/opposition links. A "payoff" from A→B is
        stored as a "supports_setup" inverse on B→A so direction is preserved.
        """
        if entry_id == related_entry_id:
            return
        inverse = _INVERSE_RELATION_TYPE.get(relation_type, relation_type)
        with Session(self._engine) as session:
            existing = session.get(PsykeRelation, (entry_id, related_entry_id))
            if existing:
                if relation_type and existing.relation_type != relation_type:
                    existing.relation_type = relation_type
                    rev = session.get(PsykeRelation, (related_entry_id, entry_id))
                    if rev:
                        rev.relation_type = inverse
                    session.commit()
                return
            session.add(PsykeRelation(
                entry_id=entry_id,
                related_entry_id=related_entry_id,
                relation_type=relation_type,
            ))
            session.add(PsykeRelation(
                entry_id=related_entry_id,
                related_entry_id=entry_id,
                relation_type=inverse,
            ))
            session.commit()
            from storyplanner.quantum_outliner.lookahead_cache import invalidate_lookahead
            invalidate_lookahead()

    def get_psyke_relation_type(
        self, entry_id: int, related_entry_id: int,
    ) -> str:
        with Session(self._engine) as session:
            rel = session.get(PsykeRelation, (entry_id, related_entry_id))
            return rel.relation_type if rel else ""

    def get_typed_related_psyke_entries(
        self, entry_id: int,
    ) -> list[tuple[PsykeEntry, str]]:
        """Return (related_entry, relation_type) tuples for an entry."""
        with Session(self._engine) as session:
            stmt = select(PsykeRelation).where(
                PsykeRelation.entry_id == entry_id,
            )
            rels = list(session.exec(stmt).all())
            if not rels:
                return []
            related_ids = [r.related_entry_id for r in rels]
            entries = list(
                session.exec(
                    select(PsykeEntry).where(PsykeEntry.id.in_(related_ids))
                ).all()
            )
            by_id = {e.id: e for e in entries}
            return [
                (by_id[r.related_entry_id], r.relation_type)
                for r in rels
                if r.related_entry_id in by_id
            ]

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
            from storyplanner.quantum_outliner.lookahead_cache import invalidate_lookahead
            invalidate_lookahead()
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
            from storyplanner.quantum_outliner.lookahead_cache import invalidate_lookahead
            invalidate_lookahead()
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

    # -- Continuity Tracking (Screenplay) -----------------------------------

    def add_continuity_item(
        self,
        project_id: int,
        scene_id: int,
        category: str,
        target: str,
        value: str,
    ) -> StoryMemoryEntry:
        """Track a continuity item for a scene.

        category is one of: "wound", "prop", "costume", "emotional_state",
        "knowledge_state". target is the character/object name; value is
        the state description.
        """
        memory_type = f"continuity_{category}"
        if memory_type not in CONTINUITY_MEMORY_TYPES:
            raise ValueError(
                f"Unknown continuity category: {category!r}. "
                f"Expected one of: wound, prop, costume, "
                f"emotional_state, knowledge_state."
            )
        return self.add_memory(
            project_id, scene_id, memory_type, target, value,
        )

    def get_continuity_for_scene(
        self, scene_id: int,
    ) -> list[StoryMemoryEntry]:
        with Session(self._engine) as session:
            stmt = (
                select(StoryMemoryEntry)
                .where(StoryMemoryEntry.scene_id == scene_id)
                .where(StoryMemoryEntry.memory_type.in_(
                    CONTINUITY_MEMORY_TYPES,
                ))
                .order_by(StoryMemoryEntry.memory_type, StoryMemoryEntry.id)
            )
            return list(session.exec(stmt).all())

    def get_continuity_by_category(
        self, project_id: int, category: str,
    ) -> list[StoryMemoryEntry]:
        memory_type = f"continuity_{category}"
        return self.get_memories_by_type(project_id, memory_type)

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

    # -- Chat -----------------------------------------------------------------

    def add_chat_message(
        self,
        project_id: int,
        role: str,
        content: str,
        metadata: dict | None = None,
    ) -> ChatMessage:
        import json
        with Session(self._engine) as session:
            msg = ChatMessage(
                project_id=project_id,
                role=role,
                content=content,
                metadata_json=json.dumps(metadata) if metadata else "",
            )
            session.add(msg)
            session.commit()
            session.refresh(msg)
            return msg

    def get_chat_messages(
        self, project_id: int, limit: int | None = None,
    ) -> list[ChatMessage]:
        with Session(self._engine) as session:
            stmt = (
                select(ChatMessage)
                .where(ChatMessage.project_id == project_id)
                .order_by(ChatMessage.id)
            )
            results = list(session.exec(stmt).all())
            if limit is not None and limit > 0:
                results = results[-limit:]
            return results

    def get_chat_messages_after(
        self, project_id: int, after_id: int,
    ) -> list[ChatMessage]:
        with Session(self._engine) as session:
            stmt = (
                select(ChatMessage)
                .where(ChatMessage.project_id == project_id)
                .where(ChatMessage.id > after_id)
                .order_by(ChatMessage.id)
            )
            return list(session.exec(stmt).all())

    def clear_chat_messages(self, project_id: int) -> None:
        with Session(self._engine) as session:
            stmt = select(ChatMessage).where(
                ChatMessage.project_id == project_id,
            )
            for m in session.exec(stmt).all():
                session.delete(m)
            summary = session.get(ChatSummary, project_id)
            if summary is not None:
                session.delete(summary)
            session.commit()

    def get_chat_summary(self, project_id: int) -> ChatSummary | None:
        with Session(self._engine) as session:
            return session.get(ChatSummary, project_id)

    def update_chat_summary(
        self, project_id: int, summary_text: str, last_id: int,
    ) -> ChatSummary:
        from datetime import datetime, timezone
        with Session(self._engine) as session:
            record = session.get(ChatSummary, project_id)
            if record is None:
                record = ChatSummary(
                    project_id=project_id,
                    summary=summary_text,
                    last_summarized_message_id=last_id,
                )
                session.add(record)
            else:
                record.summary = summary_text
                record.last_summarized_message_id = last_id
                record.updated_at = datetime.now(timezone.utc)
            session.commit()
            session.refresh(record)
            return record

    def get_chat_message_metadata(self, message_id: int) -> dict:
        import json
        with Session(self._engine) as session:
            msg = session.get(ChatMessage, message_id)
            if msg is None or not msg.metadata_json:
                return {}
            try:
                return json.loads(msg.metadata_json)
            except (json.JSONDecodeError, TypeError):
                return {}

    def update_chat_message_metadata(
        self, message_id: int, metadata: dict,
    ) -> None:
        import json
        with Session(self._engine) as session:
            msg = session.get(ChatMessage, message_id)
            if msg is None:
                return
            msg.metadata_json = json.dumps(metadata) if metadata else ""
            session.commit()

    # -- Stages ---------------------------------------------------------------

    def create_stage(
        self,
        project_id: int,
        name: str,
        *,
        description: str = "",
        parent_stage_id: int | None = None,
        scope_type: str = "project",
        scope_id: int | None = None,
        status: str = "alternate",
        metadata: dict | None = None,
    ) -> Stage:
        import json
        with Session(self._engine) as session:
            stage = Stage(
                project_id=project_id,
                name=name,
                description=description,
                parent_stage_id=parent_stage_id,
                scope_type=scope_type,
                scope_id=scope_id,
                status=status,
                metadata_json=json.dumps(metadata) if metadata else "",
            )
            session.add(stage)
            session.commit()
            session.refresh(stage)
            return stage

    def get_stage(self, stage_id: int) -> Stage | None:
        with Session(self._engine) as session:
            return session.get(Stage, stage_id)

    def get_all_stages(self, project_id: int) -> list[Stage]:
        with Session(self._engine) as session:
            stmt = (
                select(Stage)
                .where(Stage.project_id == project_id)
                .order_by(Stage.created_at)
            )
            return list(session.exec(stmt).all())

    def get_child_stages(self, stage_id: int) -> list[Stage]:
        with Session(self._engine) as session:
            stmt = (
                select(Stage)
                .where(Stage.parent_stage_id == stage_id)
                .order_by(Stage.created_at)
            )
            return list(session.exec(stmt).all())

    def update_stage(
        self,
        stage_id: int,
        *,
        name: str | None = None,
        description: str | None = None,
        status: str | None = None,
        metadata: dict | None = None,
    ) -> Stage | None:
        import json
        from datetime import datetime, timezone
        with Session(self._engine) as session:
            stage = session.get(Stage, stage_id)
            if stage is None:
                return None
            if name is not None:
                stage.name = name
            if description is not None:
                stage.description = description
            if status is not None:
                stage.status = status
            if metadata is not None:
                stage.metadata_json = json.dumps(metadata)
            stage.updated_at = datetime.now(timezone.utc)
            session.commit()
            session.refresh(stage)
            return stage

    def set_stage_status(
        self, stage_id: int, status: str,
    ) -> Stage | None:
        if status not in ("active", "archived", "canonical", "alternate"):
            return None
        stage = self.get_stage(stage_id)
        if stage is None:
            return None
        if status == "canonical" and stage.scope_type == "project":
            for other in self.get_all_stages(stage.project_id):
                if (
                    other.id != stage_id
                    and other.scope_type == "project"
                    and other.status == "canonical"
                ):
                    self.update_stage(other.id, status="alternate")
        if status == "canonical" and stage.scope_type == "scene" and stage.scope_id is not None:
            for other in self.get_all_stages(stage.project_id):
                if (
                    other.id != stage_id
                    and other.scope_type == "scene"
                    and other.scope_id == stage.scope_id
                    and other.status == "canonical"
                ):
                    self.update_stage(other.id, status="alternate")
        return self.update_stage(stage_id, status=status)

    def delete_stage(self, stage_id: int) -> None:
        with Session(self._engine) as session:
            for snap in session.exec(
                select(StageSnapshot).where(StageSnapshot.stage_id == stage_id)
            ).all():
                session.delete(snap)
            for br in session.exec(
                select(StageBranch).where(
                    (StageBranch.source_stage_id == stage_id)
                    | (StageBranch.target_stage_id == stage_id)
                )
            ).all():
                session.delete(br)
            stage = session.get(Stage, stage_id)
            if stage is not None:
                session.delete(stage)
            session.commit()

    def get_stage_metadata(self, stage_id: int) -> dict:
        import json
        stage = self.get_stage(stage_id)
        if stage is None or not stage.metadata_json:
            return {}
        try:
            return json.loads(stage.metadata_json)
        except (json.JSONDecodeError, TypeError):
            return {}

    # -- Stage snapshots ------------------------------------------------------

    def create_stage_snapshot(
        self,
        stage_id: int,
        data_json: str,
        *,
        label: str = "",
        reason: str = "",
        summary: str = "",
    ) -> StageSnapshot:
        with Session(self._engine) as session:
            snap = StageSnapshot(
                stage_id=stage_id,
                label=label,
                reason=reason,
                summary=summary,
                data_json=data_json,
            )
            session.add(snap)
            session.commit()
            session.refresh(snap)
            return snap

    def get_stage_snapshots(self, stage_id: int) -> list[StageSnapshot]:
        with Session(self._engine) as session:
            stmt = (
                select(StageSnapshot)
                .where(StageSnapshot.stage_id == stage_id)
                .order_by(StageSnapshot.created_at)
            )
            return list(session.exec(stmt).all())

    def get_snapshot(self, snapshot_id: int) -> StageSnapshot | None:
        with Session(self._engine) as session:
            return session.get(StageSnapshot, snapshot_id)

    # -- Stage branches -------------------------------------------------------

    def create_stage_branch(
        self,
        source_stage_id: int,
        target_stage_id: int,
        branch_reason: str = "",
    ) -> StageBranch:
        with Session(self._engine) as session:
            br = StageBranch(
                source_stage_id=source_stage_id,
                target_stage_id=target_stage_id,
                branch_reason=branch_reason,
            )
            session.add(br)
            session.commit()
            session.refresh(br)
            return br

    def get_branches_from(self, stage_id: int) -> list[StageBranch]:
        with Session(self._engine) as session:
            stmt = select(StageBranch).where(
                StageBranch.source_stage_id == stage_id,
            )
            return list(session.exec(stmt).all())

    @staticmethod
    def _matches(query_lower: str, *fields: str) -> bool:
        for field in fields:
            if field and query_lower in field.lower():
                return True
        return False
