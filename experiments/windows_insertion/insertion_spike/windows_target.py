"""Windows target identity and safety probes behind an injected API facade."""

from __future__ import annotations

from dataclasses import dataclass
import ctypes
from ctypes import wintypes
import logging
import os
from typing import Protocol

from .contracts import OutcomeCode, TargetAssessment, TargetToken, get_logger


ES_PASSWORD = 0x0020
GA_ROOT = 2
GWL_STYLE = -16
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
TOKEN_QUERY = 0x0008
TOKEN_INTEGRITY_LEVEL = 25
SECURITY_MANDATORY_MEDIUM_RID = 0x00002000


class TargetCaptureError(RuntimeError):
    """Raised when a target cannot be captured without ambiguity."""


@dataclass(frozen=True, repr=False)
class WindowsIdentity:
    top_window: int
    process_id: int
    thread_id: int
    focused_control: int
    automation_id: tuple[int, ...] | None = None

    def __repr__(self) -> str:
        return "WindowsIdentity(<opaque>)"


class WindowsTargetApi(Protocol):
    def capture_identity(self) -> WindowsIdentity | None: ...

    def is_window(self, identity: WindowsIdentity) -> bool: ...

    def classic_password_state(self, identity: WindowsIdentity) -> bool | None: ...

    def automation_password_state(self, identity: WindowsIdentity) -> bool | None: ...

    def is_higher_integrity(self, identity: WindowsIdentity) -> bool | None: ...


class WindowsTargetAdapter:
    def __init__(
        self,
        api: WindowsTargetApi,
        logger: logging.Logger | None = None,
    ) -> None:
        self._api = api
        self._logger = logger or get_logger()

    def capture(self) -> TargetToken:
        self._logger.debug("target phase=capture")
        identity = self._api.capture_identity()
        if identity is None:
            self._logger.warning("target capture_available=false")
            raise TargetCaptureError("target_unavailable")
        self._logger.debug(
            "target captured=true automation_identity=%s",
            identity.automation_id is not None,
        )
        return TargetToken(identity)

    def assess(self, captured_target: TargetToken) -> TargetAssessment:
        self._logger.debug("target phase=revalidate")
        captured = captured_target.identity
        if not isinstance(captured, WindowsIdentity):
            self._logger.warning("target token_valid=false")
            return TargetAssessment(OutcomeCode.TARGET_UNAVAILABLE)
        if not self._api.is_window(captured):
            self._logger.warning("target exists=false")
            return TargetAssessment(OutcomeCode.TARGET_UNAVAILABLE)

        current = self._api.capture_identity()
        if current is None:
            self._logger.warning("target current_available=false")
            return TargetAssessment(OutcomeCode.TARGET_UNAVAILABLE)
        if not self._same_identity(captured, current):
            self._logger.warning("target identity_changed=true")
            return TargetAssessment(OutcomeCode.TARGET_CHANGED)

        elevated = self._api.is_higher_integrity(current)
        if elevated is None:
            self._logger.warning("target integrity_available=false")
            return TargetAssessment(OutcomeCode.TARGET_UNAVAILABLE)
        if elevated:
            self._logger.warning("target elevated=true")
            return TargetAssessment(OutcomeCode.TARGET_ELEVATED)

        classic = self._api.classic_password_state(current)
        automation = self._api.automation_password_state(current)
        self._logger.debug(
            "target protection classic_known=%s automation_known=%s",
            classic is not None,
            automation is not None,
        )
        if classic is True or automation is True:
            return TargetAssessment(OutcomeCode.TARGET_PROTECTED)
        if classic is None and automation is None:
            self._logger.warning("target protection_available=false")
            return TargetAssessment(OutcomeCode.TARGET_UNAVAILABLE)
        return TargetAssessment()

    @staticmethod
    def _same_identity(captured: WindowsIdentity, current: WindowsIdentity) -> bool:
        if (
            captured.top_window,
            captured.process_id,
            captured.thread_id,
            captured.focused_control,
        ) != (
            current.top_window,
            current.process_id,
            current.thread_id,
            current.focused_control,
        ):
            return False
        if captured.automation_id is not None:
            return captured.automation_id == current.automation_id
        return True


class CtypesWindowsTargetApi:
    """Minimal standard-library Win32 facade; UIA is intentionally unsupported."""

    def __init__(self) -> None:
        if os.name != "nt":
            raise OSError("windows_required")
        self._user32 = ctypes.WinDLL("user32", use_last_error=True)
        self._kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        self._advapi32 = ctypes.WinDLL("advapi32", use_last_error=True)

    def capture_identity(self) -> WindowsIdentity | None:
        foreground = self._user32.GetForegroundWindow()
        if not foreground:
            return None
        process_id = wintypes.DWORD()
        thread_id = self._user32.GetWindowThreadProcessId(
            foreground, ctypes.byref(process_id)
        )
        if not thread_id:
            return None
        info = GUITHREADINFO(cbSize=ctypes.sizeof(GUITHREADINFO))
        if not self._user32.GetGUIThreadInfo(thread_id, ctypes.byref(info)):
            return None
        focused = info.hwndFocus or foreground
        top_window = self._user32.GetAncestor(foreground, GA_ROOT) or foreground
        return WindowsIdentity(
            int(top_window),
            int(process_id.value),
            int(thread_id),
            int(focused),
        )

    def is_window(self, identity: WindowsIdentity) -> bool:
        return bool(self._user32.IsWindow(identity.top_window))

    def classic_password_state(self, identity: WindowsIdentity) -> bool | None:
        class_name = ctypes.create_unicode_buffer(256)
        if not self._user32.GetClassNameW(
            identity.focused_control, class_name, len(class_name)
        ):
            return None
        if class_name.value.casefold() != "edit":
            return None
        style = self._user32.GetWindowLongW(identity.focused_control, GWL_STYLE)
        return bool(style & ES_PASSWORD)

    def automation_password_state(self, identity: WindowsIdentity) -> bool | None:
        # A tested UI Automation provider is a spike decision, not an implicit dependency.
        return None

    def is_higher_integrity(self, identity: WindowsIdentity) -> bool | None:
        target_rid = self._integrity_rid_for_process(identity.process_id)
        current_rid = self._integrity_rid_for_process(self._kernel32.GetCurrentProcessId())
        if target_rid is None or current_rid is None:
            return None
        return target_rid > current_rid

    def _integrity_rid_for_process(self, process_id: int) -> int | None:
        process = self._kernel32.OpenProcess(
            PROCESS_QUERY_LIMITED_INFORMATION, False, process_id
        )
        if not process:
            return None
        token = wintypes.HANDLE()
        try:
            if not self._advapi32.OpenProcessToken(process, TOKEN_QUERY, ctypes.byref(token)):
                return None
            required = wintypes.DWORD()
            self._advapi32.GetTokenInformation(
                token, TOKEN_INTEGRITY_LEVEL, None, 0, ctypes.byref(required)
            )
            if not required.value:
                return None
            buffer = ctypes.create_string_buffer(required.value)
            if not self._advapi32.GetTokenInformation(
                token,
                TOKEN_INTEGRITY_LEVEL,
                buffer,
                required,
                ctypes.byref(required),
            ):
                return None
            label = ctypes.cast(buffer, ctypes.POINTER(TOKEN_MANDATORY_LABEL)).contents
            count = self._advapi32.GetSidSubAuthorityCount(label.Label.Sid)
            if not count:
                return None
            sub_authority_count = ctypes.cast(count, ctypes.POINTER(ctypes.c_ubyte)).contents.value
            rid = self._advapi32.GetSidSubAuthority(
                label.Label.Sid, sub_authority_count - 1
            )
            if not rid:
                return None
            return ctypes.cast(rid, ctypes.POINTER(wintypes.DWORD)).contents.value
        finally:
            if token:
                self._kernel32.CloseHandle(token)
            self._kernel32.CloseHandle(process)


class GUITHREADINFO(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("flags", wintypes.DWORD),
        ("hwndActive", wintypes.HWND),
        ("hwndFocus", wintypes.HWND),
        ("hwndCapture", wintypes.HWND),
        ("hwndMenuOwner", wintypes.HWND),
        ("hwndMoveSize", wintypes.HWND),
        ("hwndCaret", wintypes.HWND),
        ("rcCaret", wintypes.RECT),
    ]


class SID_AND_ATTRIBUTES(ctypes.Structure):
    _fields_ = [("Sid", wintypes.LPVOID), ("Attributes", wintypes.DWORD)]


class TOKEN_MANDATORY_LABEL(ctypes.Structure):
    _fields_ = [("Label", SID_AND_ATTRIBUTES)]
