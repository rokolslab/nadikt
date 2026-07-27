import unittest

from insertion_spike.contracts import (
    ClipboardPreparation,
    ClipboardSnapshot,
    InsertionRequest,
    OutcomeCode,
    RestoreResult,
    TargetAssessment,
    TargetToken,
)
from insertion_spike.service import InsertionService
from insertion_spike.windows_injector import WindowsInputInjector


class FakeInputApi:
    def __init__(self) -> None:
        self.modifier = False
        self.sent_batches: list[tuple[object, ...]] = []
        self.send_count: int | None = None
        self.send_counts: list[int] = []
        self.error: Exception | None = None

    def modifiers_down(self) -> bool:
        return self.modifier

    def send(self, events):
        self.sent_batches.append(events)
        if self.error:
            raise self.error
        if self.send_counts:
            return self.send_counts.pop(0)
        return len(events) if self.send_count is None else self.send_count

    def last_error(self) -> int:
        return 5


class NeverClipboard:
    def prepare(self):
        return ClipboardPreparation(True, ClipboardSnapshot(None))

    def commit_mutation(self, text):
        raise AssertionError("clipboard must not be reached")

    def restore(self, snapshot):
        return RestoreResult(True)


class ProtectedTarget:
    def capture(self):
        return TargetToken("target")

    def assess(self, captured_target):
        return TargetAssessment(OutcomeCode.TARGET_PROTECTED)


class WindowsInputInjectorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.api = FakeInputApi()
        self.injector = WindowsInputInjector(self.api, modifier_wait_ms=0)

    def test_unicode_cyrillic_newline_and_surrogate_pair_are_explicit_events(self) -> None:
        result = self.injector.dispatch_unicode("Я\r\n😀")

        down_units = [event.code_unit for event in self.api.sent_batches[0][::2]]
        self.assertTrue(result.dispatched)
        self.assertEqual([0x042F, 0x000A, 0xD83D, 0xDE00], down_units)

    def test_physical_modifier_rejects_without_synthetic_release(self) -> None:
        self.api.modifier = True

        result = self.injector.dispatch_paste()

        self.assertEqual(OutcomeCode.DISPATCH_FAILED, result.code)
        self.assertEqual([], self.api.sent_batches)

    def test_partial_send_releases_only_synthetic_pressed_keys(self) -> None:
        self.api.send_count = 1

        result = self.injector.dispatch_paste()

        self.assertFalse(result.dispatched)
        self.assertEqual(2, len(self.api.sent_batches))
        cleanup = self.api.sent_batches[1]
        self.assertEqual(1, len(cleanup))
        self.assertTrue(cleanup[0].is_key_up)

    def test_partial_cleanup_failure_is_logged_without_payload(self) -> None:
        self.api.send_counts = [1, 0, 0, 0]

        with self.assertLogs("nadikt.windows_insertion_spike", level="ERROR") as captured:
            result = self.injector.dispatch_paste()

        self.assertEqual(OutcomeCode.CLEANUP_FAILED, result.code)
        self.assertIn("[FIX:synthetic-cleanup]", "\n".join(captured.output))
        self.assertFalse(self.injector.prepare_dispatch())
        bypass = self.injector.dispatch_paste(prepared=True)
        self.assertEqual(OutcomeCode.CLEANUP_FAILED, bypass.code)

    def test_dispatch_exception_is_safe_failure(self) -> None:
        self.api.error = RuntimeError("CANARY_injector_payload")

        result = self.injector.dispatch_unicode("secret")

        self.assertEqual(OutcomeCode.CLEANUP_FAILED, result.code)

    def test_dispatch_interrupt_requires_confirmed_cleanup_or_poisons_injector(self) -> None:
        self.api.error = KeyboardInterrupt()  # type: ignore[assignment]

        result = self.injector.dispatch_paste()

        self.assertEqual(OutcomeCode.CLEANUP_FAILED, result.code)
        self.assertFalse(self.injector.prepare_dispatch())

    def test_protected_target_never_reaches_direct_fallback(self) -> None:
        service = InsertionService(ProtectedTarget(), NeverClipboard(), self.injector)

        outcome = service.deliver(
            InsertionRequest("protected", "CANARY"), TargetToken("target")
        )

        self.assertEqual(OutcomeCode.TARGET_PROTECTED, outcome.code)
        self.assertEqual([], self.api.sent_batches)


if __name__ == "__main__":
    unittest.main()
