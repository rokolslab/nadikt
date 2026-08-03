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


if __name__ == "__main__":
    unittest.main()
