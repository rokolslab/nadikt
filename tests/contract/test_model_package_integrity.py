from __future__ import annotations

import hashlib
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

from benchmarks.asr.manifests import load_json, load_model_inventory, validate_model_inventory, validate_model_package_manifest
from benchmarks.asr.offline_check import validate_local_package


class ModelPackageIntegrityTest(unittest.TestCase):
    def test_valid_synthetic_package_reports_checksum_prefix_and_license_warning(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            package_dir = root / "local-packages" / "synthetic-package"
            package_dir.mkdir(parents=True)
            critical_file = package_dir / "manifest.txt"
            critical_file.write_text("synthetic metadata only\n", encoding="utf-8")
            sha256 = _sha256(critical_file)

            result = validate_local_package(
                "synthetic-package",
                Path("local-packages/synthetic-package"),
                root,
                ({"relative_path": "manifest.txt", "sha256": sha256, "size_bytes": critical_file.stat().st_size, "role": "synthetic"},),
                {
                    "local_evaluation": {"status": "approved", "review_record_id": "local"},
                    "redistribution": {"status": "review_required", "review_record_id": "redistribution"},
                    "bundling": {"status": "review_required", "review_record_id": "bundling"},
                    "installer_download": {"status": "review_required", "review_record_id": "download"},
                },
            )

        self.assertEqual("package_present", result.outcome)
        self.assertEqual((sha256[:12],), result.checksum_prefixes)
        self.assertIn("redistribution_review_required", result.warnings)
        rendered = repr(result.safe_log_context())
        self.assertNotIn(str(package_dir), rendered)
        self.assertNotIn("synthetic metadata only", rendered)

    def test_missing_package_is_controlled_outcome(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            result = validate_local_package(
                "missing-package",
                Path("local-packages/missing"),
                Path(temp_dir),
                ({"relative_path": "manifest.txt", "sha256": "0" * 64},),
            )

        self.assertEqual("missing_package", result.outcome)
        self.assertFalse(result.network_attempted)

    def test_missing_critical_file_is_controlled_outcome(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "local-packages" / "synthetic-package").mkdir(parents=True)

            result = validate_local_package(
                "synthetic-package",
                Path("local-packages/synthetic-package"),
                root,
                ({"relative_path": "manifest.txt", "sha256": "0" * 64},),
            )

        self.assertEqual("missing_critical_file", result.outcome)

    def test_checksum_mismatch_is_controlled_outcome(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            package_dir = root / "local-packages" / "synthetic-package"
            package_dir.mkdir(parents=True)
            (package_dir / "manifest.txt").write_text("synthetic metadata only\n", encoding="utf-8")
            critical_file = package_dir / "manifest.txt"

            result = validate_local_package(
                "synthetic-package",
                Path("local-packages/synthetic-package"),
                root,
                ({"relative_path": "manifest.txt", "sha256": "0" * 64, "size_bytes": critical_file.stat().st_size, "role": "synthetic"},),
            )

        self.assertEqual("checksum_mismatch", result.outcome)
        self.assertEqual(1, len(result.checksum_prefixes))

    def test_inventory_rejects_invalid_manifest_checksum_format(self) -> None:
        models = load_json(ROOT / "model_packs/model_inventory.example.json")
        models["packages"][0]["manifest_sha256"] = "not-a-sha256"

        _, errors = validate_model_inventory(models)

        self.assertIn("package_0_manifest_invalid_checksum", errors)

    def test_package_manifest_rejects_empty_critical_files(self) -> None:
        manifest = load_json(ROOT / "model_packs/model_package_manifest.example.json")
        manifest["critical_files"] = []

        package, errors = validate_model_package_manifest(manifest)

        self.assertIn("critical_files_required", errors)
        self.assertIsNone(package)

    def test_package_manifest_rejects_incomplete_gigaam_required_files(self) -> None:
        manifest = load_json(ROOT / "model_packs/model_package_manifest.example.json")
        manifest["backend"] = "gigaam"
        manifest["candidate_id"] = "gigaam-v3-e2e-ctc"
        manifest["inference_defaults"] = {"gigaam_model_name": "v3_e2e_ctc"}
        manifest["critical_files"] = [
            {"relative_path": "v3_e2e_ctc.ckpt", "sha256": "0" * 64},
        ]

        package, errors = validate_model_package_manifest(manifest)

        self.assertIn("critical_file_0_invalid_size", errors)
        self.assertIn("critical_file_0_missing_role", errors)
        self.assertIn("gigaam_required_files_missing", errors)
        self.assertIsNone(package)

    def test_package_manifest_rejects_unsafe_critical_file_path(self) -> None:
        manifest = load_json(ROOT / "model_packs/model_package_manifest.example.json")
        manifest["critical_files"][0]["relative_path"] = "../manifest.txt"

        _, errors = validate_model_package_manifest(manifest)

        self.assertIn("critical_file_0_unsafe_path", errors)

    def test_package_manifest_rejects_unapproved_local_evaluation(self) -> None:
        manifest = load_json(ROOT / "model_packs/model_package_manifest.example.json")
        manifest["rights_statuses"]["local_evaluation"]["status"] = "review_required"

        _, errors = validate_model_package_manifest(manifest)

        self.assertIn("local_evaluation_not_approved", errors)

    def test_package_manifest_rejects_non_example_placeholder_checksum(self) -> None:
        manifest = load_json(ROOT / "model_packs/model_package_manifest.example.json")
        manifest["manifest_kind"] = "model_package"

        _, errors = validate_model_package_manifest(manifest)

        self.assertIn("critical_file_0_placeholder_checksum", errors)

    def test_inventory_sidecar_digest_mismatch_is_rejected(self) -> None:
        models = load_json(ROOT / "model_packs/model_inventory.example.json")
        models["packages"][0]["manifest_sha256"] = "1" * 64
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "model_package_manifest.example.json").write_text(
                (ROOT / "model_packs/model_package_manifest.example.json").read_text(encoding="utf-8"),
                encoding="utf-8",
            )
            inventory = root / "inventory.json"
            inventory.write_text(__import__("json").dumps(models), encoding="utf-8")

            packages, errors = load_model_inventory(inventory)

        self.assertEqual([], packages)
        self.assertIn("package_0_manifest_checksum_mismatch", errors)

    def test_symlink_package_root_escape_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            root = temp_path / "inventory"
            outside = temp_path / "outside-package"
            root.mkdir()
            outside.mkdir()
            (outside / "manifest.txt").write_text("synthetic metadata only\n", encoding="utf-8")
            link = root / "local-packages" / "escaped"
            link.parent.mkdir()
            link.symlink_to(outside, target_is_directory=True)

            result = validate_local_package(
                "escaped-package",
                Path("local-packages/escaped"),
                root,
                ({"relative_path": "manifest.txt", "sha256": _sha256(outside / "manifest.txt")},),
            )

        self.assertEqual("invalid_package_path", result.outcome)

    def test_traversal_and_windows_paths_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            traversal = validate_local_package("traversal", Path("../outside"), root)
            windows = validate_local_package("windows", Path("C:\\Users\\person\\model"), root)
            windows_drive_relative = validate_local_package("windows-drive-relative", Path("C:models"), root)
            windows_rooted = validate_local_package("windows-rooted", Path("\\models"), root)

        self.assertEqual("invalid_package_path", traversal.outcome)
        self.assertEqual("invalid_package_path", windows.outcome)
        self.assertEqual("invalid_package_path", windows_drive_relative.outcome)
        self.assertEqual("invalid_package_path", windows_rooted.outcome)

    def test_local_inventory_requires_trusted_index_and_exact_sidecar_binding(self) -> None:
        inventory = {
            "schema_version": 1,
            "manifest_kind": "local_inventory",
            "inventory_id": "controlled-inventory",
            "packages": [
                {
                    "package_id": "package-a",
                    "candidate_id": "faster-whisper-small-int8",
                    "backend": "faster-whisper",
                    "package_path": "local-packages/package-a",
                    "manifest_relative_path": "package-a.manifest.json",
                    "manifest_sha256": "0" * 64,
                }
            ],
        }

        _, errors = validate_model_inventory(inventory)

        self.assertIn("trusted_index_id_required", errors)
        self.assertIn("trusted_index_sha256_required", errors)

    def test_load_model_inventory_rejects_sidecar_package_id_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            manifest = load_json(ROOT / "model_packs/model_package_manifest.example.json")
            manifest["package_id"] = "sidecar-package"
            manifest_path = root / "manifest.json"
            manifest_path.write_text(__import__("json").dumps(manifest), encoding="utf-8")
            inventory = {
                "schema_version": 1,
                "manifest_kind": "local_inventory",
                "inventory_id": "controlled-inventory",
                "trusted_index_id": "trusted-index-1",
                "trusted_index_sha256": "1" * 64,
                "packages": [
                    {
                        "package_id": "inventory-package",
                        "candidate_id": "faster-whisper-small-int8",
                        "backend": "faster-whisper",
                        "package_path": "local-packages/package-a",
                        "manifest_relative_path": "manifest.json",
                        "manifest_sha256": _sha256(manifest_path),
                    }
                ],
            }
            inventory_path = root / "inventory.json"
            inventory_path.write_text(__import__("json").dumps(inventory), encoding="utf-8")

            packages, errors = load_model_inventory(inventory_path)

        self.assertEqual([], packages)
        self.assertIn("package_0_package_id_mismatch", errors)

    def test_package_integrity_rejects_size_drift_and_unapproved_role(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            package_dir = root / "local-packages" / "synthetic-package"
            package_dir.mkdir(parents=True)
            critical_file = package_dir / "manifest.txt"
            critical_file.write_text("synthetic metadata only\n", encoding="utf-8")
            sha256 = _sha256(critical_file)

            size_drift = validate_local_package(
                "synthetic-package",
                Path("local-packages/synthetic-package"),
                root,
                ({"relative_path": "manifest.txt", "sha256": sha256, "size_bytes": critical_file.stat().st_size + 1, "role": "synthetic"},),
                package_format="synthetic",
            )
            bad_role = validate_local_package(
                "synthetic-package",
                Path("local-packages/synthetic-package"),
                root,
                ({"relative_path": "manifest.txt", "sha256": sha256, "size_bytes": critical_file.stat().st_size, "role": "ctranslate2_weights"},),
                package_format="synthetic",
            )

        self.assertEqual("size_mismatch", size_drift.outcome)
        self.assertEqual("invalid_file_role", bad_role.outcome)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


if __name__ == "__main__":
    unittest.main()
