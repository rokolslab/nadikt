"""Dictation domain models and state transitions."""

from nadikt.domain.dictation.session import (
    DictationOutcomeCode,
    DictationResultKind,
    DictationSession,
    DictationSessionError,
    DictationSessionFailure,
    DictationSessionState,
    InvalidDictationTransition,
    RetainedTranscript,
    safe_session_log_context,
)

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
