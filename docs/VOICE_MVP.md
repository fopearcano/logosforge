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
