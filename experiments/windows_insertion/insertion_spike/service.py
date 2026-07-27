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
    RestoreResult,
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

    def restore_original(self, request_id: str) -> RestoreResult:
        with self._delivery_lock:
            with self._state_lock:
                snapshot = self._retained_snapshots.get(request_id)
            if snapshot is None:
                return RestoreResult(False)
            self._logger.debug("insertion phase=explicit_clipboard_restore")
            try:
                restore = self._clipboard.restore(snapshot)
            except BaseException as error:
                self._log_boundary_error("clipboard", "explicit_restore", error)
                return RestoreResult(False)
            if restore.restored or restore.external_change:
                with self._state_lock:
                    self._retained_snapshots.pop(request_id, None)
            return restore

    def discard_original(self, request_id: str) -> bool:
        with self._delivery_lock:
            with self._state_lock:
                snapshot = self._retained_snapshots.get(request_id)
            if snapshot is None:
                return False
            try:
                self._clipboard.discard(snapshot)
            except BaseException as error:
                self._log_boundary_error("clipboard", "discard", error)
                return False
            with self._state_lock:
                discarded = self._retained_snapshots.pop(request_id, None) is not None
        self._logger.warning(
            "insertion original_snapshot_discarded=%s",
            discarded,
        )
        return discarded

    def deliver(
        self,
        request: InsertionRequest,
        captured_target: TargetToken,
        *,
        cancelled: bool = False,
    ) -> InsertionOutcome:
        started = monotonic()
        self._logger.debug("insertion phase=retain_result")
        if not self._delivery_lock.acquire(blocking=False):
            with self._state_lock:
                if request.request_id not in self._attempted_request_ids:
                    self._retained_results[request.request_id] = request.text
                    self._attempted_request_ids.add(request.request_id)
            self._logger.warning("insertion rejected code=%s", OutcomeCode.BUSY.value)
            return self._finish(request.request_id, OutcomeCode.BUSY, started)

        try:
            with self._state_lock:
                if request.request_id in self._attempted_request_ids:
                    return self._finish(
                        request.request_id,
                        OutcomeCode.ALREADY_DELIVERED,
                        started,
                    )
                self._retained_results[request.request_id] = request.text
                self._attempted_request_ids.add(request.request_id)
                if self._retained_snapshots:
                    self._logger.warning("insertion rejected pending_restoration=true")
                    return self._finish(request.request_id, OutcomeCode.BUSY, started)
            if cancelled:
                return self._finish(request.request_id, OutcomeCode.CANCELLED, started)

            assessment_code = self._assess_target(captured_target)
            if assessment_code is not None:
                self._logger.warning("insertion rejected code=%s", assessment_code.value)
                return self._finish(request.request_id, assessment_code, started)

            if request.method is InsertionMethod.DIRECT:
                return self._dispatch_direct(request, captured_target, started)
            return self._dispatch_with_clipboard(request, captured_target, started)
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
        captured_target: TargetToken,
        started: float,
    ) -> InsertionOutcome:
        if not self._prepare_input_dispatch():
            return self._finish(request.request_id, OutcomeCode.DISPATCH_FAILED, started)
        self._logger.debug("[FIX:final-target] phase=revalidate_before_direct")
        assessment_code = self._assess_target(captured_target)
        if assessment_code is not None:
            return self._finish(request.request_id, assessment_code, started)
        self._logger.debug("insertion phase=dispatch method=direct")
        result = self._safe_dispatch(
            lambda: self._injector.dispatch_unicode(request.text, prepared=True)
        )
        code = OutcomeCode.DIRECT_DISPATCHED if result.dispatched else result.code
        return self._finish(request.request_id, code or OutcomeCode.DISPATCH_FAILED, started)

    def _dispatch_with_clipboard(
        self,
        request: InsertionRequest,
        captured_target: TargetToken,
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
                return self._dispatch_direct(request, captured_target, started)
            return self._finish(request.request_id, OutcomeCode.CLIPBOARD_UNSAFE, started)

        snapshot = preparation.snapshot
        with self._state_lock:
            self._retained_snapshots[request.request_id] = snapshot

        try:
            self._logger.debug("insertion phase=clipboard_mutation")
            self._clipboard.commit_mutation(request.text)
        except BaseException as error:
            self._log_boundary_error("clipboard", "commit_mutation", error)
            return self._restore_after_dispatch(
                request.request_id,
                snapshot,
                OutcomeCode.CLIPBOARD_FAILED,
                started,
            )

        try:
            if not self._prepare_input_dispatch():
                return self._restore_after_dispatch(
                    request.request_id,
                    snapshot,
                    OutcomeCode.DISPATCH_FAILED,
                    started,
                )
            self._logger.debug("[FIX:final-target] phase=revalidate_before_paste")
            assessment_code = self._assess_target(captured_target)
            if assessment_code is not None:
                return self._restore_after_dispatch(
                    request.request_id,
                    snapshot,
                    assessment_code,
                    started,
                )
        except BaseException as error:
            self._logger.error(
                "[FIX:pre-dispatch-interrupt] exception_type=%s",
                type(error).__name__,
            )
            return self._restore_after_dispatch(
                request.request_id,
                snapshot,
                OutcomeCode.CANCELLED,
                started,
            )

        self._logger.debug("insertion phase=dispatch method=paste")
        try:
            dispatch = self._safe_dispatch(
                lambda: self._injector.dispatch_paste(prepared=True)
            )
        except BaseException as error:
            self._logger.error(
                "[FIX:dispatch-interrupt] exception_type=%s snapshot_retained=true",
                type(error).__name__,
            )
            return self._finish(
                request.request_id,
                OutcomeCode.DISPATCH_FAILED,
                started,
                original_snapshot_retained=True,
            )
        dispatch_code = OutcomeCode.DISPATCHED if dispatch.dispatched else (
            dispatch.code or OutcomeCode.DISPATCH_FAILED
        )
        # Queueing Ctrl+V does not prove consumption. Keep synthetic clipboard
        # content until the operator explicitly confirms it is safe to restore.
        return self._finish(
            request.request_id,
            dispatch_code,
            started,
            original_snapshot_retained=True,
        )

    def _prepare_input_dispatch(self) -> bool:
        self._logger.debug("[FIX:modifier-preflight] phase=before_final_target")
        try:
            return self._injector.prepare_dispatch()
        except Exception as error:
            self._log_boundary_error("injector", "prepare_dispatch", error)
            return False

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
        except BaseException as error:
            self._log_boundary_error("clipboard", "restore", error)
            return self._finish(
                request_id,
                OutcomeCode.RESTORE_FAILED,
                started,
                original_snapshot_retained=True,
            )

        if restore.external_change:
            self._logger.warning("insertion clipboard_external_change=true restoration_skipped=true")
            with self._state_lock:
                self._retained_snapshots.pop(request_id, None)
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

    def _log_boundary_error(self, boundary: str, operation: str, error: BaseException) -> None:
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
