"""Privacy-safe offline evidence DTOs for local ASR worker runs."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class OfflineEvidence:
    evidence_id: str
    mechanism: str
    mechanism_version: str
    status: str
    network_attempted: bool
    monitor_interval_ms: int | None = None

    def to_json(self) -> dict[str, object]:
        data: dict[str, object] = {
            "evidence_id": self.evidence_id,
            "mechanism": self.mechanism,
            "mechanism_version": self.mechanism_version,
            "status": self.status,
            "network_attempted": self.network_attempted,
        }
        if self.monitor_interval_ms is not None:
            data["monitor_interval_ms"] = self.monitor_interval_ms
        return data


def unverified_evidence(nonce: str) -> OfflineEvidence:
    return OfflineEvidence(
        evidence_id="offline-evidence-" + nonce[:12],
        mechanism="external_default_deny_required",
        mechanism_version="v1",
        status="NOT VERIFIED",
        network_attempted=False,
    )


__all__ = ["OfflineEvidence", "unverified_evidence"]
