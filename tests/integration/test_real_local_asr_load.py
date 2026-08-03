from __future__ import annotations

import json
import os
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from benchmarks.asr.dataset_bindings import validate_dataset_bindings
from benchmarks.asr.manifests import load_model_inventory
from benchmarks.asr.offline_check import validate_local_package
from benchmarks.asr.package_integrity import checksum_prefix
from benchmarks.asr.worker_protocol import WorkerRequest, new_nonce
from benchmarks.asr.worker_supervisor import WorkerSupervisor


class RealLocalAsrLoadTest(unittest.TestCase):
    def test_real_local_asr_load_matrix_requires_opt_in_private_config(self) -> None:
        if os.environ.get("NADIKT_REAL_ASR_ASSETS") != "1":
            self.skipTest("SKIP: NADIKT_REAL_ASR_ASSETS is not enabled")
        config_path = os.environ.get("NADIKT_REAL_ASR_CONFIG")
        if not config_path:
            self.skipTest("SKIP: NADIKT_REAL_ASR_CONFIG is not provided")

        config_file = Path(config_path)
        self.assertTrue(config_file.is_file(), "FAIL: real_asr_config_missing")
        config = json.loads(config_file.read_text(encoding="utf-8"))
        candidates = tuple(str(item) for item in config.get("candidates", ()))
        self.assertTrue(candidates, "FAIL: candidates_required")

        inventory_path = _path_from_config(config, "inventory")
        dataset_profile_path = _path_from_config(config, "dataset_profile")
        private_bindings_path = _path_from_config(config, "private_bindings")
        controlled_root = _path_from_config(config, "controlled_root")
        sample_id = str(config.get("sample_id") or "warmup_001")
        require_offline_pass = bool(config.get("require_offline_evidence_pass", True))

        packages, inventory_errors = load_model_inventory(inventory_path)
        self.assertFalse(inventory_errors, "FAIL: inventory_invalid")
        bindings = validate_dataset_bindings(dataset_profile_path, private_bindings_path, controlled_root)
        self.assertEqual("bindings_valid", bindings.outcome, "FAIL: bindings_invalid")
        sample = _sample_by_id(bindings.resolved_samples, sample_id)
        selected = {package.candidate_id: package for package in packages if package.candidate_id in candidates}
        self.assertEqual(set(candidates), set(selected), "FAIL: candidate_matrix_incomplete")

        for candidate_id in candidates:
            with self.subTest(candidate_id=candidate_id):
                package = selected[candidate_id]
                package_dir = (inventory_path.parent / package.package_path).resolve(strict=False)
                integrity = validate_local_package(
                    package.package_id,
                    package.package_path,
                    inventory_path.parent,
                    package.critical_files,
                    package.rights_statuses,
                    package.package_format,
                )
                self.assertEqual("package_present", integrity.outcome, "FAIL: package_integrity")

                result = WorkerSupervisor().run(
                    WorkerRequest(
                        nonce=new_nonce(),
                        package_id=package.package_id,
                        candidate_id=package.candidate_id,
                        backend=package.backend,
                        package_dir=package_dir,
                        capabilities=package.capabilities,
                        inference_defaults=package.inference_defaults,
                        critical_checksum_prefixes=tuple(checksum_prefix(item.get("sha256", "")) for item in package.critical_files),
                        audio_file=sample.audio_path,
                        reference_file=sample.reference_path,
                        duration_seconds=float(config.get("duration_seconds") or 1.0),
                    )
                )
                phase_outcomes = {phase.phase: phase.outcome for phase in result.worker_result.phases}

                self.assertEqual("completed", result.supervisor_outcome, "FAIL: supervisor_outcome")
                self.assertEqual("success", result.worker_result.worker_status, "FAIL: worker_status")
                for phase in ("load", "readiness", "warmup", "transcribe_probe", "close"):
                    self.assertEqual("success", phase_outcomes.get(phase), "FAIL: phase_" + phase)
                evidence = result.offline_evidence.to_json() if result.offline_evidence is not None else {"status": "NOT VERIFIED"}
                if require_offline_pass:
                    self.assertEqual("PASS", evidence.get("status"), "FAIL: offline_evidence_not_verified")


def _path_from_config(config: dict[str, object], key: str) -> Path:
    value = config.get(key)
    if not isinstance(value, str) or not value:
        raise AssertionError("FAIL: " + key + "_required")
    path = Path(value)
    if not path.exists():
        raise AssertionError("FAIL: " + key + "_missing")
    return path


def _sample_by_id(samples: tuple[object, ...], sample_id: str) -> object:
    for sample in samples:
        if getattr(sample, "sample_id", None) == sample_id:
            return sample
    raise AssertionError("FAIL: sample_missing")


if __name__ == "__main__":
    unittest.main()
