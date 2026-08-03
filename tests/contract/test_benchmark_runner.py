from __future__ import annotations

import contextlib
import hashlib
import io
import json
import struct
import sys
import tempfile
import unittest
import wave
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from benchmarks.asr.benchmark_results import BenchmarkResult, CandidateAggregate, validate_result_payload
from benchmarks.asr.benchmark_runner import _aggregate_quality_results, _aggregate_resource_samples, main, run_benchmark
from benchmarks.asr.resource_measurement import ResourceReport
from benchmarks.asr.worker_protocol import WorkerPhase, WorkerRequest, WorkerResult
from benchmarks.asr.worker_supervisor import SupervisedWorkerResult


class _FakeWorkerSupervisor:
    _RESULTS = ((1, 4, 500.0), (2, 6, 1000.0))

    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def run(self, request: WorkerRequest) -> SupervisedWorkerResult:
        call_index = len(self.calls)
        if call_index >= len(self._RESULTS):
            raise AssertionError("unexpected_fake_supervisor_call")
        numerator, denominator, duration_ms = self._RESULTS[call_index]
        self.calls.append(
            {
                "call_index": call_index,
                "candidate_id": request.candidate_id,
                "package_id": request.package_id,
                "transcribe_duration_ms": duration_ms,
            }
        )
        worker_result = WorkerResult(
            nonce=request.nonce,
            package_id=request.package_id,
            candidate_id=request.candidate_id,
            backend=request.backend,
            worker_status="success",
            phases=(WorkerPhase("transcribe_probe", "success", duration_ms),),
            quality_metrics={
                "wer": {
                    "metric_name": "wer",
                    "value": numerator / denominator,
                    "numerator": numerator,
                    "denominator": denominator,
                    "status": "ok",
                    "version": "quality-metrics-v2",
                }
            },
            offline_evidence={"status": "NOT VERIFIED"},
        )
        resource_report = ResourceReport(
            backend="fake-sampler",
            backend_version="v1",
            status="ok" if call_index == 0 else "partial",
            sample_interval_ms=200,
            duration_seconds=duration_ms / 1000.0,
            sample_count=3 + call_index,
            missed_sample_count=call_index,
            user_cpu_seconds=1.0 + call_index,
            system_cpu_seconds=0.5,
            cpu_avg_percent=50.0 + call_index * 10.0,
            cpu_max_percent=80.0 + call_index * 10.0,
            peak_rss_mib=256.0 + call_index,
            process_count_max=2,
        )
        return SupervisedWorkerResult(worker_result, resource_report)


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

    def test_result_payload_rejects_non_finite_nested_resource_values(self) -> None:
        payload = BenchmarkResult(
            run_id="run-1",
            run_kind="coding_pilot",
            nadikt_revision="abc123",
            dataset={"dataset_id": "safe"},
            candidates=(CandidateAggregate("candidate", "package", "faster-whisper", 1, 1, "success", resource_aggregates={"resource_cpu_avg_percent": float("nan")}),),
            measurement={"backend": "spawned-worker", "repeats_requested": 1, "resource_sampler": "fake:v1"},
            offline_evidence={"status": "NOT VERIFIED"},
            privacy={},
            outcome="success",
        ).to_json

        with self.assertRaisesRegex(ValueError, "benchmark_result_non_finite_number"):
            payload()

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

    def test_run_profile_dry_run_rejects_single_candidate_filter(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            inventory = _write_coding_pilot_inventory(root)
            output = root / "result.json"

            result = run_benchmark(
                inventory_path=inventory,
                dataset_profile_path=ROOT / "benchmarks/asr/datasets/coding_pilot.v1.json",
                output_path=output,
                candidate="faster-whisper-small-int8",
                repeats=3,
                run_profile_path=ROOT / "benchmarks/asr/run_profiles/coding_pilot.v1.json",
                dry_run=True,
            )

        self.assertEqual("invalid_inputs", result.outcome)
        self.assertEqual(1, result.privacy["run_profile_error_count"])

    def test_run_profile_dry_run_persists_ordered_matrix_settings(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            inventory = _write_coding_pilot_inventory(root)
            output = root / "result.json"

            result = run_benchmark(
                inventory_path=inventory,
                dataset_profile_path=ROOT / "benchmarks/asr/datasets/coding_pilot.v1.json",
                output_path=output,
                repeats=3,
                run_profile_path=ROOT / "benchmarks/asr/run_profiles/coding_pilot.v1.json",
                dry_run=True,
            )

            persisted = json.loads(output.read_text(encoding="utf-8"))

        self.assertEqual("dry_run", result.outcome)
        self.assertEqual(["gigaam-multilingual-220m", "faster-whisper-small-int8"], [candidate.candidate_id for candidate in result.candidates])
        self.assertEqual("coding-pilot-v1", persisted["settings"]["run_profile_id"])
        self.assertEqual("cpu-threads-4-openmp-4-blas-1-v1", persisted["settings"]["thread_policy_id"])

    def test_non_dry_run_persists_fake_supervisor_quality_and_resource_aggregates(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            inventory = _write_inventory(root)
            dataset = _write_dataset(root)
            bindings = _write_bindings(root, dataset)
            output = root / "result.json"
            supervisor = _FakeWorkerSupervisor()

            with patch("benchmarks.asr.benchmark_runner.WorkerSupervisor", return_value=supervisor):
                result = run_benchmark(
                    inventory_path=inventory,
                    dataset_profile_path=dataset,
                    output_path=output,
                    private_bindings_path=bindings,
                    controlled_root=root,
                    repeats=2,
                )

            persisted = json.loads(output.read_text(encoding="utf-8"))
            private_root = str(root)

        candidate = result.candidates[0]
        self.assertEqual("success", result.outcome)
        self.assertEqual(2, candidate.repeats_completed)
        self.assertEqual(
            [
                {"call_index": 0, "candidate_id": "candidate-0", "package_id": "package-0", "transcribe_duration_ms": 500.0},
                {"call_index": 1, "candidate_id": "candidate-0", "package_id": "package-0", "transcribe_duration_ms": 1000.0},
            ],
            supervisor.calls,
        )
        self.assertEqual(
            {
                "wer": {
                    "metric_name": "wer",
                    "value": 0.3,
                    "numerator": 3,
                    "denominator": 10,
                    "status": "ok",
                    "sample_measurements": 2,
                }
            },
            candidate.quality_aggregates,
        )
        self.assertEqual(
            {
                "sample_measurements": 2,
                "audio_seconds_avg": 1.0,
                "audio_seconds_max": 1.0,
                "resource_backend": "fake-sampler",
                "resource_backend_version": "v1",
                "resource_cpu_avg_percent": 56.666667,
                "resource_cpu_max_percent": 90.0,
                "resource_cpu_normalization": "one_logical_cpu_100_percent",
                "resource_duration_seconds_sum": 1.5,
                "resource_missed_sample_count": 1,
                "resource_peak_rss_mib": 257.0,
                "resource_process_count_max": 2,
                "resource_report_count": 2,
                "resource_sample_count": 7,
                "resource_sample_interval_ms": 200,
                "resource_status_ok_count": 1,
                "resource_status_partial_count": 1,
                "resource_status_unavailable_count": 0,
                "resource_system_cpu_seconds_sum": 1.0,
                "resource_user_cpu_seconds_sum": 3.0,
                "transcribe_probe_duration_ms_avg": 750.0,
                "transcribe_probe_duration_ms_max": 1000.0,
                "transcribe_probe_rtf_avg": 0.75,
                "transcribe_probe_rtf_max": 1.0,
            },
            candidate.resource_aggregates,
        )
        self.assertEqual(candidate.to_json(), persisted["candidates"][0])
        self.assertEqual("fake-sampler:v1", persisted["measurement"]["resource_sampler"])
        rendered = json.dumps(persisted, ensure_ascii=False, sort_keys=True)
        for private_value in (
            private_root,
            "controlled synthetic reference",
            "audio_file",
            "audio_path",
            "reference_file",
            "reference_text",
            "hypothesis",
        ):
            self.assertNotIn(private_value, rendered)

    def test_candidate_aggregate_includes_safe_quality_and_resource_counters(self) -> None:
        aggregate = CandidateAggregate(
            "candidate",
            "package",
            "faster-whisper",
            1,
            1,
            "success",
            {"transcribe_probe": "success"},
            _aggregate_quality_results(
                {
                    "wer": [
                        {"metric_name": "wer", "numerator": 1, "denominator": 4, "status": "ok"},
                        {"metric_name": "wer", "numerator": 2, "denominator": 6, "status": "ok"},
                    ]
                }
            ),
            _aggregate_resource_samples(
                [
                    {"audio_seconds": 2.0, "transcribe_probe_duration_ms": 500.0, "transcribe_probe_rtf": 0.25, "resource_backend": "fake", "resource_backend_version": "v1", "resource_cpu_normalization": "one_logical_cpu_100_percent", "resource_status": "ok", "resource_sample_interval_ms": 100, "resource_sample_count": 2, "resource_missed_sample_count": 0, "resource_cpu_avg_percent": 10.0, "resource_cpu_max_percent": 20.0, "resource_peak_rss_mib": 100.0},
                    {"audio_seconds": 4.0, "transcribe_probe_duration_ms": 2000.0, "transcribe_probe_rtf": 0.5, "resource_backend": "fake", "resource_backend_version": "v1", "resource_cpu_normalization": "one_logical_cpu_100_percent", "resource_status": "ok", "resource_sample_interval_ms": 100, "resource_sample_count": 2, "resource_missed_sample_count": 0, "resource_cpu_avg_percent": 30.0, "resource_cpu_max_percent": 40.0, "resource_peak_rss_mib": 120.0},
                ]
            ),
        )

        rendered = json.dumps(aggregate.to_json(), ensure_ascii=False, sort_keys=True)

        self.assertIn('"quality_aggregates"', rendered)
        self.assertIn('"resource_aggregates"', rendered)
        self.assertIn('"numerator": 3', rendered)
        self.assertIn('"transcribe_probe_rtf_avg": 0.375', rendered)
        self.assertIn('"resource_peak_rss_mib": 120.0', rendered)
        self.assertNotIn("reference_text", rendered)
        self.assertNotIn("hypothesis", rendered)


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


def _write_coding_pilot_inventory(root: Path) -> Path:
    packages = [
        ("gigaam-multilingual-220m-local", "gigaam-multilingual-220m", "gigaam", "GigaAM Multilingual 220M", {"gigaam_model_name": "multilingual_ctc"}, ["multilingual_ctc.ckpt"]),
        ("faster-whisper-small-int8-local", "faster-whisper-small-int8", "faster-whisper", "Whisper small INT8", {"beam_size": 5, "device": "cpu", "compute_type": "int8"}, ["model.bin"]),
    ]
    inventory_packages = []
    for package_id, candidate_id, backend, model_name, inference_defaults, filenames in packages:
        package_dir = root / "local-packages" / package_id
        package_dir.mkdir(parents=True)
        critical_files = []
        for filename in filenames:
            critical_file = package_dir / filename
            critical_file.write_text("synthetic metadata only\n", encoding="utf-8")
            critical_files.append({"relative_path": filename, "sha256": hashlib.sha256(critical_file.read_bytes()).hexdigest(), "size_bytes": critical_file.stat().st_size, "role": "synthetic"})
        manifest = {
            "schema_version": 1,
            "manifest_type": "model_package_manifest",
            "manifest_kind": "example",
            "package_id": package_id,
            "candidate_id": candidate_id,
            "backend": backend,
            "model_name": model_name,
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
            "inference_defaults": inference_defaults,
            "critical_files": critical_files,
            "licenses": ["synthetic"],
            "notices": ["synthetic"],
        }
        manifest_path = root / f"{package_id}.manifest.json"
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
        inventory_packages.append(
            {
                "package_id": package_id,
                "package_path": f"local-packages/{package_id}",
                "manifest_relative_path": manifest_path.name,
                "manifest_sha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
            }
        )
    inventory = {"schema_version": 1, "manifest_kind": "example", "inventory_id": "synthetic-coding-pilot-inventory", "packages": inventory_packages}
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


def _write_bindings(root: Path, dataset: Path) -> Path:
    audio_dir = root / "audio"
    reference_dir = root / "references"
    audio_dir.mkdir()
    reference_dir.mkdir()
    audio = audio_dir / "coding_001.wav"
    reference = reference_dir / "coding_001.txt"
    _write_wav(audio)
    reference.write_text("controlled synthetic reference\n", encoding="utf-8")
    bindings = {
        "schema_version": 1,
        "bindings_id": "synthetic-bindings",
        "public_manifest_sha256": _sha256(dataset),
        "samples": [
            {
                "sample_id": "coding_001",
                "audio_relative_path": "audio/coding_001.wav",
                "audio_sha256": _sha256(audio),
                "reference_relative_path": "references/coding_001.txt",
                "reference_sha256": _sha256(reference),
                "rights_status": "approved",
                "consent_status": "synthetic",
            }
        ],
    }
    path = root / "bindings.json"
    path.write_text(json.dumps(bindings, ensure_ascii=False), encoding="utf-8")
    return path


def _write_wav(path: Path) -> None:
    with wave.open(str(path), "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(16000)
        audio.writeframes(struct.pack("<h", 0) * 16000)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


if __name__ == "__main__":
    unittest.main()
