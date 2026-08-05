"""UI Automation target-safety provider boundary.

The default provider fails closed unless a Windows UIA facade is injected by a
controlled host composition root. UIA element names, automation IDs, handles,
PIDs, process names and COM reprs never leave the facade boundary.
"""

from __future__ import annotations

import hashlib
import logging
import os
from dataclasses import dataclass
from typing import Protocol

from nadikt.domain.ports.insertion import (
    TargetCapturePort,
    TargetCaptureResult,
    TargetRevalidationResult,
    TargetSafetyOutcome,
    TargetToken,
)

LOGGER = logging.getLogger(__name__)
_LOG_LEVEL = os.environ.get("NADIKT_LOG_LEVEL", os.environ.get("LOG_LEVEL", "INFO")).upper()
logging.basicConfig(level=getattr(logging, _LOG_LEVEL, logging.INFO))


class UiaFacade(Protocol):
    """Injected Windows UIA facade returning only safe probe data."""

    def focused_element_probe(self) -> "UiaElementProbe":
        """Return current focused element safety facts."""


@dataclass(frozen=True, repr=False)
class UiaElementProbe:
    """Sanitized UIA focused element facts."""

    runtime_id_parts: tuple[int, ...]
    provider_kind: str
    protection_known: bool
    is_password: bool
    is_available: bool
    integrity_level_known: bool
    elevated: bool
    process_marker: str

    def __repr__(self) -> str:
        return (
            "UiaElementProbe("
            f"runtime_id_hash={_runtime_hash(self.runtime_id_parts)!r}, "
            f"provider_kind={self.provider_kind!r}, "
            f"protection_known={self.protection_known!r}, "
            f"is_password={self.is_password!r}, "
            f"is_available={self.is_available!r}, "
            f"integrity_level_known={self.integrity_level_known!r}, "
            f"elevated={self.elevated!r})"
        )


@dataclass(frozen=True, repr=False)
class _TargetSnapshot:
    runtime_hash: str
    provider_kind: str
    process_marker: str
    protection_known: bool
    elevated: bool

    def __repr__(self) -> str:
        return (
            "_TargetSnapshot("
            f"runtime_hash={self.runtime_hash!r}, provider_kind={self.provider_kind!r}, "
            f"protection_known={self.protection_known!r}, elevated={self.elevated!r})"
        )


class UiaTargetSafetyProvider(TargetCapturePort):
    """Capture and revalidate focused UIA target snapshots."""

    def __init__(self, facade: UiaFacade | None = None) -> None:
        self._facade = facade
        self._snapshots: dict[str, _TargetSnapshot] = {}

    def capture_current_target(self) -> TargetCaptureResult:
        LOGGER.debug("uia.capture.start", extra={"provider": "uia"})
        probe = self._probe()
        token = TargetToken()
        outcome = _outcome_for_probe(probe)
        if outcome == TargetSafetyOutcome.SAFE:
            self._snapshots[token.value] = _TargetSnapshot(
                runtime_hash=_runtime_hash(probe.runtime_id_parts),
                provider_kind=probe.provider_kind,
                process_marker=probe.process_marker,
                protection_known=probe.protection_known,
                elevated=probe.elevated,
            )
        LOGGER.debug(
            "uia.capture.complete",
            extra={
                "outcome": outcome.value,
                "provider_kind": probe.provider_kind,
                "protection_known": probe.protection_known,
                "safe_to_insert": outcome == TargetSafetyOutcome.SAFE,
            },
        )
        return TargetCaptureResult(
            token=token,
            outcome=outcome,
            provider=probe.provider_kind,
            protection_known=probe.protection_known,
            safe_to_insert=outcome == TargetSafetyOutcome.SAFE,
        )

    def revalidate_target(self, token: TargetToken) -> TargetRevalidationResult:
        LOGGER.debug("uia.revalidate.start", extra={"token": "<opaque>"})
        snapshot = self._snapshots.get(token.value)
        if snapshot is None:
            return TargetRevalidationResult(token, TargetSafetyOutcome.STALE_TOKEN, False, False, False)
        probe = self._probe()
        outcome = _outcome_for_probe(probe)
        identity_stable = (
            snapshot.runtime_hash == _runtime_hash(probe.runtime_id_parts)
            and snapshot.process_marker == probe.process_marker
            and snapshot.provider_kind == probe.provider_kind
        )
        if outcome == TargetSafetyOutcome.SAFE and not identity_stable:
            outcome = TargetSafetyOutcome.TARGET_CHANGED
        LOGGER.debug(
            "uia.revalidate.complete",
            extra={
                "outcome": outcome.value,
                "identity_stable": identity_stable,
                "protection_known": probe.protection_known,
                "safe_to_insert": outcome == TargetSafetyOutcome.SAFE,
            },
        )
        return TargetRevalidationResult(
            token=token,
            outcome=outcome,
            identity_stable=identity_stable,
            protection_known=probe.protection_known,
            safe_to_insert=outcome == TargetSafetyOutcome.SAFE,
        )

    def invalidate_target(self, token: TargetToken) -> None:
        self._snapshots.pop(token.value, None)
        LOGGER.debug("uia.invalidate.complete", extra={"token": "<opaque>", "remaining_tokens": len(self._snapshots)})

    def _probe(self) -> UiaElementProbe:
        if self._facade is None:
            return UiaElementProbe((), "unavailable", False, False, False, False, False, "unknown")
        try:
            return self._facade.focused_element_probe()
        except Exception:
            LOGGER.debug("uia.probe.failed", extra={"outcome": TargetSafetyOutcome.TARGET_UNAVAILABLE.value})
            return UiaElementProbe((), "unavailable", False, False, False, False, False, "unknown")


def _outcome_for_probe(probe: UiaElementProbe) -> TargetSafetyOutcome:
    if not probe.is_available:
        return TargetSafetyOutcome.TARGET_UNAVAILABLE
    if not probe.provider_kind or probe.provider_kind == "unknown":
        return TargetSafetyOutcome.UNKNOWN_PROVIDER
    if not probe.protection_known:
        return TargetSafetyOutcome.UNKNOWN_PROVIDER
    if probe.is_password:
        return TargetSafetyOutcome.TARGET_PROTECTED
    if not probe.integrity_level_known or probe.elevated:
        return TargetSafetyOutcome.TARGET_ELEVATED
    return TargetSafetyOutcome.SAFE


def _runtime_hash(runtime_id_parts: tuple[int, ...]) -> str:
    material = ":".join(str(part) for part in runtime_id_parts).encode("utf-8")
    return hashlib.sha256(material).hexdigest()[:16]


__all__ = ["UiaElementProbe", "UiaFacade", "UiaTargetSafetyProvider"]
