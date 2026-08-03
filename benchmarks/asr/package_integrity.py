"""Local model package integrity checks for offline ASR probes."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Mapping

from .logging_config import get_logger

LOGGER = get_logger(__name__)

SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
WINDOWS_DRIVE_RE = re.compile(r"^[a-zA-Z]:")
CHECKSUM_PREFIX_LENGTH = 12


@dataclass(frozen=True)
class PackageIntegrityResult:
    """Privacy-safe package integrity outcome."""

    outcome: str
    package_id: str
    checksum_prefixes: tuple[str, ...] = field(default_factory=tuple)
    warnings: tuple[str, ...] = field(default_factory=tuple)

    def safe_log_context(self) -> dict[str, object]:
        return {
            "outcome": self.outcome,
            "package_id": self.package_id,
            "checksum_prefixes": list(self.checksum_prefixes),
            "warning_count": len(self.warnings),
            "warnings": list(self.warnings),
        }


def validate_package_integrity(
    *,
    package_id: str,
    package_path: Path,
    inventory_root: Path,
    critical_files: tuple[Mapping[str, str], ...] = (),
    rights_statuses: Mapping[str, Mapping[str, str]] | None = None,
) -> PackageIntegrityResult:
    """Validate package path, critical file checksums and license gate metadata."""

    LOGGER.debug("package_integrity_start", extra={"package_id": package_id})
    if is_unsafe_local_path(str(package_path)):
        return _finish(PackageIntegrityResult("invalid_package_path", package_id))

    root = inventory_root.resolve(strict=False)
    candidate = (root / package_path).resolve(strict=False)
    if not _is_relative_to(candidate, root):
        return _finish(PackageIntegrityResult("invalid_package_path", package_id))
    if not candidate.exists():
        return _finish(PackageIntegrityResult("missing_package", package_id))
    if not critical_files:
        return _finish(PackageIntegrityResult("missing_critical_file", package_id))

    prefixes: list[str] = []
    for critical_file in critical_files:
        relative_path = str(critical_file.get("relative_path", ""))
        expected_sha256 = str(critical_file.get("sha256", "")).lower()
        if is_unsafe_local_path(relative_path) or not relative_path:
            return _finish(PackageIntegrityResult("invalid_package_path", package_id, tuple(prefixes)))
        if not is_valid_sha256(expected_sha256):
            return _finish(PackageIntegrityResult("invalid_checksum", package_id, tuple(prefixes)))

        critical_path = (candidate / relative_path).resolve(strict=False)
        if not _is_relative_to(critical_path, candidate):
            return _finish(PackageIntegrityResult("invalid_package_path", package_id, tuple(prefixes)))
        if not critical_path.is_file():
            return _finish(PackageIntegrityResult("missing_critical_file", package_id, tuple(prefixes)))

        actual_sha256 = _sha256_file(critical_path)
        prefixes.append(actual_sha256[:CHECKSUM_PREFIX_LENGTH])
        if actual_sha256 != expected_sha256:
            return _finish(PackageIntegrityResult("checksum_mismatch", package_id, tuple(prefixes)))

    warnings = _rights_warnings(rights_statuses or {})
    return _finish(PackageIntegrityResult("package_present", package_id, tuple(prefixes), warnings))


def is_valid_sha256(value: str) -> bool:
    """Return true for lowercase canonical SHA-256 hex strings."""

    return SHA256_RE.fullmatch(value) is not None


def checksum_prefix(value: str) -> str:
    """Return a short safe checksum prefix for logs and JSON summaries."""

    normalized = value.lower()
    if not is_valid_sha256(normalized):
        return "invalid"
    return normalized[:CHECKSUM_PREFIX_LENGTH]


def is_unsafe_local_path(value: str) -> bool:
    """Reject absolute, Windows absolute, UNC and traversal paths."""

    normalized = value.replace("\\", "/")
    posix_path = PurePosixPath(normalized)
    return (
        ".." in posix_path.parts
        or posix_path.is_absolute()
        or PurePosixPath(value).is_absolute()
        or PureWindowsPath(value).is_absolute()
        or WINDOWS_DRIVE_RE.match(value) is not None
        or value.startswith("\\")
        or value.startswith("~")
    )


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _is_relative_to(child: Path, parent: Path) -> bool:
    try:
        child.relative_to(parent)
    except ValueError:
        return False
    return True


def _finish(result: PackageIntegrityResult) -> PackageIntegrityResult:
    LOGGER.info("package_integrity_done", extra=result.safe_log_context())
    return result


def _rights_warnings(rights_statuses: Mapping[str, Mapping[str, str]]) -> tuple[str, ...]:
    local_evaluation = rights_statuses.get("local_evaluation", {})
    if local_evaluation.get("status") != "approved":
        return ("local_evaluation_not_approved",)
    warnings: list[str] = []
    for field in ("redistribution", "bundling", "installer_download"):
        status = rights_statuses.get(field, {}).get("status")
        if status != "approved":
            warnings.append(f"{field}_{status or 'missing'}")
    return tuple(warnings)


__all__ = [
    "PackageIntegrityResult",
    "checksum_prefix",
    "is_unsafe_local_path",
    "is_valid_sha256",
    "validate_package_integrity",
]
