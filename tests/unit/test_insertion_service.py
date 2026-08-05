from __future__ import annotations

import unittest
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parents[2] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from nadikt.application.services import InsertionServiceOptions, SafeTextInsertionService
from nadikt.domain.ports.insertion import (
    ClipboardOutcomeCode,
    ClipboardSnapshot,
    ClipboardTransactionResult,
    InputDispatchOutcomeCode,
    InputDispatchRequest,
    InputDispatchResult,
    TargetCaptureResult,
    TargetRevalidationResult,
    TargetSafetyOutcome,
    TargetToken,
)


class InsertionServiceTest(unittest.TestCase):
    def test_stale_or_changed_target_fails_closed_and_invalidates_token(self) -> None:
        target = FakeTarget(TargetSafetyOutcome.TARGET_CHANGED)
        service = SafeTextInsertionService(target, FakeClipboard(), FakeInput())
        capture = service.capture_target()

        self.assertTrue(capture.success)
        result = service.insert_text("SECRET_TEXT")

        self.assertFalse(result.success)
        self.assertEqual("target_changed", result.outcome_code)
        self.assertEqual(1, target.invalidate_count)

    def test_dispatch_unconfirmed_keeps_pending_restore_without_retry(self) -> None:
        input_adapter = FakeInput(confirmed=False)
        service = SafeTextInsertionService(FakeTarget(TargetSafetyOutcome.SAFE), FakeClipboard(), input_adapter)
        service.capture_target()

        result = service.insert_text("SECRET_TEXT")

        self.assertFalse(result.success)
        self.assertTrue(result.pending_clipboard_restore)
        self.assertEqual(1, input_adapter.dispatch_count)
        restored = service.restore_original()
        self.assertTrue(restored.success)

    def test_direct_unicode_requires_explicit_permit(self) -> None:
        input_adapter = FakeInput(confirmed=False, direct_success=True)
        service = SafeTextInsertionService(
            FakeTarget(TargetSafetyOutcome.SAFE),
            FakeClipboard(),
            input_adapter,
            InsertionServiceOptions(permit_direct_unicode_fallback=True),
        )
        service.capture_target()

        result = service.insert_text("SECRET_TEXT")

        self.assertTrue(result.success)
        self.assertEqual(1, input_adapter.direct_count)


class FakeTarget:
    def __init__(self, revalidation_outcome: TargetSafetyOutcome) -> None:
        self._token = TargetToken("token")
        self._revalidation_outcome = revalidation_outcome
        self.invalidate_count = 0

    def capture_current_target(self) -> TargetCaptureResult:
        return TargetCaptureResult(self._token, TargetSafetyOutcome.SAFE, "fake-uia", True, True)

    def revalidate_target(self, token: TargetToken) -> TargetRevalidationResult:
        safe = self._revalidation_outcome == TargetSafetyOutcome.SAFE
        return TargetRevalidationResult(token, self._revalidation_outcome, safe, True, safe)

    def invalidate_target(self, token: TargetToken) -> None:
        self.invalidate_count += 1


class FakeClipboard:
    def prepare_text(self, token: TargetToken, text: str) -> ClipboardTransactionResult:
        return ClipboardTransactionResult(ClipboardOutcomeCode.PREPARED, ClipboardSnapshot("snapshot", 1), retained_original=True)

    def commit(self, snapshot: ClipboardSnapshot) -> ClipboardTransactionResult:
        return ClipboardTransactionResult(ClipboardOutcomeCode.COMMITTED, snapshot, retained_original=True)

    def restore_original(self, snapshot: ClipboardSnapshot) -> ClipboardTransactionResult:
        return ClipboardTransactionResult(ClipboardOutcomeCode.RESTORED, snapshot)

    def discard_original(self, snapshot: ClipboardSnapshot) -> ClipboardTransactionResult:
        return ClipboardTransactionResult(ClipboardOutcomeCode.DISCARDED, snapshot)


class FakeInput:
    def __init__(self, *, confirmed: bool = True, direct_success: bool = False) -> None:
        self._confirmed = confirmed
        self._direct_success = direct_success
        self.dispatch_count = 0
        self.direct_count = 0

    def dispatch_text(self, request: InputDispatchRequest) -> InputDispatchResult:
        self.dispatch_count += 1
        if self._confirmed:
            return InputDispatchResult(InputDispatchOutcomeCode.DISPATCH_CONFIRMED, "clipboard_paste", True)
        if request.permit_direct_unicode_fallback and self._direct_success:
            self.direct_count += 1
            return InputDispatchResult(InputDispatchOutcomeCode.DISPATCH_CONFIRMED, "direct_unicode", True)
        return InputDispatchResult(InputDispatchOutcomeCode.DISPATCH_UNCONFIRMED, "clipboard_paste", False)


if __name__ == "__main__":
    unittest.main()
