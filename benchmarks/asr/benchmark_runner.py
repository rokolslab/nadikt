"""Privacy-safe ASR benchmark runner CLI."""

from __future__ import annotations

import argparse
import json
import subprocess
import wave
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .benchmark_results import BenchmarkResult, CandidateAggregate, write_result_atomic
from .dataset_bindings import validate_dataset_bindings
from .logging_config import get_logger
from .manifests import SampleManifest, load_json, load_model_inventory, validate_dataset_manifest
from .offline_evidence import unverified_evidence
from .privacy_audit import audit_text_artifact
from .resource_measurement import ResourceReport
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
        outcome, aggregates = _run_candidates(selected, binding_result, repeats, inventory_path.parent, samples)

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
        measurement={"backend": "spawned-worker", "repeats_requested": repeats, "resource_sampler": _measurement_resource_sampler(aggregates)},
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


def _run_candidates(packages: list[object], binding_result: object | None, repeats: int, inventory_root: Path, sample_manifests: list[SampleManifest]) -> tuple[str, list[CandidateAggregate]]:
    if binding_result is None or not getattr(binding_result, "resolved_samples", ()):
        return "not_run", [
            CandidateAggregate(package.candidate_id, package.package_id, package.backend, repeats, 0, "not_run", {"bindings": "not_provided"})
            for package in packages
        ]
    samples = tuple(getattr(binding_result, "resolved_samples"))
    manifests_by_id = {sample.sample_id: sample for sample in sample_manifests}
    aggregates: list[CandidateAggregate] = []
    supervisor = WorkerSupervisor()
    for package in packages:
        completed = 0
        phase_outcomes: dict[str, str] = {}
        quality_results: dict[str, list[dict[str, object]]] = {}
        resource_samples: list[dict[str, object]] = []
        package_dir = (inventory_root / package.package_path).resolve(strict=False)
        for _repeat in range(repeats):
            repeat_success = True
            for sample in samples:
                sample_manifest = manifests_by_id.get(sample.sample_id)
                duration_seconds = _wav_duration_seconds(sample.audio_path)
                request = WorkerRequest(
                    nonce=new_nonce(),
                    package_id=package.package_id,
                    candidate_id=package.candidate_id,
                    backend=package.backend,
                    package_dir=package_dir,
                    capabilities=package.capabilities,
                    inference_defaults=package.inference_defaults,
                    audio_file=sample.audio_path,
                    reference_file=sample.reference_path,
                    expected_english_terms=sample_manifest.expected_english_terms if sample_manifest is not None else (),
                    expected_coding_terms=sample_manifest.expected_coding_terms if sample_manifest is not None else (),
                    duration_seconds=duration_seconds,
                )
                supervised = supervisor.run(request)
                result = supervised.worker_result
                phase_outcomes.update({phase.phase: phase.outcome for phase in result.phases})
                _collect_quality_results(quality_results, result.quality_metrics)
                resource_samples.append(_resource_sample(result.phases, duration_seconds, supervised.resource_report))
                if result.worker_status != "success":
                    repeat_success = False
            if repeat_success:
                completed += 1
        aggregates.append(
            CandidateAggregate(
                package.candidate_id,
                package.package_id,
                package.backend,
                repeats,
                completed,
                "success" if completed == repeats else "fail",
                phase_outcomes,
                _aggregate_quality_results(quality_results),
                _aggregate_resource_samples(resource_samples),
            )
        )
    outcome = "success" if all(item.outcome == "success" for item in aggregates) else "fail"
    return outcome, aggregates


def _git_revision() -> str:
    try:
        completed = subprocess.run(["git", "rev-parse", "--short", "HEAD"], text=True, capture_output=True, check=False, timeout=5)
    except Exception:
        return "unknown"
    return completed.stdout.strip() or "unknown"


def _collect_quality_results(target: dict[str, list[dict[str, object]]], metrics: Any) -> None:
    if not isinstance(metrics, dict):
        return
    for metric_name, metric in metrics.items():
        if isinstance(metric, dict):
            target.setdefault(str(metric_name), []).append(metric)


def _aggregate_quality_results(metrics: dict[str, list[dict[str, object]]]) -> dict[str, dict[str, object]]:
    aggregates: dict[str, dict[str, object]] = {}
    for metric_name, items in metrics.items():
        applicable = [item for item in items if item.get("status") == "ok"]
        denominator = sum(_int_value(item.get("denominator")) for item in applicable)
        numerator = sum(_int_value(item.get("numerator")) for item in applicable)
        status = "ok" if denominator else "not_applicable"
        aggregates[metric_name] = {
            "metric_name": metric_name,
            "value": round(numerator / denominator, 6) if denominator else 0.0,
            "numerator": numerator,
            "denominator": denominator,
            "status": status,
            "sample_measurements": len(items),
        }
    return aggregates


def _resource_sample(phases: tuple[object, ...], audio_seconds: float, resource_report: ResourceReport | None = None) -> dict[str, object]:
    sample: dict[str, object] = {"audio_seconds": audio_seconds}
    for phase in phases:
        phase_name = str(getattr(phase, "phase", "unknown"))
        sample[f"{phase_name}_duration_ms"] = float(getattr(phase, "duration_ms", 0.0) or 0.0)
    transcribe_ms = float(sample.get("transcribe_probe_duration_ms", 0.0) or 0.0)
    if audio_seconds > 0:
        sample["transcribe_probe_rtf"] = transcribe_ms / 1000.0 / audio_seconds
    if resource_report is not None:
        report = resource_report.to_json()
        sample.update(
            {
                "resource_backend": report["backend"],
                "resource_backend_version": report["backend_version"],
                "resource_status": report["status"],
                "resource_cpu_normalization": report["cpu_normalization"],
                "resource_sample_interval_ms": report["sample_interval_ms"],
                "resource_duration_seconds": report["duration_seconds"],
                "resource_sample_count": report["sample_count"],
                "resource_missed_sample_count": report["missed_sample_count"],
                "resource_user_cpu_seconds": report["user_cpu_seconds"],
                "resource_system_cpu_seconds": report["system_cpu_seconds"],
                "resource_cpu_avg_percent": report["cpu_avg_percent"],
                "resource_cpu_max_percent": report["cpu_max_percent"],
                "resource_peak_rss_mib": report["peak_rss_mib"],
                "resource_process_count_max": report["process_count_max"],
            }
        )
    return sample


def _aggregate_resource_samples(samples: list[dict[str, object]]) -> dict[str, object]:
    if not samples:
        return {}
    aggregates: dict[str, object] = {"sample_measurements": len(samples)}
    generic_numeric_keys = sorted(
        key
        for key in {key for sample in samples for key in sample}
        if not key.startswith("resource_") and all(isinstance(sample.get(key), (int, float)) for sample in samples if sample.get(key) is not None)
    )
    for key in generic_numeric_keys:
        values = [float(sample[key]) for sample in samples if isinstance(sample.get(key), (int, float))]
        if values:
            aggregates[f"{key}_avg"] = round(sum(values) / len(values), 6)
            aggregates[f"{key}_max"] = round(max(values), 6)
    resource_reports = [sample for sample in samples if sample.get("resource_backend")]
    if resource_reports:
        aggregates.update(_aggregate_supervisor_resources(resource_reports))
    return aggregates


def _aggregate_supervisor_resources(samples: list[dict[str, object]]) -> dict[str, object]:
    durations = [float(sample["resource_duration_seconds"]) for sample in samples if isinstance(sample.get("resource_duration_seconds"), (int, float))]
    cpu_avgs = [float(sample["resource_cpu_avg_percent"]) for sample in samples if isinstance(sample.get("resource_cpu_avg_percent"), (int, float))]
    duration_weighted_cpu = _weighted_avg(
        [(float(sample["resource_cpu_avg_percent"]), float(sample["resource_duration_seconds"])) for sample in samples if isinstance(sample.get("resource_cpu_avg_percent"), (int, float)) and isinstance(sample.get("resource_duration_seconds"), (int, float))]
    )
    result: dict[str, object] = {
        "resource_report_count": len(samples),
        "resource_status_ok_count": sum(1 for sample in samples if sample.get("resource_status") == "ok"),
        "resource_status_partial_count": sum(1 for sample in samples if sample.get("resource_status") == "partial"),
        "resource_status_unavailable_count": sum(1 for sample in samples if sample.get("resource_status") == "unavailable"),
        "resource_backend": _compatible_value(samples, "resource_backend"),
        "resource_backend_version": _compatible_value(samples, "resource_backend_version"),
        "resource_cpu_normalization": _compatible_value(samples, "resource_cpu_normalization"),
        "resource_sample_interval_ms": _compatible_value(samples, "resource_sample_interval_ms"),
        "resource_sample_count": sum(_numeric_int(sample.get("resource_sample_count")) for sample in samples),
        "resource_missed_sample_count": sum(_numeric_int(sample.get("resource_missed_sample_count")) for sample in samples),
    }
    for key in ("resource_user_cpu_seconds", "resource_system_cpu_seconds"):
        values = [float(sample[key]) for sample in samples if isinstance(sample.get(key), (int, float))]
        if values:
            result[f"{key}_sum"] = round(sum(values), 6)
    if duration_weighted_cpu is not None:
        result["resource_cpu_avg_percent"] = round(duration_weighted_cpu, 6)
    elif cpu_avgs:
        result["resource_cpu_avg_percent"] = round(sum(cpu_avgs) / len(cpu_avgs), 6)
    max_values = [float(sample["resource_cpu_max_percent"]) for sample in samples if isinstance(sample.get("resource_cpu_max_percent"), (int, float))]
    if max_values:
        result["resource_cpu_max_percent"] = round(max(max_values), 6)
    rss_values = [float(sample["resource_peak_rss_mib"]) for sample in samples if isinstance(sample.get("resource_peak_rss_mib"), (int, float))]
    if rss_values:
        result["resource_peak_rss_mib"] = round(max(rss_values), 3)
    process_values = [int(sample["resource_process_count_max"]) for sample in samples if isinstance(sample.get("resource_process_count_max"), int)]
    if process_values:
        result["resource_process_count_max"] = max(process_values)
    if durations:
        result["resource_duration_seconds_sum"] = round(sum(durations), 6)
    return result


def _measurement_resource_sampler(aggregates: list[CandidateAggregate]) -> str:
    values = []
    for candidate in aggregates:
        backend = candidate.resource_aggregates.get("resource_backend")
        version = candidate.resource_aggregates.get("resource_backend_version")
        if isinstance(backend, str) and isinstance(version, str):
            values.append(f"{backend}:{version}")
    if not values:
        return "unavailable"
    return values[0] if len(set(values)) == 1 else "mixed"


def _compatible_value(samples: list[dict[str, object]], key: str) -> object:
    values = {sample[key] for sample in samples if sample.get(key) is not None}
    if not values:
        return None
    return next(iter(values)) if len(values) == 1 else "mixed"


def _weighted_avg(values: list[tuple[float, float]]) -> float | None:
    denominator = sum(weight for _value, weight in values if weight > 0)
    if denominator <= 0:
        return None
    return sum(value * weight for value, weight in values if weight > 0) / denominator


def _numeric_int(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        return 0
    return value


def _int_value(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        return 0
    return value


def _wav_duration_seconds(path: Path) -> float:
    with wave.open(str(path), "rb") as audio:
        frame_rate = audio.getframerate()
        if frame_rate <= 0:
            return 1.0
        return audio.getnframes() / float(frame_rate)


if __name__ == "__main__":
    raise SystemExit(main())
