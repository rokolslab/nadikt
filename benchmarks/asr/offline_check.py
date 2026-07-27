"""Offline acceptance helpers for local ASR benchmark runs."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from .logging_config import get_logger
LOGGER = get_logger(__name__)


@dataclass(frozen=True)
class OfflineCheckResult:
    outcome: str
    network_block_required: bool
    network_attempted: bool
    package_id: str | None = None

    def safe_log_context(self) -> dict[str, object]:
        return {
            "outcome": self.outcome,
            "network_block_required": self.network_block_required,
            "network_attempted": self.network_attempted,
            "package_id": self.package_id,
        }


def current_offline_policy() -> bool:
    """Return whether the caller requires an externally blocked network."""

    return os.environ.get("NADIKT_BENCHMARK_OFFLINE_REQUIRED", "0") == "1"


def validate_local_package(package_id: str, package_path: Path, root: Path) -> OfflineCheckResult:
    """Classify local package availability without attempting network access."""

    resolved = root / package_path
    if not resolved.exists():
        result = OfflineCheckResult(
            outcome="missing_package",
            network_block_required=current_offline_policy(),
            network_attempted=False,
            package_id=package_id,
        )
        LOGGER.info("offline_package_check", extra=result.safe_log_context())
        return result

    result = OfflineCheckResult(
        outcome="package_present",
        network_block_required=current_offline_policy(),
        network_attempted=False,
        package_id=package_id,
    )
    LOGGER.info("offline_package_check", extra=result.safe_log_context())
    return result
