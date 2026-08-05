"""Explicit dictation session state for the production pipeline.

The domain layer deliberately does not log. Callers can use
``safe_session_log_context`` for allowlisted diagnostic fields without exposing
transcript text, audio paths, target details or clipboard payloads.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from uuid import uuid4


class DictationSessionState(str, Enum):
    """States for one bounded dictation attempt."""

    IDLE = "idle"
    CAPTURING = "capturing"
    RECOGNIZING = "recognizing"
    NORMALIZING = "normalizing"
    INSERTING = "inserting"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    FAILED = "failed"


class DictationOutcomeCode(str, Enum):
    """Typed, privacy-safe outcomes for session transitions."""

    SUCCESS = "success"
    CANCELLED = "cancelled"
    CONCURRENT_SESSION = "concurrent_session"
    INVALID_TRANSITION = "invalid_transition"
    CAPTURE_FAILED = "capture_failed"
    RECOGNITION_FAILED = "recognition_failed"
    NORMALIZATION_FAILED = "normalization_failed"
    INSERTION_FAILED = "insertion_failed"
    DOUBLE_INSERTION = "double_insertion"


class DictationResultKind(str, Enum):
    """Classification of retained text without revealing the text itself."""

    PARTIAL = "partial"
    FINAL = "final"


TERMINAL_STATES = frozenset(
    {
        DictationSessionState.COMPLETED,
        DictationSessionState.CANCELLED,
        DictationSessionState.FAILED,
    }
)


class DictationSessionError(Exception):
    """Base exception carrying only typed session failure metadata."""

    def __init__(self, failure: "DictationSessionFailure") -> None:
        super().__init__(failure.code.value)
        self.failure = failure


class InvalidDictationTransition(DictationSessionError):
    """Raised when a transition would violate the session state machine."""


@dataclass(frozen=True, repr=False)
class DictationSessionFailure:
    """Safe failure envelope for application outcomes and diagnostics."""

    code: DictationOutcomeCode
    from_state: DictationSessionState
    attempted_state: DictationSessionState | None = None
    segment_count: int = 0
    retained_result: bool = False

    def __repr__(self) -> str:
        return (
            "DictationSessionFailure("
            f"code={self.code.value!r}, "
            f"from_state={self.from_state.value!r}, "
            f"attempted_state={self.attempted_state.value if self.attempted_state else None!r}, "
            f"segment_count={self.segment_count!r}, "
            f"retained_result={self.retained_result!r})"
        )


@dataclass(frozen=True, repr=False)
class RetainedTranscript:
    """Transcript retained for later delivery, redacted from repr."""

    kind: DictationResultKind
    text: str
    segment_count: int

    def __post_init__(self) -> None:
        if self.segment_count < 0:
            raise ValueError("segment_count must be non-negative")

    @property
    def text_chars(self) -> int:
        return len(self.text)

    def __repr__(self) -> str:
        return (
            "RetainedTranscript("
            f"kind={self.kind.value!r}, "
            f"segment_count={self.segment_count!r}, "
            f"text_chars={self.text_chars!r})"
        )


@dataclass(repr=False)
class DictationSession:
    """State machine for a single bounded dictation session."""

    session_id: str = field(default_factory=lambda: uuid4().hex)
    state: DictationSessionState = DictationSessionState.IDLE
    segment_count: int = 0
    outcome_code: DictationOutcomeCode | None = None
    _retained_transcript: RetainedTranscript | None = None
    _insertion_started: bool = False

    @property
    def is_terminal(self) -> bool:
        return self.state in TERMINAL_STATES

    @property
    def has_retained_result(self) -> bool:
        return self._retained_transcript is not None

    @property
    def retained_result_kind(self) -> DictationResultKind | None:
        if self._retained_transcript is None:
            return None
        return self._retained_transcript.kind

    @property
    def retained_text_chars(self) -> int:
        if self._retained_transcript is None:
            return 0
        return self._retained_transcript.text_chars

    def require_idle(self) -> None:
        """Fail closed when another session is active."""

        if self.state == DictationSessionState.IDLE:
            return
        self._raise_failure(DictationOutcomeCode.CONCURRENT_SESSION, DictationSessionState.CAPTURING)

    def begin_capture(self) -> None:
        self.require_idle()
        self._transition_to(DictationSessionState.CAPTURING)

    def begin_recognition(self, segment_count: int) -> None:
        if segment_count < 0:
            raise ValueError("segment_count must be non-negative")
        self.segment_count = segment_count
        self._transition_to(DictationSessionState.RECOGNIZING, allowed_from={DictationSessionState.CAPTURING})

    def retain_partial_transcript(self, text: str, segment_count: int | None = None) -> None:
        self._retain_transcript(DictationResultKind.PARTIAL, text, segment_count)

    def retain_final_transcript(self, text: str, segment_count: int | None = None) -> None:
        self._retain_transcript(DictationResultKind.FINAL, text, segment_count)

    def begin_normalization(self) -> None:
        self._transition_to(DictationSessionState.NORMALIZING, allowed_from={DictationSessionState.RECOGNIZING})

    def begin_insertion(self) -> None:
        if self._insertion_started:
            self._raise_failure(DictationOutcomeCode.DOUBLE_INSERTION, DictationSessionState.INSERTING)
        self._transition_to(DictationSessionState.INSERTING, allowed_from={DictationSessionState.NORMALIZING})
        self._insertion_started = True

    def complete_delivery(self) -> None:
        self._transition_to(DictationSessionState.COMPLETED, allowed_from={DictationSessionState.INSERTING})
        self.outcome_code = DictationOutcomeCode.SUCCESS
        self._retained_transcript = None

    def cancel(self) -> None:
        if self.state == DictationSessionState.COMPLETED:
            self._raise_failure(DictationOutcomeCode.INVALID_TRANSITION, DictationSessionState.CANCELLED)
        self.state = DictationSessionState.CANCELLED
        self.outcome_code = DictationOutcomeCode.CANCELLED
        self._retained_transcript = None

    def fail(self, code: DictationOutcomeCode) -> DictationSessionFailure:
        if code in {
            DictationOutcomeCode.SUCCESS,
            DictationOutcomeCode.CANCELLED,
            DictationOutcomeCode.CONCURRENT_SESSION,
            DictationOutcomeCode.INVALID_TRANSITION,
        }:
            raise ValueError("fail code must describe a handled operation failure")
        previous_state = self.state
        self.state = DictationSessionState.FAILED
        self.outcome_code = code
        return DictationSessionFailure(
            code=code,
            from_state=previous_state,
            segment_count=self.segment_count,
            retained_result=self.has_retained_result,
        )

    def retained_transcript_for_delivery(self) -> RetainedTranscript | None:
        """Return retained text to application code; callers must not log it."""

        return self._retained_transcript

    def _retain_transcript(
        self,
        kind: DictationResultKind,
        text: str,
        segment_count: int | None,
    ) -> None:
        if self.state not in {
            DictationSessionState.RECOGNIZING,
            DictationSessionState.NORMALIZING,
            DictationSessionState.INSERTING,
            DictationSessionState.FAILED,
        }:
            self._raise_failure(DictationOutcomeCode.INVALID_TRANSITION, self.state)
        effective_segment_count = self.segment_count if segment_count is None else segment_count
        self._retained_transcript = RetainedTranscript(kind, text, effective_segment_count)

    def _transition_to(
        self,
        next_state: DictationSessionState,
        *,
        allowed_from: set[DictationSessionState] | None = None,
    ) -> None:
        allowed = allowed_from or {self.state}
        if self.state not in allowed:
            self._raise_failure(DictationOutcomeCode.INVALID_TRANSITION, next_state)
        self.state = next_state

    def _raise_failure(
        self,
        code: DictationOutcomeCode,
        attempted_state: DictationSessionState,
    ) -> None:
        failure = DictationSessionFailure(
            code=code,
            from_state=self.state,
            attempted_state=attempted_state,
            segment_count=self.segment_count,
            retained_result=self.has_retained_result,
        )
        raise InvalidDictationTransition(failure)

    def __repr__(self) -> str:
        return (
            "DictationSession("
            f"session_id={self.session_id!r}, "
            f"state={self.state.value!r}, "
            f"segment_count={self.segment_count!r}, "
            f"outcome_code={self.outcome_code.value if self.outcome_code else None!r}, "
            f"retained_result={self.has_retained_result!r}, "
            f"retained_result_kind={self.retained_result_kind.value if self.retained_result_kind else None!r})"
        )


def safe_session_log_context(session: DictationSession) -> dict[str, object]:
    """Build allowlisted session context for application logging."""

    return {
        "session_id": session.session_id,
        "state": session.state.value,
        "segment_count": session.segment_count,
        "outcome_code": session.outcome_code.value if session.outcome_code else None,
        "retained_result": session.has_retained_result,
        "retained_result_kind": session.retained_result_kind.value if session.retained_result_kind else None,
        "retained_text_chars": session.retained_text_chars,
    }


__all__ = [
    "DictationOutcomeCode",
    "DictationResultKind",
    "DictationSession",
    "DictationSessionError",
    "DictationSessionFailure",
    "DictationSessionState",
    "InvalidDictationTransition",
    "RetainedTranscript",
    "safe_session_log_context",
]
