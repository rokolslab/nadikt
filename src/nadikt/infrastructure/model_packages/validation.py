"""Runtime validation for local ASR model package bindings.

This module intentionally does not import ``benchmarks.asr``. Runtime dictation
must validate a trusted local inventory/sidecar binding before any ASR SDK import
or load path is reached.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any, Mapping

from nadikt.domain.ports.asr import AsrBackend, AsrLoadOptions
from nadikt.domain.ports.asr import AsrCapabilities

LOGGER = logging.getLogger(__name__)
_LOG_LEVEL = os.environ.get("NADIKT_LOG_LEVEL", os.environ.get("LOG_LEVEL", "INFO")).upper()
logging.basicConfig(level=getattr(logging, _LOG_LEVEL, logging.INFO))

SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
WINDOWS_DRIVE_RE = re.compile(r"^[a-zA-Z]:")
CHECKSUM_PREFIX_LENGTH = 12
SUPPORTED_MANIFEST_VERSION = 1
SUPPORTED_NADIKT_VERSION_PREFIXES = ("0.x", "0.x-prototype")
ALLOWED_BACKENDS = {backend.value for backend in AsrBackend}
PLACEHOLDER_SHA256_VALUES = {"0" * 64, "f" * 64}
GIGAAM_REQUIRED_ROLES = {"gigaam_checkpoint", "gigaam_tokenizer"}
FORMAT_ROLES = {
    "ctranslate2-directory": {"ctranslate2_weights", "ctranslate2_config", "tokenizer", "vocabulary"},
    "gigaam-cache-style": GIGAAM_REQUIRED_ROLES,
}


class ModelPackageValidationFailureCode(str, Enum):
    """Safe runtime package validation failures."""

    INVALID_INVENTORY = "invalid_inventory"
    INVALID_MANIFEST_KIND = "invalid_manifest_kind"
    EXAMPLE_MANIFEST_REJECTED = "example_manifest_rejected"
    BINDING_NOT_FOUND = "binding_not_found"
    INVALID_PACKAGE_PATH = "invalid_package_path"
    MISSING_PACKAGE = "missing_package"
    INVALID_PACKAGE_ROOT = "invalid_package_root"
    MANIFEST_MISSING = "manifest_missing"
    MANIFEST_CHECKSUM_MISMATCH = "manifest_checksum_mismatch"
    PACKAGE_ID_MISMATCH = "package_id_mismatch"
    CANDIDATE_ID_MISMATCH = "candidate_id_mismatch"
    BACKEND_MISMATCH = "backend_mismatch"
    INCOMPATIBLE_NADIKT_VERSION = "incompatible_nadikt_version"
    INCOMPATIBLE_BACKEND = "incompatible_backend"
    LOCAL_EVALUATION_NOT_APPROVED = "local_evaluation_not_approved"
    MISSING_CRITICAL_FILE = "missing_critical_file"
    INVALID_FILE_ROLE = "invalid_file_role"
    INVALID_CHECKSUM = "invalid_checksum"
    INVALID_FILE_SIZE = "invalid_file_size"
    SIZE_MISMATCH = "size_mismatch"
    CHECKSUM_MISMATCH = "checksum_mismatch"
    REQUIRED_TOOL_MISSING = "required_tool_missing"


class ModelPackageValidationError(Exception):
    """Exception carrying only safe validation failure metadata."""

    def __init__(self, failure: "ModelPackageValidationFailure") -> None:
        super().__init__(failure.code.value)
        self.failure = failure


@dataclass(frozen=True, repr=False)
class ModelPackageValidationFailure:
    """Privacy-safe validation failure envelope."""

    code: ModelPackageValidationFailureCode
    phase: str
    package_id: str | None = None
    candidate_id: str | None = None
    backend: str | None = None
    checksum_prefixes: tuple[str, ...] = field(default_factory=tuple)

    def __repr__(self) -> str:
        return (
            "ModelPackageValidationFailure("
            f"code={self.code.value!r}, phase={self.phase!r}, "
            f"package_id={self.package_id!r}, candidate_id={self.candidate_id!r}, "
            f"backend={self.backend!r}, checksum_prefixes={list(self.checksum_prefixes)!r})"
        )


@dataclass(frozen=True, repr=False)
class ModelPackageBinding:
    """Validated binding passed to ASR load code."""

    package_id: str
    candidate_id: str
    backend: AsrBackend
    load_options: AsrLoadOptions
    model_name: str
    model_revision: str
    backend_version: str
    license_marker: str
    capabilities: AsrCapabilities
    package_format: str
    checksum_prefixes: tuple[str, ...]

    def __repr__(self) -> str:
        return (
            "ModelPackageBinding("
            f"package_id={self.package_id!r}, candidate_id={self.candidate_id!r}, "
            f"backend={self.backend.value!r}, model_revision={self.model_revision!r}, "
            f"package_format={self.package_format!r}, "
            f"checksum_prefixes={list(self.checksum_prefixes)!r}, local_package_path=<redacted>)"
        )


def validate_model_package_binding(
    *,
    inventory_path: Path,
    package_id: str,
    candidate_id: str,
    backend: AsrBackend,
) -> ModelPackageBinding:
    """Validate a trusted inventory/sidecar binding before ASR SDK import."""

    LOGGER.debug(
        "model_package.validation.start",
        extra={"package_id": package_id, "candidate_id": candidate_id, "backend": backend.value},
    )
    inventory_root = inventory_path.parent.resolve(strict=False)
    inventory = _load_json(inventory_path, "inventory")
    if inventory.get("schema_version") != SUPPORTED_MANIFEST_VERSION or inventory.get("manifest_kind") == "example":
        _raise(
            ModelPackageValidationFailure(
                ModelPackageValidationFailureCode.EXAMPLE_MANIFEST_REJECTED,
                "inventory",
                package_id,
                candidate_id,
                backend.value,
            )
        )
    entries = inventory.get("packages")
    if not isinstance(entries, list):
        _raise(ModelPackageValidationFailure(ModelPackageValidationFailureCode.INVALID_INVENTORY, "inventory"))

    selected = _select_entry(entries, package_id, candidate_id, backend.value)
    package_path = _string_field(selected, "package_path")
    manifest_relative_path = _string_field(selected, "manifest_relative_path")
    manifest_sha256 = _string_field(selected, "manifest_sha256").lower()
    if _is_unsafe_local_path(package_path) or _is_unsafe_local_path(manifest_relative_path):
        _raise(_failure(ModelPackageValidationFailureCode.INVALID_PACKAGE_PATH, "inventory_entry", package_id, candidate_id, backend.value))
    if not _is_valid_sha256(manifest_sha256) or manifest_sha256 in PLACEHOLDER_SHA256_VALUES:
        _raise(_failure(ModelPackageValidationFailureCode.INVALID_CHECKSUM, "inventory_entry", package_id, candidate_id, backend.value))

    manifest_path = (inventory_root / manifest_relative_path).resolve(strict=False)
    if not _is_relative_to(manifest_path, inventory_root):
        _raise(_failure(ModelPackageValidationFailureCode.INVALID_PACKAGE_PATH, "manifest_path", package_id, candidate_id, backend.value))
    if not manifest_path.is_file():
        _raise(_failure(ModelPackageValidationFailureCode.MANIFEST_MISSING, "manifest_path", package_id, candidate_id, backend.value))
    if _sha256_file(manifest_path) != manifest_sha256:
        _raise(_failure(ModelPackageValidationFailureCode.MANIFEST_CHECKSUM_MISMATCH, "manifest_path", package_id, candidate_id, backend.value))

    manifest = _load_json(manifest_path, "sidecar")
    _validate_manifest_identity(manifest, package_id, candidate_id, backend.value)
    package_root = _validate_package_root(inventory_root, package_path, package_id, candidate_id, backend.value)
    package_format = _string_field(manifest, "package_format")
    _validate_compatibility(manifest, package_id, candidate_id, backend.value)
    checksum_prefixes = _validate_critical_files(package_root, manifest, package_id, candidate_id, backend.value, package_format)
    _validate_required_tools(manifest, package_root, package_id, candidate_id, backend.value)
    binding = ModelPackageBinding(
        package_id=package_id,
        candidate_id=candidate_id,
        backend=backend,
        load_options=AsrLoadOptions(package_root, dict(manifest.get("inference_defaults", {}))),
        model_name=_string_field(manifest, "model_name"),
        model_revision=_string_field(manifest, "model_revision"),
        backend_version=_backend_version_marker(manifest),
        license_marker=_license_marker(manifest),
        capabilities=_capabilities(manifest),
        package_format=package_format,
        checksum_prefixes=checksum_prefixes,
    )
    LOGGER.debug(
        "model_package.validation.complete",
        extra={
            "package_id": binding.package_id,
            "candidate_id": binding.candidate_id,
            "backend": binding.backend.value,
            "manifest_version": SUPPORTED_MANIFEST_VERSION,
            "checksum_prefixes": list(binding.checksum_prefixes),
            "outcome": "validated",
        },
    )
    return binding


def _select_entry(entries: list[object], package_id: str, candidate_id: str, backend: str) -> Mapping[str, Any]:
    for entry in entries:
        if not isinstance(entry, Mapping):
            continue
        if entry.get("package_id") != package_id:
            continue
        if entry.get("candidate_id", candidate_id) != candidate_id:
            _raise(_failure(ModelPackageValidationFailureCode.CANDIDATE_ID_MISMATCH, "inventory_entry", package_id, candidate_id, backend))
        if entry.get("backend", backend) != backend:
            _raise(_failure(ModelPackageValidationFailureCode.BACKEND_MISMATCH, "inventory_entry", package_id, candidate_id, backend))
        return entry
    _raise(_failure(ModelPackageValidationFailureCode.BINDING_NOT_FOUND, "inventory", package_id, candidate_id, backend))


def _validate_manifest_identity(manifest: Mapping[str, Any], package_id: str, candidate_id: str, backend: str) -> None:
    if manifest.get("schema_version") != SUPPORTED_MANIFEST_VERSION:
        _raise(_failure(ModelPackageValidationFailureCode.INVALID_MANIFEST_KIND, "sidecar", package_id, candidate_id, backend))
    if manifest.get("manifest_kind") == "example":
        _raise(_failure(ModelPackageValidationFailureCode.EXAMPLE_MANIFEST_REJECTED, "sidecar", package_id, candidate_id, backend))
    if manifest.get("manifest_type") != "model_package_manifest":
        _raise(_failure(ModelPackageValidationFailureCode.INVALID_MANIFEST_KIND, "sidecar", package_id, candidate_id, backend))
    if manifest.get("package_id") != package_id:
        _raise(_failure(ModelPackageValidationFailureCode.PACKAGE_ID_MISMATCH, "sidecar", package_id, candidate_id, backend))
    if manifest.get("candidate_id") != candidate_id:
        _raise(_failure(ModelPackageValidationFailureCode.CANDIDATE_ID_MISMATCH, "sidecar", package_id, candidate_id, backend))
    if manifest.get("backend") != backend or backend not in ALLOWED_BACKENDS:
        _raise(_failure(ModelPackageValidationFailureCode.BACKEND_MISMATCH, "sidecar", package_id, candidate_id, backend))


def _validate_package_root(
    inventory_root: Path,
    package_path: str,
    package_id: str,
    candidate_id: str,
    backend: str,
) -> Path:
    root = (inventory_root / package_path).resolve(strict=False)
    if not _is_relative_to(root, inventory_root):
        _raise(_failure(ModelPackageValidationFailureCode.INVALID_PACKAGE_PATH, "package_path", package_id, candidate_id, backend))
    if not root.exists():
        _raise(_failure(ModelPackageValidationFailureCode.MISSING_PACKAGE, "package_path", package_id, candidate_id, backend))
    if not root.is_dir():
        _raise(_failure(ModelPackageValidationFailureCode.INVALID_PACKAGE_ROOT, "package_path", package_id, candidate_id, backend))
    return root


def _validate_compatibility(manifest: Mapping[str, Any], package_id: str, candidate_id: str, backend: str) -> None:
    nadikt_versions = manifest.get("compatible_nadikt_versions", ())
    if not isinstance(nadikt_versions, list) or not any(str(item).startswith(SUPPORTED_NADIKT_VERSION_PREFIXES) for item in nadikt_versions):
        _raise(_failure(ModelPackageValidationFailureCode.INCOMPATIBLE_NADIKT_VERSION, "compatibility", package_id, candidate_id, backend))
    backend_versions = manifest.get("compatible_backend_versions", ())
    if not isinstance(backend_versions, list) or not backend_versions:
        _raise(_failure(ModelPackageValidationFailureCode.INCOMPATIBLE_BACKEND, "compatibility", package_id, candidate_id, backend))
    rights = manifest.get("rights_statuses", {})
    if not isinstance(rights, Mapping) or rights.get("local_evaluation", {}).get("status") != "approved":
        _raise(_failure(ModelPackageValidationFailureCode.LOCAL_EVALUATION_NOT_APPROVED, "rights", package_id, candidate_id, backend))


def _validate_critical_files(
    package_root: Path,
    manifest: Mapping[str, Any],
    package_id: str,
    candidate_id: str,
    backend: str,
    package_format: str,
) -> tuple[str, ...]:
    critical_files = manifest.get("critical_files", ())
    if not isinstance(critical_files, list) or not critical_files:
        _raise(_failure(ModelPackageValidationFailureCode.MISSING_CRITICAL_FILE, "critical_files", package_id, candidate_id, backend))
    allowed_roles = FORMAT_ROLES.get(package_format)
    if allowed_roles is None:
        _raise(_failure(ModelPackageValidationFailureCode.INVALID_FILE_ROLE, "critical_files", package_id, candidate_id, backend))

    seen_roles: set[str] = set()
    prefixes: list[str] = []
    for critical_file in critical_files:
        if not isinstance(critical_file, Mapping):
            _raise(_failure(ModelPackageValidationFailureCode.MISSING_CRITICAL_FILE, "critical_files", package_id, candidate_id, backend, tuple(prefixes)))
        role = _string_field(critical_file, "role")
        seen_roles.add(role)
        if role not in allowed_roles:
            _raise(_failure(ModelPackageValidationFailureCode.INVALID_FILE_ROLE, "critical_files", package_id, candidate_id, backend, tuple(prefixes)))
        relative_path = _string_field(critical_file, "relative_path")
        expected_sha256 = _string_field(critical_file, "sha256").lower()
        expected_size = critical_file.get("size_bytes")
        if _is_unsafe_local_path(relative_path):
            _raise(_failure(ModelPackageValidationFailureCode.INVALID_PACKAGE_PATH, "critical_files", package_id, candidate_id, backend, tuple(prefixes)))
        if not _is_valid_sha256(expected_sha256) or expected_sha256 in PLACEHOLDER_SHA256_VALUES:
            _raise(_failure(ModelPackageValidationFailureCode.INVALID_CHECKSUM, "critical_files", package_id, candidate_id, backend, tuple(prefixes)))
        if isinstance(expected_size, bool) or not isinstance(expected_size, int) or expected_size <= 0:
            _raise(_failure(ModelPackageValidationFailureCode.INVALID_FILE_SIZE, "critical_files", package_id, candidate_id, backend, tuple(prefixes)))
        path = (package_root / relative_path).resolve(strict=False)
        if not _is_relative_to(path, package_root):
            _raise(_failure(ModelPackageValidationFailureCode.INVALID_PACKAGE_PATH, "critical_files", package_id, candidate_id, backend, tuple(prefixes)))
        if not path.is_file():
            _raise(_failure(ModelPackageValidationFailureCode.MISSING_CRITICAL_FILE, "critical_files", package_id, candidate_id, backend, tuple(prefixes)))
        if path.stat().st_size != expected_size:
            _raise(_failure(ModelPackageValidationFailureCode.SIZE_MISMATCH, "critical_files", package_id, candidate_id, backend, tuple(prefixes)))
        actual_sha256 = _sha256_file(path)
        prefixes.append(actual_sha256[:CHECKSUM_PREFIX_LENGTH])
        if actual_sha256 != expected_sha256:
            _raise(_failure(ModelPackageValidationFailureCode.CHECKSUM_MISMATCH, "critical_files", package_id, candidate_id, backend, tuple(prefixes)))

    if backend == AsrBackend.GIGAAM.value and not GIGAAM_REQUIRED_ROLES.issubset(seen_roles):
        _raise(_failure(ModelPackageValidationFailureCode.MISSING_CRITICAL_FILE, "gigaam_required_files", package_id, candidate_id, backend, tuple(prefixes)))
    return tuple(prefixes)


def _validate_required_tools(
    manifest: Mapping[str, Any],
    package_root: Path,
    package_id: str,
    candidate_id: str,
    backend: str,
) -> None:
    tools = manifest.get("required_tools", ())
    if tools in (None, ()): 
        return
    if not isinstance(tools, list):
        _raise(_failure(ModelPackageValidationFailureCode.REQUIRED_TOOL_MISSING, "required_tools", package_id, candidate_id, backend))
    for tool in tools:
        if not isinstance(tool, Mapping):
            _raise(_failure(ModelPackageValidationFailureCode.REQUIRED_TOOL_MISSING, "required_tools", package_id, candidate_id, backend))
        relative_path = _string_field(tool, "relative_path")
        if _is_unsafe_local_path(relative_path):
            _raise(_failure(ModelPackageValidationFailureCode.INVALID_PACKAGE_PATH, "required_tools", package_id, candidate_id, backend))
        path = (package_root / relative_path).resolve(strict=False)
        if not _is_relative_to(path, package_root) or not path.is_file():
            _raise(_failure(ModelPackageValidationFailureCode.REQUIRED_TOOL_MISSING, "required_tools", package_id, candidate_id, backend))


def _capabilities(manifest: Mapping[str, Any]) -> AsrCapabilities:
    capabilities = manifest.get("capabilities", {})
    if not isinstance(capabilities, Mapping):
        capabilities = {}
    languages = capabilities.get("languages", ())
    if not isinstance(languages, list) or not languages:
        languages = ["ru"]
    max_segment_seconds = capabilities.get("max_segment_seconds", 25.0)
    if not isinstance(max_segment_seconds, int | float) or isinstance(max_segment_seconds, bool):
        max_segment_seconds = 25.0
    return AsrCapabilities(
        languages=tuple(str(language) for language in languages),
        max_segment_seconds=float(max_segment_seconds),
        punctuation=bool(capabilities.get("punctuation", False)),
        streaming=bool(capabilities.get("streaming", False)),
        word_timestamps=bool(capabilities.get("word_timestamps", False)),
    )


def _backend_version_marker(manifest: Mapping[str, Any]) -> str:
    versions = manifest.get("compatible_backend_versions", ())
    if isinstance(versions, list) and versions:
        return str(versions[0])
    return "unverified"


def _license_marker(manifest: Mapping[str, Any]) -> str:
    licenses = manifest.get("licenses", ())
    if isinstance(licenses, list) and licenses:
        return "reviewed-license-list"
    return "missing-license-marker"


def _load_json(path: Path, phase: str) -> Mapping[str, Any]:
    try:
        with path.open("r", encoding="utf-8") as file:
            data = json.load(file)
    except OSError as exc:
        raise ModelPackageValidationError(ModelPackageValidationFailure(ModelPackageValidationFailureCode.INVALID_INVENTORY, phase)) from exc
    if not isinstance(data, Mapping):
        _raise(ModelPackageValidationFailure(ModelPackageValidationFailureCode.INVALID_INVENTORY, phase))
    return data


def _string_field(data: Mapping[str, Any], field_name: str) -> str:
    value = data.get(field_name)
    if not isinstance(value, str) or not value:
        return ""
    return value


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _is_valid_sha256(value: str) -> bool:
    return SHA256_RE.fullmatch(value) is not None


def _is_unsafe_local_path(value: str) -> bool:
    normalized = value.replace("\\", "/")
    lowered = normalized.lower()
    posix_path = PurePosixPath(normalized)
    return (
        not value
        or ".." in posix_path.parts
        or "://" in lowered
        or lowered.startswith(("hf:", "hub:", "huggingface:"))
        or posix_path.is_absolute()
        or PurePosixPath(value).is_absolute()
        or PureWindowsPath(value).is_absolute()
        or WINDOWS_DRIVE_RE.match(value) is not None
        or value.startswith("\\")
        or value.startswith("~")
    )


def _is_relative_to(child: Path, parent: Path) -> bool:
    try:
        child.relative_to(parent)
    except ValueError:
        return False
    return True


def _failure(
    code: ModelPackageValidationFailureCode,
    phase: str,
    package_id: str,
    candidate_id: str,
    backend: str,
    checksum_prefixes: tuple[str, ...] = (),
) -> ModelPackageValidationFailure:
    return ModelPackageValidationFailure(code, phase, package_id, candidate_id, backend, checksum_prefixes)


def _raise(failure: ModelPackageValidationFailure) -> None:
    LOGGER.debug(
        "model_package.validation.failed",
        extra={
            "failure_code": failure.code.value,
            "phase": failure.phase,
            "package_id": failure.package_id,
            "candidate_id": failure.candidate_id,
            "backend": failure.backend,
            "checksum_prefixes": list(failure.checksum_prefixes),
        },
    )
    raise ModelPackageValidationError(failure)


__all__ = [
    "ModelPackageBinding",
    "ModelPackageValidationError",
    "ModelPackageValidationFailure",
    "ModelPackageValidationFailureCode",
    "validate_model_package_binding",
]
