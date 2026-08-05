"""Windows clipboard transaction adapter boundary."""

from __future__ import annotations

import logging
import os
import uuid
from dataclasses import dataclass
from typing import Protocol

from nadikt.domain.ports.insertion import (
    ClipboardOutcomeCode,
    ClipboardSnapshot,
    ClipboardTransactionPort,
    ClipboardTransactionResult,
    TargetToken,
)

LOGGER = logging.getLogger(__name__)
_LOG_LEVEL = os.environ.get("NADIKT_LOG_LEVEL", os.environ.get("LOG_LEVEL", "INFO")).upper()
logging.basicConfig(level=getattr(logging, _LOG_LEVEL, logging.INFO))


@dataclass(frozen=True, repr=False)
class ClipboardSafeSnapshot:
    """Facade snapshot facts without payload or file names."""

    format_count: int
    has_private_or_delayed_formats: bool
    sequence_id: str

    def __repr__(self) -> str:
        return (
            "ClipboardSafeSnapshot("
            f"format_count={self.format_count!r}, "
            f"has_private_or_delayed_formats={self.has_private_or_delayed_formats!r}, "
            f"sequence_id=<opaque>)"
        )


class ClipboardFacade(Protocol):
    """Injected Windows clipboard facade with adapter-owned payload storage."""

    def snapshot_if_safe(self) -> ClipboardSafeSnapshot | None:
        """Return safe snapshot metadata only when all formats are cloneable."""

    def place_unicode_text(self, text: str) -> bool:
        """Place text for dispatch; implementation must not log text."""

    def commit(self, snapshot_id: str) -> bool:
        """Commit adapter-owned transaction state."""

    def restore(self, snapshot_id: str) -> ClipboardOutcomeCode:
        """Restore original if clipboard sequence/ownership is still safe."""

    def discard(self, snapshot_id: str) -> bool:
        """Discard retained original snapshot by explicit decision."""


class WindowsClipboardTransactionAdapter(ClipboardTransactionPort):
    """Fail-closed clipboard adapter with injected Windows facade."""

    def __init__(self, facade: ClipboardFacade | None = None) -> None:
        self._facade = facade
        self._snapshots: dict[str, ClipboardSafeSnapshot] = {}

    def prepare_text(self, token: TargetToken, text: str) -> ClipboardTransactionResult:
        LOGGER.debug("clipboard.prepare.start", extra={"token": "<opaque>", "text_chars": len(text)})
        if self._facade is None:
            return ClipboardTransactionResult(ClipboardOutcomeCode.CLIPBOARD_UNSAFE)
        snapshot = self._facade.snapshot_if_safe()
        if snapshot is None or snapshot.has_private_or_delayed_formats:
            return ClipboardTransactionResult(ClipboardOutcomeCode.CLIPBOARD_UNSAFE)
        if not self._facade.place_unicode_text(text):
            return ClipboardTransactionResult(ClipboardOutcomeCode.CLIPBOARD_UNSAFE)
        snapshot_id = uuid.uuid4().hex
        self._snapshots[snapshot_id] = snapshot
        result_snapshot = ClipboardSnapshot(snapshot_id, snapshot.format_count, snapshot.has_private_or_delayed_formats)
        LOGGER.debug(
            "clipboard.prepare.complete",
            extra={"outcome": ClipboardOutcomeCode.PREPARED.value, "format_count": snapshot.format_count},
        )
        return ClipboardTransactionResult(ClipboardOutcomeCode.PREPARED, result_snapshot, retained_original=True)

    def commit(self, snapshot: ClipboardSnapshot) -> ClipboardTransactionResult:
        if self._facade is None or snapshot.snapshot_id not in self._snapshots:
            return ClipboardTransactionResult(ClipboardOutcomeCode.CLIPBOARD_UNSAFE, snapshot)
        committed = self._facade.commit(snapshot.snapshot_id)
        outcome = ClipboardOutcomeCode.COMMITTED if committed else ClipboardOutcomeCode.CLIPBOARD_UNSAFE
        LOGGER.debug("clipboard.commit.complete", extra={"outcome": outcome.value})
        return ClipboardTransactionResult(outcome, snapshot, retained_original=True)

    def restore_original(self, snapshot: ClipboardSnapshot) -> ClipboardTransactionResult:
        if self._facade is None or snapshot.snapshot_id not in self._snapshots:
            return ClipboardTransactionResult(ClipboardOutcomeCode.RESTORE_FAILED, snapshot, retained_original=True)
        outcome = self._facade.restore(snapshot.snapshot_id)
        if outcome == ClipboardOutcomeCode.RESTORED:
            self._snapshots.pop(snapshot.snapshot_id, None)
        LOGGER.debug("clipboard.restore.complete", extra={"outcome": outcome.value})
        return ClipboardTransactionResult(
            outcome,
            snapshot,
            sequence_changed=outcome == ClipboardOutcomeCode.SEQUENCE_CHANGED,
            retained_original=outcome != ClipboardOutcomeCode.RESTORED,
        )

    def discard_original(self, snapshot: ClipboardSnapshot) -> ClipboardTransactionResult:
        if self._facade is None or snapshot.snapshot_id not in self._snapshots:
            return ClipboardTransactionResult(ClipboardOutcomeCode.DISCARDED, snapshot)
        discarded = self._facade.discard(snapshot.snapshot_id)
        if discarded:
            self._snapshots.pop(snapshot.snapshot_id, None)
        outcome = ClipboardOutcomeCode.DISCARDED if discarded else ClipboardOutcomeCode.PENDING_CLIPBOARD_RESTORE
        LOGGER.debug("clipboard.discard.complete", extra={"outcome": outcome.value})
        return ClipboardTransactionResult(outcome, snapshot, retained_original=not discarded)


__all__ = ["ClipboardFacade", "ClipboardSafeSnapshot", "WindowsClipboardTransactionAdapter"]
