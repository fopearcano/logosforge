"""Local voice-to-script MVP (buffered dictation; local Whisper; manual commit).

Local-first and isolated: no cloud speech API, no audio leaves the machine. The
microphone and Whisper backends are optional + lazy-imported, so importing this
package is always safe even when voice is disabled or the backends are absent.
Feature-flagged OFF by default (``enable_voice_mode``). See ``docs/VOICE_MVP.md``.
"""

from __future__ import annotations

from storyplanner.voice.audio_buffer import AudioBuffer
from storyplanner.voice.editor_commit import EditorCommitTarget
from storyplanner.voice.recorder import (
    MockRecorder,
    SoundDeviceRecorder,
    VoiceRecorder,
    build_recorder,
)
from storyplanner.voice.session import VoiceSessionController
from storyplanner.voice.silence_detector import SimpleSilenceDetector
from storyplanner.voice.transcriber import (
    FasterWhisperTranscriber,
    MockTranscriber,
    Transcriber,
    build_transcriber,
)
from storyplanner.voice.types import (
    PRIVACY_NOTE,
    SETUP_MESSAGE,
    TranscriptSegment,
    VoiceSettings,
    VoiceStatus,
)

__all__ = [
    "AudioBuffer", "SimpleSilenceDetector",
    "VoiceRecorder", "MockRecorder", "SoundDeviceRecorder", "build_recorder",
    "Transcriber", "MockTranscriber", "FasterWhisperTranscriber",
    "build_transcriber",
    "VoiceSessionController", "EditorCommitTarget",
    "VoiceStatus", "TranscriptSegment", "VoiceSettings",
    "SETUP_MESSAGE", "PRIVACY_NOTE",
]


def load_voice_settings() -> VoiceSettings:
    """Load :class:`VoiceSettings` from the app settings store."""
    from storyplanner.settings import get_manager
    return VoiceSettings.from_store(get_manager().get)
