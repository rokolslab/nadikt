from contextlib import contextmanager
import unittest
from unittest.mock import MagicMock, patch

from insertion_spike.contracts import OutcomeCode
from insertion_spike.windows_clipboard import (
    CF_DIB,
    CF_DIBV5,
    CF_HDROP,
    CF_UNICODETEXT,
    ClipboardAccessError,
    CtypesClipboardApi,
    WindowsClipboardAdapter,
)


CANARY_BYTES = b"CANARY_clipboard_payload_51ab"
CF_HTML = 0xC001
CF_RTF = 0xC002
CF_UNKNOWN = 0xC003


class FakeClipboardApi:
    def __init__(self, items: dict[int, bytes | None] | None = None) -> None:
        self.items = dict(items or {})
        self.sequence = 10
        self.open_error: Exception | None = None
        self.read_error_at: int | None = None
        self.replace_error = False
        self.increment_sequence_on_replace_error = False
        self.replaced_payloads: list[dict[int, bytes]] = []

    @contextmanager
    def opened(self):
        if self.open_error:
            raise self.open_error
        yield

    def sequence_number(self) -> int:
        return self.sequence

    def list_formats(self) -> tuple[int, ...]:
        return tuple(self.items)

    def read_format(self, format_id: int) -> bytes | None:
        if self.read_error_at == format_id:
            raise ClipboardAccessError("clone_failed")
        return self.items[format_id]

    def replace_contents(self, items: dict[int, bytes]) -> None:
        if self.replace_error:
            if self.increment_sequence_on_replace_error:
                self.sequence += 1
            raise ClipboardAccessError("replace_failed")
        self.items = dict(items)
        self.replaced_payloads.append(dict(items))
        self.sequence += 1


class WindowsClipboardAdapterTests(unittest.TestCase):
    def test_win32_clipboard_is_opened_with_non_null_owner(self) -> None:
        user32 = MagicMock()
        kernel32 = MagicMock()
        user32.OpenClipboard.return_value = True
        with patch(
            "insertion_spike.windows_clipboard.ctypes.WinDLL",
            side_effect=(user32, kernel32),
        ):
            api = CtypesClipboardApi(lock_attempts=1)
            with api.opened():
                pass

        owner = user32.OpenClipboard.call_args.args[0]
        self.assertNotIn(owner, (None, 0))

    def test_win32_partial_set_retries_with_preallocated_handles(self) -> None:
        user32 = MagicMock()
        kernel32 = MagicMock()
        user32.CreateWindowExW.return_value = 1
        user32.EmptyClipboard.return_value = True
        user32.SetClipboardData.side_effect = [1, 0, 1, 1]
        kernel32.GlobalAlloc.side_effect = [101, 102, 103, 104]
        kernel32.GlobalLock.return_value = 1
        with (
            patch(
                "insertion_spike.windows_clipboard.ctypes.WinDLL",
                side_effect=(user32, kernel32),
            ),
            patch("insertion_spike.windows_clipboard.ctypes.memmove"),
        ):
            api = CtypesClipboardApi(lock_attempts=1)
            api.replace_contents({CF_UNICODETEXT: b"text", CF_DIB: b"image"})

        self.assertEqual(2, user32.EmptyClipboard.call_count)
        self.assertEqual(4, user32.SetClipboardData.call_count)
        kernel32.GlobalFree.assert_called_once_with(102)

    def test_win32_preallocation_failure_frees_earlier_handles_before_mutation(self) -> None:
        user32 = MagicMock()
        kernel32 = MagicMock()
        user32.CreateWindowExW.return_value = 1
        kernel32.GlobalAlloc.side_effect = [101, 0]
        kernel32.GlobalLock.return_value = 1
        with (
            patch(
                "insertion_spike.windows_clipboard.ctypes.WinDLL",
                side_effect=(user32, kernel32),
            ),
            patch("insertion_spike.windows_clipboard.ctypes.memmove"),
            self.assertRaises(OSError),
        ):
            api = CtypesClipboardApi(lock_attempts=1)
            api.replace_contents({CF_UNICODETEXT: b"text", CF_DIB: b"image"})

        user32.EmptyClipboard.assert_not_called()
        kernel32.GlobalFree.assert_called_once_with(101)

    def test_empty_and_supported_formats_round_trip(self) -> None:
        cases = (
            {},
            {CF_UNICODETEXT: "hello".encode("utf-16-le") + b"\x00\x00"},
            {CF_UNICODETEXT: "Привет".encode("utf-16-le") + b"\x00\x00"},
            {CF_DIB: CANARY_BYTES},
            {CF_DIBV5: CANARY_BYTES},
            {CF_HDROP: CANARY_BYTES},
            {CF_UNICODETEXT: b"t\x00\x00\x00", CF_DIB: CANARY_BYTES, CF_HDROP: b"files"},
        )
        for original in cases:
            with self.subTest(formats=tuple(original)):
                api = FakeClipboardApi(original)
                adapter = WindowsClipboardAdapter(api)

                preparation = adapter.prepare()
                adapter.commit_mutation("synthetic")
                result = adapter.restore(preparation.snapshot)  # type: ignore[arg-type]

                self.assertTrue(preparation.is_safe)
                self.assertTrue(result.restored)
                self.assertEqual(original, api.items)

    def test_rich_unknown_and_delayed_formats_reject_before_mutation(self) -> None:
        cases = (
            {CF_UNICODETEXT: b"text", CF_HTML: b"html"},
            {CF_RTF: b"rtf"},
            {CF_UNKNOWN: b"unknown"},
            {CF_UNICODETEXT: None},
        )
        for original in cases:
            with self.subTest(formats=tuple(original)):
                api = FakeClipboardApi(original)
                adapter = WindowsClipboardAdapter(api)

                preparation = adapter.prepare()

                self.assertFalse(preparation.is_safe)
                self.assertEqual(OutcomeCode.CLIPBOARD_UNSAFE, preparation.code)
                self.assertEqual([], api.replaced_payloads)

    def test_lock_contention_and_partial_clone_failure_are_safe(self) -> None:
        locked = FakeClipboardApi({CF_UNICODETEXT: b"text"})
        locked.open_error = ClipboardAccessError("locked")
        partial = FakeClipboardApi({CF_UNICODETEXT: b"text", CF_DIB: CANARY_BYTES})
        partial.read_error_at = CF_DIB

        self.assertFalse(WindowsClipboardAdapter(locked).prepare().is_safe)
        self.assertFalse(WindowsClipboardAdapter(partial).prepare().is_safe)
        self.assertEqual([], locked.replaced_payloads)
        self.assertEqual([], partial.replaced_payloads)

    def test_mutation_failure_raises_without_discarding_cloned_snapshot(self) -> None:
        api = FakeClipboardApi({CF_DIB: CANARY_BYTES})
        adapter = WindowsClipboardAdapter(api)
        preparation = adapter.prepare()
        api.replace_error = True

        with self.assertRaisesRegex(ClipboardAccessError, "clipboard_mutation_failed"):
            adapter.commit_mutation("synthetic")

        self.assertIsNotNone(preparation.snapshot)

    def test_external_sequence_change_is_never_overwritten(self) -> None:
        api = FakeClipboardApi({CF_UNICODETEXT: b"original"})
        adapter = WindowsClipboardAdapter(api)
        preparation = adapter.prepare()
        adapter.commit_mutation("synthetic")
        api.items = {CF_UNICODETEXT: b"external"}
        api.sequence += 1

        result = adapter.restore(preparation.snapshot)  # type: ignore[arg-type]

        self.assertTrue(result.external_change)
        self.assertEqual({CF_UNICODETEXT: b"external"}, api.items)

    def test_external_change_before_mutation_is_rejected_without_overwrite(self) -> None:
        api = FakeClipboardApi({CF_UNICODETEXT: b"original"})
        adapter = WindowsClipboardAdapter(api)
        adapter.prepare()
        api.items = {CF_UNICODETEXT: b"external"}
        api.sequence += 1

        with self.assertRaisesRegex(ClipboardAccessError, "clipboard_mutation_failed"):
            adapter.commit_mutation("synthetic")

        self.assertEqual({CF_UNICODETEXT: b"external"}, api.items)
        self.assertEqual([], api.replaced_payloads)

    def test_discard_releases_adapter_snapshot_without_clipboard_mutation(self) -> None:
        api = FakeClipboardApi({CF_UNICODETEXT: b"original"})
        adapter = WindowsClipboardAdapter(api)
        preparation = adapter.prepare()

        adapter.discard(preparation.snapshot)  # type: ignore[arg-type]

        self.assertIsNone(adapter._prepared_state)
        self.assertEqual([], api.replaced_payloads)

    def test_restoration_failure_keeps_original_snapshot_alive(self) -> None:
        original = bytearray(CANARY_BYTES)
        api = FakeClipboardApi({CF_DIB: original})  # type: ignore[dict-item]
        adapter = WindowsClipboardAdapter(api)
        preparation = adapter.prepare()
        adapter.commit_mutation("synthetic")
        api.replace_error = True
        api.increment_sequence_on_replace_error = True

        with self.assertRaisesRegex(ClipboardAccessError, "clipboard_restore_failed"):
            adapter.restore(preparation.snapshot)  # type: ignore[arg-type]

        self.assertEqual(CANARY_BYTES, preparation.snapshot.state.original_items[CF_DIB])  # type: ignore[union-attr]
        api.replace_error = False
        retry = adapter.restore(preparation.snapshot)  # type: ignore[arg-type]
        self.assertTrue(retry.restored)


if __name__ == "__main__":
    unittest.main()
