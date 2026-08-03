"""ASR engine contract for local Nadikt model adapters.

This module is part of the pure domain boundary. It intentionally imports only
the Python standard library and Nadikt-owned types. SDK objects from GigaAM,
faster-whisper, CTranslate2, PyTorch or UI/platform layers must not cross this
boundary.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Mapping, Protocol


class AsrBackend(str, Enum):
    """Supported backend families for benchmark and runtime metadata."""

    GIGAAM = "gigaam"
    FASTER_WHISPER = "faster-whisper"
    TONE = "tone"
    OTHER_LOCAL = "other-local"


class AsrFailureCode(str, Enum):
    """Safe failure codes; no user payload belongs in error messages."""

    MISSING_PACKAGE = "missing_package"
    INVALID_PACKAGE_PATH = "invalid_package_path"
    CHECKSUM_MISMATCH = "checksum_mismatch"
    MISSING_CRITICAL_FILE = "missing_critical_file"
    INCOMPATIBLE_BACKEND = "incompatible_backend"
    LICENSE_NOT_VERIFIED = "license_not_verified"
    ENGINE_NOT_READY = "engine_not_ready"
    SEGMENT_TOO_LONG = "segment_too_long"
    CANCELLED = "cancelled"
    TRANSCRIBE_FAILED = "transcribe_failed"
    WARM_UP_FAILED = "warm_up_failed"
    RESOURCE_RELEASE_FAILED = "resource_release_failed"


class AsrEngineError(Exception):
    """Exception carrying only a typed, privacy-safe ASR failure."""

    def __init__(self, failure: "AsrFailure") -> None:
        super().__init__(failure.code.value)
        self.failure = failure


@dataclass(frozen=True)
class AsrCapabilities:
    """Normalized feature description independent of concrete SDKs."""

    languages: tuple[str, ...]
    max_segment_seconds: float
    punctuation: bool
    streaming: bool
    word_timestamps: bool = False

    def __post_init__(self) -> None:
        if self.max_segment_seconds <= 0:
            raise ValueError("max_segment_seconds must be positive")


@dataclass(frozen=True, repr=False)
class AsrModelMetadata:
    """Safe model metadata for logs, reports and diagnostics."""

    package_id: str
    candidate_id: str
    backend: AsrBackend
    model_name: str
    model_revision: str
    backend_version: str
    license_marker: str
    capabilities: AsrCapabilities
    checksum_prefixes: tuple[str, ...] = field(default_factory=tuple)

    def __repr__(self) -> str:
        return (
            "AsrModelMetadata("
            f"package_id={self.package_id!r}, "
            f"candidate_id={self.candidate_id!r}, "
            f"backend={self.backend.value!r}, "
            f"model_revision={self.model_revision!r})"
        )


@dataclass(frozen=True, repr=False)
class AsrLoadOptions:
    """Validated local package path and normalized inference defaults."""

    local_package_path: Path
    inference_defaults: Mapping[str, object]

    def __post_init__(self) -> None:
        if not self.local_package_path:
            raise ValueError("local_package_path is required")

    def __repr__(self) -> str:
        return "AsrLoadOptions(local_package_path=<redacted>, inference_defaults=<safe-config>)"


@dataclass(frozen=True, repr=False)
class AsrSegmentInput:
    """One audio segment passed to an ASR engine.

    The audio path is deliberately redacted from repr because local paths can
    reveal user or client names.
    """

    sample_id: str
    segment_id: int
    audio_path: Path
    start_seconds: float
    end_seconds: float
    language_profile: str
    segmentation_policy_id: str

    @property
    def duration_seconds(self) -> float:
        return self.end_seconds - self.start_seconds

    def __post_init__(self) -> None:
        if self.segment_id < 0:
            raise ValueError("segment_id must be non-negative")
        if self.start_seconds < 0:
            raise ValueError("start_seconds must be non-negative")
        if self.end_seconds <= self.start_seconds:
            raise ValueError("end_seconds must be greater than start_seconds")

    def __repr__(self) -> str:
        return (
            "AsrSegmentInput("
            f"sample_id={self.sample_id!r}, "
            f"segment_id={self.segment_id!r}, "
            f"duration_seconds={self.duration_seconds:.3f}, "
            f"language_profile={self.language_profile!r}, "
            f"segmentation_policy_id={self.segmentation_policy_id!r})"
        )


@dataclass(frozen=True, repr=False)
class AsrSegmentTranscript:
    """Normalized transcript result for a segment.

    The text is intentionally omitted from repr. Application code may consume
    the text, but logging code must only use safe metadata.
    """

    segment_id: int
    text: str
    start_seconds: float
    end_seconds: float
    confidence: float | None = None

    def __repr__(self) -> str:
        return (
            "AsrSegmentTranscript("
            f"segment_id={self.segment_id!r}, "
            f"start_seconds={self.start_seconds:.3f}, "
            f"end_seconds={self.end_seconds:.3f}, "
            f"text_chars={len(self.text)})"
        )


@dataclass(frozen=True, repr=False)
class AsrFailure:
    """Typed safe ASR failure envelope without raw SDK messages."""

    code: AsrFailureCode
    phase: str
    recoverable: bool
    retryable: bool = False

    def __repr__(self) -> str:
        return (
            "AsrFailure("
            f"code={self.code.value!r}, phase={self.phase!r}, "
            f"recoverable={self.recoverable!r}, retryable={self.retryable!r})"
        )


@dataclass(frozen=True)
class AsrTimingEvent:
    """SDK-neutral lifecycle timing event for safe instrumentation."""

    phase: str
    duration_ms: float
    package_id: str
    segment_id: int | None = None
    outcome: str = "success"


class AsrInferenceObserver(Protocol):
    """Receives safe lifecycle timing without transcript/audio/SDK payload."""

    def record(self, event: AsrTimingEvent) -> None:
        """Record an allowlisted timing event."""


class AsrEngine(Protocol):
    """Unified ASR engine lifecycle contract."""

    def metadata(self) -> AsrModelMetadata:
        """Return safe metadata for the loaded or configured engine."""

    def load(self, options: AsrLoadOptions) -> None:
        """Load a verified local model package."""

    def is_ready(self) -> bool:
        """Return whether the engine can accept segment transcription."""

    def warm_up(self, segment: AsrSegmentInput, observer: AsrInferenceObserver | None = None) -> None:
        """Run actual inference on a verified non-scored segment."""

    def transcribe_segment(
        self,
        segment: AsrSegmentInput,
        observer: AsrInferenceObserver | None = None,
    ) -> AsrSegmentTranscript:
        """Transcribe exactly one valid audio segment."""

    def cancel(self) -> None:
        """Cancel current processing when supported by the backend."""

    def close(self) -> None:
        """Release model and native resources."""


def safe_engine_log_context(metadata: AsrModelMetadata) -> dict[str, object]:
    """Build privacy-safe structured context for logs."""

    return {
        "package_id": metadata.package_id,
        "candidate_id": metadata.candidate_id,
        "backend": metadata.backend.value,
        "model_revision": metadata.model_revision,
        "checksum_prefixes": list(metadata.checksum_prefixes),
    }


def safe_timing_log_context(event: AsrTimingEvent) -> dict[str, object]:
    """Build privacy-safe context for observer events."""

    return {
        "phase": event.phase,
        "duration_ms": event.duration_ms,
        "package_id": event.package_id,
        "segment_id": event.segment_id,
        "outcome": event.outcome,
    }


def ensure_segment_within_capabilities(
    segment: AsrSegmentInput,
    capabilities: AsrCapabilities,
) -> None:
    """Reject segments that exceed the active engine limit."""

    if segment.duration_seconds > capabilities.max_segment_seconds:
        raise ValueError(AsrFailureCode.SEGMENT_TOO_LONG.value)


__all__ = [
    "AsrBackend",
    "AsrCapabilities",
    "AsrEngine",
    "AsrEngineError",
    "AsrFailure",
    "AsrFailureCode",
    "AsrInferenceObserver",
    "AsrLoadOptions",
    "AsrModelMetadata",
    "AsrSegmentInput",
    "AsrSegmentTranscript",
    "AsrTimingEvent",
    "ensure_segment_within_capabilities",
    "safe_engine_log_context",
    "safe_timing_log_context",
]
