import threading
import unittest

from insertion_spike.contracts import (
    ClipboardPreparation,
    ClipboardSnapshot,
    DispatchResult,
    InsertionMethod,
    InsertionRequest,
    OutcomeCode,
    RestoreResult,
    TargetAssessment,
    TargetToken,
)
from insertion_spike.service import InsertionService


CANARY = "CANARY_service_payload_9321"


class FakeTarget:
    def __init__(self, code: OutcomeCode | None = None) -> None:
        self.code = code
        self.error: Exception | None = None

    def capture(self) -> TargetToken:
        return TargetToken("target")

    def assess(self, captured_target: TargetToken) -> TargetAssessment:
        if self.error:
            raise self.error
        return TargetAssessment(self.code)


class FakeClipboard:
    def __init__(self) -> None:
        self.preparation = ClipboardPreparation(True, ClipboardSnapshot("original"))
        self.restore_result = RestoreResult(True)
        self.prepare_error: Exception | None = None
        self.commit_error: Exception | None = None
        self.restore_error: Exception | None = None
        self.mutated = False
        self.restore_calls = 0

    def prepare(self) -> ClipboardPreparation:
        if self.prepare_error:
            raise self.prepare_error
        return self.preparation

    def commit_mutation(self, text: str) -> None:
        if self.commit_error:
            raise self.commit_error
        self.mutated = True

    def restore(self, snapshot: ClipboardSnapshot) -> RestoreResult:
        self.restore_calls += 1
        if self.restore_error:
            raise self.restore_error
        return self.restore_result


class FakeInjector:
    def __init__(self) -> None:
        self.paste_result = DispatchResult(True)
        self.direct_result = DispatchResult(True)
        self.paste_error: Exception | None = None
        self.direct_error: Exception | None = None
        self.direct_calls = 0

    def dispatch_paste(self) -> DispatchResult:
        if self.paste_error:
            raise self.paste_error
        return self.paste_result

    def dispatch_unicode(self, text: str) -> DispatchResult:
        self.direct_calls += 1
        if self.direct_error:
            raise self.direct_error
        return self.direct_result


class BlockingTarget(FakeTarget):
    def __init__(self, entered: threading.Event, release: threading.Event) -> None:
        super().__init__()
        self.entered = entered
        self.release = release

    def assess(self, captured_target: TargetToken) -> TargetAssessment:
        self.entered.set()
        self.release.wait(timeout=2)
        return TargetAssessment()


class InsertionServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.target = FakeTarget()
        self.clipboard = FakeClipboard()
        self.injector = FakeInjector()
        self.service = InsertionService(self.target, self.clipboard, self.injector)
        self.token = TargetToken("captured")

    def request(self, method: InsertionMethod = InsertionMethod.AUTO, request_id: str = "r1") -> InsertionRequest:
        return InsertionRequest(request_id, CANARY, method)

    def test_paste_dispatch_is_not_reported_as_confirmed_insertion(self) -> None:
        outcome = self.service.deliver(self.request(InsertionMethod.PASTE), self.token)

        self.assertEqual(OutcomeCode.DISPATCHED, outcome.code)
        self.assertTrue(outcome.retained_in_memory)
        self.assertEqual(CANARY, self.service.retained_result("r1"))

    def test_changed_protected_and_elevated_targets_fail_before_mutation(self) -> None:
        for code in (
            OutcomeCode.TARGET_CHANGED,
            OutcomeCode.TARGET_PROTECTED,
            OutcomeCode.TARGET_ELEVATED,
        ):
            with self.subTest(code=code):
                clipboard = FakeClipboard()
                service = InsertionService(FakeTarget(code), clipboard, FakeInjector())

                outcome = service.deliver(self.request(request_id=code.value), self.token)

                self.assertEqual(code, outcome.code)
                self.assertFalse(clipboard.mutated)

    def test_unsafe_clipboard_uses_direct_path_only_in_auto_mode(self) -> None:
        self.clipboard.preparation = ClipboardPreparation(False, code=OutcomeCode.CLIPBOARD_UNSAFE)

        auto = self.service.deliver(self.request(request_id="auto"), self.token)
        paste = self.service.deliver(
            self.request(InsertionMethod.PASTE, "paste"), self.token
        )

        self.assertEqual(OutcomeCode.DIRECT_DISPATCHED, auto.code)
        self.assertEqual(OutcomeCode.CLIPBOARD_UNSAFE, paste.code)
        self.assertEqual(1, self.injector.direct_calls)

    def test_external_clipboard_change_is_not_overwritten(self) -> None:
        self.clipboard.restore_result = RestoreResult(False, external_change=True)

        outcome = self.service.deliver(self.request(), self.token)

        self.assertEqual(OutcomeCode.DISPATCHED, outcome.code)
        self.assertEqual(1, self.clipboard.restore_calls)

    def test_dispatch_error_restores_original_and_retains_result(self) -> None:
        self.injector.paste_error = RuntimeError(CANARY)

        outcome = self.service.deliver(self.request(), self.token)

        self.assertEqual(OutcomeCode.DISPATCH_FAILED, outcome.code)
        self.assertEqual(1, self.clipboard.restore_calls)
        self.assertEqual(CANARY, self.service.retained_result("r1"))

    def test_restoration_error_retains_original_snapshot(self) -> None:
        self.clipboard.restore_error = RuntimeError(CANARY)

        outcome = self.service.deliver(self.request(), self.token)

        self.assertEqual(OutcomeCode.RESTORE_FAILED, outcome.code)
        self.assertTrue(outcome.original_snapshot_retained)
        self.assertIsNotNone(self.service.retained_snapshot("r1"))

    def test_partial_mutation_failure_attempts_immediate_restoration(self) -> None:
        self.clipboard.commit_error = RuntimeError(CANARY)

        outcome = self.service.deliver(self.request(), self.token)

        self.assertEqual(OutcomeCode.CLIPBOARD_FAILED, outcome.code)
        self.assertEqual(1, self.clipboard.restore_calls)

    def test_cancellation_happens_before_mutation(self) -> None:
        outcome = self.service.deliver(self.request(), self.token, cancelled=True)

        self.assertEqual(OutcomeCode.CANCELLED, outcome.code)
        self.assertFalse(self.clipboard.mutated)

    def test_repeated_request_is_rejected_without_second_dispatch(self) -> None:
        first = self.service.deliver(self.request(), self.token)
        second = self.service.deliver(
            InsertionRequest("r1", "DIFFERENT_RETRY_PAYLOAD"), self.token
        )

        self.assertEqual(OutcomeCode.DISPATCHED, first.code)
        self.assertEqual(OutcomeCode.ALREADY_DELIVERED, second.code)
        self.assertEqual(1, self.clipboard.restore_calls)
        self.assertEqual(CANARY, self.service.retained_result("r1"))

    def test_concurrent_request_is_rejected_as_busy(self) -> None:
        entered = threading.Event()
        release = threading.Event()
        service = InsertionService(BlockingTarget(entered, release), self.clipboard, self.injector)
        first_outcome: list[object] = []
        thread = threading.Thread(
            target=lambda: first_outcome.append(service.deliver(self.request(request_id="first"), self.token))
        )
        thread.start()
        self.assertTrue(entered.wait(timeout=1))

        second = service.deliver(self.request(request_id="second"), self.token)
        release.set()
        thread.join(timeout=2)

        self.assertEqual(OutcomeCode.BUSY, second.code)
        self.assertEqual(1, len(first_outcome))

    def test_boundary_exception_is_reduced_to_safe_code_without_payload(self) -> None:
        self.target.error = RuntimeError(CANARY)

        with self.assertLogs("nadikt.windows_insertion_spike", level="ERROR") as captured:
            outcome = self.service.deliver(self.request(), self.token)

        self.assertEqual(OutcomeCode.BOUNDARY_FAILURE, outcome.code)
        self.assertNotIn(CANARY, "\n".join(captured.output))


if __name__ == "__main__":
    unittest.main()
