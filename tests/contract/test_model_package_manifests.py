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

from benchmarks.asr.manifests import load_json, load_model_inventory, validate_model_package_manifest


class ModelPackageManifestSchemaTest(unittest.TestCase):
    def test_example_inventory_loads_bound_sidecar_manifest(self) -> None:
        packages, errors = load_model_inventory(ROOT / "model_packs/model_inventory.example.json")

        self.assertEqual([], errors)
        self.assertEqual(1, len(packages))
        self.assertEqual("faster-whisper-small-int8-local", packages[0].package_id)
        self.assertEqual("faster-whisper", packages[0].backend)

    def test_sidecar_manifest_rejects_invalid_rights_status_enum(self) -> None:
        manifest = load_json(ROOT / "model_packs/model_package_manifest.example.json")
        manifest["rights_statuses"]["redistribution"]["status"] = "unknown"

        package, errors = validate_model_package_manifest(manifest)

        self.assertIsNone(package)
        self.assertIn("rights_redistribution_invalid_status", errors)


if __name__ == "__main__":
    unittest.main()
