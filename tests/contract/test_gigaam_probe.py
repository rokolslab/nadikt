from __future__ import annotations

import sys
import tempfile
import types
import unittest
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from nadikt.domain.ports.asr import AsrLoadOptions, AsrSegmentInput
from nadikt.infrastructure.asr.gigaam import GigaAMAsrEngine


class GigaAMProbeTest(unittest.TestCase):
    def test_missing_dependency_is_controlled_outcome(self) -> None:
        engine = GigaAMAsrEngine(_metadata(), lambda: (_ for _ in ()).throw(ImportError("missing")))

        with tempfile.TemporaryDirectory() as temp_dir:
            _write_required_files(Path(temp_dir))
            with self.assertRaisesRegex(Exception, "incompatible_backend"):
                engine.load(AsrLoadOptions(Path(temp_dir), {"gigaam_model_name": "v3_e2e_ctc"}))

    def test_missing_load_model_api_is_local_loading_unconfirmed(self) -> None:
        module = types.SimpleNamespace(load_model_from_package=lambda _path: object())
        engine = GigaAMAsrEngine(_metadata(), lambda: module)

        with tempfile.TemporaryDirectory() as temp_dir:
            _write_required_files(Path(temp_dir))
            with self.assertRaisesRegex(Exception, "incompatible_backend"):
                engine.load(AsrLoadOptions(Path(temp_dir), {"gigaam_model_name": "v3_e2e_ctc"}))

    def test_download_root_loader_can_transcribe_short_segment_and_close(self) -> None:
        events: list[tuple[str, object]] = []

        class FakeModel:
            def transcribe(self, audio_path: str) -> str:
                events.append(("transcribe", Path(audio_path).name))
                return "payload must not be logged"

            def close(self) -> None:
                events.append(("close", None))

        def load_model(model_name: str, **kwargs: object) -> FakeModel:
            events.append(("load", (model_name, kwargs["download_root"], kwargs["device"], kwargs["use_flash"], kwargs["fp16_encoder"])))
            return FakeModel()

        module = types.SimpleNamespace(load_model=load_model)
        engine = GigaAMAsrEngine(_metadata(), lambda: module)

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _write_required_files(root)
            audio = root / "sample.wav"
            audio.write_bytes(b"not-real-audio")
            engine.load(AsrLoadOptions(root, {"gigaam_model_name": "v3_e2e_ctc"}))
            transcript = engine.transcribe_segment(_segment(audio, duration=24.5))
            engine.close()

        self.assertEqual("payload must not be logged", transcript.text)
        self.assertEqual("load", events[0][0])
        self.assertEqual("v3_e2e_ctc", events[0][1][0])
        self.assertEqual("cpu", events[0][1][2])
        self.assertFalse(events[0][1][3])
        self.assertFalse(events[0][1][4])
        self.assertEqual([("transcribe", "sample.wav"), ("close", None)], events[1:])

    def test_incomplete_required_files_rejects_before_load_model(self) -> None:
        module = types.SimpleNamespace(load_model=lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("must not load")))
        engine = GigaAMAsrEngine(_metadata(), lambda: module)

        with tempfile.TemporaryDirectory() as temp_dir:
            (Path(temp_dir) / "v3_e2e_ctc.ckpt").write_bytes(b"synthetic")
            with self.assertRaisesRegex(Exception, "missing_critical_file"):
                engine.load(AsrLoadOptions(Path(temp_dir), {"gigaam_model_name": "v3_e2e_ctc"}))

    def test_segment_too_long_is_rejected_before_transcribe(self) -> None:
        class FakeModel:
            def transcribe(self, _audio_path: str) -> str:
                raise AssertionError("should not transcribe long segment")

        module = types.SimpleNamespace(load_model=lambda *_args, **_kwargs: FakeModel())
        engine = GigaAMAsrEngine(_metadata(), lambda: module)

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _write_required_files(root)
            audio = root / "sample.wav"
            audio.write_bytes(b"not-real-audio")
            engine.load(AsrLoadOptions(root, {"gigaam_model_name": "v3_e2e_ctc"}))
            with self.assertRaisesRegex(Exception, "segment_too_long"):
                engine.transcribe_segment(_segment(audio, duration=26.0))

    def test_transcribe_exception_is_safe_outcome(self) -> None:
        class FailingModel:
            def transcribe(self, _audio_path: str) -> str:
                raise RuntimeError("sensitive local path must not be returned")

        module = types.SimpleNamespace(load_model=lambda *_args, **_kwargs: FailingModel())
        engine = GigaAMAsrEngine(_metadata(), lambda: module)

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _write_required_files(root)
            audio = root / "secret-canary.wav"
            audio.write_bytes(b"not-real-audio")
            engine.load(AsrLoadOptions(root, {"gigaam_model_name": "v3_e2e_ctc"}))
            with self.assertRaisesRegex(Exception, "transcribe_failed") as captured:
                engine.transcribe_segment(_segment(audio, duration=1.0))

        self.assertNotIn("secret-canary", repr(captured.exception))

    def test_configured_ffmpeg_path_is_available_only_during_transcribe(self) -> None:
        observed: list[bool] = []
        original_path = os.environ.get("PATH", "")

        class FakeModel:
            def __init__(self, expected_dir: Path) -> None:
                self._expected_dir = str(expected_dir)

            def transcribe(self, _audio_path: str) -> str:
                observed.append(self._expected_dir in os.environ.get("PATH", "").split(os.pathsep))
                return "ok"

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _write_required_files(root)
            ffmpeg = root / "tools" / "ffmpeg"
            ffmpeg.parent.mkdir(parents=True)
            ffmpeg.write_bytes(b"synthetic")
            audio = root / "sample.wav"
            audio.write_bytes(b"not-real-audio")
            module = types.SimpleNamespace(load_model=lambda *_args, **_kwargs: FakeModel(ffmpeg.parent))
            engine = GigaAMAsrEngine(_metadata(), lambda: module)

            engine.load(AsrLoadOptions(root, {"gigaam_model_name": "v3_e2e_ctc", "ffmpeg_path": str(ffmpeg)}))
            transcript = engine.transcribe_segment(_segment(audio, duration=1.0))

        self.assertEqual("ok", transcript.text)
        self.assertEqual([True], observed)
        self.assertEqual(original_path, os.environ.get("PATH", ""))


def _metadata() -> object:
    from nadikt.domain.ports.asr import AsrBackend, AsrCapabilities, AsrModelMetadata

    return AsrModelMetadata(
        package_id="gigaam-local",
        candidate_id="gigaam-v3-e2e-ctc",
        backend=AsrBackend.GIGAAM,
        model_name="GigaAM v3 e2e CTC",
        model_revision="test",
        backend_version="test",
        license_marker="approved",
        capabilities=AsrCapabilities(languages=("ru",), max_segment_seconds=25.0, punctuation=True, streaming=False),
    )


def _segment(audio: Path, *, duration: float) -> AsrSegmentInput:
    return AsrSegmentInput("sample", 0, audio, 0.0, duration, "ru", "seg-v1")


def _write_required_files(root: Path) -> None:
    (root / "v3_e2e_ctc.ckpt").write_bytes(b"synthetic")
    (root / "v3_e2e_ctc_tokenizer.model").write_bytes(b"synthetic")


if __name__ == "__main__":
    unittest.main()
