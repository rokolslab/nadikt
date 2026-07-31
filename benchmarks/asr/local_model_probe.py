"""Single-engine offline local model package probe runner."""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable

from .logging_config import get_logger
from .manifests import ModelPackageManifest, load_json, validate_model_inventory
from .offline_check import validate_local_package
from .privacy_audit import audit_text_artifact
from .probe_results import ProbeOutcome, ProbePackageResult, ProbePhaseResult

LOGGER = get_logger(__name__)
ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

ProbeFactory = Callable[[], Any]


def run_local_model_probe(
    models_path: Path,
    *,
    candidate: str | None = None,
    backend: str | None = None,
    dry_run: bool = False,
    offline_required: bool = False,
    audio_file: Path | None = None,
    audio_label: str | None = None,
    backend_factories: dict[str, ProbeFactory] | None = None,
) -> dict[str, Any]:
    """Validate local packages and run at most one backend object at a time."""

    LOGGER.info("local_model_probe_start", extra={"candidate": candidate or "all", "backend": backend or "all", "dry_run": dry_run})
    if offline_required:
        os.environ["NADIKT_BENCHMARK_OFFLINE_REQUIRED"] = "1"

    model_data = load_json(models_path)
    packages, model_errors = validate_model_inventory(model_data)
    selected = [] if model_errors else _select_packages(packages, candidate=candidate, backend=backend)
    factories = backend_factories or _default_backend_factories()

    package_results: list[ProbePackageResult] = []
    outcome_counts: Counter[str] = Counter()
    for package in selected:
        result = _probe_one_package(
            package,
            models_path.parent,
            dry_run=dry_run,
            audio_file=audio_file,
            audio_label=audio_label,
            backend_factories=factories,
        )
        package_results.append(result)
        outcome_counts[result.outcome] += 1

    created_at = datetime.now(UTC)
    summary: dict[str, Any] = {
        "run_id": "local-model-probe-" + created_at.strftime("%Y%m%dT%H%M%SZ"),
        "created_at": created_at.isoformat(),
        "inventory_id": model_data.get("inventory_id"),
        "validation_errors": model_errors,
        "selected_package_count": len(selected),
        "audio": {
            "provided": audio_file is not None,
            "audio_label": audio_label or ("provided" if audio_file else "not_provided"),
        },
        "offline": {
            "network_attempted": False,
            "network_block_required": offline_required,
            "network_block_verification": "external_environment_required" if offline_required else "not_requested",
        },
        "package_outcomes": dict(sorted(outcome_counts.items())),
        "packages": [result.to_json() for result in package_results],
    }
    privacy = audit_text_artifact(json.dumps(summary, ensure_ascii=False), canary="NADIKT_CONTROLLED_CANARY")
    summary["privacy"] = privacy.safe_log_context()
    summary["result"] = _classify_summary(model_errors, package_results)
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Probe verified local ASR model packages without network downloads.")
    parser.add_argument("--models", required=True, type=Path, help="Path to model package inventory JSON")
    parser.add_argument("--candidate", help="Candidate ID to probe")
    parser.add_argument("--backend", choices=("gigaam", "faster-whisper", "tone", "other-local"), help="Backend family to probe")
    parser.add_argument("--offline-required", action="store_true", help="Record that external network blocking is required")
    parser.add_argument("--dry-run", action="store_true", help="Validate packages without loading SDK backends")
    parser.add_argument("--audio-file", help="Local controlled audio path; never printed in summaries")
    parser.add_argument("--audio-label", help="Opaque safe audio label for logs and summaries")
    args = parser.parse_args(argv)

    summary = run_local_model_probe(
        args.models,
        candidate=args.candidate,
        backend=args.backend,
        dry_run=args.dry_run,
        offline_required=args.offline_required,
        audio_file=Path(args.audio_file) if args.audio_file else None,
        audio_label=args.audio_label,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if summary["result"] in {"passed", "passed_with_expected_missing_packages"} else 2


def _probe_one_package(
    package: ModelPackageManifest,
    inventory_root: Path,
    *,
    dry_run: bool,
    audio_file: Path | None,
    audio_label: str | None,
    backend_factories: dict[str, ProbeFactory],
) -> ProbePackageResult:
    LOGGER.debug("local_model_probe_package_start", extra={"package_id": package.package_id, "backend": package.backend})
    integrity = validate_local_package(
        package.package_id,
        package.package_path,
        inventory_root,
        package.critical_files,
        package.license_marker,
    )
    phases = [ProbePhaseResult("package_validation", integrity.outcome, details={"warning_count": len(integrity.warnings)})]
    if integrity.outcome != ProbeOutcome.PACKAGE_PRESENT.value:
        return ProbePackageResult(
            package.package_id,
            package.candidate_id,
            package.backend,
            integrity.outcome,
            integrity.checksum_prefixes,
            tuple(phases),
            integrity.warnings,
        )
    if dry_run:
        phases.append(ProbePhaseResult("backend_probe", ProbeOutcome.NOT_RUN.value, reason_code="dry_run"))
        return ProbePackageResult(
            package.package_id,
            package.candidate_id,
            package.backend,
            ProbeOutcome.PACKAGE_PRESENT.value,
            integrity.checksum_prefixes,
            tuple(phases),
            integrity.warnings,
        )

    factory = backend_factories.get(package.backend)
    if factory is None:
        phases.append(ProbePhaseResult("backend_availability", ProbeOutcome.INCOMPATIBLE_BACKEND.value))
        return ProbePackageResult(package.package_id, package.candidate_id, package.backend, ProbeOutcome.INCOMPATIBLE_BACKEND.value, integrity.checksum_prefixes, tuple(phases), integrity.warnings)

    probe = factory()
    package_dir = (inventory_root.resolve(strict=False) / package.package_path).resolve(strict=False)
    try:
        load = probe.load(package_dir, package)
        phases.append(load)
        if load.outcome == ProbeOutcome.SUCCESS.value:
            phases.append(probe.is_ready())
            phases.append(probe.warm_up())
            phases.append(_run_transcribe_phase(probe, package, audio_file, audio_label))
    finally:
        if hasattr(probe, "close"):
            phases.append(probe.close())
    return ProbePackageResult(package.package_id, package.candidate_id, package.backend, _package_outcome(phases), integrity.checksum_prefixes, tuple(phases), integrity.warnings)


def _run_transcribe_phase(probe: Any, package: ModelPackageManifest, audio_file: Path | None, audio_label: str | None) -> ProbePhaseResult:
    beam_size = int(package.inference_defaults.get("beam_size") or 5)
    if package.backend == "faster-whisper":
        return probe.transcribe(audio_file, audio_label, beam_size=beam_size)
    return probe.transcribe(audio_file, audio_label)


def _select_packages(
    packages: list[ModelPackageManifest],
    *,
    candidate: str | None,
    backend: str | None,
) -> list[ModelPackageManifest]:
    selected = []
    for package in packages:
        if candidate and package.candidate_id != candidate:
            continue
        if backend and package.backend != backend:
            continue
        selected.append(package)
    return selected


def _default_backend_factories() -> dict[str, ProbeFactory]:
    return {
        "faster-whisper": _create_faster_whisper_probe,
        "gigaam": _create_gigaam_probe,
    }


def _create_faster_whisper_probe() -> Any:
    from nadikt.infrastructure.asr.faster_whisper import FasterWhisperLocalProbe

    return FasterWhisperLocalProbe()


def _create_gigaam_probe() -> Any:
    from nadikt.infrastructure.asr.gigaam import GigaAMLocalProbe

    return GigaAMLocalProbe()


def _package_outcome(phases: list[ProbePhaseResult]) -> str:
    for phase in phases:
        if phase.outcome not in {ProbeOutcome.SUCCESS.value, ProbeOutcome.PACKAGE_PRESENT.value, ProbeOutcome.NOT_RUN.value}:
            return phase.outcome
    return ProbeOutcome.SUCCESS.value


def _classify_summary(model_errors: list[str], package_results: list[ProbePackageResult]) -> str:
    if model_errors:
        return "invalid_manifests"
    if not package_results:
        return "no_matching_packages"
    outcomes = {result.outcome for result in package_results}
    if outcomes == {ProbeOutcome.MISSING_PACKAGE.value}:
        return "passed_with_expected_missing_packages"
    if any(outcome not in {ProbeOutcome.SUCCESS.value, ProbeOutcome.PACKAGE_PRESENT.value, ProbeOutcome.MISSING_PACKAGE.value} for outcome in outcomes):
        return "completed_with_blockers"
    return "passed"


if __name__ == "__main__":
    raise SystemExit(main())
