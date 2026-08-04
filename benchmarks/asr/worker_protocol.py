"""Bounded JSON protocol for spawned ASR benchmark workers."""

from __future__ import annotations

import json
import math
import secrets
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

PROTOCOL_VERSION = 1
PROTOCOL_VERSION_V2 = 2
MAX_MESSAGE_BYTES = 128 * 1024
WORKER_STATUSES = {"success", "fail", "not_run", "protocol_error"}
SUPERVISOR_OUTCOMES = {"completed", "timeout", "terminated", "killed", "protocol_error", "privacy_error", "spawn_error", "nonzero_exit"}
PHASE_OUTCOMES = {
    "success",
    "fail",
    "not_run",
    "readiness_failed",
    "protocol_error",
    "unsupported_backend",
    "missing_package",
    "invalid_package_path",
    "checksum_mismatch",
    "missing_critical_file",
    "incompatible_backend",
    "license_not_verified",
    "engine_not_ready",
    "segment_too_long",
    "cancelled",
    "transcribe_failed",
    "warm_up_failed",
    "resource_release_failed",
}
SAMPLE_OUTCOMES = {"success", "fail", "not_run", "skipped"}
REPEAT_OUTCOMES = {"success", "fail", "not_run"}
SAFE_RESULT_KEYS = {
    "schema_version",
    "nonce",
    "package_id",
    "candidate_id",
    "backend",
    "worker_status",
    "phases",
    "quality_metrics",
    "offline_evidence",
}
SAFE_PHASE_KEYS = {"phase", "outcome", "duration_ms", "segment_id"}
SAFE_REQUEST_V2_KEYS = {"schema_version", "nonce", "package_id", "candidate_id", "backend", "package_dir", "capabilities", "inference_defaults", "critical_checksum_prefixes", "repeat"}
SAFE_REPEAT_REQUEST_KEYS = {"repeat_index", "warmup_sample", "scored_samples"}
SAFE_SAMPLE_REQUEST_KEYS = {"sample_id", "category", "audio_file", "reference_file", "duration_seconds", "scored", "expected_english_terms", "expected_coding_terms"}
SAFE_RESULT_V2_KEYS = {"schema_version", "nonce", "package_id", "candidate_id", "backend", "worker_status", "repeat"}
SAFE_REPEAT_OUTCOME_KEYS = {"repeat_index", "outcome", "phases", "samples"}
SAFE_SAMPLE_OUTCOME_KEYS = {"sample_id", "category", "scored", "outcome", "phases", "metrics", "metric_diagnostics"}
SAFE_METRIC_KEYS = {"metric_name", "metric_version", "value", "numerator", "denominator", "status"}
SAFE_METRIC_DIAGNOSTIC_KEYS = {"sample_id", "category", "metric_name", "view", "status", "numerator", "denominator", "reason_code", "count"}


@dataclass(frozen=True, repr=False)
class WorkerRequest:
    nonce: str
    package_id: str
    candidate_id: str
    backend: str
    package_dir: Path
    capabilities: Mapping[str, Any]
    inference_defaults: Mapping[str, Any]
    critical_checksum_prefixes: tuple[str, ...] = ()
    audio_file: Path | None = None
    reference_file: Path | None = None
    expected_english_terms: tuple[str, ...] = ()
    expected_coding_terms: tuple[Mapping[str, Any], ...] = ()
    duration_seconds: float | None = None

    def __repr__(self) -> str:
        return (
            "WorkerRequest("
            f"nonce_prefix={self.nonce[:8]!r}, package_id={self.package_id!r}, "
            f"candidate_id={self.candidate_id!r}, backend={self.backend!r}, "
            f"audio_provided={self.audio_file is not None}, "
            f"reference_provided={self.reference_file is not None})"
        )

    def to_worker_json(self) -> str:
        payload = {
            "schema_version": PROTOCOL_VERSION,
            "nonce": self.nonce,
            "package_id": self.package_id,
            "candidate_id": self.candidate_id,
            "backend": self.backend,
            "package_dir": str(self.package_dir),
            "capabilities": dict(self.capabilities),
            "inference_defaults": dict(self.inference_defaults),
            "critical_checksum_prefixes": list(self.critical_checksum_prefixes),
            "audio_file": str(self.audio_file) if self.audio_file is not None else None,
            "reference_file": str(self.reference_file) if self.reference_file is not None else None,
            "expected_english_terms": list(self.expected_english_terms),
            "expected_coding_terms": [dict(item) for item in self.expected_coding_terms],
            "duration_seconds": self.duration_seconds,
        }
        return dumps_bounded(payload)


@dataclass(frozen=True, repr=False)
class WorkerSampleRequest:
    sample_id: str
    category: str
    audio_file: Path
    reference_file: Path | None
    duration_seconds: float
    scored: bool
    expected_english_terms: tuple[str, ...] = ()
    expected_coding_terms: tuple[Mapping[str, Any], ...] = ()

    def __repr__(self) -> str:
        return f"WorkerSampleRequest(sample_id={self.sample_id!r}, category={self.category!r}, scored={self.scored!r})"

    def to_json(self) -> dict[str, object]:
        return {
            "sample_id": self.sample_id,
            "category": self.category,
            "audio_file": str(self.audio_file),
            "reference_file": str(self.reference_file) if self.reference_file is not None else None,
            "duration_seconds": self.duration_seconds,
            "scored": self.scored,
            "expected_english_terms": list(self.expected_english_terms),
            "expected_coding_terms": [dict(item) for item in self.expected_coding_terms],
        }


@dataclass(frozen=True, repr=False)
class WorkerRepeatRequest:
    repeat_index: int
    warmup_sample: WorkerSampleRequest
    scored_samples: tuple[WorkerSampleRequest, ...]

    def __repr__(self) -> str:
        return f"WorkerRepeatRequest(repeat_index={self.repeat_index!r}, scored_count={len(self.scored_samples)})"

    def to_json(self) -> dict[str, object]:
        return {
            "repeat_index": self.repeat_index,
            "warmup_sample": self.warmup_sample.to_json(),
            "scored_samples": [sample.to_json() for sample in self.scored_samples],
        }


@dataclass(frozen=True, repr=False)
class WorkerRequestV2:
    nonce: str
    package_id: str
    candidate_id: str
    backend: str
    package_dir: Path
    capabilities: Mapping[str, Any]
    inference_defaults: Mapping[str, Any]
    repeat: WorkerRepeatRequest
    critical_checksum_prefixes: tuple[str, ...] = ()

    def __repr__(self) -> str:
        return (
            "WorkerRequestV2("
            f"nonce_prefix={self.nonce[:8]!r}, package_id={self.package_id!r}, "
            f"candidate_id={self.candidate_id!r}, repeat_index={self.repeat.repeat_index!r})"
        )

    def to_worker_json(self) -> str:
        return dumps_bounded(
            {
                "schema_version": PROTOCOL_VERSION_V2,
                "nonce": self.nonce,
                "package_id": self.package_id,
                "candidate_id": self.candidate_id,
                "backend": self.backend,
                "package_dir": str(self.package_dir),
                "capabilities": dict(self.capabilities),
                "inference_defaults": dict(self.inference_defaults),
                "critical_checksum_prefixes": list(self.critical_checksum_prefixes),
                "repeat": self.repeat.to_json(),
            }
        )


@dataclass(frozen=True)
class WorkerPhase:
    phase: str
    outcome: str
    duration_ms: float = 0.0
    segment_id: int | None = None

    def to_json(self) -> dict[str, object]:
        data: dict[str, object] = {
            "phase": self.phase,
            "outcome": self.outcome,
            "duration_ms": round(self.duration_ms, 3),
        }
        if self.segment_id is not None:
            data["segment_id"] = self.segment_id
        return data


@dataclass(frozen=True, repr=False)
class WorkerResult:
    nonce: str
    package_id: str
    candidate_id: str
    backend: str
    worker_status: str
    phases: tuple[WorkerPhase, ...] = field(default_factory=tuple)
    quality_metrics: Mapping[str, Mapping[str, object]] = field(default_factory=dict)
    offline_evidence: Mapping[str, object] = field(default_factory=dict)

    def __repr__(self) -> str:
        return (
            "WorkerResult("
            f"nonce_prefix={self.nonce[:8]!r}, package_id={self.package_id!r}, "
            f"candidate_id={self.candidate_id!r}, backend={self.backend!r}, "
            f"worker_status={self.worker_status!r}, phase_count={len(self.phases)})"
        )

    def to_json(self) -> dict[str, object]:
        return {
            "schema_version": PROTOCOL_VERSION,
            "nonce": self.nonce,
            "package_id": self.package_id,
            "candidate_id": self.candidate_id,
            "backend": self.backend,
            "worker_status": self.worker_status,
            "phases": [phase.to_json() for phase in self.phases],
            "quality_metrics": {name: dict(value) for name, value in sorted(self.quality_metrics.items())},
            "offline_evidence": dict(self.offline_evidence),
        }

    def to_worker_json(self) -> str:
        return dumps_bounded(self.to_json())


@dataclass(frozen=True)
class WorkerMetricResult:
    metric_name: str
    metric_version: str
    value: float
    numerator: int
    denominator: int
    status: str

    def to_json(self) -> dict[str, object]:
        return {
            "metric_name": self.metric_name,
            "metric_version": self.metric_version,
            "value": self.value,
            "numerator": self.numerator,
            "denominator": self.denominator,
            "status": self.status,
        }


@dataclass(frozen=True)
class WorkerMetricDiagnostic:
    sample_id: str
    category: str
    metric_name: str
    view: str
    status: str
    numerator: int
    denominator: int
    reason_code: str
    count: int

    def to_json(self) -> dict[str, object]:
        return {
            "sample_id": self.sample_id,
            "category": self.category,
            "metric_name": self.metric_name,
            "view": self.view,
            "status": self.status,
            "numerator": self.numerator,
            "denominator": self.denominator,
            "reason_code": self.reason_code,
            "count": self.count,
        }


@dataclass(frozen=True)
class WorkerSampleOutcome:
    sample_id: str
    category: str
    scored: bool
    outcome: str
    phases: tuple[WorkerPhase, ...] = field(default_factory=tuple)
    metrics: tuple[WorkerMetricResult, ...] = field(default_factory=tuple)
    metric_diagnostics: tuple[WorkerMetricDiagnostic, ...] = field(default_factory=tuple)

    def to_json(self) -> dict[str, object]:
        return {
            "sample_id": self.sample_id,
            "category": self.category,
            "scored": self.scored,
            "outcome": self.outcome,
            "phases": [phase.to_json() for phase in self.phases],
            "metrics": [metric.to_json() for metric in self.metrics],
            "metric_diagnostics": [diagnostic.to_json() for diagnostic in self.metric_diagnostics],
        }


@dataclass(frozen=True)
class WorkerRepeatOutcome:
    repeat_index: int
    outcome: str
    phases: tuple[WorkerPhase, ...] = field(default_factory=tuple)
    samples: tuple[WorkerSampleOutcome, ...] = field(default_factory=tuple)

    def to_json(self) -> dict[str, object]:
        return {
            "repeat_index": self.repeat_index,
            "outcome": self.outcome,
            "phases": [phase.to_json() for phase in self.phases],
            "samples": [sample.to_json() for sample in self.samples],
        }


@dataclass(frozen=True, repr=False)
class WorkerResultV2:
    nonce: str
    package_id: str
    candidate_id: str
    backend: str
    worker_status: str
    repeat: WorkerRepeatOutcome

    def __repr__(self) -> str:
        return (
            "WorkerResultV2("
            f"nonce_prefix={self.nonce[:8]!r}, package_id={self.package_id!r}, "
            f"candidate_id={self.candidate_id!r}, worker_status={self.worker_status!r}, "
            f"repeat_index={self.repeat.repeat_index!r})"
        )

    def to_json(self) -> dict[str, object]:
        return {
            "schema_version": PROTOCOL_VERSION_V2,
            "nonce": self.nonce,
            "package_id": self.package_id,
            "candidate_id": self.candidate_id,
            "backend": self.backend,
            "worker_status": self.worker_status,
            "repeat": self.repeat.to_json(),
        }

    def to_worker_json(self) -> str:
        return dumps_bounded(self.to_json())


def new_nonce() -> str:
    return secrets.token_hex(16)


def dumps_bounded(payload: Mapping[str, Any]) -> str:
    _validate_finite_json(payload)
    text = json.dumps(payload, ensure_ascii=False, sort_keys=True, allow_nan=False)
    if len(text.encode("utf-8")) > MAX_MESSAGE_BYTES:
        raise ValueError("worker_message_too_large")
    return text


def loads_request(text: str) -> WorkerRequest:
    payload = _loads_bounded(text)
    if payload.get("schema_version") != PROTOCOL_VERSION:
        raise ValueError("invalid_worker_protocol_version")
    _require_keys(payload, {"schema_version", "nonce", "package_id", "candidate_id", "backend", "package_dir"}, "worker_request_missing_fields")
    return WorkerRequest(
        nonce=str(payload["nonce"]),
        package_id=str(payload["package_id"]),
        candidate_id=str(payload["candidate_id"]),
        backend=str(payload["backend"]),
        package_dir=Path(str(payload["package_dir"])),
        capabilities=_mapping(payload.get("capabilities")),
        inference_defaults=_mapping(payload.get("inference_defaults")),
        critical_checksum_prefixes=tuple(str(item) for item in payload.get("critical_checksum_prefixes", ())),
        audio_file=Path(str(payload["audio_file"])) if payload.get("audio_file") else None,
        reference_file=Path(str(payload["reference_file"])) if payload.get("reference_file") else None,
        expected_english_terms=tuple(str(item) for item in payload.get("expected_english_terms", ())),
        expected_coding_terms=tuple(_term_mapping(item) for item in payload.get("expected_coding_terms", ()) if isinstance(item, Mapping)),
        duration_seconds=float(payload["duration_seconds"]) if payload.get("duration_seconds") is not None else None,
    )


def loads_request_v2(text: str) -> WorkerRequestV2:
    payload = _loads_bounded(text)
    if payload.get("schema_version") != PROTOCOL_VERSION_V2:
        raise ValueError("invalid_worker_protocol_version")
    unknown = set(payload).difference(SAFE_REQUEST_V2_KEYS)
    if unknown:
        raise ValueError("worker_request_unknown_fields")
    _require_keys(payload, {"nonce", "package_id", "candidate_id", "backend", "package_dir", "repeat"}, "worker_request_missing_fields")
    repeat = _parse_repeat_request(payload["repeat"])
    return WorkerRequestV2(
        nonce=str(payload["nonce"]),
        package_id=str(payload["package_id"]),
        candidate_id=str(payload["candidate_id"]),
        backend=str(payload["backend"]),
        package_dir=Path(str(payload["package_dir"])),
        capabilities=_mapping(payload.get("capabilities")),
        inference_defaults=_mapping(payload.get("inference_defaults")),
        critical_checksum_prefixes=tuple(str(item) for item in payload.get("critical_checksum_prefixes", ())),
        repeat=repeat,
    )


def loads_result(text: str) -> WorkerResult:
    payload = _loads_bounded(text)
    if payload.get("schema_version") != PROTOCOL_VERSION:
        raise ValueError("invalid_worker_protocol_version")
    unknown = set(payload).difference(SAFE_RESULT_KEYS)
    if unknown:
        raise ValueError("worker_result_unknown_fields")
    phases = []
    for phase in payload.get("phases", []):
        if not isinstance(phase, Mapping):
            raise ValueError("worker_result_invalid_phase")
        if set(phase).difference(SAFE_PHASE_KEYS):
            raise ValueError("worker_phase_unknown_fields")
        phases.append(
            WorkerPhase(
                phase=str(phase["phase"]),
                outcome=str(phase["outcome"]),
                duration_ms=float(phase.get("duration_ms") or 0.0),
                segment_id=int(phase["segment_id"]) if phase.get("segment_id") is not None else None,
            )
        )
    return WorkerResult(
        nonce=str(payload["nonce"]),
        package_id=str(payload["package_id"]),
        candidate_id=str(payload["candidate_id"]),
        backend=str(payload["backend"]),
        worker_status=str(payload["worker_status"]),
        phases=tuple(phases),
        quality_metrics=_quality_mapping(payload.get("quality_metrics")),
        offline_evidence=_mapping(payload.get("offline_evidence")),
    )


def loads_result_v2(text: str) -> WorkerResultV2:
    payload = _loads_bounded(text)
    if payload.get("schema_version") != PROTOCOL_VERSION_V2:
        raise ValueError("invalid_worker_protocol_version")
    unknown = set(payload).difference(SAFE_RESULT_V2_KEYS)
    if unknown:
        raise ValueError("worker_result_unknown_fields")
    _require_keys(payload, {"nonce", "package_id", "candidate_id", "backend", "worker_status", "repeat"}, "worker_result_missing_fields")
    worker_status = str(payload["worker_status"])
    if worker_status not in WORKER_STATUSES:
        raise ValueError("worker_result_invalid_status")
    return WorkerResultV2(
        nonce=str(payload["nonce"]),
        package_id=str(payload["package_id"]),
        candidate_id=str(payload["candidate_id"]),
        backend=str(payload["backend"]),
        worker_status=worker_status,
        repeat=_parse_repeat_outcome(payload["repeat"]),
    )


def _loads_bounded(text: str) -> dict[str, Any]:
    if len(text.encode("utf-8")) > MAX_MESSAGE_BYTES:
        raise ValueError("worker_message_too_large")
    payload = json.loads(text)
    if not isinstance(payload, dict):
        raise ValueError("worker_message_not_object")
    _validate_finite_json(payload)
    return payload


def _parse_repeat_request(value: object) -> WorkerRepeatRequest:
    if not isinstance(value, Mapping):
        raise ValueError("worker_repeat_not_object")
    unknown = set(value).difference(SAFE_REPEAT_REQUEST_KEYS)
    if unknown:
        raise ValueError("worker_repeat_unknown_fields")
    _require_keys(value, {"repeat_index", "warmup_sample", "scored_samples"}, "worker_repeat_missing_fields")
    scored_raw = value["scored_samples"]
    if not isinstance(scored_raw, list) or not scored_raw:
        raise ValueError("worker_scored_samples_required")
    return WorkerRepeatRequest(
        repeat_index=_int_required(value["repeat_index"], "worker_repeat_invalid_index"),
        warmup_sample=_parse_sample_request(value["warmup_sample"], expected_scored=False),
        scored_samples=tuple(_parse_sample_request(sample, expected_scored=True) for sample in scored_raw),
    )


def _parse_sample_request(value: object, *, expected_scored: bool) -> WorkerSampleRequest:
    if not isinstance(value, Mapping):
        raise ValueError("worker_sample_not_object")
    unknown = set(value).difference(SAFE_SAMPLE_REQUEST_KEYS)
    if unknown:
        raise ValueError("worker_sample_unknown_fields")
    _require_keys(value, {"sample_id", "category", "audio_file", "duration_seconds", "scored"}, "worker_sample_missing_fields")
    scored = bool(value["scored"])
    if scored is not expected_scored:
        raise ValueError("worker_sample_scored_mismatch")
    return WorkerSampleRequest(
        sample_id=str(value["sample_id"]),
        category=str(value["category"]),
        audio_file=Path(str(value["audio_file"])),
        reference_file=Path(str(value["reference_file"])) if value.get("reference_file") else None,
        duration_seconds=_float_required(value["duration_seconds"], "worker_sample_invalid_duration"),
        scored=scored,
        expected_english_terms=tuple(str(item) for item in value.get("expected_english_terms", ())),
        expected_coding_terms=tuple(_term_mapping(item) for item in value.get("expected_coding_terms", ()) if isinstance(item, Mapping)),
    )


def _parse_repeat_outcome(value: object) -> WorkerRepeatOutcome:
    if not isinstance(value, Mapping):
        raise ValueError("worker_repeat_not_object")
    unknown = set(value).difference(SAFE_REPEAT_OUTCOME_KEYS)
    if unknown:
        raise ValueError("worker_repeat_unknown_fields")
    _require_keys(value, {"repeat_index", "outcome", "phases", "samples"}, "worker_repeat_missing_fields")
    outcome = str(value["outcome"])
    if outcome not in REPEAT_OUTCOMES:
        raise ValueError("worker_repeat_invalid_outcome")
    phases = _parse_phases(value["phases"])
    samples_raw = value["samples"]
    if not isinstance(samples_raw, list):
        raise ValueError("worker_samples_not_list")
    return WorkerRepeatOutcome(
        repeat_index=_int_required(value["repeat_index"], "worker_repeat_invalid_index"),
        outcome=outcome,
        phases=phases,
        samples=tuple(_parse_sample_outcome(sample) for sample in samples_raw),
    )


def _parse_sample_outcome(value: object) -> WorkerSampleOutcome:
    if not isinstance(value, Mapping):
        raise ValueError("worker_sample_not_object")
    unknown = set(value).difference(SAFE_SAMPLE_OUTCOME_KEYS)
    if unknown:
        raise ValueError("worker_sample_unknown_fields")
    _require_keys(value, {"sample_id", "category", "scored", "outcome", "phases", "metrics"}, "worker_sample_missing_fields")
    outcome = str(value["outcome"])
    if outcome not in SAMPLE_OUTCOMES:
        raise ValueError("worker_sample_invalid_outcome")
    metrics_raw = value["metrics"]
    if not isinstance(metrics_raw, list):
        raise ValueError("worker_metrics_not_list")
    diagnostics_raw = value.get("metric_diagnostics", [])
    if not isinstance(diagnostics_raw, list):
        raise ValueError("worker_metric_diagnostics_not_list")
    return WorkerSampleOutcome(
        sample_id=str(value["sample_id"]),
        category=str(value["category"]),
        scored=bool(value["scored"]),
        outcome=outcome,
        phases=_parse_phases(value["phases"]),
        metrics=tuple(_parse_metric(metric) for metric in metrics_raw),
        metric_diagnostics=tuple(_parse_metric_diagnostic(diagnostic) for diagnostic in diagnostics_raw),
    )


def _parse_metric(value: object) -> WorkerMetricResult:
    if not isinstance(value, Mapping):
        raise ValueError("worker_metric_not_object")
    unknown = set(value).difference(SAFE_METRIC_KEYS)
    if unknown:
        raise ValueError("worker_metric_unknown_fields")
    _require_keys(value, SAFE_METRIC_KEYS, "worker_metric_missing_fields")
    return WorkerMetricResult(
        metric_name=str(value["metric_name"]),
        metric_version=str(value["metric_version"]),
        value=_float_required(value["value"], "worker_metric_invalid_value"),
        numerator=_int_required(value["numerator"], "worker_metric_invalid_numerator"),
        denominator=_int_required(value["denominator"], "worker_metric_invalid_denominator"),
        status=str(value["status"]),
    )


def _parse_metric_diagnostic(value: object) -> WorkerMetricDiagnostic:
    if not isinstance(value, Mapping):
        raise ValueError("worker_metric_diagnostic_not_object")
    unknown = set(value).difference(SAFE_METRIC_DIAGNOSTIC_KEYS)
    if unknown:
        raise ValueError("worker_metric_diagnostic_unknown_fields")
    _require_keys(value, SAFE_METRIC_DIAGNOSTIC_KEYS, "worker_metric_diagnostic_missing_fields")
    return WorkerMetricDiagnostic(
        sample_id=str(value["sample_id"]),
        category=str(value["category"]),
        metric_name=str(value["metric_name"]),
        view=str(value["view"]),
        status=str(value["status"]),
        numerator=_int_required(value["numerator"], "worker_metric_diagnostic_invalid_numerator"),
        denominator=_int_required(value["denominator"], "worker_metric_diagnostic_invalid_denominator"),
        reason_code=str(value["reason_code"]),
        count=_int_required(value["count"], "worker_metric_diagnostic_invalid_count"),
    )


def _parse_phases(value: object) -> tuple[WorkerPhase, ...]:
    if not isinstance(value, list):
        raise ValueError("worker_phases_not_list")
    phases = []
    for phase in value:
        if not isinstance(phase, Mapping):
            raise ValueError("worker_result_invalid_phase")
        if set(phase).difference(SAFE_PHASE_KEYS):
            raise ValueError("worker_phase_unknown_fields")
        _require_keys(phase, {"phase", "outcome", "duration_ms"}, "worker_phase_missing_fields")
        outcome = str(phase["outcome"])
        if outcome not in PHASE_OUTCOMES:
            raise ValueError("worker_phase_invalid_outcome")
        phases.append(
            WorkerPhase(
                phase=str(phase["phase"]),
                outcome=outcome,
                duration_ms=_float_required(phase.get("duration_ms"), "worker_phase_invalid_duration"),
                segment_id=int(phase["segment_id"]) if phase.get("segment_id") is not None else None,
            )
        )
    return tuple(phases)


def _mapping(value: object) -> Mapping[str, Any]:
    if isinstance(value, Mapping):
        return value
    return {}


def _term_mapping(value: Mapping[str, Any]) -> Mapping[str, Any]:
    return dict(value)


def _quality_mapping(value: object) -> Mapping[str, Mapping[str, object]]:
    if not isinstance(value, Mapping):
        return {}
    result: dict[str, Mapping[str, object]] = {}
    for name, metric in value.items():
        if isinstance(metric, Mapping):
            result[str(name)] = dict(metric)
    return result


def _require_keys(value: Mapping[str, object], required: set[str], error: str) -> None:
    if required.difference(value):
        raise ValueError(error)


def _float_required(value: object, error: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(error)
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(error)
    return result


def _int_required(value: object, error: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(error)
    return value


def _validate_finite_json(value: object) -> None:
    if isinstance(value, bool) or value is None or isinstance(value, str):
        return
    if isinstance(value, (int, float)):
        if not math.isfinite(float(value)):
            raise ValueError("worker_message_non_finite_number")
        return
    if isinstance(value, Mapping):
        for nested in value.values():
            _validate_finite_json(nested)
        return
    if isinstance(value, list):
        for nested in value:
            _validate_finite_json(nested)


__all__ = [
    "MAX_MESSAGE_BYTES",
    "PROTOCOL_VERSION",
    "PROTOCOL_VERSION_V2",
    "SUPERVISOR_OUTCOMES",
    "WorkerMetricResult",
    "WorkerPhase",
    "WorkerRepeatOutcome",
    "WorkerRepeatRequest",
    "WorkerRequest",
    "WorkerRequestV2",
    "WorkerResult",
    "WorkerResultV2",
    "WorkerSampleOutcome",
    "WorkerSampleRequest",
    "dumps_bounded",
    "loads_request",
    "loads_request_v2",
    "loads_result",
    "loads_result_v2",
    "new_nonce",
]
