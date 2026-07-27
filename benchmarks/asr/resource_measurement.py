"""Resource measurement primitives for ASR benchmark phases."""

from __future__ import annotations

import logging
import resource
import time
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Iterator

from .logging_config import get_logger

LOGGER = get_logger(__name__)


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
    usage_started = resource.getrusage(resource.RUSAGE_SELF)
    result: list[ResourceSnapshot] = []
    try:
        yield result
    finally:
        usage_done = resource.getrusage(resource.RUSAGE_SELF)
        snapshot = ResourceSnapshot(
            phase_id=phase_id,
            duration_seconds=time.perf_counter() - started,
            user_cpu_seconds=usage_done.ru_utime - usage_started.ru_utime,
            system_cpu_seconds=usage_done.ru_stime - usage_started.ru_stime,
            peak_rss_mib=_peak_rss_mib(usage_done.ru_maxrss),
            measurement_backend="python-resource-getrusage",
        )
        result.append(snapshot)
        LOGGER.info("resource_phase_done", extra=snapshot.safe_log_context())


def _peak_rss_mib(raw_ru_maxrss: int) -> float | None:
    if raw_ru_maxrss <= 0:
        return None
    # Linux reports ru_maxrss in KiB. Windows host acceptance must document its
    # own measurement backend separately.
    return round(raw_ru_maxrss / 1024, 3)
