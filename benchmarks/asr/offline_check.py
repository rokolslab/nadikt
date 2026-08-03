"""Offline acceptance helpers for local ASR benchmark runs."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

from .logging_config import get_logger
from .package_integrity import validate_package_integrity
LOGGER = get_logger(__name__)


@dataclass(frozen=True)
class OfflineCheckResult:
    outcome: str
    network_block_required: bool
    network_attempted: bool
    package_id: str | None = None
    checksum_prefixes: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()

    def safe_log_context(self) -> dict[str, object]:
        return {
            "outcome": self.outcome,
            "network_block_required": self.network_block_required,
            "network_attempted": self.network_attempted,
            "package_id": self.package_id,
            "checksum_prefixes": list(self.checksum_prefixes),
            "warnings": list(self.warnings),
        }


def current_offline_policy() -> bool:
    """Return whether the caller requires an externally blocked network."""

    return os.environ.get("NADIKT_BENCHMARK_OFFLINE_REQUIRED", "0") == "1"


def validate_local_package(
    package_id: str,
    package_path: Path,
    root: Path,
    critical_files: tuple[Mapping[str, str], ...] = (),
    rights_statuses: Mapping[str, Mapping[str, str]] | None = None,
    package_format: str = "",
) -> OfflineCheckResult:
    """Classify local package availability without attempting network access."""

    LOGGER.debug("offline_package_check_start", extra={"package_id": package_id})
    integrity = validate_package_integrity(
        package_id=package_id,
        package_path=package_path,
        inventory_root=root,
        critical_files=critical_files,
        rights_statuses=rights_statuses,
        package_format=package_format,
    )
    result = OfflineCheckResult(
        outcome=integrity.outcome,
        network_block_required=current_offline_policy(),
        network_attempted=False,
        package_id=package_id,
        checksum_prefixes=integrity.checksum_prefixes,
        warnings=integrity.warnings,
    )
    LOGGER.info("offline_package_check", extra=result.safe_log_context())
    return result
