"""Audio capture contract for bounded local dictation.

This domain port stays SDK-neutral and platform-neutral. Concrete adapters own
microphone APIs, temp-file paths, device names and cleanup details; DTO reprs
expose only allowlisted timing/count/outcome metadata.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Protocol

from nadikt.domain.ports.asr import AsrSegmentInput


class AudioCaptureFailureCode(str, Enum):
    """Safe audio capture outcomes without device names or local paths."""

    CANCELLED = "cancelled"
    PERMISSION_DENIED = "permission_denied"
    DEVICE_UNAVAILABLE = "device_unavailable"
    DEVICE_DISCONNECTED = "device_disconnected"
    INVALID_DEVICE = "invalid_device"
    CAPTURE_TIMEOUT = "capture_timeout"
    LEVEL_TOO_LOW = "level_too_low"
    TEMP_CLEANUP_FAILED = "temp_cleanup_failed"
    CAPTURE_FAILED = "capture_failed"


class AudioLevelStatus(str, Enum):
    """Coarse level status for safe logs and operator feedback."""

    UNKNOWN = "unknown"
    SILENCE = "silence"
    LOW = "low"
    NORMAL = "normal"
    CLIPPED = "clipped"


class AudioCaptureError(Exception):
    """Exception carrying only a typed, privacy-safe audio failure."""

    def __init__(self, failure: "AudioCaptureFailure") -> None:
        super().__init__(failure.code.value)
        self.failure = failure


@dataclass(frozen=True, repr=False)
class AudioDeviceDescriptor:
    """Opaque device descriptor selected by an infrastructure adapter."""

    device_id: str
    capability_category: str
    is_default: bool = False

    def __repr__(self) -> str:
        return (
            "AudioDeviceDescriptor("
            f"device_id={self.device_id!r}, "
            f"capability_category={self.capability_category!r}, "
            f"is_default={self.is_default!r})"
        )


@dataclass(frozen=True, repr=False)
class AudioCaptureOptions:
    """Bounded one-shot capture options accepted by audio adapters."""

    max_duration_seconds: float
    sample_rate_hz: int
    channel_count: int = 1
    pre_buffer_seconds: float = 0.0
    selected_device_id: str | None = None
    language_profile: str = "ru-coding"
    segmentation_policy_id: str = "bounded-one-shot.v1"

    def __post_init__(self) -> None:
        if self.max_duration_seconds <= 0:
            raise ValueError("max_duration_seconds must be positive")
        if self.sample_rate_hz <= 0:
            raise ValueError("sample_rate_hz must be positive")
        if self.channel_count <= 0:
            raise ValueError("channel_count must be positive")
        if self.pre_buffer_seconds < 0:
            raise ValueError("pre_buffer_seconds must be non-negative")

    def __repr__(self) -> str:
        return (
            "AudioCaptureOptions("
            f"max_duration_seconds={self.max_duration_seconds!r}, "
            f"sample_rate_hz={self.sample_rate_hz!r}, "
            f"channel_count={self.channel_count!r}, "
            f"pre_buffer_seconds={self.pre_buffer_seconds!r}, "
            f"selected_device_id={'<set>' if self.selected_device_id else None!r}, "
            f"language_profile={self.language_profile!r}, "
            f"segmentation_policy_id={self.segmentation_policy_id!r})"
        )


@dataclass(frozen=True, repr=False)
class AudioCaptureResult:
    """One bounded segment ready for ASR plus safe capture metadata."""

    segment: AsrSegmentInput
    device: AudioDeviceDescriptor
    level_status: AudioLevelStatus
    duration_seconds: float
    sample_rate_hz: int
    channel_count: int
    cleanup_required: bool = True
    warnings: tuple[AudioCaptureFailureCode, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if self.duration_seconds <= 0:
            raise ValueError("duration_seconds must be positive")

    def __repr__(self) -> str:
        return (
            "AudioCaptureResult("
            f"sample_id={self.segment.sample_id!r}, "
            f"segment_id={self.segment.segment_id!r}, "
            f"duration_seconds={self.duration_seconds:.3f}, "
            f"sample_rate_hz={self.sample_rate_hz!r}, "
            f"channel_count={self.channel_count!r}, "
            f"level_status={self.level_status.value!r}, "
            f"cleanup_required={self.cleanup_required!r}, "
            f"warning_codes={[code.value for code in self.warnings]!r})"
        )


@dataclass(frozen=True, repr=False)
class AudioCaptureFailure:
    """Typed safe audio failure envelope."""

    code: AudioCaptureFailureCode
    phase: str
    recoverable: bool
    retryable: bool = False

    def __repr__(self) -> str:
        return (
            "AudioCaptureFailure("
            f"code={self.code.value!r}, phase={self.phase!r}, "
            f"recoverable={self.recoverable!r}, retryable={self.retryable!r})"
        )


class AudioCapturePort(Protocol):
    """Bounded one-shot microphone capture boundary."""

    def list_input_devices(self) -> tuple[AudioDeviceDescriptor, ...]:
        """Return safe descriptors for operator selection."""

    def capture_once(self, options: AudioCaptureOptions) -> AudioCaptureResult:
        """Capture one bounded audio segment suitable for ASR."""

    def cancel(self) -> None:
        """Cancel active capture when supported by the adapter."""

    def cleanup(self, result: AudioCaptureResult) -> None:
        """Remove adapter-owned temporary capture resources."""


def safe_audio_capture_log_context(result: AudioCaptureResult) -> dict[str, object]:
    """Build allowlisted capture metadata for application logging."""

    return {
        "sample_id": result.segment.sample_id,
        "segment_id": result.segment.segment_id,
        "duration_seconds": result.duration_seconds,
        "sample_rate_hz": result.sample_rate_hz,
        "channel_count": result.channel_count,
        "level_status": result.level_status.value,
        "device_id": result.device.device_id,
        "capability_category": result.device.capability_category,
        "cleanup_required": result.cleanup_required,
        "warning_codes": [code.value for code in result.warnings],
        "segmentation_policy_id": result.segment.segmentation_policy_id,
    }


__all__ = [
    "AudioCaptureError",
    "AudioCaptureFailure",
    "AudioCaptureFailureCode",
    "AudioCaptureOptions",
    "AudioCapturePort",
    "AudioCaptureResult",
    "AudioDeviceDescriptor",
    "AudioLevelStatus",
    "safe_audio_capture_log_context",
]
