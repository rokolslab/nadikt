from __future__ import annotations

import os
import unittest


class RealLocalAsrLoadTest(unittest.TestCase):
    def test_real_local_asr_load_requires_opt_in_assets(self) -> None:
        if os.environ.get("NADIKT_REAL_ASR_ASSETS") != "1":
            self.skipTest("real ASR assets are not enabled for this environment")


if __name__ == "__main__":
    unittest.main()
