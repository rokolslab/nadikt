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
    "offline_evidence",
    "privacy",
    "outcome",
}


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

    def to_json(self) -> dict[str, object]:
        payload = {
            "schema_version": 1,
            "run_id": self.run_id,
            "run_kind": self.run_kind,
            "nadikt_revision": self.nadikt_revision,
            "dataset": dict(self.dataset),
            "candidates": [candidate.to_json() for candidate in self.candidates],
            "measurement": dict(self.measurement),
            "offline_evidence": dict(self.offline_evidence),
            "privacy": dict(self.privacy),
            "outcome": self.outcome,
        }
        validate_result_payload(payload)
        return payload


def validate_result_payload(payload: Mapping[str, object]) -> None:
    unknown = set(payload).difference(ALLOWED_TOP_LEVEL_KEYS)
    if unknown:
        raise ValueError("benchmark_result_unknown_fields")
    rendered = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    forbidden = ("audio_path", "reference_text", "hypothesis", "transcript", "argv", "environment", "hostname")
    if any(marker in rendered for marker in forbidden):
        raise ValueError("benchmark_result_forbidden_payload")
    _validate_json_numbers(payload)


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
    payload = json.dumps(result.to_json(), ensure_ascii=False, indent=2, sort_keys=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=output_path.parent, delete=False) as file:
        temp_path = Path(file.name)
        file.write(payload)
        file.write("\n")
    temp_path.replace(output_path)


__all__ = ["BenchmarkResult", "CandidateAggregate", "validate_result_payload", "write_result_atomic"]
