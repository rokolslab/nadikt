"""Privacy-safe benchmark result DTOs and atomic publication helpers."""

from __future__ import annotations

import json
import math
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping

ALLOWED_TOP_LEVEL_KEYS = {
    "schema_version",
    "run_id",
    "run_kind",
    "nadikt_revision",
    "dataset",
    "candidates",
    "measurement",
    "settings",
    "offline_evidence",
    "privacy",
    "outcome",
}
ALLOWED_TOP_LEVEL_KEYS_V2 = {
    "schema_version",
    "run_id",
    "run_kind",
    "nadikt_revision",
    "dataset",
    "settings",
    "candidates",
    "measurement",
    "offline_evidence",
    "privacy",
    "validity",
    "outcome",
}
ALLOWED_CANDIDATE_KEYS_V2 = {"candidate_id", "package_id", "backend", "repeats_requested", "repeats_completed", "outcome", "repeat_outcomes", "quality_aggregates", "resource_aggregates"}
ALLOWED_REPEAT_KEYS_V2 = {"repeat_index", "outcome", "phase_outcomes", "sample_outcomes"}
ALLOWED_SAMPLE_KEYS_V2 = {"sample_id", "category", "scored", "outcome", "phase_outcomes", "metrics"}
ALLOWED_PHASE_KEYS_V2 = {"phase", "outcome", "duration_ms"}
ALLOWED_METRIC_KEYS_V2 = {"metric_name", "metric_version", "value", "numerator", "denominator", "status"}
RESULT_VERSIONS = {1, 2}


@dataclass(frozen=True)
class CandidateAggregate:
    candidate_id: str
    package_id: str
    backend: str
    repeats_requested: int
    repeats_completed: int
    outcome: str
    phase_outcomes: Mapping[str, str] = field(default_factory=dict)
    quality_aggregates: Mapping[str, Mapping[str, object]] = field(default_factory=dict)
    resource_aggregates: Mapping[str, object] = field(default_factory=dict)

    def to_json(self) -> dict[str, object]:
        return {
            "candidate_id": self.candidate_id,
            "package_id": self.package_id,
            "backend": self.backend,
            "repeats_requested": self.repeats_requested,
            "repeats_completed": self.repeats_completed,
            "outcome": self.outcome,
            "phase_outcomes": dict(sorted(self.phase_outcomes.items())),
            "quality_aggregates": {name: dict(value) for name, value in sorted(self.quality_aggregates.items())},
            "resource_aggregates": dict(sorted(self.resource_aggregates.items())),
        }


@dataclass(frozen=True)
class BenchmarkResult:
    run_id: str
    run_kind: str
    nadikt_revision: str
    dataset: Mapping[str, object]
    candidates: tuple[CandidateAggregate, ...]
    measurement: Mapping[str, object]
    offline_evidence: Mapping[str, object]
    privacy: Mapping[str, object]
    outcome: str
    settings: Mapping[str, object] = field(default_factory=dict)

    def to_json(self) -> dict[str, object]:
        payload = {
            "schema_version": 1,
            "run_id": self.run_id,
            "run_kind": self.run_kind,
            "nadikt_revision": self.nadikt_revision,
            "dataset": dict(self.dataset),
            "candidates": [candidate.to_json() for candidate in self.candidates],
            "measurement": dict(self.measurement),
            "settings": dict(self.settings),
            "offline_evidence": dict(self.offline_evidence),
            "privacy": dict(self.privacy),
            "outcome": self.outcome,
        }
        validate_result_payload(payload)
        return payload


def validate_result_payload(payload: Mapping[str, object]) -> None:
    version = payload.get("schema_version")
    if version == 1:
        _validate_result_payload_v1(payload)
        return
    if version == 2:
        _validate_result_payload_v2(payload)
        return
    raise ValueError("benchmark_result_unknown_schema_version")


def _validate_result_payload_v1(payload: Mapping[str, object]) -> None:
    unknown = set(payload).difference(ALLOWED_TOP_LEVEL_KEYS)
    if unknown:
        raise ValueError("benchmark_result_unknown_fields")
    _validate_json_numbers(payload)
    rendered = json.dumps(payload, ensure_ascii=False, sort_keys=True, allow_nan=False)
    forbidden = ("audio_path", "reference_text", "hypothesis", "transcript", "argv", "environment", "hostname")
    if any(marker in rendered for marker in forbidden):
        raise ValueError("benchmark_result_forbidden_payload")


def _validate_result_payload_v2(payload: Mapping[str, object]) -> None:
    unknown = set(payload).difference(ALLOWED_TOP_LEVEL_KEYS_V2)
    if unknown:
        raise ValueError("benchmark_result_unknown_fields")
    required = ALLOWED_TOP_LEVEL_KEYS_V2
    if required.difference(payload):
        raise ValueError("benchmark_result_missing_fields")
    candidates = payload.get("candidates")
    if not isinstance(candidates, list):
        raise ValueError("benchmark_result_candidates_not_list")
    for candidate in candidates:
        _validate_candidate_v2(candidate)
    _validate_json_numbers(payload)
    rendered = json.dumps(payload, ensure_ascii=False, sort_keys=True, allow_nan=False)
    forbidden = ("audio_path", "reference_text", "hypothesis", "transcript", "argv", "environment", "hostname")
    if any(marker in rendered for marker in forbidden):
        raise ValueError("benchmark_result_forbidden_payload")


def _validate_candidate_v2(value: object) -> None:
    if not isinstance(value, Mapping):
        raise ValueError("benchmark_result_candidate_not_object")
    if set(value).difference(ALLOWED_CANDIDATE_KEYS_V2):
        raise ValueError("benchmark_result_candidate_unknown_fields")
    if ALLOWED_CANDIDATE_KEYS_V2.difference(value):
        raise ValueError("benchmark_result_candidate_missing_fields")
    repeats = value["repeat_outcomes"]
    if not isinstance(repeats, list):
        raise ValueError("benchmark_result_repeats_not_list")
    for repeat in repeats:
        _validate_repeat_v2(repeat)


def _validate_repeat_v2(value: object) -> None:
    if not isinstance(value, Mapping):
        raise ValueError("benchmark_result_repeat_not_object")
    if set(value).difference(ALLOWED_REPEAT_KEYS_V2):
        raise ValueError("benchmark_result_repeat_unknown_fields")
    if ALLOWED_REPEAT_KEYS_V2.difference(value):
        raise ValueError("benchmark_result_repeat_missing_fields")
    _validate_phase_outcomes_v2(value["phase_outcomes"])
    samples = value["sample_outcomes"]
    if not isinstance(samples, list):
        raise ValueError("benchmark_result_samples_not_list")
    for sample in samples:
        _validate_sample_v2(sample)


def _validate_sample_v2(value: object) -> None:
    if not isinstance(value, Mapping):
        raise ValueError("benchmark_result_sample_not_object")
    if set(value).difference(ALLOWED_SAMPLE_KEYS_V2):
        raise ValueError("benchmark_result_sample_unknown_fields")
    if ALLOWED_SAMPLE_KEYS_V2.difference(value):
        raise ValueError("benchmark_result_sample_missing_fields")
    _validate_phase_outcomes_v2(value["phase_outcomes"])
    metrics = value["metrics"]
    if not isinstance(metrics, list):
        raise ValueError("benchmark_result_metrics_not_list")
    for metric in metrics:
        if not isinstance(metric, Mapping):
            raise ValueError("benchmark_result_metric_not_object")
        if set(metric).difference(ALLOWED_METRIC_KEYS_V2):
            raise ValueError("benchmark_result_metric_unknown_fields")
        if ALLOWED_METRIC_KEYS_V2.difference(metric):
            raise ValueError("benchmark_result_metric_missing_fields")


def _validate_phase_outcomes_v2(value: object) -> None:
    if not isinstance(value, list):
        raise ValueError("benchmark_result_phases_not_list")
    for phase in value:
        if not isinstance(phase, Mapping):
            raise ValueError("benchmark_result_phase_not_object")
        if set(phase).difference(ALLOWED_PHASE_KEYS_V2):
            raise ValueError("benchmark_result_phase_unknown_fields")
        if ALLOWED_PHASE_KEYS_V2.difference(phase):
            raise ValueError("benchmark_result_phase_missing_fields")


def _validate_json_numbers(value: object) -> None:
    if isinstance(value, bool) or value is None or isinstance(value, str):
        return
    if isinstance(value, (int, float)):
        if not math.isfinite(float(value)):
            raise ValueError("benchmark_result_non_finite_number")
        return
    if isinstance(value, Mapping):
        for nested in value.values():
            _validate_json_numbers(nested)
        return
    if isinstance(value, list):
        for nested in value:
            _validate_json_numbers(nested)
        return


def write_result_atomic(result: BenchmarkResult, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(result.to_json(), ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=output_path.parent, delete=False) as file:
        temp_path = Path(file.name)
        file.write(payload)
        file.write("\n")
    temp_path.replace(output_path)


__all__ = ["BenchmarkResult", "CandidateAggregate", "RESULT_VERSIONS", "validate_result_payload", "write_result_atomic"]
