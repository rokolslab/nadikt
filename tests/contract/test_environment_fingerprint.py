from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from benchmarks.asr.environment_fingerprint import build_environment_fingerprint


class EnvironmentFingerprintTest(unittest.TestCase):
    def test_fingerprint_contains_only_allowlisted_environment_fields(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            lock = Path(temp_dir) / "base.lock.txt"
            lock.write_text("nadikt-benchmark-base==0\n", encoding="utf-8")

            profile = build_environment_fingerprint(lock_files=[lock], package_names=["not-a-real-package-for-nadikt"])

        data = profile.to_json()
        rendered = json.dumps(data, ensure_ascii=False)
        self.assertIn("base.lock.txt", data["lock_digests"])
        self.assertEqual("not-installed", data["package_versions"]["not-a-real-package-for-nadikt"])
        self.assertNotIn(str(ROOT), rendered)
        self.assertNotIn("argv", rendered)
        self.assertNotIn("hostname", rendered.lower())
        self.assertNotIn("username", rendered.lower())
        self.assertNotIn("environment", rendered.lower())

    def test_inference_defaults_are_concrete_numbers(self) -> None:
        profile = build_environment_fingerprint(cpu_threads=4, openmp_num_threads=4, blas_num_threads=1)
        defaults = profile.to_json()["inference_defaults"]

        self.assertEqual(4, defaults["cpu_threads"])
        self.assertEqual(4, defaults["openmp_num_threads"])
        self.assertEqual(1, defaults["blas_num_threads"])


if __name__ == "__main__":
    unittest.main()
