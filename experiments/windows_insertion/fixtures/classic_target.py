"""Controlled native EDIT and ES_PASSWORD fixture for manual probing."""

from __future__ import annotations

import argparse
import ctypes
from ctypes import wintypes
import os
from pathlib import Path
import sys
from time import sleep


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
user32.SetFocus.argtypes = (wintypes.HWND,)
user32.DestroyWindow.argtypes = (wintypes.HWND,)
user32.GetWindowTextLengthW.argtypes = (wintypes.HWND,)
user32.GetWindowTextW.argtypes = (wintypes.HWND, wintypes.LPWSTR, ctypes.c_int)
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
    from insertion_spike.contracts import InsertionMethod, InsertionRequest
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

    adapter = WindowsTargetAdapter(CtypesWindowsTargetApi())
    user32.SetForegroundWindow(window)
    user32.SetFocus(normal)
    sleep(0.05)
    normal_token = adapter.capture()
    normal_result = adapter.assess(normal_token)
    print(
        f"RESULT case=classic_normal outcome={'safe' if normal_result.is_safe else normal_result.code.value}",
        flush=True,
    )
    service = InsertionService(
        adapter,
        UnusedClipboard(),
        WindowsInputInjector(CtypesInputApi(), modifier_wait_ms=0),
    )
    direct_outcome = service.deliver(
        InsertionRequest(
            "fixture-direct",
            "NADIKT_SYNTHETIC_Русский_😀\nLINE_2",
            InsertionMethod.DIRECT,
        ),
        normal_token,
    )
    pending = wintypes.MSG()
    while user32.PeekMessageW(ctypes.byref(pending), None, 0, 0, 1):
        user32.TranslateMessage(ctypes.byref(pending))
        user32.DispatchMessageW(ctypes.byref(pending))
    text_length = user32.GetWindowTextLengthW(normal)
    captured_text = ctypes.create_unicode_buffer(text_length + 1)
    user32.GetWindowTextW(normal, captured_text, len(captured_text))
    matched = captured_text.value.replace("\r\n", "\n") == "NADIKT_SYNTHETIC_Русский_😀\nLINE_2"
    print(
        f"RESULT case=direct_unicode outcome={direct_outcome.code.value} matched={str(matched).lower()} actual_units={text_length}",
        flush=True,
    )

    user32.SetFocus(password)
    sleep(0.05)
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

    user32.SetFocus(normal)
    destroyed_token = adapter.capture()
    user32.DestroyWindow(window)
    destroyed_result = adapter.assess(destroyed_token)
    print(f"RESULT case=destroyed_target outcome={destroyed_result.code.value}", flush=True)
    return 0


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
