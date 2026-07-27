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


class SequenceTarget(FakeTarget):
    def __init__(self, codes: list[OutcomeCode | None]) -> None:
        super().__init__()
        self.codes = list(codes)
        self.assess_calls = 0

    def assess(self, captured_target: TargetToken) -> TargetAssessment:
        code = self.codes[min(self.assess_calls, len(self.codes) - 1)]
        self.assess_calls += 1
        return TargetAssessment(code)


class RecordingTarget(FakeTarget):
    def __init__(self, events: list[str]) -> None:
        super().__init__()
        self.events = events

    def assess(self, captured_target: TargetToken) -> TargetAssessment:
        self.events.append("assess")
        return TargetAssessment()


class FakeClipboard:
    def __init__(self) -> None:
        self.preparation = ClipboardPreparation(True, ClipboardSnapshot("original"))
        self.restore_result = RestoreResult(True)
        self.prepare_error: Exception | None = None
        self.commit_error: Exception | None = None
        self.restore_error: Exception | None = None
        self.mutated = False
        self.restore_calls = 0
        self.discard_calls = 0

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

    def discard(self, snapshot: ClipboardSnapshot) -> None:
        self.discard_calls += 1


class FakeInjector:
    def __init__(self) -> None:
        self.paste_result = DispatchResult(True)
        self.direct_result = DispatchResult(True)
        self.paste_error: Exception | None = None
        self.direct_error: Exception | None = None
        self.prepare_error: BaseException | None = None
        self.direct_calls = 0
        self.paste_calls = 0

    def prepare_dispatch(self) -> bool:
        if self.prepare_error:
            raise self.prepare_error
        return True

    def dispatch_paste(self, *, prepared: bool = False) -> DispatchResult:
        self.paste_calls += 1
        if self.paste_error:
            raise self.paste_error
        return self.paste_result

    def dispatch_unicode(self, text: str, *, prepared: bool = False) -> DispatchResult:
        self.direct_calls += 1
        if self.direct_error:
            raise self.direct_error
        return self.direct_result


class RecordingInjector(FakeInjector):
    def __init__(self, events: list[str]) -> None:
        super().__init__()
        self.events = events

    def prepare_dispatch(self) -> bool:
        self.events.append("modifier_preflight")
        return True

    def dispatch_unicode(self, text: str, *, prepared: bool = False) -> DispatchResult:
        self.events.append("dispatch")
        return super().dispatch_unicode(text, prepared=prepared)


class BlockingInjector(FakeInjector):
    def __init__(self, entered: threading.Event, release: threading.Event) -> None:
        super().__init__()
        self.entered = entered
        self.release = release

    def prepare_dispatch(self) -> bool:
        self.entered.set()
        self.release.wait(timeout=2)
        return True


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
        self.assertTrue(outcome.original_snapshot_retained)
        self.assertEqual(0, self.clipboard.restore_calls)
        self.assertIsNotNone(self.service.retained_snapshot("r1"))
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

    def test_direct_dispatch_revalidates_target_immediately_before_input(self) -> None:
        target = SequenceTarget([None, OutcomeCode.TARGET_CHANGED])
        service = InsertionService(target, self.clipboard, self.injector)

        outcome = service.deliver(
            self.request(InsertionMethod.DIRECT), self.token
        )

        self.assertEqual(OutcomeCode.TARGET_CHANGED, outcome.code)
        self.assertEqual(2, target.assess_calls)
        self.assertEqual(0, self.injector.direct_calls)

    def test_modifier_preflight_precedes_final_target_assessment(self) -> None:
        events: list[str] = []
        service = InsertionService(
            RecordingTarget(events),
            self.clipboard,
            RecordingInjector(events),
        )

        outcome = service.deliver(
            self.request(InsertionMethod.DIRECT), self.token
        )

        self.assertEqual(OutcomeCode.DIRECT_DISPATCHED, outcome.code)
        self.assertEqual(
            ["assess", "modifier_preflight", "assess", "dispatch"], events
        )

    def test_paste_revalidates_after_mutation_and_restores_on_change(self) -> None:
        target = SequenceTarget([None, OutcomeCode.TARGET_CHANGED])
        service = InsertionService(target, self.clipboard, self.injector)

        outcome = service.deliver(
            self.request(InsertionMethod.PASTE), self.token
        )

        self.assertEqual(OutcomeCode.TARGET_CHANGED, outcome.code)
        self.assertEqual(2, target.assess_calls)
        self.assertEqual(0, self.injector.paste_calls)
        self.assertEqual(1, self.clipboard.restore_calls)

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
        restore = self.service.restore_original("r1")

        self.assertEqual(OutcomeCode.DISPATCHED, outcome.code)
        self.assertEqual(1, self.clipboard.restore_calls)
        self.assertTrue(restore.external_change)
        self.assertIsNone(self.service.retained_snapshot("r1"))

    def test_dispatch_error_keeps_synthetic_clipboard_and_original_snapshot(self) -> None:
        self.injector.paste_error = RuntimeError(CANARY)

        outcome = self.service.deliver(self.request(), self.token)

        self.assertEqual(OutcomeCode.DISPATCH_FAILED, outcome.code)
        self.assertTrue(outcome.original_snapshot_retained)
        self.assertEqual(0, self.clipboard.restore_calls)
        self.assertIsNotNone(self.service.retained_snapshot("r1"))
        self.assertEqual(CANARY, self.service.retained_result("r1"))

    def test_restoration_error_retains_original_snapshot(self) -> None:
        outcome = self.service.deliver(self.request(), self.token)
        self.clipboard.restore_error = RuntimeError(CANARY)
        restore = self.service.restore_original("r1")

        self.assertEqual(OutcomeCode.DISPATCHED, outcome.code)
        self.assertFalse(restore.restored)
        self.assertTrue(outcome.original_snapshot_retained)
        self.assertIsNotNone(self.service.retained_snapshot("r1"))

    def test_interrupt_before_input_restores_original_and_returns_cancelled(self) -> None:
        self.injector.prepare_error = KeyboardInterrupt()

        outcome = self.service.deliver(self.request(), self.token)

        self.assertEqual(OutcomeCode.CANCELLED, outcome.code)
        self.assertEqual(1, self.clipboard.restore_calls)
        self.assertIsNone(self.service.retained_snapshot("r1"))

    def test_interrupt_during_input_keeps_snapshot_for_explicit_restoration(self) -> None:
        self.injector.paste_error = KeyboardInterrupt()  # type: ignore[assignment]

        outcome = self.service.deliver(self.request(), self.token)

        self.assertEqual(OutcomeCode.DISPATCH_FAILED, outcome.code)
        self.assertEqual(0, self.clipboard.restore_calls)
        self.assertTrue(outcome.original_snapshot_retained)
        self.assertIsNotNone(self.service.retained_snapshot("r1"))

    def test_partial_mutation_failure_attempts_immediate_restoration(self) -> None:
        self.clipboard.commit_error = RuntimeError(CANARY)

        outcome = self.service.deliver(self.request(), self.token)

        self.assertEqual(OutcomeCode.CLIPBOARD_FAILED, outcome.code)
        self.assertEqual(1, self.clipboard.restore_calls)

    def test_interrupt_during_mutation_is_converted_and_restored(self) -> None:
        self.clipboard.commit_error = KeyboardInterrupt()  # type: ignore[assignment]

        outcome = self.service.deliver(self.request(), self.token)

        self.assertEqual(OutcomeCode.CLIPBOARD_FAILED, outcome.code)
        self.assertEqual(1, self.clipboard.restore_calls)
        self.assertIsNone(self.service.retained_snapshot("r1"))

    def test_interrupt_during_explicit_restore_keeps_snapshot_pending(self) -> None:
        outcome = self.service.deliver(self.request(), self.token)
        self.clipboard.restore_error = KeyboardInterrupt()  # type: ignore[assignment]

        restore = self.service.restore_original("r1")

        self.assertEqual(OutcomeCode.DISPATCHED, outcome.code)
        self.assertFalse(restore.restored)
        self.assertIsNotNone(self.service.retained_snapshot("r1"))

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
        self.assertEqual(0, self.clipboard.restore_calls)
        self.assertEqual(CANARY, self.service.retained_result("r1"))

    def test_new_request_is_busy_while_original_snapshot_is_pending(self) -> None:
        first = self.service.deliver(self.request(request_id="first"), self.token)

        second = self.service.deliver(self.request(request_id="second"), self.token)

        self.assertEqual(OutcomeCode.DISPATCHED, first.code)
        self.assertEqual(OutcomeCode.BUSY, second.code)
        self.assertEqual(1, self.injector.paste_calls)

    def test_discarding_original_releases_pending_transaction(self) -> None:
        self.service.deliver(self.request(request_id="first"), self.token)

        discarded = self.service.discard_original("first")
        second = self.service.deliver(
            self.request(InsertionMethod.DIRECT, "second"), self.token
        )

        self.assertTrue(discarded)
        self.assertEqual(1, self.clipboard.discard_calls)
        self.assertEqual(OutcomeCode.DIRECT_DISPATCHED, second.code)

    def test_explicit_restore_waits_for_active_delivery_to_finish(self) -> None:
        entered = threading.Event()
        release = threading.Event()
        injector = BlockingInjector(entered, release)
        service = InsertionService(self.target, self.clipboard, injector)
        delivery: list[object] = []
        restoration: list[object] = []
        delivery_thread = threading.Thread(
            target=lambda: delivery.append(
                service.deliver(self.request(), self.token)
            )
        )
        delivery_thread.start()
        self.assertTrue(entered.wait(timeout=1))
        restore_thread = threading.Thread(
            target=lambda: restoration.append(service.restore_original("r1"))
        )
        restore_thread.start()

        self.assertTrue(restore_thread.is_alive())
        release.set()
        delivery_thread.join(timeout=2)
        restore_thread.join(timeout=2)

        self.assertEqual(1, len(delivery))
        self.assertEqual(1, len(restoration))
        self.assertEqual(1, self.clipboard.restore_calls)

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
