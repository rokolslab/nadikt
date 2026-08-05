from __future__ import annotations

import tempfile
import unittest
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parents[2] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from nadikt.application.services import DictationPipelineService, DictationRunOptions, TextInsertionResult
from nadikt.domain.ports.asr import AsrBackend, AsrCapabilities, AsrModelMetadata, AsrSegmentInput, AsrSegmentTranscript
from nadikt.domain.ports.audio import AudioCaptureOptions, AudioCaptureResult, AudioDeviceDescriptor, AudioLevelStatus


class DictationPipelineTest(unittest.TestCase):
    def test_pipeline_orders_capture_asr_normalize_insert(self) -> None:
        events: list[str] = []
        with tempfile.NamedTemporaryFile(suffix=".wav") as audio:
            pipeline = DictationPipelineService(
                FakeAudio(events, Path(audio.name)),
                FakeAsr(events),
                FakeNormalizer(events),
                FakeInsertion(events, success=True),
            )

            outcome = pipeline.run_once(DictationRunOptions(_capture_options(), cleanup_audio=False))

        self.assertEqual(["capture", "asr", "normalize", "insert"], events)
        self.assertEqual("completed", outcome.status.value)
        self.assertFalse(outcome.retained_result)

    def test_pipeline_retains_result_after_insertion_failure(self) -> None:
        events: list[str] = []
        with tempfile.NamedTemporaryFile(suffix=".wav") as audio:
            pipeline = DictationPipelineService(
                FakeAudio(events, Path(audio.name)),
                FakeAsr(events),
                FakeNormalizer(events),
                FakeInsertion(events, success=False),
            )

            outcome = pipeline.run_once(DictationRunOptions(_capture_options(), cleanup_audio=False))

        self.assertEqual("failed", outcome.status.value)
        self.assertTrue(outcome.retained_result)
        self.assertGreater(outcome.retained_text_chars, 0)


class FakeAudio:
    def __init__(self, events: list[str], audio_path: Path) -> None:
        self._events = events
        self._audio_path = audio_path

    def list_input_devices(self) -> tuple[AudioDeviceDescriptor, ...]:
        return ()

    def capture_once(self, options: AudioCaptureOptions) -> AudioCaptureResult:
        self._events.append("capture")
        return AudioCaptureResult(
            segment=AsrSegmentInput("sample", 0, self._audio_path, 0.0, 1.0, options.language_profile, options.segmentation_policy_id),
            device=AudioDeviceDescriptor("device-hash", "mono-input", True),
            level_status=AudioLevelStatus.NORMAL,
            duration_seconds=1.0,
            sample_rate_hz=options.sample_rate_hz,
            channel_count=options.channel_count,
        )

    def cancel(self) -> None:
        return None

    def cleanup(self, result: AudioCaptureResult) -> None:
        return None


class FakeAsr:
    def __init__(self, events: list[str]) -> None:
        self._events = events

    def metadata(self) -> AsrModelMetadata:
        return AsrModelMetadata("pkg", "candidate", AsrBackend.FASTER_WHISPER, "model", "rev", "backend", "license", AsrCapabilities(("ru",), 30.0, True, False))

    def load(self, options: object) -> None:
        return None

    def is_ready(self) -> bool:
        return True

    def warm_up(self, segment: AsrSegmentInput, observer: object | None = None) -> None:
        return None

    def transcribe_segment(self, segment: AsrSegmentInput, observer: object | None = None) -> AsrSegmentTranscript:
        self._events.append("asr")
        return AsrSegmentTranscript(segment.segment_id, " SECRET_TRANSCRIPT ", 0.0, 1.0)

    def cancel(self) -> None:
        return None

    def close(self) -> None:
        return None


class FakeNormalizer:
    def __init__(self, events: list[str]) -> None:
        self._events = events

    def normalize(self, text: str) -> str:
        self._events.append("normalize")
        return text.strip()


class FakeInsertion:
    def __init__(self, events: list[str], *, success: bool) -> None:
        self._events = events
        self._success = success

    def insert_text(self, text: str) -> TextInsertionResult:
        self._events.append("insert")
        return TextInsertionResult(self._success, "success" if self._success else "target_changed", retained_result=not self._success)


def _capture_options() -> AudioCaptureOptions:
    return AudioCaptureOptions(max_duration_seconds=1.0, sample_rate_hz=16000)


if __name__ == "__main__":
    unittest.main()
