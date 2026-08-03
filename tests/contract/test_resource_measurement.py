from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from benchmarks.asr.measurement_backends.linux_proc import sample_process


class ResourceMeasurementTest(unittest.TestCase):
    def test_linux_proc_sampler_does_not_read_argv_or_environment(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            proc_root = Path(temp_dir)
            process = proc_root / str(os.getpid())
            process.mkdir()
            (process / "stat").write_text(" ".join(["1", "(python)", "R"] + ["0"] * 19 + ["12345"]), encoding="utf-8")
            (process / "statm").write_text("1 2 3", encoding="utf-8")
            (process / "cmdline").write_text("secret-argv", encoding="utf-8")
            (process / "environ").write_text("SECRET=1", encoding="utf-8")

            sample = sample_process(os.getpid(), proc_root=proc_root)
            rendered = repr(sample.to_json())

        self.assertIn("rss_kib", rendered)
        self.assertNotIn("secret-argv", rendered)
        self.assertNotIn("SECRET", rendered)


if __name__ == "__main__":
    unittest.main()
