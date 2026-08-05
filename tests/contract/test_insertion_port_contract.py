from __future__ import annotations

import unittest
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parents[2] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from nadikt.domain.ports.insertion import (
    ClipboardSnapshot,
    ClipboardTransactionResult,
    ClipboardOutcomeCode,
    InputDispatchRequest,
    TargetCaptureResult,
    TargetSafetyOutcome,
    TargetToken,
)
from nadikt.infrastructure.platform.windows.uia import UiaElementProbe, UiaTargetSafetyProvider


class InsertionPortContractTest(unittest.TestCase):
    def test_insertion_dto_repr_redacts_text_and_target_token(self) -> None:
        token = TargetToken("SECRET_TOKEN")
        request = InputDispatchRequest(token, "SECRET_CLIPBOARD_TEXT")
        capture = TargetCaptureResult(token, TargetSafetyOutcome.SAFE, "uia", True, True)
        transaction = ClipboardTransactionResult(ClipboardOutcomeCode.PREPARED, ClipboardSnapshot("snapshot", 2))

        rendered = " ".join([repr(token), repr(request), repr(capture), repr(transaction)])

        self.assertNotIn("SECRET_TOKEN", rendered)
        self.assertNotIn("SECRET_CLIPBOARD_TEXT", rendered)
        self.assertNotIn("HWND", rendered)
        self.assertNotIn("PID", rendered)

    def test_uia_provider_fails_closed_for_stale_changed_and_password_targets(self) -> None:
        facade = CyclingFacade(
            [
                UiaElementProbe((1, 2), "uia", True, False, True, True, False, "proc-a"),
                UiaElementProbe((9, 9), "uia", True, False, True, True, False, "proc-a"),
            ]
        )
        provider = UiaTargetSafetyProvider(facade)
        captured = provider.capture_current_target()
        changed = provider.revalidate_target(captured.token)
        stale = provider.revalidate_target(TargetToken("missing"))

        self.assertEqual(TargetSafetyOutcome.TARGET_CHANGED, changed.outcome)
        self.assertEqual(TargetSafetyOutcome.STALE_TOKEN, stale.outcome)

        password_provider = UiaTargetSafetyProvider(
            CyclingFacade([UiaElementProbe((1,), "uia", True, True, True, True, False, "proc-a")])
        )
        protected = password_provider.capture_current_target()
        self.assertEqual(TargetSafetyOutcome.TARGET_PROTECTED, protected.outcome)


class CyclingFacade:
    def __init__(self, probes: list[UiaElementProbe]) -> None:
        self._probes = probes
        self._index = 0

    def focused_element_probe(self) -> UiaElementProbe:
        probe = self._probes[min(self._index, len(self._probes) - 1)]
        self._index += 1
        return probe


if __name__ == "__main__":
    unittest.main()
