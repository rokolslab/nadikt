from __future__ import annotations

import contextlib
import hashlib
import io
import json
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

from benchmarks.asr.benchmark_results import BenchmarkResult, CandidateAggregate, validate_result_payload
from benchmarks.asr.benchmark_runner import main, run_benchmark


class BenchmarkRunnerTest(unittest.TestCase):
    def test_result_payload_rejects_forbidden_fields(self) -> None:
        payload = BenchmarkResult(
            run_id="run-1",
            run_kind="coding_pilot",
            nadikt_revision="abc123",
            dataset={"dataset_id": "safe"},
            candidates=(CandidateAggregate("candidate", "package", "faster-whisper", 3, 0, "not_run"),),
            measurement={"backend": "spawned-worker"},
            offline_evidence={"status": "NOT VERIFIED"},
            privacy={},
            outcome="not_run",
        ).to_json()
        payload["audio_path"] = "/private/audio.wav"

        with self.assertRaisesRegex(ValueError, "benchmark_result_unknown_fields"):
            validate_result_payload(payload)

    def test_dry_run_writes_safe_aggregate_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            inventory = _write_inventory(root)
            dataset = _write_dataset(root)
            output = root / "result.json"

            result = run_benchmark(
                inventory_path=inventory,
                dataset_profile_path=dataset,
                output_path=output,
                dry_run=True,
                repeats=3,
            )

            text = output.read_text(encoding="utf-8")

        self.assertEqual("dry_run", result.outcome)
        self.assertIn('"run_kind": "coding_pilot"', text)
        self.assertNotIn("audio_path", text)
        self.assertNotIn("reference_text", text)
        self.assertNotIn("hypothesis", text)

    def test_cli_prints_safe_json_and_exits_zero_for_dry_run(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            inventory = _write_inventory(root)
            dataset = _write_dataset(root)
            output = root / "result.json"
            stdout = io.StringIO()

            with contextlib.redirect_stdout(stdout):
                exit_code = main(["--inventory", str(inventory), "--dataset-profile", str(dataset), "--dry-run", "--output", str(output)])

        printed = stdout.getvalue()
        self.assertEqual(0, exit_code)
        self.assertIn('"outcome": "dry_run"', printed)
        self.assertNotIn(str(root), printed)


def _write_inventory(root: Path) -> Path:
    package_dir = root / "local-packages" / "package-0"
    package_dir.mkdir(parents=True)
    critical_file = package_dir / "manifest.txt"
    critical_file.write_text("synthetic metadata only\n", encoding="utf-8")
    sha256 = hashlib.sha256(critical_file.read_bytes()).hexdigest()
    manifest = {
        "schema_version": 1,
        "manifest_type": "model_package_manifest",
        "manifest_kind": "example",
        "package_id": "package-0",
        "candidate_id": "candidate-0",
        "backend": "faster-whisper",
        "model_name": "Synthetic CTranslate2 package",
        "model_revision": "test",
        "package_format": "synthetic",
        "compatible_nadikt_versions": ["0.x-prototype"],
        "rights_statuses": {
            "local_evaluation": {"status": "approved", "review_record_id": "local"},
            "redistribution": {"status": "review_required", "review_record_id": "redistribution"},
            "bundling": {"status": "review_required", "review_record_id": "bundling"},
            "installer_download": {"status": "review_required", "review_record_id": "download"},
        },
        "capabilities": {"languages": ["ru"], "punctuation": True, "max_segment_seconds": 25.0, "streaming": False},
        "inference_defaults": {"beam_size": 5, "device": "cpu", "compute_type": "int8"},
        "critical_files": [{"relative_path": "manifest.txt", "sha256": sha256, "size_bytes": 1, "role": "synthetic"}],
        "licenses": ["synthetic"],
        "notices": ["synthetic"],
    }
    manifest_path = root / "package-0.manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
    inventory = {
        "schema_version": 1,
        "manifest_kind": "example",
        "inventory_id": "synthetic-inventory",
        "packages": [
            {
                "package_id": "package-0",
                "package_path": "local-packages/package-0",
                "manifest_relative_path": "package-0.manifest.json",
                "manifest_sha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
            }
        ],
    }
    inventory_path = root / "inventory.json"
    inventory_path.write_text(json.dumps(inventory, ensure_ascii=False), encoding="utf-8")
    return inventory_path


def _write_dataset(root: Path) -> Path:
    dataset = {
        "schema_version": 1,
        "manifest_kind": "coding_pilot",
        "dataset_id": "synthetic-coding-pilot",
        "dataset_revision": "test",
        "samples": [
            {
                "sample_id": "coding_001",
                "category": "ru_coding_terms",
                "duration_seconds": 1.0,
                "language_profile": "ru",
                "audio_label": "controlled-audio:coding_001",
                "reference_label": "controlled-reference:coding_001",
                "expected_english_terms": [],
                "expected_coding_terms": [
                    {"term_id": "pytest", "canonical": "pytest", "accepted_variants": ["pytest"], "expected_occurrences": 1, "require_latin": True}
                ],
                "segmentation_policy_id": "seg-25s-no-overlap-v1",
            }
        ],
    }
    path = root / "dataset.json"
    path.write_text(json.dumps(dataset, ensure_ascii=False), encoding="utf-8")
    return path


if __name__ == "__main__":
    unittest.main()
