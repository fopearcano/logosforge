"""Local voice-to-script MVP — shared types and settings.

Pure data types for the local, buffered dictation subsystem. No Qt, no audio or
Whisper dependencies here — those are lazy-imported by the backend modules so the
app (and these types) stay importable everywhere, even when voice is off or the
optional local backends are not installed.

This is *near-live segmented dictation* with **local** transcription and **manual**
commit. It is not cloud realtime, not speech-to-speech, and does not classify or
auto-format transcripts. See ``docs/VOICE_MVP.md``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class VoiceStatus(str, Enum):
    """Lifecycle of a voice dictation session (UI reflects these directly)."""

    DISABLED = "disabled"            # feature flag off, or backend not configured
    OFF = "off"                      # enabled + ready, not currently listening
    LISTENING = "listening"          # capturing audio
    PROCESSING = "processing"        # transcribing a finalized segment
    TRANSCRIPT_READY = "transcript_ready"
    ERROR = "error"


@dataclass
class TranscriptSegment:
    """One transcribed segment (Alpha: always treated as plain text)."""

    text: str = ""
    is_final: bool = True
    language: str = ""
    duration_s: float = 0.0
    error: str = ""

    def is_empty(self) -> bool:
        return not (self.text or "").strip()


@dataclass
class VoiceSettings:
    """Snapshot of the voice settings (loaded from the app settings store)."""

    enabled: bool = False
    backend: str = "faster-whisper"
    model_path: str = ""
    executable_path: str = ""
    language: str = "auto"
    auto_commit: bool = False
    silence_ms: int = 900
    max_segment_seconds: int = 25
    overlap_ms: int = 0
    sample_rate: int = 16000          # Whisper-style mono 16 kHz
    channels: int = 1

    @classmethod
    def from_store(cls, get) -> "VoiceSettings":
        """Build from a ``get(key)`` accessor (e.g. ``settings.get_manager().get``)."""
        def _int(key, default):
            try:
                return int(get(key))
            except (TypeError, ValueError):
                return default
        return cls(
            enabled=bool(get("enable_voice_mode")),
            backend=str(get("voice_whisper_backend") or "faster-whisper"),
            model_path=str(get("voice_whisper_model_path") or ""),
            executable_path=str(get("voice_whisper_executable_path") or ""),
            language=str(get("voice_language") or "auto"),
            auto_commit=bool(get("voice_auto_commit")),
            silence_ms=_int("voice_silence_ms", 900),
            max_segment_seconds=_int("voice_max_segment_seconds", 25),
            overlap_ms=_int("voice_overlap_ms", 0),
        )


# Non-blocking setup message shown when the backend/model is not configured.
SETUP_MESSAGE = (
    "Local Whisper is not configured. Voice mode is disabled until setup is "
    "complete."
)
PRIVACY_NOTE = (
    "Voice mode uses local transcription. Audio is processed on this device."
)
