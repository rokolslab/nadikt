from __future__ import annotations

import json
import logging
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

from benchmarks.asr.local_model_probe import run_local_model_probe
from benchmarks.asr.manifests import load_json, validate_model_inventory
from nadikt.infrastructure.asr.faster_whisper import FasterWhisperLocalProbe


class OfflinePrivacyRegressionTest(unittest.TestCase):
    def test_offline_required_records_marker_without_network_attempt(self) -> None:
        summary = run_local_model_probe(
            ROOT / "model_packs/model_inventory.example.json",
            dry_run=True,
            offline_required=True,
        )

        self.assertFalse(summary["offline"]["network_attempted"])
        self.assertTrue(summary["offline"]["network_block_required"])
        self.assertEqual("external_environment_required", summary["offline"]["network_block_verification"])

    def test_inventory_rejects_forbidden_hub_names(self) -> None:
        models = load_json(ROOT / "model_packs/model_inventory.example.json")
        models["packages"][0]["package_path"] = "systran/faster-whisper-small"

        _, errors = validate_model_inventory(models)

        self.assertIn("package_0_forbidden_model_identifier", errors)

    def test_corrupted_package_stops_before_backend_factory(self) -> None:
        called = {"factory": False}

        def factory() -> object:
            called["factory"] = True
            raise AssertionError("backend must not be created for corrupted package")

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            package_dir = root / "local-packages" / "corrupt"
            package_dir.mkdir(parents=True)
            (package_dir / "manifest.txt").write_text("synthetic metadata only\n", encoding="utf-8")
            inventory = root / "inventory.json"
            inventory.write_text(json.dumps(_inventory_payload("0" * 64), ensure_ascii=False), encoding="utf-8")
            summary = run_local_model_probe(inventory, backend_factories={"faster-whisper": factory})

        self.assertEqual("completed_with_blockers", summary["result"])
        self.assertEqual({"checksum_mismatch": 1}, summary["package_outcomes"])
        self.assertFalse(called["factory"])

    def test_adapter_error_logs_do_not_include_exception_canary_or_audio_path(self) -> None:
        canary = "NADIKT_SECRET_AUDIO_PATH_CANARY"

        class FailingWhisperModel:
            def __init__(self, *_args: object, **_kwargs: object) -> None:
                pass

            def transcribe(self, *_args: object, **_kwargs: object) -> tuple[object, object]:
                raise RuntimeError(canary)

        with tempfile.TemporaryDirectory() as temp_dir:
            package_dir = Path(temp_dir) / "ct2-package"
            package_dir.mkdir()
            audio = Path(temp_dir) / "client-secret-audio.wav"
            audio.write_bytes(b"not-real-audio")
            probe = FasterWhisperLocalProbe(FailingWhisperModel)
            probe.load(package_dir, _manifest())

            with self.assertLogs("nadikt.infrastructure.asr.faster_whisper", level=logging.ERROR) as captured:
                result = probe.transcribe(audio, "safe-audio-label")

        rendered_logs = "\n".join(captured.output)
        self.assertEqual("transcribe_failed", result.outcome)
        self.assertNotIn(canary, rendered_logs)
        self.assertNotIn("client-secret-audio", rendered_logs)
        self.assertIn("faster_whisper_transcribe_failed", rendered_logs)


def _inventory_payload(sha256: str) -> dict[str, object]:
    return {
        "schema_version": 1,
        "inventory_id": "synthetic-corrupt-inventory",
        "packages": [
            {
                "package_id": "corrupt-package",
                "candidate_id": "faster-whisper-corrupt",
                "backend": "faster-whisper",
                "model_name": "Synthetic corrupt package",
                "model_revision": "test",
                "package_path": "local-packages/corrupt",
                "license_marker": "MIT",
                "compatible_nadikt_versions": ["0.x-prototype"],
                "capabilities": {"languages": ["ru"], "punctuation": True, "max_segment_seconds": 25.0, "streaming": False},
                "inference_defaults": {"beam_size": 5, "device": "cpu", "compute_type": "int8"},
                "critical_files": [{"relative_path": "manifest.txt", "sha256": sha256}],
            }
        ],
    }


def _manifest() -> object:
    from benchmarks.asr.manifests import ModelPackageManifest

    return ModelPackageManifest(
        package_id="fw-local",
        candidate_id="faster-whisper-small-int8",
        backend="faster-whisper",
        model_name="Whisper small CTranslate2 INT8",
        model_revision="test",
        package_path=Path("local/fw"),
        license_marker="MIT",
        capabilities={},
        inference_defaults={"beam_size": 5},
        critical_files=(),
    )


if __name__ == "__main__":
    unittest.main()
