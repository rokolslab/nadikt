"""Validation for ASR benchmark dataset and model package manifests."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any, Mapping

from .logging_config import get_logger
from .package_integrity import is_unsafe_local_path, is_valid_sha256

LOGGER = get_logger(__name__)

REQUIRED_CATEGORIES = {
    "ru_short",
    "ru_en_terms",
    "names_abbrev_numbers",
    "pauses_noise",
    "long_10m",
    "boundary_cases",
}
ALLOWED_BACKENDS = {"gigaam", "faster-whisper", "tone", "other-local"}
FORBIDDEN_SAMPLE_KEYS = {"audio_path", "transcript", "reference_text", "hypothesis", "text"}
FORBIDDEN_MODEL_IDENTIFIERS = {"tiny", "base", "small", "medium", "large", "large-v2", "large-v3"}
WINDOWS_DRIVE_RE = re.compile(r"^[a-zA-Z]:")
GIGAAM_CANDIDATE_MODEL_NAMES = {
    "gigaam-v3-e2e-ctc": "v3_e2e_ctc",
    "gigaam-v3-e2e-rnnt": "v3_e2e_rnnt",
    "gigaam-multilingual-220m": "multilingual_ctc",
}
GIGAAM_REQUIRED_CACHE_FILES = {
    "v3_e2e_ctc": {"v3_e2e_ctc.ckpt", "v3_e2e_ctc_tokenizer.model"},
    "v3_e2e_rnnt": {"v3_e2e_rnnt.ckpt", "v3_e2e_rnnt_tokenizer.model"},
    "multilingual_ctc": {"multilingual_ctc.ckpt"},
}


@dataclass(frozen=True, repr=False)
class SampleManifest:
    sample_id: str
    category: str
    duration_seconds: float
    language_profile: str
    audio_label: str
    reference_label: str
    expected_english_terms: tuple[str, ...]
    segmentation_policy_id: str

    def __repr__(self) -> str:
        return (
            "SampleManifest("
            f"sample_id={self.sample_id!r}, category={self.category!r}, "
            f"duration_seconds={self.duration_seconds:.3f})"
        )


@dataclass(frozen=True, repr=False)
class ModelPackageManifest:
    package_id: str
    candidate_id: str
    backend: str
    model_name: str
    model_revision: str
    package_path: Path
    manifest_relative_path: str
    manifest_sha256: str
    rights_statuses: Mapping[str, Mapping[str, str]]
    capabilities: Mapping[str, Any]
    inference_defaults: Mapping[str, Any]
    critical_files: tuple[Mapping[str, str], ...]

    def __repr__(self) -> str:
        return (
            "ModelPackageManifest("
            f"package_id={self.package_id!r}, candidate_id={self.candidate_id!r}, "
            f"backend={self.backend!r}, model_revision={self.model_revision!r})"
        )


def load_json(path: Path) -> dict[str, Any]:
    LOGGER.debug("manifest_load_start", extra={"path_label": path.name})
    with path.open("r", encoding="utf-8") as file:
        data = json.load(file)
    LOGGER.debug("manifest_load_done", extra={"path_label": path.name})
    return data


def load_model_inventory(path: Path) -> tuple[list[ModelPackageManifest], list[str]]:
    """Load local inventory plus immutable sidecar manifests."""

    inventory = load_json(path)
    entries, errors = validate_model_inventory(inventory)
    packages: list[ModelPackageManifest] = []
    for index, entry in enumerate(entries):
        manifest_path = (path.parent / entry.manifest_relative_path).resolve(strict=False)
        inventory_root = path.parent.resolve(strict=False)
        if not _is_relative_to(manifest_path, inventory_root):
            errors.append(f"package_{index}_manifest_path_escape")
            continue
        if not manifest_path.is_file():
            errors.append(f"package_{index}_manifest_missing")
            continue
        actual_digest = _sha256_file(manifest_path)
        if actual_digest != entry.manifest_sha256:
            errors.append(f"package_{index}_manifest_checksum_mismatch")
            continue
        manifest_data = load_json(manifest_path)
        package, manifest_errors = validate_model_package_manifest(
            manifest_data,
            package_path=entry.package_path,
            manifest_relative_path=entry.manifest_relative_path,
            manifest_sha256=entry.manifest_sha256,
        )
        errors.extend(f"package_{index}_{error}" for error in manifest_errors)
        if package is not None:
            packages.append(package)

    LOGGER.info(
        "model_inventory_sidecars_validated",
        extra={"package_count": len(packages), "error_count": len(errors)},
    )
    return packages, errors


def validate_dataset_manifest(data: Mapping[str, Any]) -> tuple[list[SampleManifest], list[str]]:
    errors: list[str] = []
    if data.get("schema_version") != 1:
        errors.append("invalid_schema_version")

    samples_data = data.get("samples")
    if not isinstance(samples_data, list) or not samples_data:
        return [], errors + ["samples_required"]

    samples: list[SampleManifest] = []
    seen_categories: set[str] = set()
    for index, item in enumerate(samples_data):
        if not isinstance(item, Mapping):
            errors.append(f"sample_{index}_not_object")
            continue
        forbidden_keys = FORBIDDEN_SAMPLE_KEYS.intersection(item)
        if forbidden_keys:
            errors.append(f"sample_{index}_forbidden_keys:{','.join(sorted(forbidden_keys))}")

        required = [
            "sample_id",
            "category",
            "duration_seconds",
            "language_profile",
            "audio_label",
            "reference_label",
            "expected_english_terms",
            "segmentation_policy_id",
        ]
        missing = [field for field in required if field not in item]
        if missing:
            errors.append(f"sample_{index}_missing:{','.join(missing)}")
            continue

        category = str(item["category"])
        duration_value = item["duration_seconds"]
        if isinstance(duration_value, bool) or not isinstance(duration_value, (int, float)):
            errors.append(f"sample_{index}_invalid_duration_type")
            continue
        duration = float(duration_value)
        if category not in REQUIRED_CATEGORIES:
            errors.append(f"sample_{index}_invalid_category")
        if duration <= 0:
            errors.append(f"sample_{index}_invalid_duration")
        if category == "long_10m" and duration < 600:
            errors.append(f"sample_{index}_long_10m_too_short")
        if _is_unsafe_path_label(str(item["audio_label"])):
            errors.append(f"sample_{index}_unsafe_audio_label")
        if _is_unsafe_path_label(str(item["reference_label"])):
            errors.append(f"sample_{index}_unsafe_reference_label")

        expected_terms = item["expected_english_terms"]
        if not isinstance(expected_terms, list):
            errors.append(f"sample_{index}_expected_english_terms_not_list")
            continue
        if not all(isinstance(term, str) for term in expected_terms):
            errors.append(f"sample_{index}_expected_english_term_not_string")
            continue

        terms = tuple(expected_terms)
        samples.append(
            SampleManifest(
                sample_id=str(item["sample_id"]),
                category=category,
                duration_seconds=duration,
                language_profile=str(item["language_profile"]),
                audio_label=str(item["audio_label"]),
                reference_label=str(item["reference_label"]),
                expected_english_terms=terms,
                segmentation_policy_id=str(item["segmentation_policy_id"]),
            )
        )
        seen_categories.add(category)

    if data.get("manifest_kind") != "example":
        missing_categories = REQUIRED_CATEGORIES.difference(seen_categories)
        if missing_categories:
            errors.append("missing_categories:" + ",".join(sorted(missing_categories)))

    LOGGER.info(
        "dataset_manifest_validated",
        extra={"sample_count": len(samples), "error_count": len(errors)},
    )
    return samples, errors


def validate_model_inventory(data: Mapping[str, Any]) -> tuple[list[ModelPackageManifest], list[str]]:
    errors: list[str] = []
    if data.get("schema_version") != 1:
        errors.append("invalid_schema_version")

    packages_data = data.get("packages")
    if not isinstance(packages_data, list) or not packages_data:
        return [], errors + ["packages_required"]

    packages: list[ModelPackageManifest] = []
    for index, item in enumerate(packages_data):
        if not isinstance(item, Mapping):
            errors.append(f"package_{index}_not_object")
            continue
        required = [
            "package_id",
            "package_path",
            "manifest_relative_path",
            "manifest_sha256",
        ]
        missing = [field for field in required if field not in item]
        if missing:
            errors.append(f"package_{index}_missing:{','.join(missing)}")
            continue

        package_errors: list[str] = []
        package_path_raw = str(item["package_path"])
        manifest_relative_path = str(item["manifest_relative_path"])
        manifest_sha256 = str(item["manifest_sha256"]).lower()
        package_path = Path(package_path_raw)
        if _is_forbidden_model_identifier(package_path_raw):
            package_errors.append(f"package_{index}_forbidden_model_identifier")
        if is_unsafe_local_path(package_path_raw):
            package_errors.append(f"package_{index}_unsafe_absolute_path")
        if is_unsafe_local_path(manifest_relative_path) or not manifest_relative_path:
            package_errors.append(f"package_{index}_manifest_unsafe_path")
        if not is_valid_sha256(manifest_sha256):
            package_errors.append(f"package_{index}_manifest_invalid_checksum")

        if package_errors:
            errors.extend(package_errors)
            continue

        packages.append(
            ModelPackageManifest(
                package_id=str(item["package_id"]),
                candidate_id="",
                backend="",
                model_name="",
                model_revision="",
                package_path=package_path,
                manifest_relative_path=manifest_relative_path,
                manifest_sha256=manifest_sha256,
                rights_statuses={},
                capabilities={},
                inference_defaults={},
                critical_files=(),
            )
        )

    LOGGER.info(
        "model_inventory_validated",
        extra={"package_count": len(packages), "error_count": len(errors)},
    )
    return packages, errors


def validate_model_package_manifest(
    data: Mapping[str, Any],
    *,
    package_path: Path | None = None,
    manifest_relative_path: str = "",
    manifest_sha256: str = "",
) -> tuple[ModelPackageManifest | None, list[str]]:
    """Validate immutable model package sidecar metadata."""

    errors: list[str] = []
    if data.get("schema_version") != 1:
        errors.append("invalid_schema_version")
    if data.get("manifest_type") != "model_package_manifest":
        errors.append("invalid_manifest_type")

    required = [
        "manifest_kind",
        "package_id",
        "candidate_id",
        "backend",
        "model_name",
        "model_revision",
        "package_format",
        "compatible_nadikt_versions",
        "rights_statuses",
        "capabilities",
        "inference_defaults",
        "critical_files",
        "licenses",
        "notices",
    ]
    missing = [field for field in required if field not in data]
    if missing:
        return None, errors + ["missing:" + ",".join(missing)]

    manifest_kind = str(data["manifest_kind"])
    backend = str(data["backend"])
    capabilities = data["capabilities"]
    inference_defaults = data["inference_defaults"]
    critical_files = data["critical_files"]
    rights_statuses = data["rights_statuses"]
    compatible_versions = data["compatible_nadikt_versions"]

    if manifest_kind not in {"example", "model_package"}:
        errors.append("invalid_manifest_kind")
    if backend not in ALLOWED_BACKENDS:
        errors.append("invalid_backend")
    if not isinstance(capabilities, Mapping):
        errors.append("capabilities_not_object")
    if not isinstance(inference_defaults, Mapping):
        errors.append("inference_defaults_not_object")
    if not isinstance(compatible_versions, list) or not all(isinstance(item, str) and item for item in compatible_versions):
        errors.append("compatible_nadikt_versions_invalid")
    if not isinstance(rights_statuses, Mapping):
        errors.append("rights_statuses_not_object")
        rights_statuses = {}
    else:
        errors.extend(_validate_rights_statuses(rights_statuses))

    if not isinstance(critical_files, list):
        return None, errors + ["critical_files_not_list"]
    if not critical_files:
        errors.append("critical_files_required")
    if not all(isinstance(file_item, Mapping) for file_item in critical_files):
        return None, errors + ["critical_file_not_object"]
    seen_paths: set[str] = set()
    for file_index, file_item in enumerate(critical_files):
        relative_path = str(file_item.get("relative_path", ""))
        sha256 = str(file_item.get("sha256", "")).lower()
        size_bytes = file_item.get("size_bytes")
        role = str(file_item.get("role", ""))
        if is_unsafe_local_path(relative_path) or not relative_path:
            errors.append(f"critical_file_{file_index}_unsafe_path")
        if relative_path in seen_paths:
            errors.append(f"critical_file_{file_index}_duplicate_path")
        seen_paths.add(relative_path)
        if not is_valid_sha256(sha256):
            errors.append(f"critical_file_{file_index}_invalid_checksum")
        if manifest_kind != "example" and sha256 == "0" * 64:
            errors.append(f"critical_file_{file_index}_placeholder_checksum")
        if isinstance(size_bytes, bool) or not isinstance(size_bytes, int) or size_bytes <= 0:
            errors.append(f"critical_file_{file_index}_invalid_size")
        if not role:
            errors.append(f"critical_file_{file_index}_missing_role")

    if backend == "gigaam" and isinstance(inference_defaults, Mapping):
        if _missing_required_gigaam_files(str(data["candidate_id"]), inference_defaults, critical_files):
            errors.append("gigaam_required_files_missing")

    local_evaluation = rights_statuses.get("local_evaluation") if isinstance(rights_statuses, Mapping) else None
    if isinstance(local_evaluation, Mapping) and local_evaluation.get("status") != "approved":
        errors.append("local_evaluation_not_approved")

    if errors:
        return None, errors
    return (
        ModelPackageManifest(
            package_id=str(data["package_id"]),
            candidate_id=str(data["candidate_id"]),
            backend=backend,
            model_name=str(data["model_name"]),
            model_revision=str(data["model_revision"]),
            package_path=package_path or Path("."),
            manifest_relative_path=manifest_relative_path,
            manifest_sha256=manifest_sha256,
            rights_statuses={key: dict(value) for key, value in rights_statuses.items()},
            capabilities=dict(capabilities),
            inference_defaults=dict(inference_defaults),
            critical_files=tuple(dict(file_item) for file_item in critical_files),
        ),
        [],
    )


def _validate_rights_statuses(data: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    allowed_statuses = {"approved", "prohibited", "review_required"}
    required = ["local_evaluation", "redistribution", "bundling", "installer_download"]
    for field in required:
        value = data.get(field)
        if not isinstance(value, Mapping):
            errors.append(f"rights_{field}_not_object")
            continue
        status = value.get("status")
        review_record_id = value.get("review_record_id")
        if status not in allowed_statuses:
            errors.append(f"rights_{field}_invalid_status")
        if not isinstance(review_record_id, str) or not review_record_id:
            errors.append(f"rights_{field}_missing_review_record_id")
    return errors


def _is_unsafe_path_label(value: str) -> bool:
    return _is_absolute_on_any_supported_platform(value) or value.startswith("~")


def _is_absolute_on_any_supported_platform(value: str) -> bool:
    return (
        PurePosixPath(value).is_absolute()
        or PureWindowsPath(value).is_absolute()
        or WINDOWS_DRIVE_RE.match(value) is not None
        or value.startswith("\\\\")
    )


def _is_forbidden_model_identifier(value: str) -> bool:
    normalized = value.strip().lower()
    if normalized in FORBIDDEN_MODEL_IDENTIFIERS:
        return True
    return normalized.startswith("openai/") or normalized.startswith("systran/")


def _missing_required_gigaam_files(candidate_id: str, inference_defaults: Mapping[str, Any], critical_files: list[object]) -> bool:
    model_name = inference_defaults.get("gigaam_model_name")
    if not isinstance(model_name, str) or not model_name:
        model_name = GIGAAM_CANDIDATE_MODEL_NAMES.get(candidate_id, "")
    required = GIGAAM_REQUIRED_CACHE_FILES.get(model_name)
    if not required:
        return True
    declared = {
        str(file_item.get("relative_path", "")).replace("\\", "/")
        for file_item in critical_files
        if isinstance(file_item, Mapping)
    }
    return not required.issubset(declared)


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
