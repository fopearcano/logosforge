# Local Voice-to-Script (Alpha MVP)

A **local-first**, feature-flagged dictation foundation: speak, get a transcript
from a **local** Whisper-style backend, review it, and **commit it as plain text**
into the active editor. It is intentionally minimal.

## What it is

- **Near-live segmented dictation.** Audio is captured locally, buffered in short
  chunks, and a segment is finalized on a pause (silence) or after a max duration,
  then transcribed locally.
- **Local transcription only.** No cloud speech API; **no audio leaves the
  device.** The backend (faster-whisper) and microphone (sounddevice) are
  **optional, lazy-loaded** dependencies.
- **Manual commit.** The transcript appears in a preview; you click **Commit to
  editor** to insert it at the cursor. Auto-commit-after-pause is an opt-in toggle,
  **off by default**.

## What it is NOT (deferred)

- Not cloud realtime / speech-to-speech / a "Live Writer Room".
- No automatic classification (dialogue / action / note / outline / PSYKE / panel).
- No automatic Fountain / screenplay formatting.
- No voice commands, no speaker diarization.
- No automatic model downloads.
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
   - `voice_whisper_backend = "faster-whisper"` (or `"mock"` for a no-audio demo)
   - `voice_whisper_model_path = "/path/to/local/model"`
   - optionally `voice_language` (`"auto"`/`"en"`/`"it"`), `voice_silence_ms`,
     `voice_max_segment_seconds`, `voice_auto_commit`.
4. Open **View → Voice Dictation (local)** (or **Ctrl/Cmd+Shift+V**).

If the flag is on but the backend/model is missing, the panel shows a
**non-blocking** setup message and the app stays fully usable.

> Privacy: *Voice mode uses local transcription. Audio is processed on this device.*

## Architecture

`storyplanner/voice/` (pure-logic core, no Qt, headless-testable):

- `types.py` — `VoiceStatus`, `TranscriptSegment`, `VoiceSettings`.
- `silence_detector.py` — stdlib RMS (`array`, no numpy) + trailing-silence.
- `audio_buffer.py` — chunk accumulation + segment finalize (silence / max-dur).
- `transcriber.py` — `Transcriber` interface, `MockTranscriber`,
  `FasterWhisperTranscriber` (lazy; **local model path only, no download**).
- `recorder.py` — `VoiceRecorder` interface, `MockRecorder`,
  `SoundDeviceRecorder` (lazy; graceful on missing mic / denied permission).
- `session.py` — `VoiceSessionController` state machine (callbacks).
- `editor_commit.py` — `EditorCommitTarget` (plain-text insert at the active
  editor's cursor; mode-agnostic via focus tracking; future hooks stubbed).

UI: `storyplanner/ui/voice_panel.py` — `VoicePanel`, an **embedded** bottom strip
(same safe pattern as the Logos suggestions / diagnostics drawers — never a
floating / top-level window, so it cannot trigger the fullscreen-minimize bug).
Transcription runs off the UI thread (recorder callback thread) and results are
marshaled back via Qt signals. Wired in `MainWindow` (flag-gated, stop-on-switch,
stop-on-close).

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
