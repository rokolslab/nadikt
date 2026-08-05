from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

SRC = Path(__file__).resolve().parents[2] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from nadikt.domain.ports.asr import AsrBackend
from nadikt.infrastructure.model_packages import ModelPackageValidationError, validate_model_package_binding


class RuntimeModelPackageValidationTest(unittest.TestCase):
    def test_example_inventory_fails_before_sdk_import(self) -> None:
        with self.assertRaises(ModelPackageValidationError) as context:
            validate_model_package_binding(
                inventory_path=Path("model_packs/model_inventory.example.json"),
                package_id="faster-whisper-small-int8-local",
                candidate_id="faster-whisper-small-int8",
                backend=AsrBackend.FASTER_WHISPER,
            )

        self.assertEqual("example_manifest_rejected", context.exception.failure.code.value)
        self.assertNotIn("gigaam", sys.modules)
        self.assertNotIn("faster_whisper", sys.modules)

    def test_valid_local_sidecar_binding_returns_redacted_load_options(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            package_root = root / "packages" / "candidate"
            package_root.mkdir(parents=True)
            model_file = package_root / "model.bin"
            model_file.write_bytes(b"model-bytes")
            model_sha = hashlib.sha256(model_file.read_bytes()).hexdigest()
            manifest = {
                "schema_version": 1,
                "manifest_type": "model_package_manifest",
                "manifest_kind": "local_package",
                "package_id": "pkg",
                "candidate_id": "candidate",
                "backend": "faster-whisper",
                "model_name": "Local model",
                "model_revision": "rev",
                "package_format": "ctranslate2-directory",
                "compatible_nadikt_versions": ["0.x-prototype"],
                "compatible_backend_versions": ["faster-whisper==local"],
                "rights_statuses": {"local_evaluation": {"status": "approved"}},
                "capabilities": {"languages": ["ru"], "max_segment_seconds": 30.0, "punctuation": True, "streaming": False},
                "inference_defaults": {"device": "cpu", "compute_type": "int8"},
                "critical_files": [{"relative_path": "model.bin", "sha256": model_sha, "size_bytes": len(b"model-bytes"), "role": "ctranslate2_weights"}],
                "licenses": ["local-review"],
            }
            manifest_path = root / "manifest.json"
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            manifest_sha = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
            inventory = {
                "schema_version": 1,
                "manifest_kind": "local_inventory",
                "packages": [
                    {
                        "package_id": "pkg",
                        "candidate_id": "candidate",
                        "backend": "faster-whisper",
                        "package_path": "packages/candidate",
                        "manifest_relative_path": "manifest.json",
                        "manifest_sha256": manifest_sha,
                    }
                ],
            }
            inventory_path = root / "inventory.json"
            inventory_path.write_text(json.dumps(inventory), encoding="utf-8")

            binding = validate_model_package_binding(
                inventory_path=inventory_path,
                package_id="pkg",
                candidate_id="candidate",
                backend=AsrBackend.FASTER_WHISPER,
            )

        self.assertEqual("pkg", binding.package_id)
        self.assertIn(model_sha[:12], binding.checksum_prefixes)
        self.assertNotIn(tmp, repr(binding))
        self.assertNotIn(tmp, repr(binding.load_options))


if __name__ == "__main__":
    unittest.main()
