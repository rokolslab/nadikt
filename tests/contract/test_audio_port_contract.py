from __future__ import annotations

import unittest
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parents[2] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from nadikt.domain.ports.asr import AsrSegmentInput
from nadikt.domain.ports.audio import AudioCaptureOptions, AudioCaptureResult, AudioDeviceDescriptor, AudioLevelStatus


class AudioPortContractTest(unittest.TestCase):
    def test_audio_dto_repr_redacts_local_path_and_device_name(self) -> None:
        segment = AsrSegmentInput("sample", 0, Path("/private/user/audio.wav"), 0.0, 1.0, "ru", "bounded-one-shot.v1")
        result = AudioCaptureResult(
            segment=segment,
            device=AudioDeviceDescriptor("opaque-device", "mono-input", True),
            level_status=AudioLevelStatus.NORMAL,
            duration_seconds=1.0,
            sample_rate_hz=16000,
            channel_count=1,
        )

        rendered = repr(result)

        self.assertNotIn("/private/user/audio.wav", rendered)
        self.assertNotIn("Realtek", rendered)
        self.assertIn("bounded-one-shot", repr(AudioCaptureOptions(1.0, 16000)))


if __name__ == "__main__":
    unittest.main()
