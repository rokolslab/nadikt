"""Bounded dictation pipeline orchestration.

This vertical-slice service intentionally handles exactly one captured segment:
``capture -> transcribe_segment -> normalize -> insert``. Long dictation, VAD,
segment assembly, user dictionaries and voice commands remain outside this
minimal slice.
"""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass
from enum import Enum
from typing import Protocol

from nadikt.domain.dictation import DictationOutcomeCode, DictationSession, safe_session_log_context
from nadikt.domain.ports.asr import AsrEngine, safe_engine_log_context
from nadikt.domain.ports.audio import (
    AudioCaptureOptions,
    AudioCapturePort,
    AudioCaptureResult,
    safe_audio_capture_log_context,
)

LOGGER = logging.getLogger(__name__)
_LOG_LEVEL = os.environ.get("NADIKT_LOG_LEVEL", os.environ.get("LOG_LEVEL", "INFO")).upper()
logging.basicConfig(level=getattr(logging, _LOG_LEVEL, logging.INFO))


class DictationPipelineStatus(str, Enum):
    """Safe high-level pipeline statuses."""

    COMPLETED = "completed"
    CANCELLED = "cancelled"
    FAILED = "failed"


class TextNormalizerPort(Protocol):
    """Deterministic text normalizer boundary."""

    def normalize(self, text: str) -> str:
        """Return insertion-shaped text. Callers must not log text."""


@dataclass(frozen=True, repr=False)
class TextInsertionResult:
    """Insertion outcome without inserted text or target details."""

    success: bool
    outcome_code: str
    retained_result: bool = False
    pending_clipboard_restore: bool = False

    def __repr__(self) -> str:
        return (
            "TextInsertionResult("
            f"success={self.success!r}, outcome_code={self.outcome_code!r}, "
            f"retained_result={self.retained_result!r}, "
            f"pending_clipboard_restore={self.pending_clipboard_restore!r})"
        )


class TextInsertionPort(Protocol):
    """Application-facing insertion service boundary."""

    def insert_text(self, text: str) -> TextInsertionResult:
        """Insert text into the captured safe target. Callers must not log text."""


@dataclass(frozen=True, repr=False)
class DictationRunOptions:
    """Options for one bounded dictation pipeline run."""

    capture: AudioCaptureOptions
    cleanup_audio: bool = True

    def __repr__(self) -> str:
        return f"DictationRunOptions(capture={self.capture!r}, cleanup_audio={self.cleanup_audio!r})"


@dataclass(frozen=True, repr=False)
class DictationRunOutcome:
    """Pipeline result with transcript redacted from repr/logging."""

    status: DictationPipelineStatus
    session_id: str
    outcome_code: str
    retained_result: bool
    retained_text_chars: int
    segment_count: int
    duration_ms: float

    def __repr__(self) -> str:
        return (
            "DictationRunOutcome("
            f"status={self.status.value!r}, session_id={self.session_id!r}, "
            f"outcome_code={self.outcome_code!r}, retained_result={self.retained_result!r}, "
            f"retained_text_chars={self.retained_text_chars!r}, "
            f"segment_count={self.segment_count!r}, duration_ms={self.duration_ms:.3f})"
        )


class DictationPipelineService:
    """Coordinates one bounded dictation session through injected ports."""

    def __init__(
        self,
        audio_capture: AudioCapturePort,
        asr_engine: AsrEngine,
        text_normalizer: TextNormalizerPort,
        insertion_service: TextInsertionPort,
    ) -> None:
        self._audio_capture = audio_capture
        self._asr_engine = asr_engine
        self._text_normalizer = text_normalizer
        self._insertion_service = insertion_service

    def run_once(self, options: DictationRunOptions) -> DictationRunOutcome:
        started_at = time.perf_counter()
        session = DictationSession()
        capture_result: AudioCaptureResult | None = None
        LOGGER.debug("dictation_pipeline.run_once.start", extra={"session_id": session.session_id})
        try:
            LOGGER.debug("dictation_pipeline.state.begin_capture", extra=safe_session_log_context(session))
            session.begin_capture()
            capture_result = self._audio_capture.capture_once(options.capture)
            LOGGER.debug("dictation_pipeline.capture.complete", extra=safe_audio_capture_log_context(capture_result))

            session.begin_recognition(segment_count=1)
            metadata = self._asr_engine.metadata()
            LOGGER.debug(
                "dictation_pipeline.asr.transcribe.start",
                extra={**safe_session_log_context(session), **safe_engine_log_context(metadata)},
            )
            transcript = self._asr_engine.transcribe_segment(capture_result.segment)
            session.retain_final_transcript(transcript.text, segment_count=1)
            LOGGER.debug(
                "dictation_pipeline.asr.transcribe.complete",
                extra={
                    **safe_session_log_context(session),
                    "segment_id": transcript.segment_id,
                    "text_chars": len(transcript.text),
                },
            )

            session.begin_normalization()
            LOGGER.debug(
                "dictation_pipeline.normalization.start",
                extra={**safe_session_log_context(session), "input_chars": len(transcript.text)},
            )
            normalized_text = self._text_normalizer.normalize(transcript.text)
            session.retain_final_transcript(normalized_text, segment_count=1)
            LOGGER.debug(
                "dictation_pipeline.normalization.complete",
                extra={
                    **safe_session_log_context(session),
                    "output_chars": len(normalized_text),
                    "rule_scope": "deterministic-slice",
                },
            )

            session.begin_insertion()
            LOGGER.debug("dictation_pipeline.insertion.start", extra=safe_session_log_context(session))
            insertion = self._insertion_service.insert_text(normalized_text)
            LOGGER.debug(
                "dictation_pipeline.insertion.complete",
                extra={
                    **safe_session_log_context(session),
                    "insertion_outcome": insertion.outcome_code,
                    "pending_clipboard_restore": insertion.pending_clipboard_restore,
                },
            )
            if not insertion.success:
                session.fail(DictationOutcomeCode.INSERTION_FAILED)
                return self._outcome(session, started_at, insertion.outcome_code)

            session.complete_delivery()
            return self._outcome(session, started_at, DictationOutcomeCode.SUCCESS.value)
        except Exception:
            failure_code = self._failure_code_for_state(session)
            LOGGER.debug(
                "dictation_pipeline.run_once.failed",
                extra={**safe_session_log_context(session), "failure_code": failure_code.value},
            )
            if not session.is_terminal:
                session.fail(failure_code)
            return self._outcome(session, started_at, session.outcome_code.value if session.outcome_code else "failed")
        finally:
            if capture_result is not None and options.cleanup_audio:
                LOGGER.debug("dictation_pipeline.audio_cleanup.start", extra=safe_audio_capture_log_context(capture_result))
                try:
                    self._audio_capture.cleanup(capture_result)
                except Exception:
                    LOGGER.debug(
                        "[FIX] dictation_pipeline.audio_cleanup.failed",
                        extra={**safe_audio_capture_log_context(capture_result), "cleanup_outcome": "failed_retained_pipeline_outcome"},
                    )
                else:
                    LOGGER.debug("dictation_pipeline.audio_cleanup.complete", extra=safe_audio_capture_log_context(capture_result))

    def _failure_code_for_state(self, session: DictationSession) -> DictationOutcomeCode:
        if session.state.value == "capturing":
            return DictationOutcomeCode.CAPTURE_FAILED
        if session.state.value == "recognizing":
            return DictationOutcomeCode.RECOGNITION_FAILED
        if session.state.value == "normalizing":
            return DictationOutcomeCode.NORMALIZATION_FAILED
        return DictationOutcomeCode.INSERTION_FAILED

    def _outcome(
        self,
        session: DictationSession,
        started_at: float,
        outcome_code: str,
    ) -> DictationRunOutcome:
        status = DictationPipelineStatus.COMPLETED
        if session.state.value == "cancelled":
            status = DictationPipelineStatus.CANCELLED
        elif session.state.value == "failed":
            status = DictationPipelineStatus.FAILED
        outcome = DictationRunOutcome(
            status=status,
            session_id=session.session_id,
            outcome_code=outcome_code,
            retained_result=session.has_retained_result,
            retained_text_chars=session.retained_text_chars,
            segment_count=session.segment_count,
            duration_ms=(time.perf_counter() - started_at) * 1000,
        )
        LOGGER.debug("dictation_pipeline.run_once.outcome", extra={"outcome": repr(outcome)})
        return outcome


__all__ = [
    "DictationPipelineService",
    "DictationPipelineStatus",
    "DictationRunOptions",
    "DictationRunOutcome",
    "TextInsertionPort",
    "TextInsertionResult",
    "TextNormalizerPort",
]
