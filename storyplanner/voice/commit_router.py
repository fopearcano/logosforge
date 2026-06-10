"""Voice Commit Router — safe, mode-aware transcript commit targets (Phase 2).

After local transcription the user **reviews** the transcript, **chooses** a
target and **explicitly commits** — this module decides which targets exist
for the current writing mode, validates them, and executes the commit. It is
pure logic (no Qt): the voice panel supplies a :class:`VoiceCommitContext`
built by the main window.

Hard rules (Alpha):

* listing/previewing targets never mutates anything — only
  :func:`commit_transcript` writes, and only after explicit user action;
* no automatic target guessing, no command execution, no LLM classification,
  no character-name guessing, no panel-field guessing, no image prompts;
* a transcript captured in one project can never be committed into another
  (the project id is checked at commit time);
* unsupported targets are listed **disabled with a reason** rather than
  hidden, so the UI can explain itself — and they stay inert.

Deferred by design (each listed disabled with its reason): Outline /
Series-episode draft items (the outline is scene-derived; there is no safe
"unclassified draft" area yet) and append-to-manuscript (the open editor owns
the scene body — a direct DB append could clobber unsaved editor state; the
cursor target covers that flow).
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field

from storyplanner.voice.types import TranscriptSegment

# Target ids (stable; the UI stores/restores selection by id).
T_CURSOR = "active_cursor"
T_NOTE = "note"
T_PSYKE = "psyche_draft_entry"
T_OUTLINE = "outline_draft_item"
T_MANUSCRIPT_APPEND = "manuscript_append"
T_SP_ACTION = "screenplay_action"
T_SP_DIALOGUE = "screenplay_dialogue"
T_GN_VISUAL = "graphic_panel_visual"
T_GN_CAPTION = "graphic_panel_caption"
T_GN_DIALOGUE = "graphic_panel_dialogue"
T_GN_SFX = "graphic_panel_sfx"
T_GN_NOTES = "graphic_panel_notes"
T_STAGE_DIRECTION = "stage_direction"
T_STAGE_DIALOGUE = "stage_dialogue"
T_SERIES_EPISODE_OUTLINE = "series_episode_outline_item"

_GN_FIELD_BY_TARGET = {
    T_GN_VISUAL: "visual_description",
    T_GN_CAPTION: "caption",
    T_GN_DIALOGUE: "dialogue",
    T_GN_SFX: "sfx",
    T_GN_NOTES: "notes",
}

PSYKE_ENTRY_TYPES = ("other", "character", "place", "object", "lore", "theme")

_REASON_NO_EDITOR = "Click into an editor first."
_REASON_NO_PANEL = "Select a Panel first."
_REASON_NO_CHARACTER = "Pick a character first."
_REASON_OUTLINE = "Outline voice target not available yet."
_REASON_APPEND = ("Use cursor insert — the open editor owns the scene body.")
_REASON_PROJECT_CHANGED = ("Project changed since transcription. Review "
                           "before committing.")


@dataclass
class CommitTarget:
    """One selectable commit destination (may be disabled with a reason)."""

    id: str
    label: str
    mode: str
    enabled: bool
    target_type: str
    reason_if_disabled: str = ""
    target_ref: tuple | None = None


@dataclass
class VoiceCommitContext:
    """Everything the router may inspect. Building one mutates nothing."""

    db: object
    project_id: int
    writing_mode: str = "novel"
    # Cursor insertion (the existing EditorCommitTarget path).
    has_active_editor: bool = False
    insert_at_cursor: Callable[[str], bool] | None = None
    # Graphic Novel: the panel whose script block was last focused —
    # (scene_id, page_idx, panel_idx) — or None.
    gn_panel_ref: tuple[int, int, int] | None = None
    # Explicit user selections from the panel UI (never guessed).
    psyke_entry_type: str = "other"
    character_name: str = ""
    # Project the transcript was captured in (None = not captured yet).
    transcript_project_id: int | None = None
    extras: dict = field(default_factory=dict)


# ---------------------------------------------------------------- helpers
def _gn_panel_exists(ctx: VoiceCommitContext) -> bool:
    if ctx.gn_panel_ref is None:
        return False
    scene_id, page_idx, panel_idx = ctx.gn_panel_ref
    try:
        scene = ctx.db.get_scene_by_id(scene_id)
        if scene is None or scene.project_id != ctx.project_id:
            return False
        from storyplanner import graphic_novel_blocks as gnb
        script = gnb.load_scene_script(ctx.db, scene_id)
        return (0 <= page_idx < len(script.pages)
                and 0 <= panel_idx < len(script.pages[page_idx].panels))
    except Exception:
        return False


def _cursor_target(ctx: VoiceCommitContext, target_id: str, label: str,
                   *, enabled: bool = True, reason: str = "") -> CommitTarget:
    ok = bool(ctx.has_active_editor and ctx.insert_at_cursor is not None)
    if not ok:
        enabled, reason = False, _REASON_NO_EDITOR
    return CommitTarget(id=target_id, label=label, mode=ctx.writing_mode,
                        enabled=enabled, target_type=target_id,
                        reason_if_disabled=reason if not enabled else "")


def _note_title(text: str) -> str:
    head = " ".join((text or "").split())[:40].strip()
    return f"Voice note — {head}" if head else "Voice note"


# ------------------------------------------------------------------- API
def get_available_voice_commit_targets(
        ctx: VoiceCommitContext) -> list[CommitTarget]:
    """List targets for the context's mode. Read-only — never mutates."""
    mode = (ctx.writing_mode or "novel").lower()
    targets: list[CommitTarget] = [
        _cursor_target(ctx, T_CURSOR, "Insert at cursor"),
        CommitTarget(id=T_NOTE, label="New Note (Voice note)", mode=mode,
                     enabled=True, target_type=T_NOTE),
        CommitTarget(id=T_PSYKE, label="PSYKE draft entry", mode=mode,
                     enabled=True, target_type=T_PSYKE),
        CommitTarget(id=T_MANUSCRIPT_APPEND, label="Append to Manuscript",
                     mode=mode, enabled=False, target_type=T_MANUSCRIPT_APPEND,
                     reason_if_disabled=_REASON_APPEND),
        CommitTarget(id=T_OUTLINE, label="Outline draft item", mode=mode,
                     enabled=False, target_type=T_OUTLINE,
                     reason_if_disabled=_REASON_OUTLINE),
    ]

    if mode == "screenplay":
        targets.append(_cursor_target(ctx, T_SP_ACTION, "Insert as Action"))
        dlg = _cursor_target(ctx, T_SP_DIALOGUE,
                             "Insert as Dialogue (chosen character)")
        if dlg.enabled and not (ctx.character_name or "").strip():
            dlg.enabled = False
            dlg.reason_if_disabled = _REASON_NO_CHARACTER
        targets.append(dlg)
    elif mode == "graphic_novel":
        panel_ok = _gn_panel_exists(ctx)
        for tid, label in ((T_GN_VISUAL, "Panel → Visual"),
                           (T_GN_CAPTION, "Panel → Caption"),
                           (T_GN_DIALOGUE, "Panel → Dialogue"),
                           (T_GN_SFX, "Panel → SFX"),
                           (T_GN_NOTES, "Panel → Notes")):
            targets.append(CommitTarget(
                id=tid, label=label, mode=mode, enabled=panel_ok,
                target_type=tid,
                reason_if_disabled="" if panel_ok else _REASON_NO_PANEL,
                target_ref=ctx.gn_panel_ref if panel_ok else None))
    elif mode == "stage_script":
        targets.append(_cursor_target(ctx, T_STAGE_DIRECTION,
                                      "Insert as Stage Direction"))
        dlg = _cursor_target(ctx, T_STAGE_DIALOGUE,
                             "Insert as Dialogue (chosen character)")
        if dlg.enabled and not (ctx.character_name or "").strip():
            dlg.enabled = False
            dlg.reason_if_disabled = _REASON_NO_CHARACTER
        targets.append(dlg)
    elif mode == "series":
        targets.append(CommitTarget(
            id=T_SERIES_EPISODE_OUTLINE, label="Episode Outline draft item",
            mode=mode, enabled=False, target_type=T_SERIES_EPISODE_OUTLINE,
            reason_if_disabled=_REASON_OUTLINE))
    return targets


def validate_voice_commit_target(target_id: str,
                                 ctx: VoiceCommitContext) -> tuple[bool, str]:
    """Re-check one target against the LIVE context (read-only)."""
    if (ctx.transcript_project_id is not None
            and ctx.transcript_project_id != ctx.project_id):
        return False, _REASON_PROJECT_CHANGED
    for target in get_available_voice_commit_targets(ctx):
        if target.id == target_id:
            if target.enabled:
                return True, ""
            return False, target.reason_if_disabled or "Target unavailable."
    return False, "Target unavailable."


def preview_commit_target(target_id: str, ctx: VoiceCommitContext) -> str:
    """Human description of what commit WOULD do. Never mutates."""
    for target in get_available_voice_commit_targets(ctx):
        if target.id == target_id:
            if not target.enabled:
                return target.reason_if_disabled or "Target unavailable."
            return f"Commit inserts the transcript into: {target.label}"
    return "Target unavailable."


def commit_transcript(segment: TranscriptSegment | str, target_id: str,
                      ctx: VoiceCommitContext) -> tuple[bool, str]:
    """Execute ONE explicit commit. Returns (ok, status message)."""
    seg = (segment if isinstance(segment, TranscriptSegment)
           else TranscriptSegment(text=str(segment)))
    text = (seg.text or "").strip()
    if not text:
        return False, "Nothing to commit."
    ok, reason = validate_voice_commit_target(target_id, ctx)
    if not ok:
        return False, reason

    target = next(t for t in get_available_voice_commit_targets(ctx)
                  if t.id == target_id)
    done, message = _execute(text, target, ctx)
    if done:
        seg.committed = True
        seg.committed_target = target_id
        seg.committed_at = time.time()
        message = message or f"Transcript committed to {target.label}."
    return done, message


def _execute(text: str, target: CommitTarget,
             ctx: VoiceCommitContext) -> tuple[bool, str]:
    tid = target.id

    if tid == T_CURSOR:
        ok = bool(ctx.insert_at_cursor and ctx.insert_at_cursor(text))
        return (ok, "" if ok
                else "No active editor — click into the editor, then Commit.")

    if tid == T_SP_ACTION:
        ok = bool(ctx.insert_at_cursor
                  and ctx.insert_at_cursor(f"\n\n{text}\n\n"))
        return ok, "" if ok else "No active editor."

    if tid == T_SP_DIALOGUE:
        name = (ctx.character_name or "").strip().upper()
        ok = bool(ctx.insert_at_cursor
                  and ctx.insert_at_cursor(f"\n\n{name}\n{text}\n\n"))
        return ok, "" if ok else "No active editor."

    if tid == T_STAGE_DIRECTION:
        ok = bool(ctx.insert_at_cursor
                  and ctx.insert_at_cursor(f"\n\nSTAGE: {text}\n\n"))
        return ok, "" if ok else "No active editor."

    if tid == T_STAGE_DIALOGUE:
        name = (ctx.character_name or "").strip().upper()
        ok = bool(ctx.insert_at_cursor
                  and ctx.insert_at_cursor(f"\n\nCHARACTER: {name}\n{text}\n\n"))
        return ok, "" if ok else "No active editor."

    if tid == T_NOTE:
        ctx.db.create_note(ctx.project_id, _note_title(text), content=text)
        return True, ""

    if tid == T_PSYKE:
        entry_type = (ctx.psyke_entry_type or "other").lower()
        if entry_type not in PSYKE_ENTRY_TYPES:
            entry_type = "other"        # never guessed, never widened
        ctx.db.create_psyke_entry(ctx.project_id, _note_title(text),
                                  entry_type=entry_type, notes=text)
        return True, ""

    if tid in _GN_FIELD_BY_TARGET:
        if target.target_ref is None:
            return False, _REASON_NO_PANEL
        scene_id, page_idx, panel_idx = target.target_ref
        field_name = _GN_FIELD_BY_TARGET[tid]
        from storyplanner import graphic_novel_blocks as gnb
        from storyplanner import graphic_novel_outline as gno
        script = gnb.load_scene_script(ctx.db, scene_id)
        try:
            existing = getattr(script.pages[page_idx].panels[panel_idx],
                               field_name, "")
        except IndexError:
            return False, _REASON_NO_PANEL
        value = f"{existing}\n{text}" if (existing or "").strip() else text
        done = gno.set_panel_field(ctx.db, scene_id, page_idx, panel_idx,
                                   field_name, value)
        return (bool(done), "" if done else _REASON_NO_PANEL)

    return False, "Target unavailable."
