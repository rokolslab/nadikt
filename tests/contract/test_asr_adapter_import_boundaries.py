from __future__ import annotations

import sys
import unittest
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


class AsrAdapterImportBoundariesTest(unittest.TestCase):
    def test_infrastructure_asr_imports_without_optional_sdks(self) -> None:
        had_faster_whisper = "faster_whisper" in sys.modules
        had_gigaam = "gigaam" in sys.modules

        import nadikt.infrastructure.asr  # noqa: F401
        import nadikt.infrastructure.asr.faster_whisper  # noqa: F401
        import nadikt.infrastructure.asr.gigaam  # noqa: F401

        if not had_faster_whisper:
            self.assertNotIn("faster_whisper", sys.modules)
        if not had_gigaam:
            self.assertNotIn("gigaam", sys.modules)

    def test_domain_does_not_import_infrastructure(self) -> None:
        source = (SRC / "nadikt/domain/ports/asr.py").read_text(encoding="utf-8")

        self.assertNotIn("nadikt.infrastructure", source)
        self.assertNotIn("benchmarks.asr", source)
        self.assertNotIn("ProbePhaseResult", source)
        self.assertIsNone(re.search(r"^\s*(from|import)\s+faster_whisper", source, re.MULTILINE))
        self.assertIsNone(re.search(r"^\s*(from|import)\s+gigaam", source, re.MULTILINE))


if __name__ == "__main__":
    unittest.main()
