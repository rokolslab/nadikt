"""Linux/WSL process-tree measurement placeholders for spawned workers."""

from __future__ import annotations

from dataclasses import dataclass

from pathlib import Path


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


def sample_process(pid: int, proc_root: Path = Path("/proc")) -> LinuxProcSample:
    """Read safe aggregate process counters without argv/environ/cwd."""

    stat_path = proc_root / str(pid) / "stat"
    statm_path = proc_root / str(pid) / "statm"
    start_time_ticks = None
    rss_kib = None
    if stat_path.is_file():
        parts = stat_path.read_text(encoding="utf-8", errors="replace").split()
        if len(parts) > 21:
            start_time_ticks = int(parts[21])
    if statm_path.is_file():
        parts = statm_path.read_text(encoding="utf-8", errors="replace").split()
        if len(parts) > 1:
            rss_kib = int(parts[1]) * 4
    return LinuxProcSample(pid=pid, start_time_ticks=start_time_ticks, rss_kib=rss_kib)


__all__ = ["LinuxProcSample", "sample_process"]
