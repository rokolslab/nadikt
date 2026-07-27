from __future__ import annotations

import contextlib
import hashlib
import io
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

from benchmarks.asr.local_model_probe import main, run_local_model_probe
from benchmarks.asr.probe_results import ProbePackageResult, ProbePhaseResult


class LocalModelProbeTest(unittest.TestCase):
    def test_probe_result_repr_and_json_are_redacted(self) -> None:
        result = ProbePackageResult(
            package_id="safe-package",
            candidate_id="safe-candidate",
            backend="faster-whisper",
            outcome="success",
            phases=(
                ProbePhaseResult(
                    "transcribe_probe",
                    "success",
                    details={"segment_count": 2, "audio_path": "/sensitive/user/audio.wav", "transcript_text": "secret"},
                ),
            ),
        )

        rendered = json.dumps(result.to_json(), ensure_ascii=False)

        self.assertNotIn("/sensitive/user/audio.wav", repr(result))
        self.assertNotIn("/sensitive/user/audio.wav", rendered)
        self.assertNotIn("secret", rendered)
        self.assertIn("segment_count", rendered)

    def test_runner_closes_one_engine_before_loading_next(self) -> None:
        events: list[str] = []
        active = {"loaded": False}
        test_case = self

        class FakeProbe:
            def load(self, _package_dir: Path, manifest: object) -> ProbePhaseResult:
                test_case.assertFalse(active["loaded"])
                active["loaded"] = True
                events.append(f"load:{manifest.package_id}")
                return ProbePhaseResult("load", "success")

            def is_ready(self) -> ProbePhaseResult:
                return ProbePhaseResult("readiness", "success")

            def warm_up(self) -> ProbePhaseResult:
                return ProbePhaseResult("warmup", "success")

            def transcribe(self, _audio_file: Path | None, _audio_label: str | None, **_kwargs: object) -> ProbePhaseResult:
                return ProbePhaseResult("transcribe_probe", "not_run")

            def close(self) -> ProbePhaseResult:
                active["loaded"] = False
                events.append("close")
                return ProbePhaseResult("close", "success")

        with tempfile.TemporaryDirectory() as temp_dir:
            models = _write_inventory(Path(temp_dir), package_count=2)
            summary = run_local_model_probe(models, backend_factories={"faster-whisper": FakeProbe})

        self.assertEqual("passed", summary["result"])
        self.assertEqual(["load:package-0", "close", "load:package-1", "close"], events)

    def test_missing_package_stops_before_backend_factory(self) -> None:
        called = {"factory": False}

        def factory() -> object:
            called["factory"] = True
            raise AssertionError("backend must not be created for missing package")

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            models = root / "inventory.json"
            models.write_text(json.dumps(_inventory_payload(package_count=1), ensure_ascii=False), encoding="utf-8")
            summary = run_local_model_probe(models, backend_factories={"faster-whisper": factory})

        self.assertEqual("passed_with_expected_missing_packages", summary["result"])
        self.assertFalse(called["factory"])

    def test_cli_summary_never_prints_audio_file_path(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            models = _write_inventory(root, package_count=1)
            sensitive_audio = root / "client-secret-audio.wav"
            sensitive_audio.write_bytes(b"not-real-audio")
            stdout = io.StringIO()

            with contextlib.redirect_stdout(stdout):
                exit_code = main([
                    "--models",
                    str(models),
                    "--dry-run",
                    "--audio-file",
                    str(sensitive_audio),
                    "--audio-label",
                    "controlled-audio-001",
                ])

        output = stdout.getvalue()
        self.assertEqual(0, exit_code)
        self.assertNotIn("client-secret-audio", output)
        self.assertIn("controlled-audio-001", output)


def _write_inventory(root: Path, *, package_count: int) -> Path:
    payload = _inventory_payload(package_count=package_count)
    for item in payload["packages"]:
        package_dir = root / item["package_path"]
        package_dir.mkdir(parents=True)
        critical_file = package_dir / "manifest.txt"
        critical_file.write_text("synthetic metadata only\n", encoding="utf-8")
        item["critical_files"][0]["sha256"] = hashlib.sha256(critical_file.read_bytes()).hexdigest()
    models = root / "inventory.json"
    models.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return models


def _inventory_payload(*, package_count: int) -> dict[str, object]:
    return {
        "schema_version": 1,
        "inventory_id": "synthetic-local-probe-inventory",
        "packages": [
            {
                "package_id": f"package-{index}",
                "candidate_id": f"candidate-{index}",
                "backend": "faster-whisper",
                "model_name": "Synthetic CTranslate2 package",
                "model_revision": "test",
                "package_path": f"local-packages/package-{index}",
                "license_marker": "MIT",
                "compatible_nadikt_versions": ["0.x-prototype"],
                "capabilities": {"languages": ["ru"], "punctuation": True, "max_segment_seconds": 25.0, "streaming": False},
                "inference_defaults": {"beam_size": 5, "device": "cpu", "compute_type": "int8"},
                "critical_files": [{"relative_path": "manifest.txt", "sha256": "0" * 64}],
            }
            for index in range(package_count)
        ],
    }


if __name__ == "__main__":
    unittest.main()
