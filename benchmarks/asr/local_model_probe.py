"""Single-engine offline local model package probe runner."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable

from .logging_config import get_logger
from .manifests import ModelPackageManifest, load_json, load_model_inventory
from .offline_check import validate_local_package
from .package_integrity import checksum_prefix
from .privacy_audit import audit_text_artifact
from .probe_results import ProbeOutcome, ProbePackageResult, ProbePhaseResult

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from nadikt.domain.ports.asr import (
    AsrBackend,
    AsrCapabilities,
    AsrEngine,
    AsrEngineError,
    AsrLoadOptions,
    AsrModelMetadata,
    AsrSegmentInput,
)

LOGGER = get_logger(__name__)

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
    packages, model_errors = load_model_inventory(models_path)
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
        package.rights_statuses,
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
    return _SpawnedWorkerProbeAdapter()


def _create_gigaam_probe() -> Any:
    return _SpawnedWorkerProbeAdapter()


class _SpawnedWorkerProbeAdapter:
    """Default probe adapter that keeps ASR SDK imports inside a child process."""

    def __init__(self) -> None:
        self._package: ModelPackageManifest | None = None
        self._package_dir: Path | None = None
        self._load_result: object | None = None

    def load(self, package_dir: Path, package: ModelPackageManifest) -> ProbePhaseResult:
        self._package = package
        self._package_dir = package_dir
        result = self._run_worker(audio_file=None)
        self._load_result = result
        for phase in result.phases:
            if phase.phase == "load":
                return ProbePhaseResult("load", phase.outcome, phase.duration_ms)
        return ProbePhaseResult("load", result.worker_status)

    def is_ready(self) -> ProbePhaseResult:
        result = self._load_result
        if result is None:
            return ProbePhaseResult("readiness", ProbeOutcome.READINESS_FAILED.value)
        for phase in result.phases:
            if phase.phase == "readiness":
                return ProbePhaseResult("readiness", phase.outcome, phase.duration_ms)
        return ProbePhaseResult("readiness", ProbeOutcome.READINESS_FAILED.value)

    def warm_up(self) -> ProbePhaseResult:
        return ProbePhaseResult("warmup", ProbeOutcome.NOT_RUN.value, reason_code="worker_requires_audio")

    def transcribe(self, audio_file: Path | None, _audio_label: str | None, **_kwargs: object) -> ProbePhaseResult:
        if audio_file is None:
            return ProbePhaseResult("transcribe_probe", ProbeOutcome.NOT_RUN.value)
        result = self._run_worker(audio_file=audio_file)
        for phase in result.phases:
            if phase.phase == "transcribe_probe":
                return ProbePhaseResult("transcribe_probe", phase.outcome, phase.duration_ms)
        return ProbePhaseResult("transcribe_probe", result.worker_status)

    def close(self) -> ProbePhaseResult:
        return ProbePhaseResult("close", ProbeOutcome.SUCCESS.value)

    def _run_worker(self, *, audio_file: Path | None) -> object:
        from .worker_protocol import WorkerRequest, new_nonce
        from .worker_supervisor import WorkerSupervisor

        package = self._package
        package_dir = self._package_dir
        if package is None or package_dir is None:
            raise RuntimeError("worker_probe_not_loaded")
        request = WorkerRequest(
            nonce=new_nonce(),
            package_id=package.package_id,
            candidate_id=package.candidate_id,
            backend=package.backend,
            package_dir=package_dir,
            capabilities=package.capabilities,
            inference_defaults=package.inference_defaults,
            critical_checksum_prefixes=tuple(checksum_prefix(item.get("sha256", "")) for item in package.critical_files),
            audio_file=audio_file,
            duration_seconds=float(package.inference_defaults.get("probe_duration_seconds") or 1.0) if audio_file is not None else None,
        )
        return WorkerSupervisor().run(request)


class _DomainEngineProbeAdapter:
    """Bridge benchmark probe phases to runtime AsrEngine without leaking text."""

    def __init__(self, engine_cls: Callable[[AsrModelMetadata], AsrEngine]) -> None:
        self._engine_cls = engine_cls
        self._engine: AsrEngine | None = None
        self._package: ModelPackageManifest | None = None
        self._package_dir: Path | None = None

    def load(self, package_dir: Path, package: ModelPackageManifest) -> ProbePhaseResult:
        started = time.monotonic()
        self._package = package
        self._package_dir = package_dir
        self._engine = self._engine_cls(_metadata_from_package(package))
        try:
            self._engine.load(AsrLoadOptions(package_dir, package.inference_defaults))
        except AsrEngineError as error:
            return _probe_phase_from_error("load", error, started)
        return _probe_phase("load", ProbeOutcome.SUCCESS.value, started)

    def is_ready(self) -> ProbePhaseResult:
        started = time.monotonic()
        if self._engine is not None and self._engine.is_ready():
            return _probe_phase("readiness", ProbeOutcome.SUCCESS.value, started)
        return _probe_phase("readiness", ProbeOutcome.READINESS_FAILED.value, started)

    def warm_up(self) -> ProbePhaseResult:
        started = time.monotonic()
        segment = self._segment_from_audio(None)
        if self._engine is None or segment is None:
            return _probe_phase("warmup", ProbeOutcome.NOT_RUN.value, started)
        try:
            self._engine.warm_up(segment)
        except AsrEngineError as error:
            return _probe_phase_from_error("warmup", error, started)
        return _probe_phase("warmup", ProbeOutcome.SUCCESS.value, started)

    def transcribe(self, audio_file: Path | None, _audio_label: str | None, **_kwargs: object) -> ProbePhaseResult:
        started = time.monotonic()
        segment = self._segment_from_audio(audio_file)
        if self._engine is None or segment is None:
            return _probe_phase("transcribe_probe", ProbeOutcome.NOT_RUN.value, started)
        try:
            self._engine.transcribe_segment(segment)
        except AsrEngineError as error:
            return _probe_phase_from_error("transcribe_probe", error, started)
        return _probe_phase("transcribe_probe", ProbeOutcome.SUCCESS.value, started)

    def close(self) -> ProbePhaseResult:
        started = time.monotonic()
        if self._engine is None:
            return _probe_phase("close", ProbeOutcome.SUCCESS.value, started)
        try:
            self._engine.close()
        except AsrEngineError as error:
            return _probe_phase_from_error("close", error, started)
        finally:
            self._engine = None
        return _probe_phase("close", ProbeOutcome.SUCCESS.value, started)

    def _segment_from_audio(self, audio_file: Path | None) -> AsrSegmentInput | None:
        if audio_file is None:
            return None
        package = self._package
        duration = 1.0
        if package is not None:
            duration = float(package.inference_defaults.get("probe_duration_seconds") or 1.0)
        return AsrSegmentInput(
            sample_id="local_probe_sample",
            segment_id=0,
            audio_path=audio_file,
            start_seconds=0.0,
            end_seconds=duration,
            language_profile="ru",
            segmentation_policy_id="local-probe-v1",
        )


def _metadata_from_package(package: ModelPackageManifest) -> AsrModelMetadata:
    capabilities = package.capabilities
    return AsrModelMetadata(
        package_id=package.package_id,
        candidate_id=package.candidate_id,
        backend=AsrBackend(package.backend),
        model_name=package.model_name,
        model_revision=package.model_revision,
        backend_version=str(package.inference_defaults.get("backend_version") or "benchmark-lock"),
        license_marker=_license_marker(package),
        capabilities=AsrCapabilities(
            languages=tuple(str(item) for item in capabilities.get("languages", ("ru",))),
            max_segment_seconds=float(capabilities.get("max_segment_seconds") or 25.0),
            punctuation=bool(capabilities.get("punctuation", False)),
            streaming=bool(capabilities.get("streaming", False)),
            word_timestamps=bool(capabilities.get("word_timestamps", False)),
        ),
        checksum_prefixes=tuple(checksum_prefix(item.get("sha256", "")) for item in package.critical_files),
    )


def _license_marker(package: ModelPackageManifest) -> str:
    local_evaluation = package.rights_statuses.get("local_evaluation", {})
    return str(local_evaluation.get("status") or "unknown")


def _probe_phase(phase: str, outcome: str, started: float, *, details: dict[str, object] | None = None) -> ProbePhaseResult:
    return ProbePhaseResult(phase, outcome, (time.monotonic() - started) * 1000, details=details or {})


def _probe_phase_from_error(phase: str, error: AsrEngineError, started: float) -> ProbePhaseResult:
    return _probe_phase(phase, _probe_outcome_from_failure(error), started)


def _probe_outcome_from_failure(error: AsrEngineError) -> str:
    mapping = {
        "missing_package": ProbeOutcome.MISSING_PACKAGE.value,
        "invalid_package_path": ProbeOutcome.HUB_IDENTIFIER_REJECTED.value,
        "missing_critical_file": ProbeOutcome.MISSING_CRITICAL_FILE.value,
        "incompatible_backend": ProbeOutcome.BACKEND_UNAVAILABLE.value,
        "engine_not_ready": ProbeOutcome.READINESS_FAILED.value,
        "segment_too_long": ProbeOutcome.SEGMENT_TOO_LONG.value,
        "transcribe_failed": ProbeOutcome.TRANSCRIBE_FAILED.value,
        "warm_up_failed": ProbeOutcome.TRANSCRIBE_FAILED.value,
        "resource_release_failed": ProbeOutcome.CLOSE_FAILED.value,
    }
    return mapping.get(error.failure.code.value, error.failure.code.value)


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
