"""Offline evidence helpers for spawned ASR workers."""

from __future__ import annotations

from .offline_evidence import OfflineEvidence, OfflineMonitorObservation, qualified_evidence, unverified_evidence


def build_unverified_worker_evidence(nonce: str) -> OfflineEvidence:
    """Return explicit non-PASS evidence until a qualified monitor is wired."""

    return unverified_evidence(nonce)


def build_worker_evidence(
    nonce: str,
    *,
    observation: OfflineMonitorObservation | None,
    nadikt_revision: str = "unknown",
    lock_digest_prefix: str = "unknown",
    package_digest_prefix: str = "unknown",
) -> OfflineEvidence:
    """Build fail-closed worker evidence from a qualified monitor observation."""

    return qualified_evidence(
        nonce,
        observation=observation,
        nadikt_revision=nadikt_revision,
        lock_digest_prefix=lock_digest_prefix,
        package_digest_prefix=package_digest_prefix,
    )


__all__ = ["build_unverified_worker_evidence", "build_worker_evidence"]
