# Local Voice-to-Script (Alpha MVP)

A **local-first**, feature-flagged dictation foundation: speak, get a transcript
from a **local PC** or **trusted local-LAN** Whisper backend, review it, and
**commit it as plain text** into the active editor. It is intentionally minimal.

## Backend modes (`voice_backend_mode`, default `"disabled"`)

| mode | what it does |
|------|--------------|
| `disabled` | default safe state — voice UI inert, app unaffected |
| `mock` | dependency-free test/demo backend (no mic, canned transcript) |
| `local_process` | transcription on **this computer** via faster-whisper (local model path, lazy optional dependency, no auto-download) |
| `lan_server` | mic capture stays local; finalized segments go to a **Whisper server you configured on the trusted local network** — see `docs/LOCAL_LAN_WHISPER.md`. **Private/loopback addresses only; public URLs / ngrok / tunnels are blocked; redirects refused.** |

## What it is

- **Near-live segmented dictation.** Audio is captured locally, buffered in short
  chunks, and a segment is finalized on a pause (silence) or after a max duration,
  then transcribed by the selected local backend.
- **Local/LAN transcription only.** No cloud speech API; audio never leaves your
  device except, in LAN mode, to the private-network server you explicitly
  configured. The backends (faster-whisper) and microphone (sounddevice) are
  **optional, lazy-loaded** dependencies; the LAN client is stdlib `urllib`.
- **Manual commit.** The transcript appears in a preview; you click **Commit to
  editor** to insert it at the cursor. Auto-commit-after-pause is an opt-in toggle,
  **off by default**.

## What it is NOT (deferred)

- Not cloud realtime / speech-to-speech / a "Live Writer Room".
- No OpenAI Realtime API, no cloud speech API, no public/tunnel endpoints
  (ngrok / cloudflare tunnels are blocked by the private-host rule).
- No automatic classification (dialogue / action / note / outline / PSYKE / panel).
- No automatic Fountain / screenplay formatting.
- No voice commands, no speaker diarization.
- No automatic model downloads; no LAN auto-discovery or network scanning.
- No ComfyUI / image generation.

## Setup (local)

Voice mode is **OFF by default**. To use it:

1. Install the optional local backends (not bundled, to keep Alpha light):
   ```bash
   pip install faster-whisper sounddevice
   ```
2. Obtain a **local** Whisper model directory (faster-whisper / CTranslate2 format)
   — the app will **not** download one for you.
3. In the settings store, set:
   - `enable_voice_mode = true`
   - `voice_backend_mode = "local_process"` (or `"lan_server"` / `"mock"`) —
     also switchable from the panel's **Backend** selector
   - Local PC: `voice_whisper_model_path = "/path/to/local/model"`
   - LAN: `voice_lan_base_url = "http://<private-lan-ip>:8000"` (see
     `docs/LOCAL_LAN_WHISPER.md`)
   - optionally `voice_language` (`"auto"`/`"en"`/`"it"`), `voice_silence_ms`,
     `voice_max_segment_seconds`, `voice_auto_commit`.
4. Open **View → Voice Dictation (local)** (or **Ctrl/Cmd+Shift+V**). This
   toggles a **floating, modeless, resizable** Voice Dictation window (show →
   hide → show again; the title-bar close, the **Hide** button and **Esc** all
   hide it without losing state). The panel has the status indicator, backend
   selector, a contextual field (model path / LAN URL), a **Check LAN server**
   health button in LAN mode, a scrollable transcript preview that grows with
   the window, and Start / Stop / Commit to editor / Clear / Hide. Hiding or
   closing while recording **stops the session safely and keeps the transcript
   preview** — nothing is silently discarded, and commit stays manual
   (auto-commit is an explicit opt-in, off by default).

If the flag is on but the backend/model is missing, the panel shows a
**non-blocking** setup message and the app stays fully usable.

> Privacy: *Voice mode uses local transcription. Audio is processed on this device.*

## Architecture

`storyplanner/voice/` (pure-logic core, no Qt, headless-testable):

- `types.py` — `VoiceStatus`, `TranscriptSegment`, `VoiceSettings`.
- `silence_detector.py` — stdlib RMS (`array`, no numpy) + trailing-silence.
- `audio_buffer.py` — chunk accumulation + segment finalize (silence / max-dur).
- `transcriber.py` — `Transcriber` interface, `MockTranscriber`,
  `DisabledTranscriber`, `FasterWhisperTranscriber` (lazy; **local model path
  only, no download**), `build_transcriber` (backend-mode dispatch).
- `lan_server.py` — `LanWhisperTranscriber` (stdlib urllib; multipart WAV
  upload; injectable transport) + the **private-host URL validator** and
  no-redirect opener that keep LAN mode off the public internet.
- `recorder.py` — `VoiceRecorder` interface, `MockRecorder`,
  `SoundDeviceRecorder` (lazy; graceful on missing mic / denied permission).
- `session.py` — `VoiceSessionController` state machine (callbacks).
- `editor_commit.py` — `EditorCommitTarget` (plain-text insert at the active
  editor's cursor; mode-agnostic via focus tracking; future hooks stubbed).

UI: `storyplanner/ui/voice_panel.py` — `VoicePanel` (the dictation surface)
hosted in `VoiceDictationWindow`, a **floating, modeless, resizable** window
that is always **parented to the main window** (never a parentless top-level
window, no extra window flags — the rules that keep it clear of the old
standalone-Pages fullscreen-minimize bug). One instance; the menu action /
shortcut toggles show↔hide; close/Hide/Esc hide it with state preserved, and
it never minimizes/hides/closes the main window, never auto-shows at launch
and never auto-starts recording. Transcription runs off the UI thread
(recorder callback thread) and results are marshaled back via Qt signals.
Wired in `MainWindow` (flag-gated, stop-on-switch, stop-on-close).

## Editor insertion (Alpha)

- Only `insert_as_plain_text(transcript)` is live — inserts at the active editor's
  cursor in **any** mode (Novel / Screenplay / Graphic Novel / Stage / Series).
- It never auto-creates scenes/pages/panels, never auto-formats, never guesses
  action vs. dialogue.
- If no editable field is focused, Commit shows a non-blocking message.
- On project switch, the tracked editor is cleared so a pending transcript can
  never be committed into the wrong project.

## Commit targets (Phase 2 — the Voice Commit Router)

After reviewing the transcript, the user picks a **Send to** target in the
panel and clicks Commit. Targets are listed by
`storyplanner/voice/commit_router.py` per writing mode — **listing never
mutates anything**; only the explicit Commit writes, and only after the
router re-validates the target against the live project (a transcript
captured in one project can never be committed into another). Unavailable
targets stay visible but **disabled with a reason**.

Implemented targets:

- **All modes** — Insert at cursor (the original MVP path); **New Note**
  (title `Voice note — <first words>`, body = transcript); **PSYKE draft
  entry** (entry type chosen by the user from Character / Place / Object /
  Lore / Theme / **Other (default)** — the transcript is **never**
  auto-classified).
- **Screenplay** — Insert as Action (blank-line paragraph at cursor); Insert
  as Dialogue under a **manually chosen** character (cue line + dialogue at
  cursor; character names are **never guessed** from the transcript).
- **Graphic Novel** — Panel → Visual / Caption / Dialogue / SFX / Notes for
  the **selected** Panel (the script block last focused in the Manuscript or
  deep-linked from the Outline); text **appends** to the field. With no
  Panel selected the targets are disabled: *"Select a Panel first."* No
  image prompts, no ComfyUI.
- **Stage Script** — Insert as Stage Direction (`STAGE: …` paragraph);
  Insert as Dialogue under a manually chosen character
  (`CHARACTER: NAME` + line).
- **Series** — cursor insert targets the selected Scene's Manuscript editor;
  Notes/PSYKE as above.

Deferred (listed disabled, with these exact reasons): **Outline draft item**
and **Series Episode Outline item** — *"Outline voice target not available
yet."* (the outline is scene-derived; there is no safe unclassified-draft
area); **Append to Manuscript** — *"Use cursor insert — the open editor owns
the scene body."* (a direct DB append could clobber unsaved editor state).

Segments now carry explicit-commit metadata (`id`, `created_at`, `source`,
`committed`, `committed_target`, `committed_at`); no audio is ever stored.
The project is marked dirty **only after** a successful commit; Clear
mutates nothing.

## Transcript history & review (Phase 3)

Finalized segments also land in a **local, session-only transcript history**
inside the panel (`storyplanner/voice/history.py` — nothing is persisted, no
telemetry; per-segment audio is kept **in memory only** for *Retry* and is
dropped on discard/clear). For each segment the user can, explicitly:

- **Edit** (load into the preview → *Apply Edit*; `original_text` is kept and
  *Restore* brings it back; an emptied segment can never be committed);
- **Select** (checkboxes) and **Commit selected** — segments concatenate in
  visible order with their **edited** text and go through the Commit Router
  (never around it); successful commits mark the segments
  `committed → target`, failures leave them pending;
- **Merge** adjacent uncommitted segments / **Split** one at the preview
  cursor (text-level only; audio is not split, so Retry lapses);
- **Retry transcription** when the segment's local audio is still held —
  re-runs the LOCAL transcriber only; a failed retry keeps the old text;
  otherwise the button explains: *"Audio segment no longer available."*;
- **Discard** / **Clear uncommitted** / clear the session;
- **Undo last voice commit** (single level, target-scoped): cursor-family
  inserts undo via the editor's own undo stack **only if nothing changed
  since** (document-revision guard — unrelated edits are never reverted);
  Graphic Novel field commits restore the captured previous value; Note /
  PSYKE commits delete the created entry only if it is unchanged. When undo
  is not safe the button is disabled with the reason.

Project safety is per-segment: each entry records the project (and writing
mode) it was captured in; switching projects freezes the visible history and
any commit of foreign segments is blocked: *"This transcript was captured in
another project. Switch back or explicitly retarget."*

## Dictation vs Intent mode (Phase 4 — the Voice Intent Router)

The panel has an explicit mode selector — **Dictation** (default: the
transcript is content; the Phase 2 commit targets apply) and **Intent**
(opt-in: the transcript is an *instruction*). Intent mode is **preview-first
and confirm-only** (`storyplanner/voice/intent_router.py`): pick an intent,
click **Preview**, review the before/after (or the Note/PSYKE-entry
preview), then **Apply** — or **Cancel**, which mutates nothing. Command
mode is never inferred from a transcript; nothing ever auto-applies.

Fixed intent allowlist:

- **Clean up transcript** (rule-based, no AI): whitespace/capitalization
  normalization, optional spoken punctuation ("comma" → ",", "period" →
  ".", "new paragraph" → break), final period — never fabricates content.
  Applying updates only the transcript segment (project untouched).
- **Insert cleaned transcript** — cleaned text routed through the chosen
  commit target (the Commit Router; never bypassed).
- **Rewrite selected text** (AI) — needs an editor selection; before/after
  + diff preview; apply replaces exactly the selection (one undo step).
  Disabled without a selection: *"Select text first."*
- **Summarize to Note** (AI) — note preview; apply creates the Note.
- **Send to PSYKE draft entry** — user-chosen type (default **Other**,
  never classified); entry preview; apply creates it.
- **Graphic Novel: send to selected Panel field** — user-chosen field
  (Visual/Caption/Dialogue/SFX/Notes); append preview; Outline/Manuscript
  mirror after apply. No image prompts, no ComfyUI.
- **Outline draft item** — still listed disabled (*"Outline voice target
  not available yet."*).

AI policy: AI-backed intents use the app's **existing provider settings
only** (`build_active_provider` + the shared chat completion) — **text in,
text out; audio is never sent to AI or any cloud speech API**. With no
provider configured they are disabled with: *"AI text operation
unavailable. Configure an AI provider or use rule-based cleanup."*

Safety: previews store the project id and the expected before-state; Apply
re-validates the live project, target existence and before-text — a stale
preview is blocked with *"Target changed since preview. Regenerate preview
before applying."* Applied intents produce the same operation records as
Phase 3, so **Undo last commit** covers them (editor revision guard, GN
previous-value restore, created Note/PSYKE deletion). No shell/system
commands, no voice-command execution, no unrestricted agent.

## Billy Voice Bridge (Phase 5)

A **Billy** row in the panel bridges selected transcript segments to Billy —
the app's Assistant chat agent — as a question or an editing instruction.
Billy receives **transcript text + a minimal safe context only** (project
title, writing mode, selection snippet, selected GN panel fields — never
audio, never API keys/provider settings, never other-project data), through
the app's **existing provider configuration** (nothing is chosen silently;
unconfigured ⇒ every Billy action disables with *"Billy is not configured.
Voice-to-Billy actions are unavailable."*).

Operations (fixed allowlist; unavailable ones disable with a reason):
**Ask Billy** (chat-only answer, nothing to apply), **Rewrite selected
text**, **Continue from cursor**, **Summarize to Note**, **Propose PSYKE
draft** (user-chosen type, default Other), **Propose Panel field update**
(GN, selected panel + chosen field, replace with before/after diff;
Outline/Manuscript mirror), and **Propose Outline item** (still listed
disabled). Every proposal is **preview-first**: Generate → review
(before/after + diff or entity preview) → explicit **Apply** (routed through
the existing Intent/Commit routers, inheriting live re-validation and the
Phase 3 undo records) or **Cancel** (zero mutation). Stale proposals are
blocked: *"Target changed since Billy generated this proposal. Regenerate
before applying."* / *"Project changed since this proposal was generated.
Switch back or regenerate."*

**Not voice commands:** dangerous spoken instructions ("delete the
project", "run this command", "send to ComfyUI", "open terminal", …) are
never executed and never even reach the provider — Billy answers chat-only:
*"I can't perform that action from voice in Alpha."* Transcript history
tracks `sent_to_billy` / proposal id / applied-or-cancelled per segment (no
secrets, no audio).

## Future hooks (anchor points, not implemented)

`EditorCommitTarget` defines (and deliberately stubs) the later shape:
`insert_as_screenplay_dialogue`, `insert_as_action`, `insert_as_note`,
`send_to_outline`, `send_to_psyke`, `send_to_graphic_novel_panel`,
`send_to_stage_direction`, `send_to_series_outline`; plus a future voice-command
parser and a later cloud-realtime path.

## Known limitations

- Near-live **segmented** dictation only (not true streaming).
- No classification / formatting / commands / diarization.
- Real microphone + transcription require the optional local backends + a local
  model path; without them, the feature shows a setup message and stays inert.
- Transcribing the final segment on Stop runs inline (brief, one segment).
