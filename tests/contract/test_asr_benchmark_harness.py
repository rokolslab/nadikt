from __future__ import annotations

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

from benchmarks.asr.dry_run import run_dry_run
from benchmarks.asr.manifests import load_json, validate_dataset_manifest, validate_model_inventory
from benchmarks.asr.offline_check import validate_local_package
from benchmarks.asr.privacy_audit import audit_text_artifact
from benchmarks.asr.quality_metrics import cer, english_term_accuracy, latin_preservation_rate, wer
from benchmarks.asr.segmentation_manifest import SegmentDescriptor, validate_segments
from nadikt.domain.ports.asr import AsrCapabilities, AsrSegmentInput, ensure_segment_within_capabilities


class AsrBenchmarkHarnessTest(unittest.TestCase):
    def test_example_manifests_are_valid(self) -> None:
        dataset = load_json(ROOT / "benchmarks/asr/datasets/dataset.example.json")
        models = load_json(ROOT / "model_packs/model_inventory.example.json")

        samples, dataset_errors = validate_dataset_manifest(dataset)
        packages, model_errors = validate_model_inventory(models)

        self.assertEqual([], dataset_errors)
        self.assertEqual([], model_errors)
        self.assertEqual(6, len(samples))
        self.assertEqual(4, len(packages))

    def test_dataset_rejects_windows_absolute_labels(self) -> None:
        dataset = load_json(ROOT / "benchmarks/asr/datasets/dataset.example.json")
        dataset["samples"][0]["audio_label"] = "C:\\Users\\person\\audio.wav"
        dataset["samples"][1]["reference_label"] = "\\\\server\\share\\reference.txt"

        _, errors = validate_dataset_manifest(dataset)

        self.assertIn("sample_0_unsafe_audio_label", errors)
        self.assertIn("sample_1_unsafe_reference_label", errors)

    def test_dataset_reports_invalid_duration_type(self) -> None:
        dataset = load_json(ROOT / "benchmarks/asr/datasets/dataset.example.json")
        dataset["samples"][0]["duration_seconds"] = "not-a-number"
        dataset["samples"][1]["duration_seconds"] = True

        samples, errors = validate_dataset_manifest(dataset)

        self.assertIn("sample_0_invalid_duration_type", errors)
        self.assertIn("sample_1_invalid_duration_type", errors)
        self.assertEqual(4, len(samples))

    def test_dataset_reports_bad_expected_terms_type(self) -> None:
        dataset = load_json(ROOT / "benchmarks/asr/datasets/dataset.example.json")
        dataset["samples"][0]["expected_english_terms"] = None
        dataset["samples"][1]["expected_english_terms"] = ["Windows", 123]

        samples, errors = validate_dataset_manifest(dataset)

        self.assertIn("sample_0_expected_english_terms_not_list", errors)
        self.assertIn("sample_1_expected_english_term_not_string", errors)
        self.assertEqual(4, len(samples))

    def test_model_inventory_rejects_unsafe_paths(self) -> None:
        models = load_json(ROOT / "model_packs/model_inventory.example.json")
        models["packages"][0]["package_path"] = "C:\\Users\\person\\model"
        models["packages"][1]["package_path"] = "../outside-root/model"

        _, errors = validate_model_inventory(models)

        self.assertIn("package_0_unsafe_absolute_path", errors)
        self.assertIn("package_1_unsafe_absolute_path", errors)

    def test_model_inventory_reports_bad_object_types(self) -> None:
        models = load_json(ROOT / "model_packs/model_inventory.example.json")
        models["packages"][0]["capabilities"] = "bad"
        models["packages"][1]["critical_files"] = "bad"

        packages, errors = validate_model_inventory(models)

        self.assertIn("package_0_capabilities_not_object", errors)
        self.assertIn("package_1_critical_files_not_list", errors)
        self.assertEqual(2, len(packages))

    def test_offline_check_rejects_windows_absolute_path_directly(self) -> None:
        result = validate_local_package(
            "unsafe-package",
            Path("C:\\Users\\person\\model"),
            ROOT,
        )

        self.assertEqual("invalid_package_path", result.outcome)
        self.assertFalse(result.network_attempted)

    def test_dry_run_reports_missing_packages_without_payload(self) -> None:
        summary = run_dry_run(
            ROOT / "benchmarks/asr/datasets/dataset.example.json",
            ROOT / "model_packs/model_inventory.example.json",
        )

        rendered = json.dumps(summary, ensure_ascii=False)
        self.assertEqual("passed_with_expected_missing_packages", summary["result"])
        self.assertEqual({"missing_package": 4}, summary["models"]["package_outcomes"])
        self.assertFalse(summary["offline"]["network_attempted"])
        self.assertNotIn("transcript_text", rendered)
        self.assertNotIn("audio_bytes", rendered)
        self.assertNotIn("NADIKT_CONTROLLED_CANARY", rendered)

    def test_quality_metrics_use_synthetic_text_only(self) -> None:
        self.assertEqual(0.0, wer("проверить сервер", "проверить сервер").value)
        self.assertGreater(wer("проверить сервер", "проверить").value, 0.0)
        self.assertEqual(0.0, cer("abc", "abc").value)
        self.assertEqual(1.0, english_term_accuracy(["Windows", "GitHub"], "windows github").value)
        self.assertEqual(1.0, latin_preservation_rate(["PostgreSQL"], "проверить PostgreSQL").value)

    def test_segmentation_rejects_too_long_segment(self) -> None:
        errors = validate_segments(
            [
                SegmentDescriptor(
                    sample_id="sample_001",
                    segment_id=0,
                    start_seconds=0.0,
                    end_seconds=26.0,
                    overlap_left_seconds=0.0,
                    overlap_right_seconds=0.0,
                    boundary_policy_id="seg-25s-v1",
                )
            ],
            max_segment_seconds=25.0,
        )

        self.assertIn("sample_001:0:segment_too_long", errors)

    def test_asr_contract_redacts_sensitive_repr(self) -> None:
        segment = AsrSegmentInput(
            sample_id="sample_001",
            segment_id=0,
            audio_path=Path("/sensitive/user/audio.wav"),
            start_seconds=0.0,
            end_seconds=10.0,
            language_profile="ru",
            segmentation_policy_id="seg-25s-v1",
        )

        rendered = repr(segment)
        self.assertNotIn("/sensitive/user/audio.wav", rendered)
        ensure_segment_within_capabilities(segment, AsrCapabilities(("ru",), 25.0, True, False))

    def test_privacy_audit_flags_canary_without_returning_value(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "artifact.log"
            path.write_text("safe metadata NADIKT_SECRET_CANARY", encoding="utf-8")
            result = audit_text_artifact(path.read_text(encoding="utf-8"), canary="NADIKT_SECRET_CANARY")

        self.assertTrue(result.canary_present)
        self.assertNotIn("NADIKT_SECRET_CANARY", repr(result.safe_log_context()))


if __name__ == "__main__":
    unittest.main()
