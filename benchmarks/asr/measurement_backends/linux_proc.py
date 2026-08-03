"""Linux/WSL process-tree measurement for spawned workers."""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from pathlib import Path

from ..logging_config import get_logger
from ..resource_measurement import ProcessIdentity, ResourcePointSample

LOGGER = get_logger(__name__)
BACKEND = "linux-proc"
BACKEND_VERSION = "linux-proc-v2"


@dataclass(frozen=True)
class LinuxProcSample:
    pid: int
    start_time_ticks: int | None
    rss_kib: int | None

    def to_json(self) -> dict[str, object]:
        return {
            "pid": self.pid,
            "start_time_ticks_present": self.start_time_ticks is not None,
            "rss_kib": self.rss_kib,
        }


@dataclass(frozen=True)
class _ProcRecord:
    pid: int
    ppid: int
    start_time_ticks: int
    user_ticks: int
    system_ticks: int
    rss_pages: int | None


def sample_process(pid: int, proc_root: Path = Path("/proc")) -> LinuxProcSample:
    """Read safe aggregate process counters without argv/environ/cwd."""

    record = _read_process_record(pid, proc_root=proc_root, page_size_kib=_page_size_kib())
    start_time_ticks = record.start_time_ticks if record is not None else None
    rss_kib = record.rss_pages * _page_size_kib() if record is not None and record.rss_pages is not None else None
    return LinuxProcSample(pid=pid, start_time_ticks=start_time_ticks, rss_kib=rss_kib)


class LinuxProcTreeSampler:
    """Sample safe resource counters for a root process and descendants."""

    backend = BACKEND
    backend_version = BACKEND_VERSION

    def __init__(self, *, proc_root: Path = Path("/proc"), clock_ticks: int | None = None, page_size_kib: int | None = None) -> None:
        self._proc_root = proc_root
        self._clock_ticks = clock_ticks or os.sysconf("SC_CLK_TCK")
        self._page_size_kib = page_size_kib or _page_size_kib()

    def sample(self, pid: int) -> ResourcePointSample:
        LOGGER.debug("linux_proc_sample_start", extra={"backend": self.backend, "backend_version": self.backend_version})
        records = _read_all_process_records(self._proc_root, self._page_size_kib)
        root = records.get(pid)
        if root is None:
            LOGGER.warning("linux_proc_sample_missed", extra={"backend": self.backend, "reason_code": "root_missing"})
            return ResourcePointSample(
                monotonic_seconds=time.monotonic(),
                identity=ProcessIdentity(pid, None),
                user_cpu_seconds=None,
                system_cpu_seconds=None,
                rss_kib=None,
                process_count=0,
                status="missed",
                missed_reason="root_missing",
            )
        descendants = _descendant_records(pid, records)
        user_ticks = sum(record.user_ticks for record in descendants)
        system_ticks = sum(record.system_ticks for record in descendants)
        rss_kib_values = [record.rss_pages * self._page_size_kib for record in descendants if record.rss_pages is not None]
        sample = ResourcePointSample(
            monotonic_seconds=time.monotonic(),
            identity=ProcessIdentity(pid, root.start_time_ticks),
            user_cpu_seconds=user_ticks / self._clock_ticks,
            system_cpu_seconds=system_ticks / self._clock_ticks,
            rss_kib=sum(rss_kib_values) if rss_kib_values else None,
            process_count=len(descendants),
        )
        LOGGER.debug("linux_proc_sample_done", extra={"backend": self.backend, "process_count": sample.process_count, "status": sample.status})
        return sample


def _read_all_process_records(proc_root: Path, page_size_kib: int) -> dict[int, _ProcRecord]:
    records: dict[int, _ProcRecord] = {}
    try:
        entries = tuple(proc_root.iterdir())
    except OSError:
        return records
    for entry in entries:
        if not entry.name.isdecimal():
            continue
        record = _read_process_record(int(entry.name), proc_root=proc_root, page_size_kib=page_size_kib)
        if record is not None:
            records[record.pid] = record
    return records


def _read_process_record(pid: int, *, proc_root: Path, page_size_kib: int) -> _ProcRecord | None:
    stat_path = proc_root / str(pid) / "stat"
    statm_path = proc_root / str(pid) / "statm"
    try:
        stat_text = stat_path.read_text(encoding="utf-8", errors="replace")
        record = _parse_stat(stat_text)
    except (OSError, ValueError):
        return None
    rss_pages = None
    try:
        statm_parts = statm_path.read_text(encoding="utf-8", errors="replace").split()
        if len(statm_parts) > 1:
            rss_pages = int(statm_parts[1])
    except (OSError, ValueError):
        rss_pages = None
    return _ProcRecord(record.pid, record.ppid, record.start_time_ticks, record.user_ticks, record.system_ticks, rss_pages)


def _parse_stat(text: str) -> _ProcRecord:
    left = text.find("(")
    right = text.rfind(")")
    if left < 1 or right <= left:
        raise ValueError("linux_proc_malformed_stat")
    pid = int(text[:left].strip())
    fields = text[right + 2 :].split()
    if len(fields) <= 19:
        raise ValueError("linux_proc_truncated_stat")
    return _ProcRecord(
        pid=pid,
        ppid=int(fields[1]),
        start_time_ticks=int(fields[19]),
        user_ticks=int(fields[11]),
        system_ticks=int(fields[12]),
        rss_pages=None,
    )


def _descendant_records(root_pid: int, records: dict[int, _ProcRecord]) -> tuple[_ProcRecord, ...]:
    children: dict[int, list[int]] = {}
    for record in records.values():
        children.setdefault(record.ppid, []).append(record.pid)
    selected: list[_ProcRecord] = []
    stack = [root_pid]
    seen: set[int] = set()
    while stack:
        pid = stack.pop()
        if pid in seen:
            continue
        seen.add(pid)
        record = records.get(pid)
        if record is None:
            continue
        selected.append(record)
        stack.extend(children.get(pid, ()))
    return tuple(selected)


def _page_size_kib() -> int:
    try:
        return int(os.sysconf("SC_PAGE_SIZE")) // 1024
    except (OSError, ValueError):
        return 4


__all__ = ["LinuxProcSample", "LinuxProcTreeSampler", "sample_process"]
