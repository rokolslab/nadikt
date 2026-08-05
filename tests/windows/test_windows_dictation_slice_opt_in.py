from __future__ import annotations

import os
import unittest


class WindowsDictationSliceOptInTest(unittest.TestCase):
    @unittest.skipUnless(os.environ.get("NADIKT_WINDOWS_SLICE_TESTS") == "1", "Windows slice real checks are opt-in")
    def test_required_real_asset_configuration_is_present_when_enabled(self) -> None:
        required = [
            "NADIKT_WINDOWS_SLICE_INVENTORY",
            "NADIKT_WINDOWS_SLICE_PACKAGE_ID",
            "NADIKT_WINDOWS_SLICE_CANDIDATE_ID",
            "NADIKT_WINDOWS_SLICE_BACKEND",
            "NADIKT_WINDOWS_SLICE_WARMUP_AUDIO",
        ]
        missing = [name for name in required if not os.environ.get(name)]
        self.assertFalse(missing, f"missing opt-in Windows slice config: {missing}")


if __name__ == "__main__":
    unittest.main()
