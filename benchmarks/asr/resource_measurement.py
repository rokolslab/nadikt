"""Resource measurement primitives for ASR benchmark phases and workers."""

from __future__ import annotations

import math
import os
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Iterator, Protocol

try:
    import resource
except ImportError:  # pragma: no cover - exercised on non-POSIX hosts.
    resource = None  # type: ignore[assignment]

from .logging_config import get_logger

LOGGER = get_logger(__name__)

CPU_NORMALIZATION = "one_logical_cpu_100_percent"
RESOURCE_REPORT_VERSION = "resource-report-v1"
PHASE_RESOURCE_REPORT_VERSION = "phase-resource-report-v1"


@dataclass(frozen=True)
class ResourceSnapshot:
    phase_id: str
    duration_seconds: float
    user_cpu_seconds: float
    system_cpu_seconds: float
    peak_rss_mib: float | None
    measurement_backend: str

    def safe_log_context(self) -> dict[str, object]:
        return {
            "phase_id": self.phase_id,
            "duration_seconds": round(self.duration_seconds, 6),
            "user_cpu_seconds": round(self.user_cpu_seconds, 6),
            "system_cpu_seconds": round(self.system_cpu_seconds, 6),
            "peak_rss_mib": self.peak_rss_mib,
            "measurement_backend": self.measurement_backend,
        }


@contextmanager
def measure_phase(phase_id: str) -> Iterator[list[ResourceSnapshot]]:
    """Measure a phase with monotonic time and available process counters."""

    LOGGER.debug("resource_phase_start", extra={"phase_id": phase_id})
    started = time.perf_counter()
    usage_started = resource.getrusage(resource.RUSAGE_SELF) if resource is not None else None
    result: list[ResourceSnapshot] = []
    try:
        yield result
    finally:
        usage_done = resource.getrusage(resource.RUSAGE_SELF) if resource is not None else None
        snapshot = ResourceSnapshot(
            phase_id=phase_id,
            duration_seconds=time.perf_counter() - started,
            user_cpu_seconds=(usage_done.ru_utime - usage_started.ru_utime) if usage_started is not None and usage_done is not None else 0.0,
            system_cpu_seconds=(usage_done.ru_stime - usage_started.ru_stime) if usage_started is not None and usage_done is not None else 0.0,
            peak_rss_mib=_peak_rss_mib(usage_done.ru_maxrss) if usage_done is not None else None,
            measurement_backend="python-resource-getrusage" if resource is not None else "unavailable",
        )
        result.append(snapshot)
        LOGGER.info("resource_phase_done", extra=snapshot.safe_log_context())


def _peak_rss_mib(raw_ru_maxrss: int) -> float | None:
    if raw_ru_maxrss <= 0:
        return None
    # Linux reports ru_maxrss in KiB. Windows host acceptance must document its
    # own measurement backend separately.
    return round(raw_ru_maxrss / 1024, 3)


@dataclass(frozen=True)
class ProcessIdentity:
    """Private process identity used to reject PID reuse."""

    pid: int
    start_time_ticks: int | None

    def matches(self, other: "ProcessIdentity") -> bool:
        if self.pid != other.pid:
            return False
        if self.start_time_ticks is None or other.start_time_ticks is None:
            return True
        return self.start_time_ticks == other.start_time_ticks


@dataclass(frozen=True)
class ResourcePointSample:
    """A single safe process-tree resource snapshot owned by the supervisor."""

    monotonic_seconds: float
    identity: ProcessIdentity
    user_cpu_seconds: float | None
    system_cpu_seconds: float | None
    rss_kib: int | None
    process_count: int
    status: str = "ok"
    missed_reason: str | None = None

    def __post_init__(self) -> None:
        _validate_finite("monotonic_seconds", self.monotonic_seconds, allow_zero=True)
        if self.user_cpu_seconds is not None:
            _validate_finite("user_cpu_seconds", self.user_cpu_seconds, allow_zero=True)
        if self.system_cpu_seconds is not None:
            _validate_finite("system_cpu_seconds", self.system_cpu_seconds, allow_zero=True)
        if self.rss_kib is not None and self.rss_kib < 0:
            raise ValueError("resource_sample_negative_rss")
        if self.process_count < 0:
            raise ValueError("resource_sample_negative_process_count")

    @property
    def cpu_seconds(self) -> float | None:
        if self.user_cpu_seconds is None or self.system_cpu_seconds is None:
            return None
        return self.user_cpu_seconds + self.system_cpu_seconds

    def is_usable(self) -> bool:
        return self.status == "ok" and self.cpu_seconds is not None


class ResourceSampler(Protocol):
    """Supervisor-side sampler backend; workers never self-report resources."""

    backend: str
    backend_version: str

    def sample(self, pid: int) -> ResourcePointSample: ...


@dataclass(frozen=True)
class ResourceReport:
    """Publishable resource report with private process identity removed."""

    backend: str
    backend_version: str
    status: str
    sample_interval_ms: int
    cpu_normalization: str = CPU_NORMALIZATION
    duration_seconds: float | None = None
    sample_count: int = 0
    missed_sample_count: int = 0
    missed_reasons: tuple[str, ...] = field(default_factory=tuple)
    process_count_max: int | None = None
    user_cpu_seconds: float | None = None
    system_cpu_seconds: float | None = None
    cpu_avg_percent: float | None = None
    cpu_max_percent: float | None = None
    peak_rss_mib: float | None = None

    def to_json(self) -> dict[str, object]:
        return {
            "version": RESOURCE_REPORT_VERSION,
            "backend": self.backend,
            "backend_version": self.backend_version,
            "status": self.status,
            "sample_interval_ms": self.sample_interval_ms,
            "cpu_normalization": self.cpu_normalization,
            "duration_seconds": _round_or_none(self.duration_seconds, 6),
            "sample_count": self.sample_count,
            "missed_sample_count": self.missed_sample_count,
            "missed_reasons": list(self.missed_reasons),
            "process_count_max": self.process_count_max,
            "user_cpu_seconds": _round_or_none(self.user_cpu_seconds, 6),
            "system_cpu_seconds": _round_or_none(self.system_cpu_seconds, 6),
            "cpu_avg_percent": _round_or_none(self.cpu_avg_percent, 6),
            "cpu_max_percent": _round_or_none(self.cpu_max_percent, 6),
            "peak_rss_mib": _round_or_none(self.peak_rss_mib, 3),
        }

    def safe_log_context(self) -> dict[str, object]:
        return {
            "backend": self.backend,
            "backend_version": self.backend_version,
            "status": self.status,
            "sample_interval_ms": self.sample_interval_ms,
            "sample_count": self.sample_count,
            "missed_sample_count": self.missed_sample_count,
            "process_count_max": self.process_count_max,
            "duration_seconds": _round_or_none(self.duration_seconds, 6),
            "cpu_avg_percent": _round_or_none(self.cpu_avg_percent, 6),
            "cpu_max_percent": _round_or_none(self.cpu_max_percent, 6),
            "peak_rss_mib": _round_or_none(self.peak_rss_mib, 3),
        }

    @classmethod
    def unavailable(cls, backend: str, backend_version: str, sample_interval_ms: int, reason: str) -> "ResourceReport":
        LOGGER.warning("resource_report_unavailable", extra={"backend": backend, "backend_version": backend_version, "reason_code": reason})
        return cls(
            backend=backend,
            backend_version=backend_version,
            status="unavailable",
            sample_interval_ms=sample_interval_ms,
            missed_sample_count=1,
            missed_reasons=(reason,),
        )

    @classmethod
    def from_samples(
        cls,
        *,
        backend: str,
        backend_version: str,
        sample_interval_ms: int,
        samples: tuple[ResourcePointSample, ...],
        missed_reasons: tuple[str, ...] = (),
    ) -> "ResourceReport":
        usable = [sample for sample in samples if sample.is_usable()]
        missed = [sample for sample in samples if not sample.is_usable()]
        all_reasons = tuple(dict.fromkeys(reason for reason in (*missed_reasons, *[sample.missed_reason or sample.status for sample in missed]) if reason))
        if len(usable) < 2:
            status = "unavailable" if not usable else "partial"
            report = cls(
                backend=backend,
                backend_version=backend_version,
                status=status,
                sample_interval_ms=sample_interval_ms,
                sample_count=len(usable),
                missed_sample_count=len(missed) + len(missed_reasons),
                missed_reasons=all_reasons,
                process_count_max=max((sample.process_count for sample in usable), default=None),
                peak_rss_mib=_peak_kib_to_mib(usable),
            )
            LOGGER.warning("resource_report_incomplete", extra=report.safe_log_context())
            return report

        root_identity = usable[0].identity
        intervals: list[float] = []
        cpu_deltas: list[float] = []
        extra_missed = 0
        for previous, current in zip(usable, usable[1:]):
            if not root_identity.matches(current.identity):
                extra_missed += 1
                all_reasons = tuple(dict.fromkeys((*all_reasons, "pid_identity_changed")))
                continue
            wall_delta = current.monotonic_seconds - previous.monotonic_seconds
            cpu_delta = (current.cpu_seconds or 0.0) - (previous.cpu_seconds or 0.0)
            if wall_delta <= 0 or cpu_delta < 0:
                extra_missed += 1
                all_reasons = tuple(dict.fromkeys((*all_reasons, "invalid_counter_delta")))
                continue
            intervals.append(wall_delta)
            cpu_deltas.append(cpu_delta)

        if not intervals:
            report = cls(
                backend=backend,
                backend_version=backend_version,
                status="partial",
                sample_interval_ms=sample_interval_ms,
                sample_count=len(usable),
                missed_sample_count=len(missed) + len(missed_reasons) + extra_missed,
                missed_reasons=all_reasons,
                process_count_max=max((sample.process_count for sample in usable), default=None),
                peak_rss_mib=_peak_kib_to_mib(usable),
            )
            LOGGER.warning("resource_report_no_valid_deltas", extra=report.safe_log_context())
            return report

        duration_seconds = usable[-1].monotonic_seconds - usable[0].monotonic_seconds
        total_cpu = sum(cpu_deltas)
        interval_percents = [(cpu_delta / wall_delta) * 100.0 for cpu_delta, wall_delta in zip(cpu_deltas, intervals)]
        user_delta = (usable[-1].user_cpu_seconds or 0.0) - (usable[0].user_cpu_seconds or 0.0)
        system_delta = (usable[-1].system_cpu_seconds or 0.0) - (usable[0].system_cpu_seconds or 0.0)
        report = cls(
            backend=backend,
            backend_version=backend_version,
            status="ok" if not all_reasons and extra_missed == 0 else "partial",
            sample_interval_ms=sample_interval_ms,
            duration_seconds=duration_seconds,
            sample_count=len(usable),
            missed_sample_count=len(missed) + len(missed_reasons) + extra_missed,
            missed_reasons=all_reasons,
            process_count_max=max((sample.process_count for sample in usable), default=None),
            user_cpu_seconds=max(0.0, user_delta),
            system_cpu_seconds=max(0.0, system_delta),
            cpu_avg_percent=(total_cpu / sum(intervals)) * 100.0,
            cpu_max_percent=max(interval_percents),
            peak_rss_mib=_peak_kib_to_mib(usable),
        )
        LOGGER.info("resource_report_done", extra=report.safe_log_context())
        return report


@dataclass(frozen=True)
class PhaseResourceReport:
    """Safe phase-level resource coverage summary derived from supervisor samples."""

    phase_id: str
    status: str
    duration_ms: float
    sample_count: int
    missed_sample_count: int
    missed_reasons: tuple[str, ...] = field(default_factory=tuple)
    boundary_coverage: str = "unknown"
    maximum_gap_ms: float | None = None
    cpu_avg_percent: float | None = None
    cpu_max_percent: float | None = None
    sampled_peak_process_tree_rss_mib: float | None = None

    def to_json(self) -> dict[str, object]:
        return {
            "version": PHASE_RESOURCE_REPORT_VERSION,
            "phase_id": self.phase_id,
            "status": self.status,
            "duration_ms": round(self.duration_ms, 3),
            "sample_count": self.sample_count,
            "missed_sample_count": self.missed_sample_count,
            "missed_reasons": list(self.missed_reasons),
            "boundary_coverage": self.boundary_coverage,
            "maximum_gap_ms": _round_or_none(self.maximum_gap_ms, 3),
            "cpu_avg_percent": _round_or_none(self.cpu_avg_percent, 6),
            "cpu_max_percent": _round_or_none(self.cpu_max_percent, 6),
            "sampled_peak_process_tree_rss_mib": _round_or_none(self.sampled_peak_process_tree_rss_mib, 3),
        }


def phase_resource_report(phase_id: str, duration_ms: float, lifecycle_report: ResourceReport) -> PhaseResourceReport:
    """Build a bounded phase coverage report without private process identity."""

    duration = max(0.0, duration_ms)
    reasons: list[str] = []
    if duration < lifecycle_report.sample_interval_ms:
        reasons.append("phase_too_short")
    if lifecycle_report.status == "unavailable":
        reasons.extend(reason for reason in lifecycle_report.missed_reasons if reason)
        reasons.append("boundary_missing")
    status = "ok" if not reasons and lifecycle_report.status == "ok" else "partial"
    if lifecycle_report.status == "unavailable":
        status = "unavailable"
    report = PhaseResourceReport(
        phase_id=phase_id,
        status=status,
        duration_ms=duration,
        sample_count=lifecycle_report.sample_count if status != "unavailable" else 0,
        missed_sample_count=lifecycle_report.missed_sample_count + len(reasons),
        missed_reasons=tuple(dict.fromkeys(reasons)),
        boundary_coverage="covered" if status == "ok" else "not_covered",
        maximum_gap_ms=float(lifecycle_report.sample_interval_ms) if lifecycle_report.sample_count else None,
        cpu_avg_percent=lifecycle_report.cpu_avg_percent if status == "ok" else None,
        cpu_max_percent=lifecycle_report.cpu_max_percent if status == "ok" else None,
        sampled_peak_process_tree_rss_mib=lifecycle_report.peak_rss_mib if status != "unavailable" else None,
    )
    LOGGER.debug("phase_resource_report_done", extra={"phase_id": phase_id, "status": report.status, "missed_reason_count": len(report.missed_reasons)})
    return report


def create_default_resource_sampler() -> ResourceSampler | None:
    if os.name != "posix":
        return None
    try:
        from .measurement_backends.linux_proc import LinuxProcTreeSampler
    except Exception:
        LOGGER.warning("resource_sampler_backend_unavailable", extra={"backend": "linux-proc", "reason_code": "import_failed"})
        return None
    return LinuxProcTreeSampler()


def _validate_finite(name: str, value: float, *, allow_zero: bool) -> None:
    if not math.isfinite(value) or value < 0 or (value == 0 and not allow_zero):
        raise ValueError(f"resource_{name}_invalid")


def _round_or_none(value: float | None, digits: int) -> float | None:
    if value is None:
        return None
    if not math.isfinite(value) or value < 0:
        raise ValueError("resource_report_invalid_number")
    return round(value, digits)


def _peak_kib_to_mib(samples: list[ResourcePointSample]) -> float | None:
    values = [sample.rss_kib for sample in samples if sample.rss_kib is not None]
    if not values:
        return None
    return max(values) / 1024.0


__all__ = [
    "CPU_NORMALIZATION",
    "PHASE_RESOURCE_REPORT_VERSION",
    "ProcessIdentity",
    "PhaseResourceReport",
    "ResourcePointSample",
    "ResourceReport",
    "ResourceSampler",
    "ResourceSnapshot",
    "create_default_resource_sampler",
    "measure_phase",
    "phase_resource_report",
]
