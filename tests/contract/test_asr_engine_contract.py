from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from nadikt.domain.ports.asr import (
    AsrBackend,
    AsrCapabilities,
    AsrLoadOptions,
    AsrModelMetadata,
    AsrFailure,
    AsrFailureCode,
    AsrInferenceObserver,
    AsrSegmentInput,
    AsrTimingEvent,
    safe_timing_log_context,
)


class AsrEngineContractTest(unittest.TestCase):
    def test_warmup_observer_event_is_safe(self) -> None:
        event = AsrTimingEvent(
            phase="warm_up_done",
            duration_ms=12.5,
            package_id="safe-package",
            segment_id=0,
            outcome="success",
        )

        context = safe_timing_log_context(event)
        rendered = repr(context)

        self.assertEqual("warm_up_done", context["phase"])
        self.assertNotIn("transcript", rendered)
        self.assertNotIn("/private/audio.wav", rendered)

    def test_typed_failure_repr_does_not_include_sdk_message(self) -> None:
        failure = AsrFailure(AsrFailureCode.WARM_UP_FAILED, phase="warm_up", recoverable=True, retryable=False)

        rendered = repr(failure)

        self.assertIn("warm_up_failed", rendered)
        self.assertNotIn("Traceback", rendered)
        self.assertNotIn("RuntimeError", rendered)

    def test_segment_input_remains_only_audio_bearing_input_type(self) -> None:
        segment = AsrSegmentInput(
            sample_id="warmup_001",
            segment_id=0,
            audio_path=Path("/private/audio.wav"),
            start_seconds=0.0,
            end_seconds=1.0,
            language_profile="ru",
            segmentation_policy_id="seg-25s-no-overlap-v1",
        )

        self.assertNotIn("/private/audio.wav", repr(segment))


class RecordingObserver:
    def __init__(self) -> None:
        self.events: list[AsrTimingEvent] = []

    def record(self, event: AsrTimingEvent) -> None:
        self.events.append(event)


def _accepts_observer(_observer: AsrInferenceObserver) -> None:
    return None


class ObserverConformanceTest(unittest.TestCase):
    def test_observer_protocol_accepts_recording_observer(self) -> None:
        observer = RecordingObserver()
        event = AsrTimingEvent("load_done", 1.0, "safe-package")

        _accepts_observer(observer)
        observer.record(event)

        self.assertEqual([event], observer.events)


class ReusableAdapterConformanceTest(unittest.TestCase):
    def test_faster_whisper_adapter_conforms_to_asr_engine_shape(self) -> None:
        from nadikt.infrastructure.asr.faster_whisper import FasterWhisperAsrEngine

        class FakeWhisperModel:
            def __init__(self, *_args: object, **_kwargs: object) -> None:
                pass

            def transcribe(self, *_args: object, **_kwargs: object) -> tuple[object, object]:
                return iter(()), object()

        with __import__("tempfile").TemporaryDirectory() as temp_dir:
            package_dir = Path(temp_dir)
            audio = package_dir / "warmup.wav"
            audio.write_bytes(b"synthetic")
            engine = FasterWhisperAsrEngine(_metadata(AsrBackend.FASTER_WHISPER, "faster-whisper-small-int8"), FakeWhisperModel)

            engine.load(AsrLoadOptions(package_dir, {"beam_size": 5}))
            self.assertTrue(engine.is_ready())
            engine.warm_up(_segment(audio))
            result = engine.transcribe_segment(_segment(audio))
            engine.cancel()
            engine.close()
            engine.close()

        self.assertEqual(0, result.segment_id)

    def test_gigaam_adapter_conforms_to_asr_engine_shape(self) -> None:
        from nadikt.infrastructure.asr.gigaam import GigaAMAsrEngine

        class FakeModel:
            def transcribe(self, *_args: object) -> str:
                return "synthetic"

        module = __import__("types").SimpleNamespace(load_model=lambda *_args, **_kwargs: FakeModel())

        with __import__("tempfile").TemporaryDirectory() as temp_dir:
            package_dir = Path(temp_dir)
            (package_dir / "v3_e2e_ctc.ckpt").write_bytes(b"synthetic")
            (package_dir / "v3_e2e_ctc_tokenizer.model").write_bytes(b"synthetic")
            audio = package_dir / "warmup.wav"
            audio.write_bytes(b"synthetic")
            engine = GigaAMAsrEngine(_metadata(AsrBackend.GIGAAM, "gigaam-v3-e2e-ctc"), lambda: module)

            engine.load(AsrLoadOptions(package_dir, {"gigaam_model_name": "v3_e2e_ctc"}))
            self.assertTrue(engine.is_ready())
            engine.warm_up(_segment(audio))
            result = engine.transcribe_segment(_segment(audio))
            engine.cancel()
            engine.close()
            engine.close()

        self.assertEqual("synthetic", result.text)


def _metadata(backend: AsrBackend, candidate_id: str) -> AsrModelMetadata:
    return AsrModelMetadata(
        package_id="safe-package",
        candidate_id=candidate_id,
        backend=backend,
        model_name="Synthetic model",
        model_revision="test",
        backend_version="test",
        license_marker="approved",
        capabilities=AsrCapabilities(languages=("ru",), max_segment_seconds=25.0, punctuation=True, streaming=False),
    )


def _segment(audio: Path) -> AsrSegmentInput:
    return AsrSegmentInput("sample", 0, audio, 0.0, 1.0, "ru", "seg-v1")


if __name__ == "__main__":
    unittest.main()
