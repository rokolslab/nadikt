from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from benchmarks.asr.measurement_backends.linux_proc import LinuxProcTreeSampler, sample_process
from benchmarks.asr.resource_measurement import ProcessIdentity, ResourcePointSample, ResourceReport


class ResourceMeasurementTest(unittest.TestCase):
    def test_resource_report_aggregates_cpu_and_peak_rss_without_identity(self) -> None:
        samples = (
            ResourcePointSample(10.0, ProcessIdentity(123, 1000), 1.0, 0.5, 1024, 1),
            ResourcePointSample(12.0, ProcessIdentity(123, 1000), 2.0, 1.0, 4096, 2),
            ResourcePointSample(14.0, ProcessIdentity(123, 1000), 5.0, 1.0, 2048, 1),
        )

        report = ResourceReport.from_samples(backend="fake", backend_version="v1", sample_interval_ms=200, samples=samples)
        rendered = repr(report.to_json())

        self.assertEqual("ok", report.status)
        self.assertEqual(3, report.sample_count)
        self.assertEqual(112.5, report.cpu_avg_percent)
        self.assertEqual(150.0, report.cpu_max_percent)
        self.assertEqual(4.0, report.peak_rss_mib)
        self.assertNotIn("123", rendered)
        self.assertNotIn("1000", rendered)

    def test_resource_report_marks_identity_change_as_partial(self) -> None:
        samples = (
            ResourcePointSample(1.0, ProcessIdentity(123, 1000), 1.0, 0.0, 1024, 1),
            ResourcePointSample(2.0, ProcessIdentity(123, 2000), 2.0, 0.0, 1024, 1),
        )

        report = ResourceReport.from_samples(backend="fake", backend_version="v1", sample_interval_ms=100, samples=samples)

        self.assertEqual("partial", report.status)
        self.assertIn("pid_identity_changed", report.missed_reasons)
        self.assertIsNone(report.cpu_avg_percent)

    def test_resource_report_unavailable_uses_none_not_zero_metrics(self) -> None:
        report = ResourceReport.unavailable("fake", "v1", 100, "unsupported_platform")

        self.assertEqual("unavailable", report.status)
        self.assertIsNone(report.cpu_avg_percent)
        self.assertIsNone(report.peak_rss_mib)
        self.assertEqual(1, report.missed_sample_count)

    def test_linux_proc_sampler_does_not_read_argv_or_environment(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            proc_root = Path(temp_dir)
            process = proc_root / str(os.getpid())
            process.mkdir()
            (process / "stat").write_text(_stat(os.getpid(), 0, 1, 2, 12345), encoding="utf-8")
            (process / "statm").write_text("1 2 3", encoding="utf-8")
            (process / "cmdline").write_text("secret-argv", encoding="utf-8")
            (process / "environ").write_text("SECRET=1", encoding="utf-8")

            sample = sample_process(os.getpid(), proc_root=proc_root)
            rendered = repr(sample.to_json())

        self.assertIn("rss_kib", rendered)
        self.assertNotIn("secret-argv", rendered)
        self.assertNotIn("SECRET", rendered)

    def test_linux_proc_tree_sampler_aggregates_root_and_descendants(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            proc_root = Path(temp_dir)
            _write_proc(proc_root, 10, 1, user_ticks=100, system_ticks=50, start_time=1000, rss_pages=3)
            _write_proc(proc_root, 11, 10, user_ticks=20, system_ticks=10, start_time=1100, rss_pages=7)
            _write_proc(proc_root, 12, 1, user_ticks=999, system_ticks=999, start_time=1200, rss_pages=99)
            sampler = LinuxProcTreeSampler(proc_root=proc_root, clock_ticks=100, page_size_kib=8)

            with patch("benchmarks.asr.measurement_backends.linux_proc.time.monotonic", return_value=42.0):
                sample = sampler.sample(10)

        self.assertEqual(ProcessIdentity(10, 1000), sample.identity)
        self.assertEqual(2, sample.process_count)
        self.assertEqual(1.2, sample.user_cpu_seconds)
        self.assertEqual(0.6, sample.system_cpu_seconds)
        self.assertEqual(80, sample.rss_kib)

    def test_linux_proc_tree_sampler_handles_process_names_with_parentheses(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            proc_root = Path(temp_dir)
            process = proc_root / "10"
            process.mkdir()
            (process / "stat").write_text(_stat(10, 1, 3, 4, 1000, comm="(worker name)"), encoding="utf-8")
            (process / "statm").write_text("1 1", encoding="utf-8")

            sample = LinuxProcTreeSampler(proc_root=proc_root, clock_ticks=100, page_size_kib=4).sample(10)

        self.assertEqual(0.03, sample.user_cpu_seconds)
        self.assertEqual(0.04, sample.system_cpu_seconds)

    def test_linux_proc_tree_sampler_marks_missing_root_as_missed(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            sample = LinuxProcTreeSampler(proc_root=Path(temp_dir), clock_ticks=100, page_size_kib=4).sample(10)

        self.assertEqual("missed", sample.status)
        self.assertEqual("root_missing", sample.missed_reason)
        self.assertIsNone(sample.user_cpu_seconds)


def _write_proc(proc_root: Path, pid: int, ppid: int, *, user_ticks: int, system_ticks: int, start_time: int, rss_pages: int) -> None:
    process = proc_root / str(pid)
    process.mkdir()
    (process / "stat").write_text(_stat(pid, ppid, user_ticks, system_ticks, start_time), encoding="utf-8")
    (process / "statm").write_text(f"1 {rss_pages} 0", encoding="utf-8")


def _stat(pid: int, ppid: int, user_ticks: int, system_ticks: int, start_time: int, *, comm: str = "python") -> str:
    fields = ["R", str(ppid)] + ["0"] * 9 + [str(user_ticks), str(system_ticks)] + ["0"] * 6 + [str(start_time), "0"]
    return f"{pid} ({comm}) " + " ".join(fields)


if __name__ == "__main__":
    unittest.main()
