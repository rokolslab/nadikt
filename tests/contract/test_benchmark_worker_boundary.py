from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from benchmarks.asr.worker_protocol import (
    WorkerMetricResult,
    WorkerMetricDiagnostic,
    WorkerPhase,
    WorkerRepeatOutcome,
    WorkerRepeatRequest,
    WorkerRequest,
    WorkerRequestV2,
    WorkerResult,
    WorkerResultV2,
    WorkerSampleOutcome,
    WorkerSampleRequest,
    loads_request_v2,
    loads_result,
    loads_result_v2,
    new_nonce,
)
from benchmarks.asr import benchmark_worker


class BenchmarkWorkerBoundaryTest(unittest.TestCase):
    def test_worker_request_repr_redacts_private_paths(self) -> None:
        request = WorkerRequest(
            nonce=new_nonce(),
            package_id="package-a",
            candidate_id="candidate-a",
            backend="faster-whisper",
            package_dir=Path("/private/model/root"),
            capabilities={"languages": ["ru"], "max_segment_seconds": 25.0},
            inference_defaults={"beam_size": 5},
            audio_file=Path("/private/audio/client.wav"),
            duration_seconds=1.0,
        )

        rendered = repr(request)

        self.assertNotIn("/private/model", rendered)
        self.assertNotIn("client.wav", rendered)
        self.assertIn("audio_provided=True", rendered)

    def test_worker_result_rejects_unknown_fields(self) -> None:
        payload = WorkerResult(
            nonce="abc",
            package_id="package-a",
            candidate_id="candidate-a",
            backend="faster-whisper",
            worker_status="success",
            phases=(WorkerPhase("load", "success"),),
        ).to_json()
        payload["transcript_text"] = "secret"

        with self.assertRaisesRegex(ValueError, "worker_result_unknown_fields"):
            loads_result(json.dumps(payload))

    def test_worker_result_json_contains_only_safe_fields(self) -> None:
        result = WorkerResult(
            nonce="abc",
            package_id="package-a",
            candidate_id="candidate-a",
            backend="gigaam",
            worker_status="success",
            phases=(WorkerPhase("transcribe_probe", "success", 1.25, segment_id=0),),
            quality_metrics={"wer": {"metric_name": "wer", "value": 0.25, "numerator": 1, "denominator": 4, "status": "ok"}},
            offline_evidence={"evidence_id": "offline-evidence-abc", "status": "NOT VERIFIED"},
        )

        rendered = json.dumps(result.to_json(), ensure_ascii=False)

        self.assertIn("transcribe_probe", rendered)
        self.assertIn("quality_metrics", rendered)
        self.assertNotIn("audio_path", rendered)
        self.assertNotIn("reference_text", rendered)
        self.assertNotIn("hypothesis", rendered)

    def test_worker_supervisor_uses_stdin_not_private_paths_in_argv(self) -> None:
        source = (ROOT / "benchmarks/asr/worker_supervisor.py").read_text(encoding="utf-8")

        self.assertIn("process.communicate(input=request.to_worker_json()", source)
        self.assertIn('"-m", "benchmarks.asr.benchmark_worker"', source)
        popen_block = source.partition("self.popen_factory(")[2].partition(")\n        sampler")[0]
        self.assertNotIn("audio_file", popen_block)

    def test_worker_result_does_not_accept_worker_declared_resources(self) -> None:
        payload = WorkerResult(
            nonce="abc",
            package_id="package-a",
            candidate_id="candidate-a",
            backend="faster-whisper",
            worker_status="success",
        ).to_json()
        payload["resource_report"] = {"cpu_avg_percent": 10.0}

        with self.assertRaisesRegex(ValueError, "worker_result_unknown_fields"):
            loads_result(json.dumps(payload))

    def test_worker_request_v2_round_trips_repeat_with_warmup_and_scored_samples(self) -> None:
        request = WorkerRequestV2(
            nonce="nonce-v2",
            package_id="package-a",
            candidate_id="candidate-a",
            backend="faster-whisper",
            package_dir=Path("/private/model"),
            capabilities={"languages": ["ru"]},
            inference_defaults={"beam_size": 5},
            repeat=WorkerRepeatRequest(
                repeat_index=0,
                warmup_sample=WorkerSampleRequest(
                    sample_id="warmup_001",
                    category="warmup",
                    audio_file=Path("/private/audio/warmup.wav"),
                    reference_file=None,
                    duration_seconds=5.0,
                    scored=False,
                ),
                scored_samples=(
                    WorkerSampleRequest(
                        sample_id="ru_short_001",
                        category="ru_short",
                        audio_file=Path("/private/audio/ru_short.wav"),
                        reference_file=Path("/private/references/ru_short.txt"),
                        duration_seconds=12.0,
                        scored=True,
                    ),
                ),
            ),
        )

        loaded = loads_request_v2(request.to_worker_json())

        self.assertEqual("nonce-v2", loaded.nonce)
        self.assertEqual(0, loaded.repeat.repeat_index)
        self.assertFalse(loaded.repeat.warmup_sample.scored)
        self.assertEqual("ru_short_001", loaded.repeat.scored_samples[0].sample_id)
        self.assertNotIn("warmup.wav", repr(loaded))

    def test_worker_request_v2_rejects_unknown_version_and_bad_scored_flag(self) -> None:
        request = WorkerRequestV2(
            nonce="nonce-v2",
            package_id="package-a",
            candidate_id="candidate-a",
            backend="faster-whisper",
            package_dir=Path("/private/model"),
            capabilities={},
            inference_defaults={},
            repeat=WorkerRepeatRequest(
                repeat_index=0,
                warmup_sample=WorkerSampleRequest("warmup", "warmup", Path("/private/w.wav"), None, 1.0, False),
                scored_samples=(WorkerSampleRequest("sample", "ru_short", Path("/private/s.wav"), None, 1.0, True),),
            ),
        ).to_worker_json()
        payload = json.loads(request)
        payload["schema_version"] = 999

        with self.assertRaisesRegex(ValueError, "invalid_worker_protocol_version"):
            loads_request_v2(json.dumps(payload))

        payload = json.loads(request)
        payload["repeat"]["warmup_sample"]["scored"] = True
        with self.assertRaisesRegex(ValueError, "worker_sample_scored_mismatch"):
            loads_request_v2(json.dumps(payload))

    def test_worker_result_v2_contains_typed_repeat_sample_and_metrics(self) -> None:
        result = WorkerResultV2(
            nonce="nonce-v2",
            package_id="package-a",
            candidate_id="candidate-a",
            backend="faster-whisper",
            worker_status="success",
            repeat=WorkerRepeatOutcome(
                repeat_index=1,
                outcome="success",
                phases=(WorkerPhase("load", "success", 10.0),),
                samples=(
                    WorkerSampleOutcome(
                        sample_id="ru_short_001",
                        category="ru_short",
                        scored=True,
                        outcome="success",
                        phases=(WorkerPhase("transcribe", "success", 20.0),),
                        metrics=(WorkerMetricResult("wer", "quality-metrics-v2", 0.25, 1, 4, "ok"),),
                    ),
                ),
            ),
        )

        loaded = loads_result_v2(result.to_worker_json())

        self.assertEqual("success", loaded.worker_status)
        self.assertEqual("quality-metrics-v2", loaded.repeat.samples[0].metrics[0].metric_version)
        self.assertNotIn("quality_metrics", json.dumps(result.to_json(), ensure_ascii=False))

    def test_worker_result_v2_rejects_unknown_fields_and_non_finite_values(self) -> None:
        result = WorkerResultV2(
            nonce="nonce-v2",
            package_id="package-a",
            candidate_id="candidate-a",
            backend="faster-whisper",
            worker_status="success",
            repeat=WorkerRepeatOutcome(0, "success"),
        ).to_json()
        result["repeat"]["samples"] = []
        result["repeat"]["phase_outcomes"] = []
        result["repeat"]["private_path"] = "/private/audio.wav"

        with self.assertRaisesRegex(ValueError, "worker_repeat_unknown_fields"):
            loads_result_v2(json.dumps(result))

        result = WorkerResultV2(
            nonce="nonce-v2",
            package_id="package-a",
            candidate_id="candidate-a",
            backend="faster-whisper",
            worker_status="success",
            repeat=WorkerRepeatOutcome(0, "success", phases=(WorkerPhase("load", "success", float("nan")),)),
        )
        with self.assertRaisesRegex(ValueError, "worker_message_non_finite_number"):
            result.to_worker_json()

    def test_worker_v2_runs_one_repeat_lifecycle_with_warmup_excluded_from_metrics(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            warmup_audio = root / "warmup.wav"
            scored_audio = root / "scored.wav"
            reference = root / "reference.txt"
            warmup_audio.write_bytes(b"synthetic")
            scored_audio.write_bytes(b"synthetic")
            reference.write_text("hello API", encoding="utf-8")
            request = WorkerRequestV2(
                nonce="nonce-v2",
                package_id="package-a",
                candidate_id="candidate-a",
                backend="faster-whisper",
                package_dir=root / "model",
                capabilities={"languages": ["ru"]},
                inference_defaults={},
                repeat=WorkerRepeatRequest(
                    repeat_index=2,
                    warmup_sample=WorkerSampleRequest("warmup_001", "warmup", warmup_audio, None, 1.0, False),
                    scored_samples=(WorkerSampleRequest("scored_001", "ru_coding_terms", scored_audio, reference, 1.0, True, expected_english_terms=("API",)),),
                ),
            )
            engine = _FakeEngine()

            with patch("benchmarks.asr.benchmark_worker._engine_from_request", return_value=engine):
                result = benchmark_worker.run_worker(request)

        self.assertIsInstance(result, WorkerResultV2)
        self.assertEqual("success", result.worker_status)
        self.assertEqual(["load", "readiness", "close"], [phase.phase for phase in result.repeat.phases])
        self.assertEqual(["warmup_001", "scored_001"], [sample.sample_id for sample in result.repeat.samples])
        self.assertEqual([], list(result.repeat.samples[0].metrics))
        self.assertEqual(["wer", "cer", "english_term_accuracy", "latin_preservation_rate", "coding_term_accuracy"], [metric.metric_name for metric in result.repeat.samples[1].metrics])
        self.assertEqual(["load", "is_ready", "warmup:warmup_001", "transcribe:scored_001", "close"], engine.events)

    def test_worker_metrics_prefer_rich_coding_terms_for_english_and_latin_counts(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            audio = root / "scored.wav"
            reference = root / "reference.txt"
            audio.write_bytes(b"synthetic")
            reference.write_text("synthetic reference", encoding="utf-8")
            sample = WorkerSampleRequest(
                sample_id="scored_001",
                category="ru_coding_terms",
                audio_file=audio,
                reference_file=reference,
                duration_seconds=1.0,
                scored=True,
                expected_english_terms=("legacy-only",),
                expected_coding_terms=(
                    {"canonical": "FastAPI route", "accepted_variants": ["FastAPI route", "Fast API route"], "expected_occurrences": 2, "require_latin": True},
                    {"canonical": "локальный термин", "accepted_variants": ["локальный термин"], "expected_occurrences": 1, "require_latin": False},
                ),
            )

            metrics = {metric.metric_name: metric for metric in benchmark_worker._sample_metrics(sample, "Fast API route локальный термин")}

        self.assertEqual(2, metrics["english_term_accuracy"].numerator)
        self.assertEqual(3, metrics["english_term_accuracy"].denominator)
        self.assertEqual(1, metrics["latin_preservation_rate"].numerator)
        self.assertEqual(2, metrics["latin_preservation_rate"].denominator)

    def test_worker_result_v2_round_trips_safe_metric_diagnostics(self) -> None:
        result = WorkerResultV2(
            nonce="nonce-v2",
            package_id="package-a",
            candidate_id="candidate-a",
            backend="faster-whisper",
            worker_status="success",
            repeat=WorkerRepeatOutcome(
                0,
                "success",
                samples=(
                    WorkerSampleOutcome(
                        sample_id="sample_001",
                        category="ru_coding_terms",
                        scored=True,
                        outcome="success",
                        metric_diagnostics=(WorkerMetricDiagnostic("sample_001", "ru_coding_terms", "latin_preservation_rate", "raw", "ok", 0, 2, "latin_missing", 2),),
                    ),
                ),
            ),
        )

        loaded = loads_result_v2(result.to_worker_json())

        diagnostic = loaded.repeat.samples[0].metric_diagnostics[0]
        self.assertEqual("latin_missing", diagnostic.reason_code)
        self.assertEqual(2, diagnostic.count)
        self.assertNotIn("reference_text", json.dumps(result.to_json(), ensure_ascii=False))

    def test_worker_result_v2_accepts_safe_asr_failure_phase_codes(self) -> None:
        result = WorkerResultV2(
            nonce="nonce-v2",
            package_id="package-a",
            candidate_id="candidate-a",
            backend="gigaam",
            worker_status="fail",
            repeat=WorkerRepeatOutcome(0, "fail", phases=(WorkerPhase("load", "missing_package", 1.0),)),
        )

        loaded = loads_result_v2(result.to_worker_json())

        self.assertEqual("missing_package", loaded.repeat.phases[0].outcome)

    def test_local_probe_default_factory_does_not_import_runtime_adapters_in_parent(self) -> None:
        source = (ROOT / "benchmarks/asr/local_model_probe.py").read_text(encoding="utf-8")

        default_factory_block = source.split("def _create_faster_whisper_probe", 1)[1]
        default_factory_block = default_factory_block.split("class _DomainEngineProbeAdapter", 1)[0]
        self.assertNotIn("nadikt.infrastructure.asr", default_factory_block)

    def test_integration_real_load_test_is_opt_in(self) -> None:
        path = ROOT / "tests/integration/test_real_local_asr_load.py"
        self.assertIn("NADIKT_REAL_ASR_ASSETS", path.read_text(encoding="utf-8"))


class _FakeTranscript:
    text = "hello API"


class _FakeEngine:
    def __init__(self) -> None:
        self.events: list[str] = []

    def load(self, _options: object) -> None:
        self.events.append("load")

    def is_ready(self) -> bool:
        self.events.append("is_ready")
        return True

    def warm_up(self, segment: object) -> None:
        self.events.append(f"warmup:{segment.sample_id}")

    def transcribe_segment(self, segment: object) -> _FakeTranscript:
        self.events.append(f"transcribe:{segment.sample_id}")
        return _FakeTranscript()

    def close(self) -> None:
        self.events.append("close")


if __name__ == "__main__":
    unittest.main()
