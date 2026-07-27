"""Platform-neutral contracts for the disposable insertion spike."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
import logging
import os
from typing import Protocol, runtime_checkable


LOGGER_NAME = "nadikt.windows_insertion_spike"
_SAFE_LOG_LEVELS = {
    "CRITICAL": logging.CRITICAL,
    "ERROR": logging.ERROR,
    "WARNING": logging.WARNING,
    "WARN": logging.WARNING,
    "INFO": logging.INFO,
    "DEBUG": logging.DEBUG,
}


def get_logger() -> logging.Logger:
    """Return the spike logger configured from LOG_LEVEL without payload data."""
    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel(_SAFE_LOG_LEVELS.get(os.getenv("LOG_LEVEL", "INFO").upper(), logging.INFO))
    return logger


class InsertionMethod(StrEnum):
    AUTO = "auto"
    PASTE = "paste"
    DIRECT = "direct"


class OutcomeCode(StrEnum):
    DISPATCHED = "dispatched"
    DIRECT_DISPATCHED = "direct_dispatched"
    CANCELLED = "cancelled"
    BUSY = "busy"
    ALREADY_DELIVERED = "already_delivered"
    TARGET_CHANGED = "target_changed"
    TARGET_UNAVAILABLE = "target_unavailable"
    TARGET_PROTECTED = "target_protected"
    TARGET_ELEVATED = "target_elevated"
    CLIPBOARD_UNSAFE = "clipboard_unsafe"
    CLIPBOARD_FAILED = "clipboard_failed"
    DISPATCH_FAILED = "dispatch_failed"
    CLEANUP_FAILED = "cleanup_failed"
    RESTORE_FAILED = "restore_failed"
    BOUNDARY_FAILURE = "boundary_failure"


SAFE_ERROR_CODES = frozenset(code for code in OutcomeCode if code not in {
    OutcomeCode.DISPATCHED,
    OutcomeCode.DIRECT_DISPATCHED,
})


@dataclass(frozen=True, repr=False)
class InsertionRequest:
    """A request whose sensitive result text is intentionally absent from repr."""

    request_id: str
    text: str = field(compare=False)
    method: InsertionMethod = InsertionMethod.AUTO

    def __repr__(self) -> str:
        return f"InsertionRequest(request_id={self.request_id!r}, method={self.method.value!r})"


@dataclass(frozen=True, repr=False)
class TargetToken:
    """Opaque target identity; platform values must not cross this boundary."""

    key: str = field(compare=True)

    def __repr__(self) -> str:
        return "TargetToken(<opaque>)"


@dataclass(frozen=True)
class TargetAssessment:
    code: OutcomeCode | None = None

    @property
    def is_safe(self) -> bool:
        return self.code is None


@dataclass(frozen=True, repr=False)
class ClipboardSnapshot:
    """Opaque snapshot held in memory by the clipboard adapter."""

    state: object = field(compare=False)

    def __repr__(self) -> str:
        return "ClipboardSnapshot(<opaque>)"


@dataclass(frozen=True)
class ClipboardPreparation:
    is_safe: bool
    snapshot: ClipboardSnapshot | None = None
    code: OutcomeCode | None = None


@dataclass(frozen=True)
class RestoreResult:
    restored: bool
    external_change: bool = False


@dataclass(frozen=True)
class DispatchResult:
    dispatched: bool
    code: OutcomeCode | None = None


@dataclass(frozen=True)
class InsertionOutcome:
    request_id: str
    code: OutcomeCode
    retained_in_memory: bool = True
    original_snapshot_retained: bool = False
    duration_ms: int = 0


@runtime_checkable
class TargetAdapter(Protocol):
    def capture(self) -> TargetToken: ...

    def assess(self, captured_target: TargetToken) -> TargetAssessment: ...


@runtime_checkable
class ClipboardAdapter(Protocol):
    def prepare(self) -> ClipboardPreparation: ...

    def commit_mutation(self, text: str) -> None: ...

    def restore(self, snapshot: ClipboardSnapshot) -> RestoreResult: ...

    def discard(self, snapshot: ClipboardSnapshot) -> None: ...


@runtime_checkable
class InputInjector(Protocol):
    def prepare_dispatch(self) -> bool: ...

    def dispatch_paste(self, *, prepared: bool = False) -> DispatchResult: ...

    def dispatch_unicode(self, text: str, *, prepared: bool = False) -> DispatchResult: ...
