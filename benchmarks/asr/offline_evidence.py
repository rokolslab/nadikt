"""Privacy-safe offline evidence DTOs for local ASR worker runs."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

OFFLINE_EVIDENCE_STATUSES = {"PASS", "FAIL", "NOT VERIFIED"}


@dataclass(frozen=True)
class OfflineEvidence:
    evidence_id: str
    mechanism: str
    mechanism_version: str
    status: str
    network_attempted: bool
    missed_event_count: int = 0
    finalized_after_reap: bool = False
    monitor_interval_ms: int | None = None
    reason: str | None = None
    nonce_prefix: str | None = None
    nadikt_revision: str | None = None
    lock_digest_prefix: str | None = None
    package_digest_prefix: str | None = None
    process_identity: Mapping[str, object] | None = None

    def to_json(self) -> dict[str, object]:
        if self.status not in OFFLINE_EVIDENCE_STATUSES:
            raise ValueError("offline_evidence_invalid_status")
        data: dict[str, object] = {
            "evidence_id": self.evidence_id,
            "mechanism": self.mechanism,
            "mechanism_version": self.mechanism_version,
            "status": self.status,
            "network_attempted": self.network_attempted,
            "missed_event_count": self.missed_event_count,
            "finalized_after_reap": self.finalized_after_reap,
        }
        if self.monitor_interval_ms is not None:
            data["monitor_interval_ms"] = self.monitor_interval_ms
        if self.reason is not None:
            data["reason"] = self.reason
        if self.nonce_prefix is not None:
            data["nonce_prefix"] = self.nonce_prefix
        if self.nadikt_revision is not None:
            data["nadikt_revision"] = self.nadikt_revision
        if self.lock_digest_prefix is not None:
            data["lock_digest_prefix"] = self.lock_digest_prefix
        if self.package_digest_prefix is not None:
            data["package_digest_prefix"] = self.package_digest_prefix
        if self.process_identity is not None:
            data["process_identity"] = dict(self.process_identity)
        return data


def unverified_evidence(nonce: str, *, reason: str = "qualified_monitor_not_configured") -> OfflineEvidence:
    return OfflineEvidence(
        evidence_id="offline-evidence-" + nonce[:12],
        mechanism="external_default_deny_required",
        mechanism_version="v1",
        status="NOT VERIFIED",
        network_attempted=False,
        reason=reason,
        nonce_prefix=nonce[:12],
    )


@dataclass(frozen=True)
class OfflineMonitorObservation:
    """Sanitized result from a qualified network monitor.

    The monitor implementation must keep raw packet/socket evidence outside Git;
    this DTO carries only aggregate counts and safe identity fields.
    """

    mechanism: str
    mechanism_version: str
    finalized_after_reap: bool
    observed_attempt_count: int
    missed_event_count: int
    monitor_interval_ms: int
    positive_control_passed: bool
    negative_control_passed: bool
    process_identity: Mapping[str, object]


def qualified_evidence(
    nonce: str,
    *,
    observation: OfflineMonitorObservation | None,
    nadikt_revision: str,
    lock_digest_prefix: str,
    package_digest_prefix: str,
) -> OfflineEvidence:
    if observation is None:
        return unverified_evidence(nonce)
    if observation.observed_attempt_count > 0:
        status = "FAIL"
        reason = "network_attempt_observed"
    elif not observation.finalized_after_reap:
        status = "NOT VERIFIED"
        reason = "monitor_not_finalized_after_reap"
    elif observation.missed_event_count > 0:
        status = "NOT VERIFIED"
        reason = "monitor_missed_events"
    elif not observation.positive_control_passed or not observation.negative_control_passed:
        status = "NOT VERIFIED"
        reason = "monitor_controls_incomplete"
    else:
        status = "PASS"
        reason = "default_deny_observed_zero_attempts"
    return OfflineEvidence(
        evidence_id="offline-evidence-" + nonce[:12],
        mechanism=observation.mechanism,
        mechanism_version=observation.mechanism_version,
        status=status,
        network_attempted=observation.observed_attempt_count > 0,
        missed_event_count=observation.missed_event_count,
        finalized_after_reap=observation.finalized_after_reap,
        monitor_interval_ms=observation.monitor_interval_ms,
        reason=reason,
        nonce_prefix=nonce[:12],
        nadikt_revision=nadikt_revision,
        lock_digest_prefix=lock_digest_prefix,
        package_digest_prefix=package_digest_prefix,
        process_identity=dict(observation.process_identity),
    )


__all__ = ["OFFLINE_EVIDENCE_STATUSES", "OfflineEvidence", "OfflineMonitorObservation", "qualified_evidence", "unverified_evidence"]
