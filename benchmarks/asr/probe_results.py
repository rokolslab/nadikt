"""Privacy-safe result DTOs for local ASR package probes."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping

SAFE_DETAIL_KEYS = {"segment_count", "warning_count", "resource_count", "phase_count"}


class ProbeOutcome(str, Enum):
    SUCCESS = "success"
    PACKAGE_PRESENT = "package_present"
    MISSING_PACKAGE = "missing_package"
    INVALID_PACKAGE_PATH = "invalid_package_path"
    MISSING_CRITICAL_FILE = "missing_critical_file"
    CHECKSUM_MISMATCH = "checksum_mismatch"
    INVALID_CHECKSUM = "invalid_checksum"
    LICENSE_NOT_VERIFIED = "license_not_verified"
    INCOMPATIBLE_BACKEND = "incompatible_backend"
    BACKEND_UNAVAILABLE = "backend_unavailable"
    LOCAL_LOADING_UNCONFIRMED = "local_loading_unconfirmed"
    HUB_IDENTIFIER_REJECTED = "hub_identifier_rejected"
    NOT_RUN = "not_run"
    SKIPPED = "skipped"
    LOAD_FAILED = "load_failed"
    READINESS_FAILED = "readiness_failed"
    WARMUP_FAILED = "warmup_failed"
    TRANSCRIBE_FAILED = "transcribe_failed"
    SEGMENT_TOO_LONG = "segment_too_long"
    CLOSE_FAILED = "close_failed"


@dataclass(frozen=True, repr=False)
class ProbePhaseResult:
    phase: str
    outcome: str
    duration_ms: float = 0.0
    reason_code: str | None = None
    details: Mapping[str, Any] = field(default_factory=dict)

    def __repr__(self) -> str:
        return (
            "ProbePhaseResult("
            f"phase={self.phase!r}, outcome={self.outcome!r}, "
            f"duration_ms={self.duration_ms:.3f}, reason_code={self.reason_code!r})"
        )

    def to_json(self) -> dict[str, Any]:
        safe = {
            "phase": self.phase,
            "outcome": self.outcome,
            "duration_ms": round(self.duration_ms, 3),
        }
        if self.reason_code:
            safe["reason_code"] = self.reason_code
        if self.details:
            safe["details"] = _safe_details(self.details)
        return safe


@dataclass(frozen=True, repr=False)
class ProbePackageResult:
    package_id: str
    candidate_id: str
    backend: str
    outcome: str
    checksum_prefixes: tuple[str, ...] = ()
    phases: tuple[ProbePhaseResult, ...] = ()
    warnings: tuple[str, ...] = ()

    def __repr__(self) -> str:
        return (
            "ProbePackageResult("
            f"package_id={self.package_id!r}, candidate_id={self.candidate_id!r}, "
            f"backend={self.backend!r}, outcome={self.outcome!r})"
        )

    def to_json(self) -> dict[str, Any]:
        return {
            "package_id": self.package_id,
            "candidate_id": self.candidate_id,
            "backend": self.backend,
            "outcome": self.outcome,
            "checksum_prefixes": list(self.checksum_prefixes),
            "warnings": list(self.warnings),
            "phases": [phase.to_json() for phase in self.phases],
        }


__all__ = ["ProbeOutcome", "ProbePackageResult", "ProbePhaseResult"]


def _safe_details(details: Mapping[str, Any]) -> dict[str, Any]:
    safe: dict[str, Any] = {}
    for key, value in details.items():
        if key not in SAFE_DETAIL_KEYS:
            continue
        if isinstance(value, (bool, int, float, str)):
            safe[key] = value
    return safe
