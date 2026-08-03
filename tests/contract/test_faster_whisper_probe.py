from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from benchmarks.asr.manifests import ModelPackageManifest
from nadikt.infrastructure.asr.faster_whisper import FasterWhisperLocalProbe


class FasterWhisperProbeTest(unittest.TestCase):
    def test_load_uses_local_cpu_int8_and_consumes_segments_generator(self) -> None:
        created: dict[str, object] = {}
        consumed: list[str] = []

        class FakeWhisperModel:
            def __init__(self, model_path: str, *, device: str, compute_type: str) -> None:
                created["model_path"] = model_path
                created["device"] = device
                created["compute_type"] = compute_type

            def transcribe(self, audio_path: str, *, beam_size: int) -> tuple[object, object]:
                created["audio_path"] = audio_path
                created["beam_size"] = beam_size

                def segments() -> object:
                    for index in range(2):
                        consumed.append(f"segment-{index}")
                        yield object()

                return segments(), object()

            def close(self) -> None:
                created["closed"] = True

        with tempfile.TemporaryDirectory() as temp_dir:
            package_dir = Path(temp_dir) / "ct2-package"
            package_dir.mkdir()
            audio = Path(temp_dir) / "sample.wav"
            audio.write_bytes(b"not-real-audio")
            probe = FasterWhisperLocalProbe(FakeWhisperModel)

            load = probe.load(package_dir, _manifest())
            transcribe = probe.transcribe(audio, "controlled-audio", beam_size=7)
            close = probe.close()

        self.assertEqual("success", load.outcome)
        self.assertEqual("success", transcribe.outcome)
        self.assertEqual("success", close.outcome)
        self.assertEqual("cpu", created["device"])
        self.assertEqual("int8", created["compute_type"])
        self.assertEqual(7, created["beam_size"])
        self.assertEqual(["segment-0", "segment-1"], consumed)
        self.assertTrue(created["closed"])

    def test_missing_dependency_is_controlled_outcome(self) -> None:
        probe = FasterWhisperLocalProbe()

        with tempfile.TemporaryDirectory() as temp_dir:
            package_dir = Path(temp_dir) / "ct2-package"
            package_dir.mkdir()
            with patch("nadikt.infrastructure.asr.faster_whisper.importlib.import_module", side_effect=ImportError("missing")):
                result = probe.load(package_dir, _manifest())

        self.assertEqual("backend_unavailable", result.outcome)

    def test_incompatible_dependency_is_controlled_outcome(self) -> None:
        probe = FasterWhisperLocalProbe()

        with tempfile.TemporaryDirectory() as temp_dir:
            package_dir = Path(temp_dir) / "ct2-package"
            package_dir.mkdir()
            with patch("nadikt.infrastructure.asr.faster_whisper.importlib.import_module", return_value=object()):
                result = probe.load(package_dir, _manifest())

        self.assertEqual("backend_unavailable", result.outcome)

    def test_hub_identifier_is_rejected(self) -> None:
        probe = FasterWhisperLocalProbe(lambda *args, **kwargs: object())

        result = probe.load(Path("small"), _manifest())

        self.assertEqual("hub_identifier_rejected", result.outcome)

    def test_transcribe_exception_is_safe_outcome(self) -> None:
        class FailingWhisperModel:
            def __init__(self, *_args: object, **_kwargs: object) -> None:
                pass

            def transcribe(self, *_args: object, **_kwargs: object) -> tuple[object, object]:
                raise RuntimeError("sensitive local path must not be returned")

        with tempfile.TemporaryDirectory() as temp_dir:
            package_dir = Path(temp_dir) / "ct2-package"
            package_dir.mkdir()
            audio = Path(temp_dir) / "secret-canary.wav"
            audio.write_bytes(b"not-real-audio")
            probe = FasterWhisperLocalProbe(FailingWhisperModel)
            probe.load(package_dir, _manifest())
            result = probe.transcribe(audio, "safe-label")

        self.assertEqual("transcribe_failed", result.outcome)
        self.assertNotIn("secret-canary", repr(result))


def _manifest() -> ModelPackageManifest:
    return ModelPackageManifest(
        package_id="fw-local",
        candidate_id="faster-whisper-small-int8",
        backend="faster-whisper",
        model_name="Whisper small CTranslate2 INT8",
        model_revision="test",
        package_path=Path("local/fw"),
        manifest_relative_path="manifest.json",
        manifest_sha256="0" * 64,
        rights_statuses={"local_evaluation": {"status": "approved", "review_record_id": "test"}},
        capabilities={},
        inference_defaults={"beam_size": 5},
        critical_files=(),
    )


if __name__ == "__main__":
    unittest.main()
