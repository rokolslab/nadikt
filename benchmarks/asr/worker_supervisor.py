"""Parent-side spawned worker supervisor for local ASR benchmark probes."""

from __future__ import annotations

import subprocess
import sys
import threading
from dataclasses import dataclass, field
from typing import Callable

from .privacy_audit import audit_text_artifact
from .resource_measurement import ResourcePointSample, ResourceReport, ResourceSampler, create_default_resource_sampler
from .worker_protocol import WorkerRequest, WorkerRequestV2, WorkerResult, WorkerResultV2, loads_result, loads_result_v2

SamplerFactory = Callable[[], ResourceSampler | None]
PopenFactory = Callable[..., subprocess.Popen[str]]


@dataclass(frozen=True)
class SupervisedWorkerResult:
    worker_result: WorkerResult | WorkerResultV2
    resource_report: ResourceReport


@dataclass(frozen=True)
class WorkerSupervisor:
    timeout_seconds: float = 120.0
    sample_interval_seconds: float = 0.2
    terminate_grace_seconds: float = 5.0
    sampler_factory: SamplerFactory = create_default_resource_sampler
    popen_factory: PopenFactory = subprocess.Popen

    def run(self, request: WorkerRequest | WorkerRequestV2) -> SupervisedWorkerResult:
        process = self.popen_factory(
            [sys.executable, "-m", "benchmarks.asr.benchmark_worker"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        sampler = self.sampler_factory()
        collector = _ResourceCollector(sampler, sample_interval_seconds=self.sample_interval_seconds)
        collector.start(int(getattr(process, "pid", 0) or 0))
        try:
            stdout, stderr = process.communicate(input=request.to_worker_json(), timeout=self.timeout_seconds)
        except subprocess.TimeoutExpired:
            collector.note_missed("worker_timeout")
            process.terminate()
            try:
                stdout, stderr = process.communicate(timeout=self.terminate_grace_seconds)
                collector.note_missed("worker_terminated")
            except subprocess.TimeoutExpired:
                process.kill()
                stdout, stderr = process.communicate()
                collector.note_missed("worker_killed")
        resource_report = collector.finish()
        audit = audit_text_artifact((stdout or "") + (stderr or ""), canary="NADIKT_CONTROLLED_CANARY")
        if audit.canary_present or audit.forbidden_payload_count:
            raise ValueError("worker_output_privacy_violation")
        result = _loads_worker_result(stdout or "")
        if result.nonce != request.nonce:
            raise ValueError("worker_result_nonce_mismatch")
        return SupervisedWorkerResult(result, resource_report)


def _loads_worker_result(text: str) -> WorkerResult | WorkerResultV2:
    try:
        return loads_result_v2(text)
    except ValueError as error:
        if str(error) != "invalid_worker_protocol_version":
            raise
    return loads_result(text)


@dataclass
class _ResourceCollector:
    sampler: ResourceSampler | None
    sample_interval_seconds: float
    _pid: int = 0
    _samples: list[ResourcePointSample] = field(default_factory=list)
    _missed_reasons: list[str] = field(default_factory=list)
    _stop_event: threading.Event = field(default_factory=threading.Event)
    _lock: threading.Lock = field(default_factory=threading.Lock)
    _thread: threading.Thread | None = None

    def start(self, pid: int) -> None:
        self._pid = pid
        if self.sampler is None or pid <= 0:
            self.note_missed("sampler_unavailable" if self.sampler is None else "pid_unavailable")
            return
        self._collect_once()
        self._thread = threading.Thread(target=self._run, name="nadikt-asr-resource-sampler", daemon=True)
        self._thread.start()

    def note_missed(self, reason: str) -> None:
        with self._lock:
            self._missed_reasons.append(reason)

    def finish(self) -> ResourceReport:
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=max(self.sample_interval_seconds * 2, 0.1))
        if self.sampler is None:
            return ResourceReport.unavailable("unavailable", "none", self._interval_ms(), "sampler_unavailable")
        if self._pid <= 0:
            return ResourceReport.unavailable(self.sampler.backend, self.sampler.backend_version, self._interval_ms(), "pid_unavailable")
        self._collect_once()
        with self._lock:
            samples = tuple(self._samples)
            missed_reasons = tuple(self._missed_reasons)
        return ResourceReport.from_samples(
            backend=self.sampler.backend,
            backend_version=self.sampler.backend_version,
            sample_interval_ms=self._interval_ms(),
            samples=samples,
            missed_reasons=missed_reasons,
        )

    def _run(self) -> None:
        while not self._stop_event.wait(self.sample_interval_seconds):
            self._collect_once()

    def _collect_once(self) -> None:
        if self.sampler is None or self._pid <= 0:
            return
        try:
            sample = self.sampler.sample(self._pid)
        except Exception:
            self.note_missed("sampler_exception")
            return
        with self._lock:
            self._samples.append(sample)

    def _interval_ms(self) -> int:
        return max(1, int(round(self.sample_interval_seconds * 1000)))


__all__ = ["SupervisedWorkerResult", "WorkerSupervisor"]
