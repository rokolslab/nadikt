"""Clipboard snapshot, mutation, ownership, and restoration transaction."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
import ctypes
from ctypes import wintypes
import logging
import os
from time import sleep
from typing import ContextManager, Iterator, Protocol

from .contracts import (
    ClipboardPreparation,
    ClipboardSnapshot,
    OutcomeCode,
    RestoreResult,
    get_logger,
)


CF_DIB = 8
CF_UNICODETEXT = 13
CF_HDROP = 15
CF_DIBV5 = 17
SUPPORTED_FORMATS = frozenset({CF_DIB, CF_UNICODETEXT, CF_HDROP, CF_DIBV5})
GMEM_MOVEABLE = 0x0002
HWND_MESSAGE = -3


class ClipboardAccessError(RuntimeError):
    """Clipboard boundary failed without exposing its contents."""


class ClipboardApi(Protocol):
    def opened(self) -> ContextManager[None]: ...

    def sequence_number(self) -> int: ...

    def list_formats(self) -> tuple[int, ...]: ...

    def read_format(self, format_id: int) -> bytes | None: ...

    def replace_contents(self, items: dict[int, bytes]) -> None: ...


@dataclass(repr=False)
class WindowsClipboardState:
    original_items: dict[int, bytes]
    sequence_before_mutation: int
    mutation_sequence: int | None = None

    def __repr__(self) -> str:
        return "WindowsClipboardState(<opaque>)"


class WindowsClipboardAdapter:
    def __init__(
        self,
        api: ClipboardApi,
        logger: logging.Logger | None = None,
    ) -> None:
        self._api = api
        self._logger = logger or get_logger()
        self._prepared_state: WindowsClipboardState | None = None

    def prepare(self) -> ClipboardPreparation:
        self._logger.debug("clipboard phase=prepare")
        try:
            with self._api.opened():
                sequence = self._api.sequence_number()
                formats = self._api.list_formats()
                unsupported = [item for item in formats if item not in SUPPORTED_FORMATS]
                self._logger.debug(
                    "clipboard format_count=%d known=%s",
                    len(formats),
                    not unsupported,
                )
                if unsupported:
                    self._logger.warning("clipboard unsupported_format=true")
                    return ClipboardPreparation(False, code=OutcomeCode.CLIPBOARD_UNSAFE)

                cloned: dict[int, bytes] = {}
                for format_id in formats:
                    payload = self._api.read_format(format_id)
                    if payload is None:
                        self._logger.warning("clipboard delayed_or_noncloneable=true")
                        return ClipboardPreparation(False, code=OutcomeCode.CLIPBOARD_UNSAFE)
                    cloned[format_id] = bytes(payload)
        except Exception as error:
            self._log_error("prepare", error)
            return ClipboardPreparation(False, code=OutcomeCode.CLIPBOARD_UNSAFE)

        state = WindowsClipboardState(cloned, sequence)
        self._prepared_state = state
        return ClipboardPreparation(True, ClipboardSnapshot(state))

    def commit_mutation(self, text: str) -> None:
        if self._prepared_state is None:
            raise ClipboardAccessError("clipboard_not_prepared")
        self._logger.debug("clipboard phase=commit_mutation")
        encoded = text.encode("utf-16-le") + b"\x00\x00"
        self._prepared_state.mutation_sequence = (
            self._prepared_state.sequence_before_mutation
        )
        try:
            with self._api.opened():
                if (
                    self._api.sequence_number()
                    != self._prepared_state.sequence_before_mutation
                ):
                    raise ClipboardAccessError("clipboard_changed_before_mutation")
                try:
                    self._api.replace_contents({CF_UNICODETEXT: encoded})
                finally:
                    # The clipboard is still locked, so this ownership marker cannot race.
                    self._prepared_state.mutation_sequence = self._api.sequence_number()
        except Exception as error:
            self._log_error("commit_mutation", error)
            raise ClipboardAccessError("clipboard_mutation_failed") from None

    def restore(self, snapshot: ClipboardSnapshot) -> RestoreResult:
        state = snapshot.state
        if not isinstance(state, WindowsClipboardState) or state.mutation_sequence is None:
            raise ClipboardAccessError("clipboard_snapshot_invalid")
        self._logger.debug("clipboard phase=restore")
        try:
            with self._api.opened():
                if self._api.sequence_number() != state.mutation_sequence:
                    self._logger.warning("clipboard ownership_lost=true")
                    return RestoreResult(False, external_change=True)
                self._api.replace_contents(dict(state.original_items))
        except Exception as error:
            self._log_error("restore", error)
            raise ClipboardAccessError("clipboard_restore_failed") from None
        finally:
            self._prepared_state = None
        return RestoreResult(True)

    def _log_error(self, operation: str, error: Exception) -> None:
        win32_code = getattr(error, "winerror", None)
        self._logger.error(
            "clipboard operation=%s exception_type=%s win32_code=%s",
            operation,
            type(error).__name__,
            win32_code if isinstance(win32_code, int) else "unavailable",
        )

    def close(self) -> None:
        close = getattr(self._api, "close", None)
        if callable(close):
            close()


class CtypesClipboardApi:
    """Win32 global-memory implementation for cloneable clipboard formats."""

    def __init__(self, *, lock_attempts: int = 5, lock_delay_ms: int = 20) -> None:
        if os.name != "nt":
            raise OSError("windows_required")
        self._user32 = ctypes.WinDLL("user32", use_last_error=True)
        self._kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        self._lock_attempts = max(1, lock_attempts)
        self._lock_delay_seconds = max(0, lock_delay_ms) / 1000
        self._configure_prototypes()
        self._owner_window = self._user32.CreateWindowExW(
            0,
            "STATIC",
            None,
            0,
            0,
            0,
            0,
            0,
            wintypes.HWND(HWND_MESSAGE),
            None,
            None,
            None,
        )
        if not self._owner_window:
            raise ClipboardAccessError("clipboard_owner_window_failed")
        get_logger().debug("[FIX:clipboard-owner] owner_window_created=true")

    @contextmanager
    def opened(self) -> Iterator[None]:
        for attempt in range(self._lock_attempts):
            if self._user32.OpenClipboard(self._owner_window):
                break
            if attempt + 1 < self._lock_attempts:
                sleep(self._lock_delay_seconds)
        else:
            raise ClipboardAccessError("clipboard_locked")
        try:
            yield
        finally:
            self._user32.CloseClipboard()

    def close(self) -> None:
        if self._owner_window:
            self._user32.DestroyWindow(self._owner_window)
            self._owner_window = None

    def sequence_number(self) -> int:
        return int(self._user32.GetClipboardSequenceNumber())

    def list_formats(self) -> tuple[int, ...]:
        formats: list[int] = []
        current = 0
        ctypes.set_last_error(0)
        while True:
            current = self._user32.EnumClipboardFormats(current)
            if not current:
                error = ctypes.get_last_error()
                if error:
                    raise ctypes.WinError(error)
                return tuple(formats)
            formats.append(int(current))

    def read_format(self, format_id: int) -> bytes | None:
        handle = self._user32.GetClipboardData(format_id)
        if not handle:
            return None
        size = self._kernel32.GlobalSize(handle)
        if not size:
            return None
        pointer = self._kernel32.GlobalLock(handle)
        if not pointer:
            return None
        try:
            return ctypes.string_at(pointer, size)
        finally:
            self._kernel32.GlobalUnlock(handle)

    def replace_contents(self, items: dict[int, bytes]) -> None:
        if not self._user32.EmptyClipboard():
            raise ctypes.WinError(ctypes.get_last_error())
        for format_id, payload in items.items():
            self._set_bytes(format_id, payload)

    def _set_bytes(self, format_id: int, payload: bytes) -> None:
        handle = self._kernel32.GlobalAlloc(GMEM_MOVEABLE, len(payload))
        if not handle:
            raise ctypes.WinError(ctypes.get_last_error())
        pointer = self._kernel32.GlobalLock(handle)
        if not pointer:
            self._kernel32.GlobalFree(handle)
            raise ctypes.WinError(ctypes.get_last_error())
        try:
            ctypes.memmove(pointer, payload, len(payload))
        finally:
            self._kernel32.GlobalUnlock(handle)
        if not self._user32.SetClipboardData(format_id, handle):
            self._kernel32.GlobalFree(handle)
            raise ctypes.WinError(ctypes.get_last_error())

    def _configure_prototypes(self) -> None:
        self._user32.CreateWindowExW.restype = wintypes.HWND
        self._user32.CreateWindowExW.argtypes = (
            wintypes.DWORD,
            wintypes.LPCWSTR,
            wintypes.LPCWSTR,
            wintypes.DWORD,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_int,
            wintypes.HWND,
            wintypes.HANDLE,
            wintypes.HINSTANCE,
            wintypes.LPVOID,
        )
        self._user32.DestroyWindow.argtypes = (wintypes.HWND,)
        self._user32.OpenClipboard.argtypes = (wintypes.HWND,)
        self._user32.GetClipboardData.restype = wintypes.HANDLE
        self._user32.GetClipboardData.argtypes = (wintypes.UINT,)
        self._user32.SetClipboardData.restype = wintypes.HANDLE
        self._user32.SetClipboardData.argtypes = (wintypes.UINT, wintypes.HANDLE)
        self._kernel32.GlobalAlloc.restype = wintypes.HGLOBAL
        self._kernel32.GlobalAlloc.argtypes = (wintypes.UINT, ctypes.c_size_t)
        self._kernel32.GlobalLock.restype = wintypes.LPVOID
        self._kernel32.GlobalLock.argtypes = (wintypes.HGLOBAL,)
        self._kernel32.GlobalUnlock.argtypes = (wintypes.HGLOBAL,)
        self._kernel32.GlobalFree.argtypes = (wintypes.HGLOBAL,)
        self._kernel32.GlobalSize.restype = ctypes.c_size_t
        self._kernel32.GlobalSize.argtypes = (wintypes.HGLOBAL,)
        self._user32.EmptyClipboard.restype = wintypes.BOOL
        self._user32.EnumClipboardFormats.argtypes = (wintypes.UINT,)
