"""Safe one-shot text insertion orchestration."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass

from nadikt.application.services.dictation_pipeline import TextInsertionResult
from nadikt.domain.ports.insertion import (
    ClipboardOutcomeCode,
    ClipboardSnapshot,
    ClipboardTransactionPort,
    InputDispatchOutcomeCode,
    InputDispatchPort,
    InputDispatchRequest,
    InsertionFailureCode,
    TargetCapturePort,
    TargetSafetyOutcome,
    TargetToken,
    safe_target_log_context,
)

LOGGER = logging.getLogger(__name__)
_LOG_LEVEL = os.environ.get("NADIKT_LOG_LEVEL", os.environ.get("LOG_LEVEL", "INFO")).upper()
logging.basicConfig(level=getattr(logging, _LOG_LEVEL, logging.INFO))


@dataclass(frozen=True, repr=False)
class InsertionServiceOptions:
    """Policy flags for one-shot insertion."""

    permit_direct_unicode_fallback: bool = False
    restore_original_after_dispatch: bool = True

    def __repr__(self) -> str:
        return (
            "InsertionServiceOptions("
            f"permit_direct_unicode_fallback={self.permit_direct_unicode_fallback!r}, "
            f"restore_original_after_dispatch={self.restore_original_after_dispatch!r})"
        )


class SafeTextInsertionService:
    """Coordinates target safety, clipboard transaction and input dispatch."""

    def __init__(
        self,
        target_capture: TargetCapturePort,
        clipboard: ClipboardTransactionPort,
        input_dispatch: InputDispatchPort,
        options: InsertionServiceOptions | None = None,
    ) -> None:
        self._target_capture = target_capture
        self._clipboard = clipboard
        self._input_dispatch = input_dispatch
        self._options = options or InsertionServiceOptions()
        self._target_token: TargetToken | None = None
        self._pending_snapshot: ClipboardSnapshot | None = None

    @property
    def has_pending_clipboard_restore(self) -> bool:
        return self._pending_snapshot is not None

    def capture_target(self) -> TextInsertionResult:
        LOGGER.debug("insertion.capture_target.start", extra={"operation": "capture_target"})
        result = self._target_capture.capture_current_target()
        LOGGER.debug("insertion.capture_target.complete", extra=safe_target_log_context(result))
        if result.outcome != TargetSafetyOutcome.SAFE or not result.safe_to_insert:
            self._target_capture.invalidate_target(result.token)
            return TextInsertionResult(False, _target_failure_code(result.outcome).value, retained_result=True)
        self._target_token = result.token
        return TextInsertionResult(True, result.outcome.value)

    def insert_text(self, text: str) -> TextInsertionResult:
        LOGGER.debug(
            "insertion.insert_text.start",
            extra={"text_chars": len(text), "pending_clipboard_restore": self.has_pending_clipboard_restore},
        )
        if self._target_token is None:
            captured = self.capture_target()
            if not captured.success:
                return captured
        token = self._target_token
        snapshot: ClipboardSnapshot | None = None
        try:
            revalidation = self._target_capture.revalidate_target(token)
            LOGGER.debug("insertion.revalidate.complete", extra=safe_target_log_context(revalidation))
            if revalidation.outcome != TargetSafetyOutcome.SAFE or not revalidation.safe_to_insert:
                return self._terminal_failure(token, _target_failure_code(revalidation.outcome))

            prepared = self._clipboard.prepare_text(token, text)
            LOGGER.debug(
                "insertion.clipboard.prepare.complete",
                extra={
                    "outcome": prepared.outcome.value,
                    "format_count": prepared.snapshot.format_count if prepared.snapshot else 0,
                    "sequence_changed": prepared.sequence_changed,
                },
            )
            if prepared.outcome != ClipboardOutcomeCode.PREPARED or prepared.snapshot is None:
                return self._terminal_failure(token, InsertionFailureCode.CLIPBOARD_UNSAFE)
            snapshot = prepared.snapshot

            dispatch = self._input_dispatch.dispatch_text(
                InputDispatchRequest(
                    token=token,
                    text=text,
                    permit_direct_unicode_fallback=self._options.permit_direct_unicode_fallback,
                )
            )
            LOGGER.debug(
                "insertion.dispatch.complete",
                extra={"outcome": dispatch.outcome.value, "method": dispatch.method, "confirmed": dispatch.confirmed},
            )
            if dispatch.outcome != InputDispatchOutcomeCode.DISPATCH_CONFIRMED or not dispatch.confirmed:
                self._pending_snapshot = snapshot
                self._target_capture.invalidate_target(token)
                self._target_token = None
                return TextInsertionResult(
                    False,
                    InsertionFailureCode.DISPATCH_UNCONFIRMED.value,
                    retained_result=True,
                    pending_clipboard_restore=True,
                )

            committed = self._clipboard.commit(snapshot)
            LOGGER.debug("insertion.clipboard.commit.complete", extra={"outcome": committed.outcome.value})
            if self._options.restore_original_after_dispatch:
                restored = self._clipboard.restore_original(snapshot)
                LOGGER.debug("insertion.clipboard.restore.complete", extra={"outcome": restored.outcome.value})
                if restored.outcome != ClipboardOutcomeCode.RESTORED:
                    self._pending_snapshot = snapshot
                    return self._pending_restore_failure(token)

            self._target_capture.invalidate_target(token)
            self._target_token = None
            return TextInsertionResult(True, ClipboardOutcomeCode.COMMITTED.value)
        except Exception:
            LOGGER.debug("insertion.insert_text.failed", extra={"failure_code": InsertionFailureCode.DISPATCH_UNCONFIRMED.value})
            if snapshot is not None:
                self._pending_snapshot = snapshot
            self._target_capture.invalidate_target(token)
            self._target_token = None
            return TextInsertionResult(
                False,
                InsertionFailureCode.PENDING_CLIPBOARD_RESTORE.value if snapshot is not None else InsertionFailureCode.DISPATCH_UNCONFIRMED.value,
                retained_result=True,
                pending_clipboard_restore=snapshot is not None,
            )

    def restore_original(self) -> TextInsertionResult:
        snapshot = self._pending_snapshot
        if snapshot is None:
            return TextInsertionResult(True, ClipboardOutcomeCode.RESTORED.value)
        result = self._clipboard.restore_original(snapshot)
        LOGGER.debug("insertion.restore_original.complete", extra={"outcome": result.outcome.value})
        if result.outcome == ClipboardOutcomeCode.RESTORED:
            self._pending_snapshot = None
            return TextInsertionResult(True, result.outcome.value)
        return TextInsertionResult(False, InsertionFailureCode.PENDING_CLIPBOARD_RESTORE.value, retained_result=True, pending_clipboard_restore=True)

    def discard_original(self) -> TextInsertionResult:
        snapshot = self._pending_snapshot
        if snapshot is None:
            return TextInsertionResult(True, ClipboardOutcomeCode.DISCARDED.value)
        result = self._clipboard.discard_original(snapshot)
        LOGGER.debug("insertion.discard_original.complete", extra={"outcome": result.outcome.value})
        if result.outcome == ClipboardOutcomeCode.DISCARDED:
            self._pending_snapshot = None
            return TextInsertionResult(True, result.outcome.value)
        return TextInsertionResult(False, InsertionFailureCode.PENDING_CLIPBOARD_RESTORE.value, retained_result=True, pending_clipboard_restore=True)

    def cancel(self) -> None:
        token = self._target_token
        if token is not None:
            self._target_capture.invalidate_target(token)
        self._target_token = None
        LOGGER.debug("insertion.cancel.complete", extra={"pending_clipboard_restore": self.has_pending_clipboard_restore})

    def _terminal_failure(self, token: TargetToken, code: InsertionFailureCode) -> TextInsertionResult:
        self._target_capture.invalidate_target(token)
        self._target_token = None
        return TextInsertionResult(False, code.value, retained_result=True)

    def _pending_restore_failure(self, token: TargetToken) -> TextInsertionResult:
        self._target_capture.invalidate_target(token)
        self._target_token = None
        return TextInsertionResult(
            False,
            InsertionFailureCode.PENDING_CLIPBOARD_RESTORE.value,
            retained_result=True,
            pending_clipboard_restore=True,
        )


def _target_failure_code(outcome: TargetSafetyOutcome) -> InsertionFailureCode:
    mapping = {
        TargetSafetyOutcome.TARGET_CHANGED: InsertionFailureCode.TARGET_CHANGED,
        TargetSafetyOutcome.TARGET_UNAVAILABLE: InsertionFailureCode.TARGET_UNAVAILABLE,
        TargetSafetyOutcome.TARGET_PROTECTED: InsertionFailureCode.TARGET_PROTECTED,
        TargetSafetyOutcome.TARGET_ELEVATED: InsertionFailureCode.TARGET_ELEVATED,
        TargetSafetyOutcome.STALE_TOKEN: InsertionFailureCode.STALE_TOKEN,
    }
    return mapping.get(outcome, InsertionFailureCode.TARGET_UNAVAILABLE)


__all__ = ["InsertionServiceOptions", "SafeTextInsertionService"]
