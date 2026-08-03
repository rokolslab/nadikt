"""Offline evidence helpers for spawned ASR workers."""

from __future__ import annotations

from .offline_evidence import OfflineEvidence, unverified_evidence


def build_unverified_worker_evidence(nonce: str) -> OfflineEvidence:
    """Return explicit non-PASS evidence until a qualified monitor is wired."""

    return unverified_evidence(nonce)


__all__ = ["build_unverified_worker_evidence"]
