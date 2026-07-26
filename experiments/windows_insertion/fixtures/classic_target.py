"""Controlled native EDIT and ES_PASSWORD fixture for manual probing."""

from __future__ import annotations

import ctypes
from ctypes import wintypes
import os


CLASS_NAME = "NadiktInsertionSpikeFixture"
WS_OVERLAPPEDWINDOW = 0x00CF0000
WS_VISIBLE = 0x10000000
WS_CHILD = 0x40000000
WS_BORDER = 0x00800000
ES_AUTOHSCROLL = 0x0080
ES_PASSWORD = 0x0020
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


def create_fixture() -> wintypes.HWND:
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
        WS_CHILD | WS_VISIBLE | WS_BORDER | ES_AUTOHSCROLL,
        24,
        35,
        460,
        32,
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
    return window


def main() -> int:
    create_fixture()
    print("READY case=classic_target", flush=True)
    message = wintypes.MSG()
    while user32.GetMessageW(ctypes.byref(message), None, 0, 0) > 0:
        user32.TranslateMessage(ctypes.byref(message))
        user32.DispatchMessageW(ctypes.byref(message))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
