"""Bounded JSON protocol for spawned ASR benchmark workers."""

from __future__ import annotations

import json
import secrets
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

PROTOCOL_VERSION = 1
MAX_MESSAGE_BYTES = 128 * 1024
SAFE_RESULT_KEYS = {
    "schema_version",
    "nonce",
    "package_id",
    "candidate_id",
    "backend",
    "worker_status",
    "phases",
    "offline_evidence",
}
SAFE_PHASE_KEYS = {"phase", "outcome", "duration_ms", "segment_id"}


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
    duration_seconds: float | None = None

    def __repr__(self) -> str:
        return (
            "WorkerRequest("
            f"nonce_prefix={self.nonce[:8]!r}, package_id={self.package_id!r}, "
            f"candidate_id={self.candidate_id!r}, backend={self.backend!r}, "
            f"audio_provided={self.audio_file is not None})"
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
            "duration_seconds": self.duration_seconds,
        }
        return dumps_bounded(payload)


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
            "offline_evidence": dict(self.offline_evidence),
        }

    def to_worker_json(self) -> str:
        return dumps_bounded(self.to_json())


def new_nonce() -> str:
    return secrets.token_hex(16)


def dumps_bounded(payload: Mapping[str, Any]) -> str:
    text = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    if len(text.encode("utf-8")) > MAX_MESSAGE_BYTES:
        raise ValueError("worker_message_too_large")
    return text


def loads_request(text: str) -> WorkerRequest:
    payload = _loads_bounded(text)
    if payload.get("schema_version") != PROTOCOL_VERSION:
        raise ValueError("invalid_worker_protocol_version")
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
        duration_seconds=float(payload["duration_seconds"]) if payload.get("duration_seconds") is not None else None,
    )


def loads_result(text: str) -> WorkerResult:
    payload = _loads_bounded(text)
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
        offline_evidence=_mapping(payload.get("offline_evidence")),
    )


def _loads_bounded(text: str) -> dict[str, Any]:
    if len(text.encode("utf-8")) > MAX_MESSAGE_BYTES:
        raise ValueError("worker_message_too_large")
    payload = json.loads(text)
    if not isinstance(payload, dict):
        raise ValueError("worker_message_not_object")
    return payload


def _mapping(value: object) -> Mapping[str, Any]:
    if isinstance(value, Mapping):
        return value
    return {}


__all__ = [
    "MAX_MESSAGE_BYTES",
    "PROTOCOL_VERSION",
    "WorkerPhase",
    "WorkerRequest",
    "WorkerResult",
    "dumps_bounded",
    "loads_request",
    "loads_result",
    "new_nonce",
]
