import unittest
from unittest.mock import MagicMock, patch

from insertion_spike.contracts import OutcomeCode
from insertion_spike.windows_target import (
    CtypesWindowsTargetApi,
    WindowsIdentity,
    WindowsTargetAdapter,
)


def identity(
    *,
    window: int = 10,
    process: int = 20,
    thread: int = 30,
    control: int = 40,
    automation: tuple[int, ...] | None = (1, 2),
    process_marker: int = 50,
) -> WindowsIdentity:
    return WindowsIdentity(window, process, thread, control, automation, process_marker)


class FakeTargetApi:
    def __init__(self) -> None:
        self.current: WindowsIdentity | None = identity()
        self.window_exists = True
        self.classic_password: bool | None = False
        self.automation_password: bool | None = False
        self.higher_integrity: bool | None = False

    def capture_identity(self) -> WindowsIdentity | None:
        return self.current

    def is_window(self, captured: WindowsIdentity) -> bool:
        return self.window_exists

    def classic_password_state(self, current: WindowsIdentity) -> bool | None:
        return self.classic_password

    def automation_password_state(self, current: WindowsIdentity) -> bool | None:
        return self.automation_password

    def is_higher_integrity(self, current: WindowsIdentity) -> bool | None:
        return self.higher_integrity


class WindowsTargetAdapterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.api = FakeTargetApi()
        self.adapter = WindowsTargetAdapter(self.api)
        self.token = self.adapter.capture()

    def test_same_unprotected_target_is_safe(self) -> None:
        self.assertTrue(self.adapter.assess(self.token).is_safe)

    def test_other_window_is_changed(self) -> None:
        self.api.current = identity(window=11)

        self.assertEqual(OutcomeCode.TARGET_CHANGED, self.adapter.assess(self.token).code)

    def test_other_control_in_same_window_is_changed(self) -> None:
        self.api.current = identity(control=41)

        self.assertEqual(OutcomeCode.TARGET_CHANGED, self.adapter.assess(self.token).code)

    def test_changed_automation_identity_is_changed(self) -> None:
        self.api.current = identity(automation=(1, 3))

        self.assertEqual(OutcomeCode.TARGET_CHANGED, self.adapter.assess(self.token).code)

    def test_reused_process_id_with_new_process_marker_is_changed(self) -> None:
        self.api.current = identity(process_marker=51)

        self.assertEqual(OutcomeCode.TARGET_CHANGED, self.adapter.assess(self.token).code)

    def test_destroyed_handle_is_unavailable(self) -> None:
        self.api.window_exists = False

        self.assertEqual(OutcomeCode.TARGET_UNAVAILABLE, self.adapter.assess(self.token).code)

    def test_classic_and_browser_password_are_protected(self) -> None:
        for source in ("classic", "automation"):
            with self.subTest(source=source):
                api = FakeTargetApi()
                api.classic_password = source == "classic"
                api.automation_password = source == "automation"
                adapter = WindowsTargetAdapter(api)

                result = adapter.assess(adapter.capture())

                self.assertEqual(OutcomeCode.TARGET_PROTECTED, result.code)

    def test_unavailable_protection_probes_fail_closed(self) -> None:
        self.api.classic_password = None
        self.api.automation_password = None

        self.assertEqual(OutcomeCode.TARGET_UNAVAILABLE, self.adapter.assess(self.token).code)

    def test_elevated_process_is_rejected(self) -> None:
        self.api.higher_integrity = True

        self.assertEqual(OutcomeCode.TARGET_ELEVATED, self.adapter.assess(self.token).code)

    def test_unknown_integrity_fails_closed(self) -> None:
        self.api.higher_integrity = None

        self.assertEqual(OutcomeCode.TARGET_UNAVAILABLE, self.adapter.assess(self.token).code)

    def test_classic_style_read_error_fails_closed(self) -> None:
        user32 = MagicMock()
        user32.GetClassNameW.side_effect = lambda _, buffer, __: setattr(
            buffer, "value", "Edit"
        ) or 1
        user32.GetWindowLongW.return_value = 0
        api = object.__new__(CtypesWindowsTargetApi)
        api._user32 = user32

        with patch("insertion_spike.windows_target.ctypes.get_last_error", return_value=5):
            result = api.classic_password_state(identity())

        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
