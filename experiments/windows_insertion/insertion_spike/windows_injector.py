"""Controlled Ctrl+V and Unicode SendInput dispatch."""

from __future__ import annotations

from dataclasses import dataclass
import ctypes
from ctypes import wintypes
import logging
import os
from time import monotonic, sleep
from typing import Protocol

from .contracts import DispatchResult, OutcomeCode, get_logger


VK_CONTROL = 0x11
VK_V = 0x56
VK_SHIFT = 0x10
VK_MENU = 0x12
VK_LWIN = 0x5B
VK_RWIN = 0x5C
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_UNICODE = 0x0004
INPUT_KEYBOARD = 1


@dataclass(frozen=True)
class KeyEvent:
    virtual_key: int = 0
    code_unit: int = 0
    is_key_up: bool = False
    is_unicode: bool = False


class InputApi(Protocol):
    def modifiers_down(self) -> bool: ...

    def send(self, events: tuple[KeyEvent, ...]) -> int: ...

    def last_error(self) -> int: ...


class WindowsInputInjector:
    def __init__(
        self,
        api: InputApi,
        *,
        modifier_wait_ms: int = 150,
        logger: logging.Logger | None = None,
    ) -> None:
        self._api = api
        self._modifier_wait_seconds = max(0, modifier_wait_ms) / 1000
        self._logger = logger or get_logger()

    def prepare_dispatch(self) -> bool:
        ready = self._wait_for_released_modifiers()
        self._logger.debug(
            "[FIX:modifier-preflight] modifiers_released=%s",
            ready,
        )
        return ready

    def dispatch_paste(self, *, prepared: bool = False) -> DispatchResult:
        self._logger.debug("injector phase=dispatch method=paste event_count=4")
        if not self._ready_for_immediate_dispatch(prepared):
            self._logger.warning("injector physical_modifier=true")
            return DispatchResult(False, OutcomeCode.DISPATCH_FAILED)
        events = (
            KeyEvent(virtual_key=VK_CONTROL),
            KeyEvent(virtual_key=VK_V),
            KeyEvent(virtual_key=VK_V, is_key_up=True),
            KeyEvent(virtual_key=VK_CONTROL, is_key_up=True),
        )
        return self._send_complete(events)

    def dispatch_unicode(self, text: str, *, prepared: bool = False) -> DispatchResult:
        code_units = self._utf16_code_units(text)
        self._logger.debug(
            "injector phase=dispatch method=direct event_count=%d",
            len(code_units) * 2,
        )
        if not self._ready_for_immediate_dispatch(prepared):
            self._logger.warning("injector physical_modifier=true")
            return DispatchResult(False, OutcomeCode.DISPATCH_FAILED)
        events = tuple(
            event
            for code_unit in code_units
            for event in (
                KeyEvent(code_unit=code_unit, is_unicode=True),
                KeyEvent(code_unit=code_unit, is_key_up=True, is_unicode=True),
            )
        )
        return self._send_complete(events)

    def _ready_for_immediate_dispatch(self, prepared: bool) -> bool:
        if not prepared and not self.prepare_dispatch():
            return False
        # Do not wait here: service performs final target assessment after preflight.
        return not self._api.modifiers_down()

    def _wait_for_released_modifiers(self) -> bool:
        deadline = monotonic() + self._modifier_wait_seconds
        while self._api.modifiers_down():
            if monotonic() >= deadline:
                return False
            sleep(min(0.01, self._modifier_wait_seconds))
        return True

    def _send_complete(self, events: tuple[KeyEvent, ...]) -> DispatchResult:
        try:
            sent = self._api.send(events)
        except Exception as error:
            self._logger.error(
                "injector operation=send exception_type=%s",
                type(error).__name__,
            )
            return DispatchResult(False, OutcomeCode.DISPATCH_FAILED)
        if sent != len(events):
            self._logger.error(
                "injector operation=send event_count_mismatch=true expected=%d sent=%d win32_code=%d",
                len(events),
                sent,
                self._api.last_error(),
            )
            self._release_synthetic_keys(events[:sent])
            return DispatchResult(False, OutcomeCode.DISPATCH_FAILED)
        self._logger.info("injector outcome=dispatched")
        return DispatchResult(True)

    def _release_synthetic_keys(self, sent_events: tuple[KeyEvent, ...]) -> None:
        pressed: list[KeyEvent] = []
        for event in sent_events:
            matching = next(
                (
                    item
                    for item in reversed(pressed)
                    if item.virtual_key == event.virtual_key
                    and item.code_unit == event.code_unit
                    and item.is_unicode == event.is_unicode
                ),
                None,
            )
            if event.is_key_up and matching is not None:
                pressed.remove(matching)
            elif not event.is_key_up:
                pressed.append(event)
        cleanup = tuple(
            KeyEvent(
                virtual_key=event.virtual_key,
                code_unit=event.code_unit,
                is_key_up=True,
                is_unicode=event.is_unicode,
            )
            for event in reversed(pressed)
        )
        if cleanup:
            try:
                released = self._api.send(cleanup)
                if released != len(cleanup):
                    self._logger.error(
                        "[FIX:synthetic-cleanup] event_count_mismatch=true expected=%d sent=%d win32_code=%d",
                        len(cleanup),
                        released,
                        self._api.last_error(),
                    )
            except Exception as error:
                self._logger.error(
                    "[FIX:synthetic-cleanup] exception_type=%s",
                    type(error).__name__,
                )

    @staticmethod
    def _utf16_code_units(text: str) -> tuple[int, ...]:
        normalized = text.replace("\r\n", "\n").replace("\r", "\n")
        encoded = normalized.encode("utf-16-le")
        return tuple(
            int.from_bytes(encoded[offset : offset + 2], "little")
            for offset in range(0, len(encoded), 2)
        )


class CtypesInputApi:
    def __init__(self) -> None:
        if os.name != "nt":
            raise OSError("windows_required")
        self._user32 = ctypes.WinDLL("user32", use_last_error=True)
        self._user32.SendInput.argtypes = (
            wintypes.UINT,
            ctypes.POINTER(INPUT),
            ctypes.c_int,
        )
        self._user32.SendInput.restype = wintypes.UINT

    def modifiers_down(self) -> bool:
        return any(
            self._user32.GetAsyncKeyState(key) & 0x8000
            for key in (VK_CONTROL, VK_SHIFT, VK_MENU, VK_LWIN, VK_RWIN)
        )

    def send(self, events: tuple[KeyEvent, ...]) -> int:
        if not events:
            return 0
        inputs = (INPUT * len(events))()
        for index, event in enumerate(events):
            flags = 0
            if event.is_unicode:
                flags |= KEYEVENTF_UNICODE
            if event.is_key_up:
                flags |= KEYEVENTF_KEYUP
            inputs[index].type = INPUT_KEYBOARD
            inputs[index].data.ki = KEYBDINPUT(
                wVk=0 if event.is_unicode else event.virtual_key,
                wScan=event.code_unit if event.is_unicode else 0,
                dwFlags=flags,
                time=0,
                dwExtraInfo=0,
            )
        return int(self._user32.SendInput(len(events), inputs, ctypes.sizeof(INPUT)))

    def last_error(self) -> int:
        return ctypes.get_last_error()


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", wintypes.WORD),
        ("wScan", wintypes.WORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", wintypes.WPARAM),
    ]


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", wintypes.LONG),
        ("dy", wintypes.LONG),
        ("mouseData", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", wintypes.WPARAM),
    ]


class HARDWAREINPUT(ctypes.Structure):
    _fields_ = [
        ("uMsg", wintypes.DWORD),
        ("wParamL", wintypes.WORD),
        ("wParamH", wintypes.WORD),
    ]


class INPUT_UNION(ctypes.Union):
    _fields_ = [
        ("mi", MOUSEINPUT),
        ("ki", KEYBDINPUT),
        ("hi", HARDWAREINPUT),
    ]


class INPUT(ctypes.Structure):
    _fields_ = [("type", wintypes.DWORD), ("data", INPUT_UNION)]
