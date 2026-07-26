"""Fail-closed orchestration for a single insertion delivery attempt."""

from __future__ import annotations

import logging
from threading import Lock
from time import monotonic

from .contracts import (
    ClipboardAdapter,
    ClipboardSnapshot,
    DispatchResult,
    InputInjector,
    InsertionMethod,
    InsertionOutcome,
    InsertionRequest,
    OutcomeCode,
    TargetAdapter,
    TargetToken,
    get_logger,
)


class InsertionService:
    """Coordinate target checks and delivery without retrying a request."""

    def __init__(
        self,
        target: TargetAdapter,
        clipboard: ClipboardAdapter,
        injector: InputInjector,
        logger: logging.Logger | None = None,
    ) -> None:
        self._target = target
        self._clipboard = clipboard
        self._injector = injector
        self._logger = logger or get_logger()
        self._delivery_lock = Lock()
        self._state_lock = Lock()
        self._attempted_request_ids: set[str] = set()
        self._retained_results: dict[str, str] = {}
        self._retained_snapshots: dict[str, ClipboardSnapshot] = {}

    def retained_result(self, request_id: str) -> str | None:
        """Return an in-memory result; callers must not log the value."""
        with self._state_lock:
            return self._retained_results.get(request_id)

    def retained_snapshot(self, request_id: str) -> ClipboardSnapshot | None:
        with self._state_lock:
            return self._retained_snapshots.get(request_id)

    def deliver(
        self,
        request: InsertionRequest,
        captured_target: TargetToken,
        *,
        cancelled: bool = False,
    ) -> InsertionOutcome:
        started = monotonic()
        self._logger.debug("insertion phase=retain_result")
        with self._state_lock:
            self._retained_results[request.request_id] = request.text
            if request.request_id in self._attempted_request_ids:
                return self._finish(request.request_id, OutcomeCode.ALREADY_DELIVERED, started)
            self._attempted_request_ids.add(request.request_id)

        if not self._delivery_lock.acquire(blocking=False):
            self._logger.warning("insertion rejected code=%s", OutcomeCode.BUSY.value)
            return self._finish(request.request_id, OutcomeCode.BUSY, started)

        try:
            if cancelled:
                return self._finish(request.request_id, OutcomeCode.CANCELLED, started)

            assessment_code = self._assess_target(captured_target)
            if assessment_code is not None:
                self._logger.warning("insertion rejected code=%s", assessment_code.value)
                return self._finish(request.request_id, assessment_code, started)

            if request.method is InsertionMethod.DIRECT:
                return self._dispatch_direct(request, started)
            return self._dispatch_with_clipboard(request, started)
        finally:
            self._delivery_lock.release()

    def _assess_target(self, captured_target: TargetToken) -> OutcomeCode | None:
        self._logger.debug("insertion phase=target_revalidation")
        try:
            assessment = self._target.assess(captured_target)
        except Exception as error:
            self._logger.error(
                "insertion boundary=target operation=assess exception_type=%s",
                type(error).__name__,
            )
            return OutcomeCode.BOUNDARY_FAILURE
        return assessment.code

    def _dispatch_direct(
        self,
        request: InsertionRequest,
        started: float,
    ) -> InsertionOutcome:
        self._logger.debug("insertion phase=dispatch method=direct")
        result = self._safe_dispatch(lambda: self._injector.dispatch_unicode(request.text))
        code = OutcomeCode.DIRECT_DISPATCHED if result.dispatched else result.code
        return self._finish(request.request_id, code or OutcomeCode.DISPATCH_FAILED, started)

    def _dispatch_with_clipboard(
        self,
        request: InsertionRequest,
        started: float,
    ) -> InsertionOutcome:
        self._logger.debug("insertion phase=clipboard_prepare")
        try:
            preparation = self._clipboard.prepare()
        except Exception as error:
            self._log_boundary_error("clipboard", "prepare", error)
            return self._finish(request.request_id, OutcomeCode.CLIPBOARD_FAILED, started)

        if not preparation.is_safe or preparation.snapshot is None:
            self._logger.warning("insertion clipboard_safe=false")
            if request.method is InsertionMethod.AUTO:
                return self._dispatch_direct(request, started)
            return self._finish(request.request_id, OutcomeCode.CLIPBOARD_UNSAFE, started)

        snapshot = preparation.snapshot
        with self._state_lock:
            self._retained_snapshots[request.request_id] = snapshot

        try:
            self._logger.debug("insertion phase=clipboard_mutation")
            self._clipboard.commit_mutation(request.text)
        except Exception as error:
            self._log_boundary_error("clipboard", "commit_mutation", error)
            return self._finish(
                request.request_id,
                OutcomeCode.CLIPBOARD_FAILED,
                started,
                original_snapshot_retained=True,
            )

        self._logger.debug("insertion phase=dispatch method=paste")
        dispatch = self._safe_dispatch(self._injector.dispatch_paste)
        dispatch_code = OutcomeCode.DISPATCHED if dispatch.dispatched else (
            dispatch.code or OutcomeCode.DISPATCH_FAILED
        )
        return self._restore_after_dispatch(request.request_id, snapshot, dispatch_code, started)

    def _restore_after_dispatch(
        self,
        request_id: str,
        snapshot: ClipboardSnapshot,
        dispatch_code: OutcomeCode,
        started: float,
    ) -> InsertionOutcome:
        self._logger.debug("insertion phase=clipboard_restore")
        try:
            restore = self._clipboard.restore(snapshot)
        except Exception as error:
            self._log_boundary_error("clipboard", "restore", error)
            return self._finish(
                request_id,
                OutcomeCode.RESTORE_FAILED,
                started,
                original_snapshot_retained=True,
            )

        if restore.external_change:
            self._logger.warning("insertion clipboard_external_change=true restoration_skipped=true")
            return self._finish(request_id, dispatch_code, started)
        if not restore.restored:
            return self._finish(
                request_id,
                OutcomeCode.RESTORE_FAILED,
                started,
                original_snapshot_retained=True,
            )

        with self._state_lock:
            self._retained_snapshots.pop(request_id, None)
        return self._finish(request_id, dispatch_code, started)

    def _safe_dispatch(self, operation: object) -> DispatchResult:
        try:
            return operation()  # type: ignore[operator]
        except Exception as error:
            self._log_boundary_error("injector", "dispatch", error)
            return DispatchResult(False, OutcomeCode.DISPATCH_FAILED)

    def _log_boundary_error(self, boundary: str, operation: str, error: Exception) -> None:
        self._logger.error(
            "insertion boundary=%s operation=%s exception_type=%s",
            boundary,
            operation,
            type(error).__name__,
        )

    def _finish(
        self,
        request_id: str,
        code: OutcomeCode,
        started: float,
        *,
        original_snapshot_retained: bool = False,
    ) -> InsertionOutcome:
        duration_ms = max(0, int((monotonic() - started) * 1000))
        level = logging.INFO if code in {
            OutcomeCode.DISPATCHED,
            OutcomeCode.DIRECT_DISPATCHED,
        } else logging.WARNING
        self._logger.log(level, "insertion outcome=%s duration_ms=%d", code.value, duration_ms)
        return InsertionOutcome(
            request_id=request_id,
            code=code,
            retained_in_memory=True,
            original_snapshot_retained=original_snapshot_retained,
            duration_ms=duration_ms,
        )
