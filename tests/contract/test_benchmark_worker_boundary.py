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

from benchmarks.asr.worker_protocol import WorkerPhase, WorkerRequest, WorkerResult, loads_result, new_nonce


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
            offline_evidence={"evidence_id": "offline-evidence-abc", "status": "NOT VERIFIED"},
        )

        rendered = json.dumps(result.to_json(), ensure_ascii=False)

        self.assertIn("transcribe_probe", rendered)
        self.assertNotIn("audio_path", rendered)
        self.assertNotIn("reference_text", rendered)
        self.assertNotIn("hypothesis", rendered)

    def test_worker_supervisor_uses_stdin_not_private_paths_in_argv(self) -> None:
        source = (ROOT / "benchmarks/asr/worker_supervisor.py").read_text(encoding="utf-8")

        self.assertIn("input=request.to_worker_json()", source)
        self.assertIn('"-m", "benchmarks.asr.benchmark_worker"', source)
        self.assertNotIn("audio_file", source.partition("subprocess.run(")[2].partition(")")[0])

    def test_local_probe_default_factory_does_not_import_runtime_adapters_in_parent(self) -> None:
        source = (ROOT / "benchmarks/asr/local_model_probe.py").read_text(encoding="utf-8")

        default_factory_block = source.split("def _create_faster_whisper_probe", 1)[1]
        default_factory_block = default_factory_block.split("class _DomainEngineProbeAdapter", 1)[0]
        self.assertNotIn("nadikt.infrastructure.asr", default_factory_block)

    def test_integration_real_load_test_is_opt_in(self) -> None:
        path = ROOT / "tests/integration/test_real_local_asr_load.py"
        self.assertIn("NADIKT_REAL_ASR_ASSETS", path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
