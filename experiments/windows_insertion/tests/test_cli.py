import contextlib
import io
import unittest
from unittest.mock import MagicMock, patch

from insertion_spike import cli
from insertion_spike.contracts import (
    ClipboardPreparation,
    ClipboardSnapshot,
    DispatchResult,
    RestoreResult,
    TargetAssessment,
    TargetToken,
)
from insertion_spike.cli import RuntimeDependencies


class FakeTarget:
    def __init__(self) -> None:
        self.capture_calls = 0

    def capture(self):
        self.capture_calls += 1
        return TargetToken("target")

    def assess(self, captured_target):
        return TargetAssessment()


class FakeClipboard:
    def __init__(self) -> None:
        self.commit_calls = 0
        self.close_calls = 0
        self.restore_calls = 0

    def prepare(self):
        return ClipboardPreparation(True, ClipboardSnapshot("original"))

    def commit_mutation(self, text):
        self.commit_calls += 1

    def restore(self, snapshot):
        self.restore_calls += 1
        return RestoreResult(True)

    def close(self):
        self.close_calls += 1


class FakeInjector:
    def prepare_dispatch(self):
        return True

    def dispatch_paste(self, *, prepared=False):
        return DispatchResult(True)

    def dispatch_unicode(self, text, *, prepared=False):
        return DispatchResult(True)


class CliTests(unittest.TestCase):
    def setUp(self) -> None:
        self.target = FakeTarget()
        self.clipboard = FakeClipboard()
        self.runtime = RuntimeDependencies(self.target, self.clipboard, FakeInjector())

    def capture_run(self, args, dependencies=None):
        stdout = io.StringIO()
        stderr = io.StringIO()
        with (
            contextlib.redirect_stdout(stdout),
            contextlib.redirect_stderr(stderr),
            patch("builtins.input", return_value="RESTORE"),
        ):
            result = cli.run(args, dependencies=dependencies)
        return result, stdout.getvalue() + stderr.getvalue()

    def test_dry_run_never_creates_or_calls_platform_runtime(self) -> None:
        result, output = self.capture_run(["--confirm", "--dry-run"])

        self.assertEqual(0, result)
        self.assertIn("dry_run=true", output)
        self.assertNotIn(cli.SYNTHETIC_PAYLOAD, output)

    def test_cancel_happens_before_capture_or_mutation(self) -> None:
        result, output = self.capture_run(["--confirm", "--cancel"], self.runtime)

        self.assertEqual(2, result)
        self.assertEqual(0, self.target.capture_calls)
        self.assertEqual(0, self.clipboard.commit_calls)
        self.assertNotIn(cli.SYNTHETIC_PAYLOAD, output)

    def test_two_stage_delivery_uses_captured_token(self) -> None:
        result, output = self.capture_run(
            [
                "--confirm",
                "--method",
                "paste",
                "--capture-countdown",
                "0",
                "--delivery-countdown",
                "0",
                "--hold",
            ],
            self.runtime,
        )

        self.assertEqual(0, result)
        self.assertEqual(1, self.target.capture_calls)
        self.assertEqual(1, self.clipboard.commit_calls)
        self.assertEqual(1, self.clipboard.restore_calls)
        self.assertEqual(1, self.clipboard.close_calls)
        self.assertIn("phase=capture complete=true", output)
        self.assertIn("outcome=dispatched", output)
        self.assertNotIn(cli.SYNTHETIC_PAYLOAD, output)

    def test_runtime_composition_closes_clipboard_owner_on_later_failure(self) -> None:
        clipboard_api = MagicMock()
        with (
            patch.object(cli, "CtypesWindowsTargetApi"),
            patch.object(cli, "WindowsTargetAdapter"),
            patch.object(cli, "CtypesClipboardApi", return_value=clipboard_api),
            patch.object(cli, "WindowsClipboardAdapter"),
            patch.object(cli, "CtypesInputApi", side_effect=RuntimeError("input_failed")),
        ):
            with self.assertRaisesRegex(RuntimeError, "input_failed"):
                cli.create_runtime()

        clipboard_api.close.assert_called_once_with()

    def test_keyboard_interrupt_cannot_bypass_pending_restoration(self) -> None:
        stdout = io.StringIO()
        with (
            contextlib.redirect_stdout(stdout),
            patch("builtins.input", side_effect=[KeyboardInterrupt(), "RESTORE"]),
        ):
            result = cli.run(
                [
                    "--confirm",
                    "--method",
                    "paste",
                    "--capture-countdown",
                    "0",
                    "--delivery-countdown",
                    "0",
                    "--hold",
                ],
                dependencies=self.runtime,
            )

        self.assertEqual(0, result)
        self.assertEqual(1, self.clipboard.restore_calls)
        self.assertIn("input_interrupted=true", stdout.getvalue())

    def test_failed_explicit_restoration_stays_pending_for_retry(self) -> None:
        service = MagicMock()
        service.restore_original.side_effect = [
            RestoreResult(False),
            RestoreResult(True),
        ]
        stdout = io.StringIO()
        with (
            contextlib.redirect_stdout(stdout),
            patch("builtins.input", side_effect=["RESTORE", "RESTORE"]),
        ):
            cli._resolve_pending_restoration(service, "request")

        self.assertEqual(2, service.restore_original.call_count)
        self.assertIn("restore_failed=true", stdout.getvalue())

    def test_failed_discard_stays_pending_for_retry(self) -> None:
        service = MagicMock()
        service.discard_original.side_effect = [False, True]
        stdout = io.StringIO()
        with (
            contextlib.redirect_stdout(stdout),
            patch(
                "builtins.input",
                side_effect=["DISCARD_ORIGINAL", "DISCARD_ORIGINAL"],
            ),
        ):
            cli._resolve_pending_restoration(service, "request")

        self.assertEqual(2, service.discard_original.call_count)
        self.assertIn("discard_failed=true", stdout.getvalue())


if __name__ == "__main__":
    unittest.main()
