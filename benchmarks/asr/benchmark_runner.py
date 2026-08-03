"""Privacy-safe ASR benchmark runner CLI."""

from __future__ import annotations

import argparse
import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .benchmark_results import BenchmarkResult, CandidateAggregate, write_result_atomic
from .dataset_bindings import validate_dataset_bindings
from .logging_config import get_logger
from .manifests import load_json, load_model_inventory, validate_dataset_manifest
from .offline_evidence import unverified_evidence
from .privacy_audit import audit_text_artifact
from .worker_protocol import WorkerRequest, new_nonce
from .worker_supervisor import WorkerSupervisor

LOGGER = get_logger(__name__)
DEFAULT_RESULTS_DIR = Path("benchmarks/asr/results")


def run_benchmark(
    *,
    inventory_path: Path,
    dataset_profile_path: Path,
    output_path: Path,
    private_bindings_path: Path | None = None,
    controlled_root: Path | None = None,
    candidate: str | None = None,
    repeats: int = 3,
    run_kind: str = "coding_pilot",
    dry_run: bool = False,
) -> BenchmarkResult:
    LOGGER.info("benchmark_runner_start", extra={"run_kind": run_kind, "candidate": candidate or "all", "repeats": repeats, "dry_run": dry_run})
    packages, model_errors = load_model_inventory(inventory_path)
    dataset_data = load_json(dataset_profile_path)
    samples, dataset_errors = validate_dataset_manifest(dataset_data)
    binding_result = None
    if private_bindings_path is not None and controlled_root is not None:
        binding_result = validate_dataset_bindings(dataset_profile_path, private_bindings_path, controlled_root)

    selected = [package for package in packages if candidate is None or package.candidate_id == candidate]
    run_id = "pilot-ru-coding-" + datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    aggregates: list[CandidateAggregate] = []
    if model_errors or dataset_errors or (binding_result is not None and binding_result.errors):
        outcome = "invalid_inputs"
    elif dry_run:
        outcome = "dry_run"
        aggregates = [
            CandidateAggregate(package.candidate_id, package.package_id, package.backend, repeats, 0, "not_run", {"worker": "not_run"})
            for package in selected
        ]
    else:
        outcome, aggregates = _run_candidates(selected, binding_result, repeats)

    privacy_payload = {
        "model_error_count": len(model_errors),
        "dataset_error_count": len(dataset_errors),
        "binding_error_count": len(binding_result.errors) if binding_result is not None else 0,
    }
    evidence = unverified_evidence(run_id).to_json()
    result = BenchmarkResult(
        run_id=run_id,
        run_kind=run_kind,
        nadikt_revision=_git_revision(),
        dataset={
            "dataset_id": str(dataset_data.get("dataset_id") or "unknown"),
            "dataset_revision": str(dataset_data.get("dataset_revision") or "unknown"),
            "sample_count": len(samples),
            "binding_status": binding_result.outcome if binding_result is not None else "not_provided",
        },
        candidates=tuple(aggregates),
        measurement={"backend": "spawned-worker", "repeats_requested": repeats, "resource_sampler": "linux-proc-v1"},
        offline_evidence=evidence,
        privacy=privacy_payload,
        outcome=outcome,
    )
    rendered = json.dumps(result.to_json(), ensure_ascii=False, sort_keys=True)
    audit = audit_text_artifact(rendered, canary="NADIKT_CONTROLLED_CANARY")
    if audit.canary_present or audit.forbidden_payload_count:
        raise ValueError("benchmark_result_privacy_violation")
    write_result_atomic(result, output_path)
    LOGGER.info("benchmark_runner_done", extra={"run_id": run_id, "outcome": outcome, "candidate_count": len(aggregates)})
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run privacy-safe Nadikt ASR benchmark aggregates.")
    parser.add_argument("--inventory", required=True, type=Path)
    parser.add_argument("--dataset-profile", required=True, type=Path)
    parser.add_argument("--private-bindings", type=Path)
    parser.add_argument("--controlled-root", type=Path)
    parser.add_argument("--candidate")
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--run-kind", default="coding_pilot")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    if args.repeats < 1:
        raise SystemExit("--repeats must be positive")
    output = args.output or DEFAULT_RESULTS_DIR / ("pilot-ru-coding-" + datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ") + ".json")
    result = run_benchmark(
        inventory_path=args.inventory,
        dataset_profile_path=args.dataset_profile,
        output_path=output,
        private_bindings_path=args.private_bindings,
        controlled_root=args.controlled_root,
        candidate=args.candidate,
        repeats=args.repeats,
        run_kind=args.run_kind,
        dry_run=args.dry_run,
    )
    print(json.dumps(result.to_json(), ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result.outcome in {"dry_run", "success", "not_run"} else 2


def _run_candidates(packages: list[object], binding_result: object | None, repeats: int) -> tuple[str, list[CandidateAggregate]]:
    if binding_result is None or not getattr(binding_result, "resolved_samples", ()):
        return "not_run", [
            CandidateAggregate(package.candidate_id, package.package_id, package.backend, repeats, 0, "not_run", {"bindings": "not_provided"})
            for package in packages
        ]
    samples = tuple(getattr(binding_result, "resolved_samples"))
    aggregates: list[CandidateAggregate] = []
    supervisor = WorkerSupervisor()
    for package in packages:
        completed = 0
        phase_outcomes: dict[str, str] = {}
        for _repeat in range(repeats):
            sample = samples[0]
            request = WorkerRequest(
                nonce=new_nonce(),
                package_id=package.package_id,
                candidate_id=package.candidate_id,
                backend=package.backend,
                package_dir=package.package_path,
                capabilities=package.capabilities,
                inference_defaults=package.inference_defaults,
                audio_file=sample.audio_path,
                duration_seconds=1.0,
            )
            result = supervisor.run(request)
            phase_outcomes.update({phase.phase: phase.outcome for phase in result.phases})
            if result.worker_status == "success":
                completed += 1
        aggregates.append(CandidateAggregate(package.candidate_id, package.package_id, package.backend, repeats, completed, "success" if completed == repeats else "fail", phase_outcomes))
    outcome = "success" if all(item.outcome == "success" for item in aggregates) else "fail"
    return outcome, aggregates


def _git_revision() -> str:
    try:
        completed = subprocess.run(["git", "rev-parse", "--short", "HEAD"], text=True, capture_output=True, check=False, timeout=5)
    except Exception:
        return "unknown"
    return completed.stdout.strip() or "unknown"


if __name__ == "__main__":
    raise SystemExit(main())
