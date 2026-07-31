from __future__ import annotations

import types
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

from benchmarks.asr.manifests import ModelPackageManifest
from nadikt.infrastructure.asr.gigaam import GigaAMLocalProbe


class GigaAMProbeTest(unittest.TestCase):
    def test_missing_dependency_is_controlled_outcome(self) -> None:
        probe = GigaAMLocalProbe(lambda: (_ for _ in ()).throw(ImportError("missing")))

        with tempfile.TemporaryDirectory() as temp_dir:
            result = probe.load(Path(temp_dir), _manifest())

        self.assertEqual("backend_unavailable", result.outcome)

    def test_missing_load_model_api_is_local_loading_unconfirmed(self) -> None:
        module = types.SimpleNamespace(load_model_from_package=lambda _path: object())
        probe = GigaAMLocalProbe(lambda: module)

        with tempfile.TemporaryDirectory() as temp_dir:
            result = probe.load(Path(temp_dir), _manifest())

        self.assertEqual("local_loading_unconfirmed", result.outcome)

    def test_download_root_loader_can_transcribe_short_segment_and_close(self) -> None:
        events: list[tuple[str, object]] = []

        class FakeModel:
            def transcribe(self, audio_path: str) -> str:
                events.append(("transcribe", Path(audio_path).name))
                return "payload must not be exposed"

            def close(self) -> None:
                events.append(("close", None))

        def load_model(model_name: str, **kwargs: object) -> FakeModel:
            events.append(("load", (model_name, kwargs["download_root"], kwargs["device"], kwargs["use_flash"], kwargs["fp16_encoder"])))
            return FakeModel()

        module = types.SimpleNamespace(load_model=load_model)
        probe = GigaAMLocalProbe(lambda: module)

        with tempfile.TemporaryDirectory() as temp_dir:
            audio = Path(temp_dir) / "sample.wav"
            audio.write_bytes(b"not-real-audio")
            load = probe.load(Path(temp_dir), _manifest())
            transcribe = probe.transcribe(audio, "controlled-audio", duration_seconds=24.5)
            close = probe.close()

        self.assertEqual("success", load.outcome)
        self.assertEqual("success", transcribe.outcome)
        self.assertEqual("success", close.outcome)
        self.assertEqual("load", events[0][0])
        self.assertEqual("v3_e2e_ctc", events[0][1][0])
        self.assertEqual("cpu", events[0][1][2])
        self.assertFalse(events[0][1][3])
        self.assertFalse(events[0][1][4])
        self.assertEqual([("transcribe", "sample.wav"), ("close", None)], events[1:])

    def test_empty_critical_files_rejects_before_load_model(self) -> None:
        module = types.SimpleNamespace(load_model=lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("must not load")))
        probe = GigaAMLocalProbe(lambda: module)
        manifest = ModelPackageManifest(
            package_id="gigaam-local",
            candidate_id="gigaam-v3-e2e-ctc",
            backend="gigaam",
            model_name="GigaAM v3 e2e CTC",
            model_revision="test",
            package_path=Path("local/gigaam"),
            license_marker="TO_BE_VERIFIED",
            capabilities={},
            inference_defaults={},
            critical_files=(),
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            result = probe.load(Path(temp_dir), manifest)

        self.assertEqual("missing_critical_file", result.outcome)

    def test_incomplete_required_files_rejects_before_load_model(self) -> None:
        module = types.SimpleNamespace(load_model=lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("must not load")))
        probe = GigaAMLocalProbe(lambda: module)
        manifest = ModelPackageManifest(
            package_id="gigaam-local",
            candidate_id="gigaam-v3-e2e-ctc",
            backend="gigaam",
            model_name="GigaAM v3 e2e CTC",
            model_revision="test",
            package_path=Path("local/gigaam"),
            license_marker="TO_BE_VERIFIED",
            capabilities={},
            inference_defaults={},
            critical_files=({"relative_path": "v3_e2e_ctc.ckpt", "sha256": "0" * 64},),
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            result = probe.load(Path(temp_dir), manifest)

        self.assertEqual("missing_critical_file", result.outcome)

    def test_segment_too_long_is_rejected_before_transcribe(self) -> None:
        class FakeModel:
            def transcribe(self, _audio_path: str) -> str:
                raise AssertionError("should not transcribe long segment")

        module = types.SimpleNamespace(load_model=lambda *_args, **_kwargs: FakeModel())
        probe = GigaAMLocalProbe(lambda: module)

        with tempfile.TemporaryDirectory() as temp_dir:
            audio = Path(temp_dir) / "sample.wav"
            audio.write_bytes(b"not-real-audio")
            probe.load(Path(temp_dir), _manifest())
            result = probe.transcribe(audio, "controlled-audio", duration_seconds=26.0)

        self.assertEqual("segment_too_long", result.outcome)

    def test_transcribe_exception_is_safe_outcome(self) -> None:
        class FailingModel:
            def transcribe(self, _audio_path: str) -> str:
                raise RuntimeError("sensitive local path must not be returned")

        module = types.SimpleNamespace(load_model=lambda *_args, **_kwargs: FailingModel())
        probe = GigaAMLocalProbe(lambda: module)

        with tempfile.TemporaryDirectory() as temp_dir:
            audio = Path(temp_dir) / "secret-canary.wav"
            audio.write_bytes(b"not-real-audio")
            probe.load(Path(temp_dir), _manifest())
            result = probe.transcribe(audio, "safe-label", duration_seconds=1.0)

        self.assertEqual("transcribe_failed", result.outcome)
        self.assertNotIn("secret-canary", repr(result))


def _manifest() -> ModelPackageManifest:
    return ModelPackageManifest(
        package_id="gigaam-local",
        candidate_id="gigaam-v3-e2e-ctc",
        backend="gigaam",
        model_name="GigaAM v3 e2e CTC",
        model_revision="test",
        package_path=Path("local/gigaam"),
        license_marker="TO_BE_VERIFIED",
        capabilities={},
        inference_defaults={},
        critical_files=(
            {"relative_path": "v3_e2e_ctc.ckpt", "sha256": "0" * 64},
            {"relative_path": "v3_e2e_ctc_tokenizer.model", "sha256": "0" * 64},
        ),
    )


if __name__ == "__main__":
    unittest.main()
