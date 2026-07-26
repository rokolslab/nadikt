from contextlib import contextmanager
import sys
import unittest
from unittest.mock import patch

from fixtures import clipboard_racer
from insertion_spike.cli import SYNTHETIC_PAYLOAD
from insertion_spike.windows_clipboard import CF_UNICODETEXT


class FakeClipboardApi:
    def __init__(self, text: str) -> None:
        self.payload = text.encode("utf-16-le") + b"\x00\x00"
        self.replace_calls = 0

    @contextmanager
    def opened(self):
        yield

    def list_formats(self):
        return (CF_UNICODETEXT,)

    def read_format(self, format_id):
        return self.payload

    def replace_contents(self, items):
        self.replace_calls += 1

    def close(self):
        pass


class ClipboardRacerTests(unittest.TestCase):
    def test_racer_requires_explicit_confirmation_before_mutation(self) -> None:
        api = FakeClipboardApi("user clipboard")
        with (
            patch.object(clipboard_racer, "CtypesClipboardApi", return_value=api),
            patch.object(sys, "argv", ["clipboard_racer.py", "--delay-ms", "0"]),
        ):
            result = clipboard_racer.main()

        self.assertEqual(2, result)
        self.assertEqual(0, api.replace_calls)

    def test_racer_rejects_non_synthetic_current_clipboard(self) -> None:
        api = FakeClipboardApi("user clipboard")
        with (
            patch.object(clipboard_racer, "CtypesClipboardApi", return_value=api),
            patch.object(
                sys,
                "argv",
                ["clipboard_racer.py", "--confirm", "--delay-ms", "0"],
            ),
        ):
            result = clipboard_racer.main()

        self.assertEqual(1, result)
        self.assertEqual(0, api.replace_calls)

    def test_racer_mutates_only_expected_cli_synthetic_clipboard(self) -> None:
        api = FakeClipboardApi(SYNTHETIC_PAYLOAD)
        with (
            patch.object(clipboard_racer, "CtypesClipboardApi", return_value=api),
            patch.object(
                sys,
                "argv",
                ["clipboard_racer.py", "--confirm", "--delay-ms", "0"],
            ),
        ):
            result = clipboard_racer.main()

        self.assertEqual(0, result)
        self.assertEqual(1, api.replace_calls)


if __name__ == "__main__":
    unittest.main()
