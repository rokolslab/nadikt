from __future__ import annotations

import sys
import unittest
from dataclasses import dataclass
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch

SRC = Path(__file__).resolve().parents[2] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from nadikt.application.services import TextInsertionResult
from nadikt.presentation.cli import windows_dictation_slice


class WindowsDictationSliceCliTest(unittest.TestCase):
    def test_cli_closes_asr_engine_when_pipeline_raises_after_load(self) -> None:
        engine = FakeEngine()
        components = FakeComponents(FakeInsertionService(), FakeFailingPipeline(), engine)

        with redirect_stdout(StringIO()):
            with patch.object(windows_dictation_slice, "validate_model_package_binding", return_value=object()):
                with patch.object(windows_dictation_slice, "build_windows_dictation_slice", return_value=components):
                    exit_code = windows_dictation_slice.main(
                        [
                            "--inventory",
                            "private-inventory.json",
                            "--package-id",
                            "pkg",
                            "--candidate-id",
                            "candidate",
                            "--backend",
                            "faster-whisper",
                            "--warm-up-audio-file",
                            "private-warmup.wav",
                        ]
                    )

        self.assertEqual(1, exit_code)
        self.assertEqual(1, engine.close_count)


@dataclass(frozen=True)
class FakeComponents:
    insertion_service: "FakeInsertionService"
    pipeline: "FakeFailingPipeline"
    asr_engine: "FakeEngine"


class FakeInsertionService:
    has_pending_clipboard_restore = False

    def capture_target(self) -> TextInsertionResult:
        return TextInsertionResult(True, "safe")


class FakeFailingPipeline:
    def run_once(self, options: object) -> object:
        raise RuntimeError("synthetic pipeline failure")


class FakeEngine:
    def __init__(self) -> None:
        self.close_count = 0

    def close(self) -> None:
        self.close_count += 1


if __name__ == "__main__":
    unittest.main()
