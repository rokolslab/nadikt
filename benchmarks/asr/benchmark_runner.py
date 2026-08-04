"""Privacy-safe ASR benchmark runner CLI."""

from __future__ import annotations

import argparse
import json
import math
import subprocess
import wave
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .benchmark_results import BenchmarkResult, CandidateAggregate, write_result_atomic
from .dataset_bindings import validate_dataset_bindings
from .environment_fingerprint import build_environment_fingerprint
from .logging_config import get_logger
from .manifests import SampleManifest, load_json, load_model_inventory, load_run_profile, validate_dataset_manifest, validate_run_profile_preflight
from .offline_evidence import unverified_evidence
from .privacy_audit import audit_text_artifact
from .resource_measurement import ResourceReport, phase_resource_report
from .worker_protocol import WorkerMetricDiagnostic, WorkerMetricResult, WorkerRepeatRequest, WorkerRequestV2, WorkerSampleOutcome, WorkerSampleRequest, new_nonce
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
    run_profile_path: Path | None = None,
    dry_run: bool = False,
    launcher_pythons: dict[str, str] | None = None,
) -> BenchmarkResult:
    LOGGER.info("benchmark_runner_start", extra={"run_kind": run_kind, "candidate": candidate or "all", "repeats": repeats, "dry_run": dry_run})
    packages, model_errors = load_model_inventory(inventory_path)
    dataset_data = load_json(dataset_profile_path)
    samples, dataset_errors = validate_dataset_manifest(dataset_data)
    run_profile = None
    profile_errors: list[str] = []
    if run_profile_path is not None:
        run_profile, profile_errors = load_run_profile(run_profile_path)
    binding_result = None
    if private_bindings_path is not None and controlled_root is not None:
        binding_result = validate_dataset_bindings(dataset_profile_path, private_bindings_path, controlled_root)

    selected = [package for package in packages if candidate is None or package.candidate_id == candidate]
    if run_profile is not None and candidate is None:
        package_by_candidate = {package.candidate_id: package for package in selected}
        selected = [package_by_candidate[candidate_id] for candidate_id in run_profile.ordered_candidate_ids if candidate_id in package_by_candidate]
        profile_errors.extend(
            validate_run_profile_preflight(
                profile=run_profile,
                dataset_data=dataset_data,
                samples=samples,
                candidate_ids=[package.candidate_id for package in selected],
                repeats=repeats,
            )
        )
    elif run_profile is not None:
        profile_errors.append("run_profile_disallows_single_candidate_filter")
    run_id = "pilot-ru-coding-" + datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    aggregates: list[CandidateAggregate] = []
    if model_errors or dataset_errors or profile_errors or (binding_result is not None and binding_result.errors):
        outcome = "invalid_inputs"
    elif dry_run:
        outcome = "dry_run"
        aggregates = [
            CandidateAggregate(package.candidate_id, package.package_id, package.backend, repeats, 0, "not_run", {"worker": "not_run"})
            for package in selected
        ]
    else:
        outcome, aggregates = _run_candidates(selected, binding_result, repeats, inventory_path.parent, samples, run_profile, launcher_pythons or {})

    privacy_payload = {
        "model_error_count": len(model_errors),
        "dataset_error_count": len(dataset_errors),
        "run_profile_error_count": len(profile_errors),
        "binding_error_count": len(binding_result.errors) if binding_result is not None else 0,
    }
    evidence = unverified_evidence(run_id).to_json()
    git_revision = _git_revision(full=True)
    git_clean = _git_clean()
    validity = _publication_validity(
        outcome=outcome,
        aggregates=aggregates,
        run_profile=run_profile,
        selected=selected,
        offline_evidence=evidence,
        git_clean=git_clean,
    )
    result = BenchmarkResult(
        run_id=run_id,
        run_kind=run_kind,
        nadikt_revision=git_revision[:12] if git_revision != "unknown" else "unknown",
        dataset={
            "dataset_id": str(dataset_data.get("dataset_id") or "unknown"),
            "dataset_revision": str(dataset_data.get("dataset_revision") or "unknown"),
            "sample_count": len(samples),
            "binding_status": binding_result.outcome if binding_result is not None else "not_provided",
        },
        candidates=tuple(aggregates),
        measurement={
            "backend": "spawned-worker",
            "repeats_requested": repeats,
            "resource_sampler": _measurement_resource_sampler(aggregates),
            "execution_fingerprint": _execution_fingerprint(run_profile, selected, git_revision).to_json(),
        },
        settings=_safe_settings(run_profile, candidate, repeats),
        offline_evidence=evidence,
        privacy=privacy_payload,
        outcome=outcome,
        validity=validity,
    )
    rendered = json.dumps(result.to_json(), ensure_ascii=False, sort_keys=True)
    audit = audit_text_artifact(rendered, canary="NADIKT_CONTROLLED_CANARY")
    if audit.has_violation:
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
    parser.add_argument("--run-profile", type=Path)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--launcher-python", action="append", default=[], metavar="CANDIDATE=PYTHON", help="Private per-candidate Python executable for worker launch; not persisted to results.")
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
        run_profile_path=args.run_profile,
        dry_run=args.dry_run,
        launcher_pythons=_parse_launcher_python_options(args.launcher_python),
    )
    print(json.dumps(result.to_json(), ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result.outcome in {"dry_run", "success", "not_run"} else 2


def _run_candidates(packages: list[object], binding_result: object | None, repeats: int, inventory_root: Path, sample_manifests: list[SampleManifest], run_profile: object | None = None, launcher_pythons: dict[str, str] | None = None) -> tuple[str, list[CandidateAggregate]]:
    if binding_result is None or not getattr(binding_result, "resolved_samples", ()):
        return "not_run", [
            CandidateAggregate(package.candidate_id, package.package_id, package.backend, repeats, 0, "not_run", {"bindings": "not_provided"})
            for package in packages
        ]
    samples = tuple(getattr(binding_result, "resolved_samples"))
    manifests_by_id = {sample.sample_id: sample for sample in sample_manifests}
    warmup_sample, scored_samples = _split_worker_samples(samples, manifests_by_id, run_profile)
    aggregates: list[CandidateAggregate] = []
    launcher_pythons = launcher_pythons or {}
    for package in packages:
        supervisor = WorkerSupervisor(python_executable=launcher_pythons.get(package.candidate_id))
        completed = 0
        phase_outcomes: dict[str, str] = {}
        quality_results: dict[str, list[dict[str, object]]] = {}
        quality_diagnostics: list[dict[str, object]] = []
        resource_samples: list[dict[str, object]] = []
        repeat_outcomes: list[dict[str, object]] = []
        package_dir = (inventory_root / package.package_path).resolve(strict=False)
        for repeat_index in range(repeats):
            request = WorkerRequestV2(
                nonce=new_nonce(),
                package_id=package.package_id,
                candidate_id=package.candidate_id,
                backend=package.backend,
                package_dir=package_dir,
                capabilities=package.capabilities,
                inference_defaults=package.inference_defaults,
                critical_checksum_prefixes=tuple(str(item.get("sha256", ""))[:12] for item in package.critical_files if isinstance(item, dict)),
                repeat=WorkerRepeatRequest(repeat_index=repeat_index, warmup_sample=warmup_sample, scored_samples=scored_samples),
            )
            supervised = supervisor.run(request)
            result = supervised.worker_result
            if not hasattr(result, "repeat"):
                raise ValueError("worker_result_v2_required")
            phase_outcomes["supervisor"] = supervised.supervisor_outcome
            phase_outcomes.update({phase.phase: phase.outcome for phase in result.repeat.phases})
            repeat_outcomes.append(_repeat_outcome_json(result.repeat))
            for sample in result.repeat.samples:
                if sample.scored:
                    _collect_sample_metrics(quality_results, sample.metrics, sample.category)
                    _collect_sample_diagnostics(quality_diagnostics, sample.metric_diagnostics)
            resource_samples.append(_resource_sample_v2(result.repeat.samples, scored_samples, result.repeat.phases, supervised.resource_report))
            if supervised.supervisor_outcome == "completed" and result.worker_status == "success" and result.repeat.outcome == "success":
                completed += 1
        aggregates.append(
            CandidateAggregate(
                candidate_id=package.candidate_id,
                package_id=package.package_id,
                backend=package.backend,
                repeats_requested=repeats,
                repeats_completed=completed,
                outcome="success" if completed == repeats else "fail",
                phase_outcomes=phase_outcomes,
                quality_aggregates=_aggregate_quality_results(quality_results),
                resource_aggregates=_aggregate_resource_samples(resource_samples),
                quality_diagnostics=tuple(quality_diagnostics),
                repeat_outcomes=tuple(repeat_outcomes),
            )
        )
    outcome = "success" if all(item.outcome == "success" for item in aggregates) else "fail"
    return outcome, aggregates


def _git_revision(*, full: bool = False) -> str:
    try:
        command = ["git", "rev-parse", "HEAD"] if full else ["git", "rev-parse", "--short", "HEAD"]
        completed = subprocess.run(command, text=True, capture_output=True, check=False, timeout=5)
    except Exception:
        return "unknown"
    return completed.stdout.strip() or "unknown"


def _parse_launcher_python_options(values: list[str]) -> dict[str, str]:
    result: dict[str, str] = {}
    for value in values:
        candidate_id, separator, executable = value.partition("=")
        if not candidate_id or not separator or not executable:
            raise ValueError("invalid_launcher_python_option")
        result[candidate_id] = executable
    return result


def _git_clean() -> bool:
    try:
        completed = subprocess.run(["git", "status", "--porcelain"], text=True, capture_output=True, check=False, timeout=5)
    except Exception:
        return False
    return completed.returncode == 0 and not completed.stdout.strip()


def _publication_validity(*, outcome: str, aggregates: list[CandidateAggregate], run_profile: object | None, selected: list[object], offline_evidence: dict[str, object], git_clean: bool) -> dict[str, object]:
    expected_candidates = tuple(getattr(run_profile, "ordered_candidate_ids", ())) if run_profile is not None else tuple(package.candidate_id for package in selected)
    actual_candidates = tuple(candidate.candidate_id for candidate in aggregates)
    exact_matrix = bool(expected_candidates) and actual_candidates == expected_candidates
    blockers: list[str] = []
    if outcome != "success":
        blockers.append("run_not_successful")
    if not exact_matrix:
        blockers.append("incomplete_candidate_matrix")
    if not git_clean:
        blockers.append("git_worktree_not_clean")
    if offline_evidence.get("status") != "PASS":
        blockers.append("offline_evidence_not_verified")
    if not _quality_matrix_complete(aggregates):
        blockers.append("quality_matrix_incomplete")
    return {
        "schema_version": 2,
        "publication_allowed": not blockers,
        "blockers": sorted(set(blockers)),
        "exact_candidate_matrix": exact_matrix,
        "git_clean": git_clean,
        "offline_evidence_status": str(offline_evidence.get("status") or "unknown"),
    }


def _quality_matrix_complete(aggregates: list[CandidateAggregate]) -> bool:
    if not aggregates:
        return False
    required = {
        "category:ru_coding_terms:wer",
        "category:ru_coding_terms:cer",
        "category:ru_coding_terms:coding_term_accuracy",
        "category:ru_coding_terms:english_term_accuracy",
        "category:ru_coding_terms:latin_preservation_rate",
    }
    return all(required.issubset(set(aggregate.quality_aggregates)) for aggregate in aggregates)


def _repeat_outcome_json(repeat: object) -> dict[str, object]:
    return {
        "repeat_index": int(getattr(repeat, "repeat_index")),
        "outcome": str(getattr(repeat, "outcome")),
        "phase_outcomes": [_phase_json(phase) for phase in getattr(repeat, "phases", ())],
        "sample_outcomes": [_sample_outcome_json(sample) for sample in getattr(repeat, "samples", ())],
    }


def _sample_outcome_json(sample: object) -> dict[str, object]:
    return {
        "sample_id": str(getattr(sample, "sample_id")),
        "category": str(getattr(sample, "category")),
        "scored": bool(getattr(sample, "scored")),
        "outcome": str(getattr(sample, "outcome")),
        "phase_outcomes": [_phase_json(phase) for phase in getattr(sample, "phases", ())],
        "metrics": [metric.to_json() for metric in getattr(sample, "metrics", ())],
        "metric_diagnostics": [diagnostic.to_json() for diagnostic in getattr(sample, "metric_diagnostics", ())],
    }


def _phase_json(phase: object) -> dict[str, object]:
    return {
        "phase": str(getattr(phase, "phase")),
        "outcome": str(getattr(phase, "outcome")),
        "duration_ms": round(float(getattr(phase, "duration_ms", 0.0) or 0.0), 3),
    }


def _execution_fingerprint(run_profile: object | None, packages: list[object], git_revision: str) -> object:
    return build_environment_fingerprint(
        lock_files=sorted((Path.cwd() / "requirements" / "benchmark").glob("*.lock.txt")),
        git_revision=git_revision,
        git_clean=_git_clean(),
        launcher_profiles=dict(getattr(run_profile, "launcher_profiles", {})) if run_profile is not None else {},
        package_digest_prefixes={str(package.package_id): str(package.manifest_sha256)[:12] for package in packages},
    )


def _collect_quality_results(target: dict[str, list[dict[str, object]]], metrics: Any) -> None:
    if not isinstance(metrics, dict):
        return
    for metric_name, metric in metrics.items():
        if isinstance(metric, dict):
            target.setdefault(str(metric_name), []).append(metric)


def _collect_sample_metrics(target: dict[str, list[dict[str, object]]], metrics: tuple[WorkerMetricResult, ...], category: str) -> None:
    for metric in metrics:
        metric_json = metric.to_json()
        target.setdefault(metric.metric_name, []).append(metric_json)
        target.setdefault(f"category:{category}:{metric.metric_name}", []).append(metric_json)


def _collect_sample_diagnostics(target: list[dict[str, object]], diagnostics: tuple[WorkerMetricDiagnostic, ...]) -> None:
    target.extend(diagnostic.to_json() for diagnostic in diagnostics)


def _aggregate_quality_results(metrics: dict[str, list[dict[str, object]]]) -> dict[str, dict[str, object]]:
    aggregates: dict[str, dict[str, object]] = {}
    for metric_name, items in metrics.items():
        applicable = [item for item in items if item.get("status") == "ok"]
        denominator = sum(_int_value(item.get("denominator")) for item in applicable)
        numerator = sum(_int_value(item.get("numerator")) for item in applicable)
        status = "ok" if denominator else "not_applicable"
        aggregates[metric_name] = {
            "metric_name": metric_name.split(":")[-1],
            "category": metric_name.split(":")[1] if metric_name.startswith("category:") else "corpus",
            "value": round(numerator / denominator, 6) if denominator else 0.0,
            "numerator": numerator,
            "denominator": denominator,
            "status": status,
            "sample_measurements": len(items),
            "applicable_measurements": len(applicable),
            "not_applicable_measurements": sum(1 for item in items if item.get("status") == "not_applicable"),
            "completeness_status": "complete" if len(applicable) == len(items) and denominator else "incomplete",
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


def _resource_sample_v2(samples: tuple[WorkerSampleOutcome, ...], sample_requests: tuple[WorkerSampleRequest, ...], repeat_phases: tuple[object, ...] = (), resource_report: ResourceReport | None = None) -> dict[str, object]:
    durations_by_id = {sample.sample_id: sample.duration_seconds for sample in sample_requests}
    successful_scored = tuple(sample for sample in samples if sample.scored and sample.outcome == "success")
    audio_seconds = sum(float(durations_by_id.get(sample.sample_id, 0.0)) for sample in successful_scored)
    transcribe_ms = sum(
        float(phase.duration_ms or 0.0)
        for sample in successful_scored
        for phase in sample.phases
        if phase.phase == "transcribe"
    )
    sample_rtf_values = []
    for sample in successful_scored:
        duration = float(durations_by_id.get(sample.sample_id, 0.0))
        sample_transcribe_ms = sum(float(phase.duration_ms or 0.0) for phase in sample.phases if phase.phase == "transcribe")
        if duration > 0:
            sample_rtf_values.append(sample_transcribe_ms / 1000.0 / duration)
    result: dict[str, object] = {
        "audio_seconds": audio_seconds,
        "scored_sample_success_count": len(successful_scored),
        "corpus_audio_seconds": audio_seconds,
        "corpus_transcribe_duration_ms": transcribe_ms,
        "sample_rtf_values": sample_rtf_values,
        # v1-compatible aliases retained until result v2 publication replaces aggregate shape.
        "transcribe_probe_duration_ms": transcribe_ms,
    }
    if audio_seconds > 0:
        corpus_rtf = transcribe_ms / 1000.0 / audio_seconds
        result["corpus_rtf"] = corpus_rtf
        result["transcribe_probe_rtf"] = corpus_rtf
    if resource_report is not None:
        result.update(_resource_report_fields(resource_report))
        result["phase_resource_reports"] = [_phase_report_json(phase.phase, float(phase.duration_ms or 0.0), resource_report) for phase in repeat_phases]
        for sample in samples:
            for phase in sample.phases:
                result.setdefault("phase_resource_reports", []).append(_phase_report_json(phase.phase, float(phase.duration_ms or 0.0), resource_report))
    return result


def _phase_report_json(phase_id: str, duration_ms: float, resource_report: ResourceReport) -> dict[str, object]:
    return phase_resource_report(phase_id, duration_ms, resource_report).to_json()


def _split_worker_samples(samples: tuple[object, ...], manifests_by_id: dict[str, SampleManifest], run_profile: object | None) -> tuple[WorkerSampleRequest, tuple[WorkerSampleRequest, ...]]:
    if run_profile is not None:
        warmup_ids = set(getattr(run_profile, "warmup_sample_ids"))
        scored_categories = set(getattr(run_profile, "scored_categories"))
        warmup_source = next((sample for sample in samples if sample.sample_id in warmup_ids), samples[0])
        scored_sources = tuple(sample for sample in samples if manifests_by_id.get(sample.sample_id) is not None and manifests_by_id[sample.sample_id].category in scored_categories)
    else:
        warmup_source = samples[0]
        scored_sources = samples
    if not scored_sources:
        scored_sources = samples
    return (
        _to_worker_sample(warmup_source, manifests_by_id, scored=False),
        tuple(_to_worker_sample(sample, manifests_by_id, scored=True) for sample in scored_sources),
    )


def _to_worker_sample(sample: object, manifests_by_id: dict[str, SampleManifest], *, scored: bool) -> WorkerSampleRequest:
    sample_manifest = manifests_by_id.get(sample.sample_id)
    return WorkerSampleRequest(
        sample_id=sample.sample_id,
        category=sample_manifest.category if sample_manifest is not None else ("scored" if scored else "warmup"),
        audio_file=sample.audio_path,
        reference_file=sample.reference_path if scored else None,
        duration_seconds=_wav_duration_seconds(sample.audio_path),
        scored=scored,
        expected_english_terms=sample_manifest.expected_english_terms if sample_manifest is not None else (),
        expected_coding_terms=sample_manifest.expected_coding_terms if sample_manifest is not None else (),
    )


def _resource_report_fields(resource_report: ResourceReport) -> dict[str, object]:
    report = resource_report.to_json()
    return {
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
        "resource_sampled_peak_process_tree_rss_mib": report["peak_rss_mib"],
        "resource_process_count_max": report["process_count_max"],
    }


def _aggregate_resource_samples(samples: list[dict[str, object]]) -> dict[str, object]:
    if not samples:
        return {}
    aggregates: dict[str, object] = {"sample_measurements": len(samples)}
    aggregates.update(_aggregate_rtf_samples(samples))
    aggregates.update(_aggregate_phase_resource_reports(samples))
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


def _aggregate_rtf_samples(samples: list[dict[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    audio_seconds = sum(float(sample["corpus_audio_seconds"]) for sample in samples if isinstance(sample.get("corpus_audio_seconds"), (int, float)))
    transcribe_ms = sum(float(sample["corpus_transcribe_duration_ms"]) for sample in samples if isinstance(sample.get("corpus_transcribe_duration_ms"), (int, float)))
    repeat_rtfs = [float(sample["corpus_rtf"]) for sample in samples if isinstance(sample.get("corpus_rtf"), (int, float))]
    sample_rtfs = [float(value) for sample in samples for value in sample.get("sample_rtf_values", []) if isinstance(value, (int, float))]
    if audio_seconds > 0:
        result["corpus_audio_seconds_sum"] = round(audio_seconds, 6)
        result["corpus_transcribe_duration_ms_sum"] = round(transcribe_ms, 6)
        result["corpus_rtf"] = round(transcribe_ms / 1000.0 / audio_seconds, 6)
    if repeat_rtfs:
        result["repeat_corpus_rtf_n"] = len(repeat_rtfs)
        result["repeat_corpus_rtf_avg"] = round(sum(repeat_rtfs) / len(repeat_rtfs), 6)
        result["repeat_corpus_rtf_max"] = round(max(repeat_rtfs), 6)
    if sample_rtfs:
        ordered = sorted(sample_rtfs)
        result["sample_rtf_n"] = len(ordered)
        result["sample_rtf_median"] = round(_nearest_rank(ordered, 0.5), 6)
        result["sample_rtf_p95"] = round(_nearest_rank(ordered, 0.95), 6)
        result["sample_rtf_max"] = round(max(ordered), 6)
    return result


def _aggregate_phase_resource_reports(samples: list[dict[str, object]]) -> dict[str, object]:
    reports = [report for sample in samples for report in sample.get("phase_resource_reports", []) if isinstance(report, dict)]
    if not reports:
        return {}
    reasons = sorted({str(reason) for report in reports for reason in report.get("missed_reasons", []) if isinstance(reason, str)})
    return {
        "phase_resource_report_count": len(reports),
        "phase_resource_status_ok_count": sum(1 for report in reports if report.get("status") == "ok"),
        "phase_resource_status_partial_count": sum(1 for report in reports if report.get("status") == "partial"),
        "phase_resource_status_unavailable_count": sum(1 for report in reports if report.get("status") == "unavailable"),
        "phase_resource_missed_reasons": reasons,
    }


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
        result["sampled_peak_process_tree_rss_mib"] = round(max(rss_values), 3)
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


def _safe_settings(run_profile: object | None, candidate: str | None, repeats: int) -> dict[str, object]:
    settings: dict[str, object] = {
        "requested_candidate_filter": candidate or "all",
        "requested_repeats": repeats,
    }
    if run_profile is not None:
        settings["run_profile_id"] = getattr(run_profile, "profile_id")
        settings["run_kind"] = getattr(run_profile, "run_kind")
        settings["ordered_candidate_ids"] = list(getattr(run_profile, "ordered_candidate_ids"))
        settings["min_repeats"] = getattr(run_profile, "min_repeats")
        settings["dataset_revision"] = getattr(run_profile, "dataset_revision")
        settings["scored_categories"] = list(getattr(run_profile, "scored_categories"))
        settings["warmup_sample_ids"] = list(getattr(run_profile, "warmup_sample_ids"))
        settings["scoring_policy_id"] = getattr(run_profile, "scoring_policy_id")
        settings["normalization_policy_id"] = getattr(run_profile, "normalization_policy_id")
        settings["metric_policy_id"] = getattr(run_profile, "metric_policy_id")
        settings["percentile_policy_id"] = getattr(run_profile, "percentile_policy_id")
        settings["thread_policy_id"] = getattr(run_profile, "thread_policy_id")
        settings["launcher_profiles"] = dict(getattr(run_profile, "launcher_profiles"))
    return settings


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


def _nearest_rank(sorted_values: list[float], percentile: float) -> float:
    if not sorted_values:
        return 0.0
    rank = max(1, int(math.ceil(percentile * len(sorted_values))))
    return sorted_values[min(rank, len(sorted_values)) - 1]


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
