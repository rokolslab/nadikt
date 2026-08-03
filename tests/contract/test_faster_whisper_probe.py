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

from nadikt.domain.ports.asr import AsrLoadOptions, AsrSegmentInput, AsrTimingEvent
from nadikt.infrastructure.asr.faster_whisper import FasterWhisperAsrEngine


class FasterWhisperProbeTest(unittest.TestCase):
    def test_load_uses_local_cpu_int8_and_consumes_segments_generator(self) -> None:
        created: dict[str, object] = {}
        consumed: list[str] = []
        events: list[AsrTimingEvent] = []

        class FakeWhisperModel:
            def __init__(self, model_path: str, *, device: str, compute_type: str) -> None:
                created["model_path"] = model_path
                created["device"] = device
                created["compute_type"] = compute_type

            def transcribe(self, audio_path: str, *, beam_size: int, **_kwargs: object) -> tuple[object, object]:
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
            engine = FasterWhisperAsrEngine(_metadata(), FakeWhisperModel)
            engine.load(AsrLoadOptions(package_dir, {"beam_size": 7}))
            transcript = engine.transcribe_segment(_segment(audio), _Observer(events))
            engine.close()

        self.assertEqual("", transcript.text)
        self.assertEqual("cpu", created["device"])
        self.assertEqual("int8", created["compute_type"])
        self.assertEqual(7, created["beam_size"])
        self.assertEqual(["segment-0", "segment-1"], consumed)
        self.assertTrue(created["closed"])
        self.assertEqual(["first_result", "transcribe_done"], [event.phase for event in events])

    def test_missing_dependency_is_controlled_outcome(self) -> None:
        engine = FasterWhisperAsrEngine(_metadata())

        with tempfile.TemporaryDirectory() as temp_dir:
            package_dir = Path(temp_dir) / "ct2-package"
            package_dir.mkdir()
            with patch("nadikt.infrastructure.asr.faster_whisper.importlib.import_module", side_effect=ImportError("missing")):
                with self.assertRaisesRegex(Exception, "incompatible_backend"):
                    engine.load(AsrLoadOptions(package_dir, {}))

    def test_incompatible_dependency_is_controlled_outcome(self) -> None:
        engine = FasterWhisperAsrEngine(_metadata())

        with tempfile.TemporaryDirectory() as temp_dir:
            package_dir = Path(temp_dir) / "ct2-package"
            package_dir.mkdir()
            with patch("nadikt.infrastructure.asr.faster_whisper.importlib.import_module", return_value=object()):
                with self.assertRaisesRegex(Exception, "incompatible_backend"):
                    engine.load(AsrLoadOptions(package_dir, {}))

    def test_hub_identifier_is_rejected(self) -> None:
        engine = FasterWhisperAsrEngine(_metadata(), lambda *args, **kwargs: object())

        with self.assertRaisesRegex(Exception, "invalid_package_path"):
            engine.load(AsrLoadOptions(Path("small"), {}))

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
            engine = FasterWhisperAsrEngine(_metadata(), FailingWhisperModel)
            engine.load(AsrLoadOptions(package_dir, {}))
            with self.assertRaisesRegex(Exception, "transcribe_failed") as captured:
                engine.transcribe_segment(_segment(audio))

        self.assertNotIn("secret-canary", repr(captured.exception))


class _Observer:
    def __init__(self, events: list[AsrTimingEvent]) -> None:
        self.events = events

    def record(self, event: AsrTimingEvent) -> None:
        self.events.append(event)


def _metadata() -> object:
    from nadikt.domain.ports.asr import AsrBackend, AsrCapabilities, AsrModelMetadata

    return AsrModelMetadata(
        package_id="fw-local",
        candidate_id="faster-whisper-small-int8",
        backend=AsrBackend.FASTER_WHISPER,
        model_name="Whisper small CTranslate2 INT8",
        model_revision="test",
        backend_version="test",
        license_marker="approved",
        capabilities=AsrCapabilities(languages=("ru",), max_segment_seconds=25.0, punctuation=True, streaming=False),
    )


def _segment(audio: Path) -> AsrSegmentInput:
    return AsrSegmentInput("sample", 0, audio, 0.0, 1.0, "ru", "seg-v1")


if __name__ == "__main__":
    unittest.main()
