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

from benchmarks.asr.manifests import load_json, validate_model_inventory
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
                ({"relative_path": "manifest.txt", "sha256": sha256},),
                "TO_BE_VERIFIED",
            )

        self.assertEqual("package_present", result.outcome)
        self.assertEqual((sha256[:12],), result.checksum_prefixes)
        self.assertEqual(("license_not_verified",), result.warnings)
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

            result = validate_local_package(
                "synthetic-package",
                Path("local-packages/synthetic-package"),
                root,
                ({"relative_path": "manifest.txt", "sha256": "0" * 64},),
            )

        self.assertEqual("checksum_mismatch", result.outcome)
        self.assertEqual(1, len(result.checksum_prefixes))

    def test_inventory_rejects_invalid_checksum_format(self) -> None:
        models = load_json(ROOT / "model_packs/model_inventory.example.json")
        models["packages"][0]["critical_files"][0]["sha256"] = "not-a-sha256"

        _, errors = validate_model_inventory(models)

        self.assertIn("package_0_critical_file_0_invalid_checksum", errors)

    def test_inventory_rejects_unsafe_critical_file_path(self) -> None:
        models = load_json(ROOT / "model_packs/model_inventory.example.json")
        models["packages"][0]["critical_files"][0]["relative_path"] = "../manifest.txt"

        _, errors = validate_model_inventory(models)

        self.assertIn("package_0_critical_file_0_unsafe_path", errors)

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

        self.assertEqual("invalid_package_path", traversal.outcome)
        self.assertEqual("invalid_package_path", windows.outcome)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


if __name__ == "__main__":
    unittest.main()
