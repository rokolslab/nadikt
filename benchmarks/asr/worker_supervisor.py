"""Parent-side spawned worker supervisor for local ASR benchmark probes."""

from __future__ import annotations

import subprocess
import sys
import threading
import time
from dataclasses import dataclass, field
from typing import Callable

from .offline_evidence import OfflineEvidence, unverified_evidence
from .privacy_audit import audit_text_artifact
from .resource_measurement import ResourcePointSample, ResourceReport, ResourceSampler, create_default_resource_sampler
from .worker_protocol import SUPERVISOR_OUTCOMES, WorkerPhase, WorkerRepeatOutcome, WorkerRequest, WorkerRequestV2, WorkerResult, WorkerResultV2, loads_result, loads_result_v2

SamplerFactory = Callable[[], ResourceSampler | None]
PopenFactory = Callable[..., subprocess.Popen[str]]


@dataclass(frozen=True)
class SupervisorEvent:
    event: str
    outcome: str
    elapsed_ms: float

    def to_json(self) -> dict[str, object]:
        return {"event": self.event, "outcome": self.outcome, "elapsed_ms": round(self.elapsed_ms, 3)}


@dataclass(frozen=True)
class SupervisedWorkerResult:
    worker_result: WorkerResult | WorkerResultV2
    resource_report: ResourceReport
    offline_evidence: OfflineEvidence | None = None
    supervisor_outcome: str = "completed"
    timeline: tuple[SupervisorEvent, ...] = ()


@dataclass(frozen=True)
class WorkerSupervisor:
    timeout_seconds: float = 120.0
    sample_interval_seconds: float = 0.2
    terminate_grace_seconds: float = 5.0
    max_capture_bytes: int = 128 * 1024
    python_executable: str | None = None
    sampler_factory: SamplerFactory = create_default_resource_sampler
    popen_factory: PopenFactory = subprocess.Popen

    def run(self, request: WorkerRequest | WorkerRequestV2) -> SupervisedWorkerResult:
        timeline = _Timeline()
        try:
            process = self.popen_factory(
                [self.python_executable or sys.executable, "-m", "benchmarks.asr.benchmark_worker"],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            timeline.add("spawn", "completed")
        except Exception:
            timeline.add("spawn", "spawn_error")
            return SupervisedWorkerResult(
                _failure_worker_result(request, "fail", "spawn_error"),
                ResourceReport.unavailable("unavailable", "none", self._interval_ms(), "spawn_error"),
                unverified_evidence(request.nonce, reason="spawn_error_before_monitor"),
                "spawn_error",
                timeline.events,
            )
        try:
            sampler = self.sampler_factory()
        except Exception:
            sampler = None
            timeline.add("sampler", "unavailable")
        collector = _ResourceCollector(sampler, sample_interval_seconds=self.sample_interval_seconds)
        collector.start(int(getattr(process, "pid", 0) or 0))
        supervisor_outcome = "completed"
        stdout = ""
        stderr = ""
        try:
            stdout, stderr = process.communicate(input=request.to_worker_json(), timeout=self.timeout_seconds)
            timeline.add("communicate", "completed")
        except subprocess.TimeoutExpired:
            supervisor_outcome = "timeout"
            collector.note_missed("worker_timeout")
            timeline.add("communicate", "timeout")
            process.terminate()
            try:
                stdout, stderr = process.communicate(timeout=self.terminate_grace_seconds)
                collector.note_missed("worker_terminated")
                supervisor_outcome = "terminated"
                timeline.add("terminate", "terminated")
            except subprocess.TimeoutExpired:
                process.kill()
                stdout, stderr = process.communicate()
                collector.note_missed("worker_killed")
                supervisor_outcome = "killed"
                timeline.add("kill", "killed")
        resource_report = collector.finish()
        offline_evidence = unverified_evidence(request.nonce, reason="qualified_monitor_not_configured")
        timeline.add("resource_collection", resource_report.status)
        capture = _bounded_capture(stdout or "", stderr or "", self.max_capture_bytes)
        stdout = ""
        stderr = ""
        if capture.oversized:
            timeline.add("capture", "protocol_error")
            return SupervisedWorkerResult(_failure_worker_result(request, "protocol_error", "protocol_error"), resource_report, offline_evidence, "protocol_error", timeline.events)
        if capture.stderr.strip():
            timeline.add("capture", "privacy_error")
            return SupervisedWorkerResult(_failure_worker_result(request, "fail", "privacy_error"), resource_report, offline_evidence, "privacy_error", timeline.events)
        timeline.add("capture", "completed")
        audit = audit_text_artifact(capture.stdout + capture.stderr, canary=_worker_canary(request))
        if audit.has_violation:
            timeline.add("privacy_audit", "privacy_error")
            return SupervisedWorkerResult(_failure_worker_result(request, "fail", "privacy_error"), resource_report, offline_evidence, "privacy_error", timeline.events)
        timeline.add("privacy_audit", "completed")
        try:
            result = _loads_worker_result(capture.stdout)
        except Exception:
            timeline.add("parse", "protocol_error")
            return SupervisedWorkerResult(_failure_worker_result(request, "protocol_error", "protocol_error"), resource_report, offline_evidence, "protocol_error", timeline.events)
        capture = _CapturedText("", "", False)
        if result.nonce != request.nonce:
            timeline.add("nonce", "protocol_error")
            return SupervisedWorkerResult(_failure_worker_result(request, "protocol_error", "protocol_error"), resource_report, offline_evidence, "protocol_error", timeline.events)
        timeline.add("parse", "completed")
        return_code = getattr(process, "returncode", 0)
        if isinstance(return_code, int) and return_code != 0 and supervisor_outcome == "completed":
            supervisor_outcome = "nonzero_exit"
            timeline.add("exit_status", "nonzero_exit")
        return SupervisedWorkerResult(result, resource_report, offline_evidence, supervisor_outcome, timeline.events)

    def _interval_ms(self) -> int:
        return max(1, int(round(self.sample_interval_seconds * 1000)))


def _loads_worker_result(text: str) -> WorkerResult | WorkerResultV2:
    try:
        return loads_result_v2(text)
    except ValueError as error:
        if str(error) != "invalid_worker_protocol_version":
            raise
    return loads_result(text)


@dataclass(frozen=True)
class _CapturedText:
    stdout: str
    stderr: str
    oversized: bool


def _bounded_capture(stdout: str, stderr: str, max_capture_bytes: int) -> _CapturedText:
    stdout_bytes = stdout.encode("utf-8", errors="replace")
    stderr_bytes = stderr.encode("utf-8", errors="replace")
    if len(stdout_bytes) + len(stderr_bytes) > max_capture_bytes:
        return _CapturedText("", "", True)
    return _CapturedText(stdout, stderr, False)


def _worker_canary(request: WorkerRequest | WorkerRequestV2) -> str:
    return "NADIKT_CONTROLLED_CANARY_" + request.nonce[:12]


def _failure_worker_result(request: WorkerRequest | WorkerRequestV2, worker_status: str, outcome: str) -> WorkerResult | WorkerResultV2:
    phase = WorkerPhase("supervisor", "protocol_error" if outcome == "protocol_error" else "fail")
    if isinstance(request, WorkerRequestV2):
        return WorkerResultV2(
            nonce=request.nonce,
            package_id=request.package_id,
            candidate_id=request.candidate_id,
            backend=request.backend,
            worker_status=worker_status,
            repeat=WorkerRepeatOutcome(request.repeat.repeat_index, "fail", phases=(phase,), samples=()),
        )
    return WorkerResult(
        nonce=request.nonce,
        package_id=request.package_id,
        candidate_id=request.candidate_id,
        backend=request.backend,
        worker_status=worker_status,
        phases=(phase,),
    )


@dataclass
class _Timeline:
    started: float = field(default_factory=time.monotonic)
    _events: list[SupervisorEvent] = field(default_factory=list)

    @property
    def events(self) -> tuple[SupervisorEvent, ...]:
        return tuple(self._events)

    def add(self, event: str, outcome: str) -> None:
        safe_outcome = outcome if outcome in SUPERVISOR_OUTCOMES or outcome in {"ok", "partial", "unavailable"} else "completed"
        self._events.append(SupervisorEvent(event, safe_outcome, (time.monotonic() - self.started) * 1000))


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


__all__ = ["SUPERVISOR_OUTCOMES", "SupervisedWorkerResult", "SupervisorEvent", "WorkerSupervisor"]
