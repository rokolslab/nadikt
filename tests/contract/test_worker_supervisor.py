from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from benchmarks.asr.resource_measurement import ProcessIdentity, ResourcePointSample
from benchmarks.asr.worker_protocol import WorkerRequest, WorkerResult
from benchmarks.asr.worker_supervisor import WorkerSupervisor


class WorkerSupervisorTest(unittest.TestCase):
    def test_supervisor_returns_worker_result_and_parent_resource_report(self) -> None:
        request = _request()
        process = _FakeProcess(WorkerResult(request.nonce, request.package_id, request.candidate_id, request.backend, "success").to_worker_json())
        sampler = _FakeSampler()

        result = WorkerSupervisor(
            timeout_seconds=1.0,
            sample_interval_seconds=100.0,
            sampler_factory=lambda: sampler,
            popen_factory=lambda *_args, **_kwargs: process,
        ).run(request)

        self.assertEqual("success", result.worker_result.worker_status)
        self.assertEqual("ok", result.resource_report.status)
        self.assertEqual("fake-sampler", result.resource_report.backend)
        self.assertEqual(["terminate:False", "kill:False"], process.events)
        self.assertEqual(request.to_worker_json(), process.input_seen)

    def test_timeout_terminates_then_kills_and_preserves_partial_report(self) -> None:
        request = _request()
        process = _TimeoutProcess(WorkerResult(request.nonce, request.package_id, request.candidate_id, request.backend, "fail").to_worker_json())

        result = WorkerSupervisor(
            timeout_seconds=1.0,
            terminate_grace_seconds=0.1,
            sample_interval_seconds=100.0,
            sampler_factory=lambda: _FakeSampler(),
            popen_factory=lambda *_args, **_kwargs: process,
        ).run(request)

        self.assertEqual("fail", result.worker_result.worker_status)
        self.assertEqual("partial", result.resource_report.status)
        self.assertIn("worker_timeout", result.resource_report.missed_reasons)
        self.assertTrue(process.terminated)
        self.assertTrue(process.killed)


class _FakeSampler:
    backend = "fake-sampler"
    backend_version = "v1"

    def __init__(self) -> None:
        self._index = 0

    def sample(self, pid: int) -> ResourcePointSample:
        self._index += 1
        return ResourcePointSample(
            monotonic_seconds=float(self._index),
            identity=ProcessIdentity(pid, 1000),
            user_cpu_seconds=float(self._index),
            system_cpu_seconds=0.0,
            rss_kib=1024 * self._index,
            process_count=1,
        )


class _FakeProcess:
    pid = 123

    def __init__(self, stdout: str) -> None:
        self._stdout = stdout
        self.input_seen: str | None = None
        self.terminated = False
        self.killed = False
        self.events: list[str] = []

    def communicate(self, input: str | None = None, timeout: float | None = None) -> tuple[str, str]:
        if input is not None:
            self.input_seen = input
        self.events.append(f"terminate:{self.terminated}")
        self.events.append(f"kill:{self.killed}")
        return self._stdout, ""

    def terminate(self) -> None:
        self.terminated = True

    def kill(self) -> None:
        self.killed = True


class _TimeoutProcess(_FakeProcess):
    def __init__(self, stdout: str) -> None:
        super().__init__(stdout)
        self._communicate_calls = 0

    def communicate(self, input: str | None = None, timeout: float | None = None) -> tuple[str, str]:
        self._communicate_calls += 1
        if input is not None:
            self.input_seen = input
        if self._communicate_calls <= 2:
            raise subprocess.TimeoutExpired(cmd="fake", timeout=timeout or 0.0)
        return self._stdout, ""


def _request() -> WorkerRequest:
    return WorkerRequest(
        nonce="nonce-1",
        package_id="package-a",
        candidate_id="candidate-a",
        backend="faster-whisper",
        package_dir=Path("/private/model"),
        capabilities={},
        inference_defaults={},
    )


if __name__ == "__main__":
    unittest.main()
