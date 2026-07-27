"""Controlled native EDIT and ES_PASSWORD fixture for manual probing."""

from __future__ import annotations

import argparse
import ctypes
from ctypes import wintypes
import os
from pathlib import Path
import sys
from time import monotonic, sleep


CLASS_NAME = "NadiktInsertionSpikeFixture"
WS_OVERLAPPEDWINDOW = 0x00CF0000
WS_VISIBLE = 0x10000000
WS_CHILD = 0x40000000
WS_BORDER = 0x00800000
ES_AUTOHSCROLL = 0x0080
ES_PASSWORD = 0x0020
ES_MULTILINE = 0x0004
ES_WANTRETURN = 0x1000
CW_USEDEFAULT = 0x80000000
WM_DESTROY = 0x0002
SW_SHOW = 5


if os.name != "nt":
    raise SystemExit("windows_required")


user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
kernel32.GetModuleHandleW.restype = wintypes.HMODULE
kernel32.GetCurrentThreadId.restype = wintypes.DWORD
user32.LoadCursorW.restype = wintypes.HANDLE
user32.CreateWindowExW.restype = wintypes.HWND
user32.CreateWindowExW.argtypes = (
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
user32.DefWindowProcW.restype = wintypes.LPARAM
user32.DefWindowProcW.argtypes = (
    wintypes.HWND,
    wintypes.UINT,
    wintypes.WPARAM,
    wintypes.LPARAM,
)
user32.SetForegroundWindow.restype = wintypes.BOOL
user32.SetForegroundWindow.argtypes = (wintypes.HWND,)
user32.GetForegroundWindow.restype = wintypes.HWND
user32.GetWindowThreadProcessId.restype = wintypes.DWORD
user32.GetWindowThreadProcessId.argtypes = (
    wintypes.HWND,
    ctypes.POINTER(wintypes.DWORD),
)
user32.AttachThreadInput.restype = wintypes.BOOL
user32.AttachThreadInput.argtypes = (wintypes.DWORD, wintypes.DWORD, wintypes.BOOL)
user32.BringWindowToTop.restype = wintypes.BOOL
user32.BringWindowToTop.argtypes = (wintypes.HWND,)
user32.GetFocus.restype = wintypes.HWND
user32.SetFocus.restype = wintypes.HWND
user32.SetFocus.argtypes = (wintypes.HWND,)
user32.DestroyWindow.restype = wintypes.BOOL
user32.DestroyWindow.argtypes = (wintypes.HWND,)
user32.GetWindowTextLengthW.restype = ctypes.c_int
user32.GetWindowTextLengthW.argtypes = (wintypes.HWND,)
user32.GetWindowTextW.restype = ctypes.c_int
user32.GetWindowTextW.argtypes = (wintypes.HWND, wintypes.LPWSTR, ctypes.c_int)
user32.ShowWindow.restype = wintypes.BOOL
user32.ShowWindow.argtypes = (wintypes.HWND, ctypes.c_int)
user32.UpdateWindow.restype = wintypes.BOOL
user32.UpdateWindow.argtypes = (wintypes.HWND,)
user32.GetMessageW.restype = wintypes.BOOL
user32.GetMessageW.argtypes = (
    ctypes.POINTER(wintypes.MSG),
    wintypes.HWND,
    wintypes.UINT,
    wintypes.UINT,
)
user32.PeekMessageW.restype = wintypes.BOOL
user32.PeekMessageW.argtypes = (
    ctypes.POINTER(wintypes.MSG),
    wintypes.HWND,
    wintypes.UINT,
    wintypes.UINT,
    wintypes.UINT,
)
user32.TranslateMessage.restype = wintypes.BOOL
user32.TranslateMessage.argtypes = (ctypes.POINTER(wintypes.MSG),)
user32.DispatchMessageW.restype = wintypes.LPARAM
user32.DispatchMessageW.argtypes = (ctypes.POINTER(wintypes.MSG),)
WNDPROC = ctypes.WINFUNCTYPE(
    wintypes.LPARAM,
    wintypes.HWND,
    wintypes.UINT,
    wintypes.WPARAM,
    wintypes.LPARAM,
)


@WNDPROC
def window_proc(hwnd, message, wparam, lparam):
    if message == WM_DESTROY:
        user32.PostQuitMessage(0)
        return 0
    return user32.DefWindowProcW(hwnd, message, wparam, lparam)


class WNDCLASSW(ctypes.Structure):
    _fields_ = [
        ("style", wintypes.UINT),
        ("lpfnWndProc", WNDPROC),
        ("cbClsExtra", ctypes.c_int),
        ("cbWndExtra", ctypes.c_int),
        ("hInstance", wintypes.HINSTANCE),
        ("hIcon", wintypes.HICON),
        ("hCursor", wintypes.HANDLE),
        ("hbrBackground", wintypes.HBRUSH),
        ("lpszMenuName", wintypes.LPCWSTR),
        ("lpszClassName", wintypes.LPCWSTR),
    ]


user32.RegisterClassW.restype = wintypes.WORD
user32.RegisterClassW.argtypes = (ctypes.POINTER(WNDCLASSW),)


def create_fixture() -> tuple[wintypes.HWND, wintypes.HWND, wintypes.HWND]:
    instance = kernel32.GetModuleHandleW(None)
    window_class = WNDCLASSW(
        lpfnWndProc=window_proc,
        hInstance=instance,
        hCursor=user32.LoadCursorW(None, 32512),
        hbrBackground=6,
        lpszClassName=CLASS_NAME,
    )
    if not user32.RegisterClassW(ctypes.byref(window_class)):
        error = ctypes.get_last_error()
        if error != 1410:
            raise ctypes.WinError(error)

    window = user32.CreateWindowExW(
        0,
        CLASS_NAME,
        "Nadikt controlled fixture",
        WS_OVERLAPPEDWINDOW | WS_VISIBLE,
        CW_USEDEFAULT,
        CW_USEDEFAULT,
        520,
        220,
        None,
        None,
        instance,
        None,
    )
    if not window:
        raise ctypes.WinError(ctypes.get_last_error())
    normal = user32.CreateWindowExW(
        0,
        "EDIT",
        "",
        WS_CHILD | WS_VISIBLE | WS_BORDER | ES_MULTILINE | ES_WANTRETURN,
        24,
        20,
        460,
        65,
        window,
        1001,
        instance,
        None,
    )
    password = user32.CreateWindowExW(
        0,
        "EDIT",
        "",
        WS_CHILD | WS_VISIBLE | WS_BORDER | ES_AUTOHSCROLL | ES_PASSWORD,
        24,
        105,
        460,
        32,
        window,
        1002,
        instance,
        None,
    )
    if not normal or not password:
        raise ctypes.WinError(ctypes.get_last_error())
    user32.SetFocus(normal)
    user32.ShowWindow(window, SW_SHOW)
    user32.UpdateWindow(window)
    return window, normal, password


def run_self_check(
    window: wintypes.HWND,
    normal: wintypes.HWND,
    password: wintypes.HWND,
) -> int:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from insertion_spike.contracts import InsertionMethod, InsertionRequest, OutcomeCode
    from insertion_spike.service import InsertionService
    from insertion_spike.windows_injector import CtypesInputApi, WindowsInputInjector
    from insertion_spike.windows_target import CtypesWindowsTargetApi, WindowsTargetAdapter

    class UnusedClipboard:
        def prepare(self):
            raise AssertionError("clipboard_not_permitted")

        def commit_mutation(self, text):
            raise AssertionError("clipboard_not_permitted")

        def restore(self, snapshot):
            raise AssertionError("clipboard_not_permitted")

    class GuardedInputApi:
        def __init__(self, expected_window, expected_control):
            self._delegate = CtypesInputApi()
            self._expected_window = expected_window
            self._expected_control = expected_control

        def modifiers_down(self):
            return self._delegate.modifiers_down()

        def send(self, events):
            if (
                user32.GetForegroundWindow() != self._expected_window
                or user32.GetFocus() != self._expected_control
            ):
                return 0
            return self._delegate.send(events)

        def last_error(self):
            return self._delegate.last_error()

    adapter = WindowsTargetAdapter(CtypesWindowsTargetApi())
    if not _focus_fixture_control(window, normal):
        print("RESULT case=fixture_focus outcome=unavailable", flush=True)
        user32.DestroyWindow(window)
        return 1
    normal_token = adapter.capture()
    normal_result = adapter.assess(normal_token)
    print(
        f"RESULT case=classic_normal outcome={'safe' if normal_result.is_safe else normal_result.code.value}",
        flush=True,
    )
    service = InsertionService(
        adapter,
        UnusedClipboard(),
        WindowsInputInjector(GuardedInputApi(window, normal), modifier_wait_ms=0),
    )
    direct_outcome = service.deliver(
        InsertionRequest(
            "fixture-direct",
            "NADIKT_SYNTHETIC_Русский_😀\nLINE_2",
            InsertionMethod.DIRECT,
        ),
        normal_token,
    )
    expected_text = "NADIKT_SYNTHETIC_Русский_😀\nLINE_2"
    deadline = monotonic() + 0.5
    matched = False
    text_length = 0
    while monotonic() < deadline:
        pending = wintypes.MSG()
        while user32.PeekMessageW(ctypes.byref(pending), None, 0, 0, 1):
            user32.TranslateMessage(ctypes.byref(pending))
            user32.DispatchMessageW(ctypes.byref(pending))
        text_length = user32.GetWindowTextLengthW(normal)
        captured_text = ctypes.create_unicode_buffer(text_length + 1)
        user32.GetWindowTextW(normal, captured_text, len(captured_text))
        matched = captured_text.value.replace("\r\n", "\n") == expected_text
        if matched:
            break
        sleep(0.01)
    print(
        f"RESULT case=direct_unicode outcome={direct_outcome.code.value} matched={str(matched).lower()} actual_units={text_length}",
        flush=True,
    )

    if not _focus_fixture_control(window, password):
        print("RESULT case=fixture_focus outcome=unavailable", flush=True)
        user32.DestroyWindow(window)
        return 1
    changed_result = adapter.assess(normal_token)
    print(f"RESULT case=changed_control outcome={changed_result.code.value}", flush=True)

    password_token = adapter.capture()
    password_result = adapter.assess(password_token)
    print(f"RESULT case=classic_password outcome={password_result.code.value}", flush=True)
    blocked_outcome = service.deliver(
        InsertionRequest(
            "fixture-protected",
            "NADIKT_SYNTHETIC_BLOCKED",
            InsertionMethod.DIRECT,
        ),
        password_token,
    )
    protected_unchanged = user32.GetWindowTextLengthW(password) == 0
    print(
        f"RESULT case=protected_delivery outcome={blocked_outcome.code.value} unchanged={str(protected_unchanged).lower()}",
        flush=True,
    )

    if not _focus_fixture_control(window, normal):
        print("RESULT case=fixture_focus outcome=unavailable", flush=True)
        user32.DestroyWindow(window)
        return 1
    destroyed_token = adapter.capture()
    user32.DestroyWindow(window)
    destroyed_result = adapter.assess(destroyed_token)
    print(f"RESULT case=destroyed_target outcome={destroyed_result.code.value}", flush=True)
    passed = all(
        (
            normal_result.is_safe,
            direct_outcome.code is OutcomeCode.DIRECT_DISPATCHED,
            matched,
            changed_result.code is OutcomeCode.TARGET_CHANGED,
            password_result.code is OutcomeCode.TARGET_PROTECTED,
            blocked_outcome.code is OutcomeCode.TARGET_PROTECTED,
            protected_unchanged,
            destroyed_result.code is OutcomeCode.TARGET_UNAVAILABLE,
        )
    )
    return 0 if passed else 1


def _focus_fixture_control(window: wintypes.HWND, control: wintypes.HWND) -> bool:
    foreground = user32.GetForegroundWindow()
    foreground_thread = user32.GetWindowThreadProcessId(foreground, None)
    current_thread = kernel32.GetCurrentThreadId()
    attached = False
    if foreground_thread and foreground_thread != current_thread:
        attached = bool(
            user32.AttachThreadInput(current_thread, foreground_thread, True)
        )
    try:
        user32.BringWindowToTop(window)
        user32.SetForegroundWindow(window)
        user32.SetFocus(control)
        sleep(0.05)
        return (
            user32.GetForegroundWindow() == window
            and user32.GetFocus() == control
        )
    finally:
        if attached:
            user32.AttachThreadInput(current_thread, foreground_thread, False)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--self-check", action="store_true")
    args = parser.parse_args()
    window, normal, password = create_fixture()
    print("READY case=classic_target", flush=True)
    if args.self_check:
        return run_self_check(window, normal, password)
    message = wintypes.MSG()
    while user32.GetMessageW(ctypes.byref(message), None, 0, 0) > 0:
        user32.TranslateMessage(ctypes.byref(message))
        user32.DispatchMessageW(ctypes.byref(message))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
