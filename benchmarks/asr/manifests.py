"""Validation for ASR benchmark dataset and model package manifests."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path, PurePath
from typing import Any, Mapping

from .logging_config import get_logger

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
    license_marker: str
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
        duration = float(item["duration_seconds"])
        if category not in REQUIRED_CATEGORIES:
            errors.append(f"sample_{index}_invalid_category")
        if duration <= 0:
            errors.append(f"sample_{index}_invalid_duration")
        if category == "long_10m" and duration < 600:
            errors.append(f"sample_{index}_long_10m_too_short")
        if _looks_like_absolute_path(str(item["audio_label"])):
            errors.append(f"sample_{index}_unsafe_audio_label")
        if _looks_like_absolute_path(str(item["reference_label"])):
            errors.append(f"sample_{index}_unsafe_reference_label")

        terms = tuple(str(term) for term in item.get("expected_english_terms", ()))
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
            "candidate_id",
            "backend",
            "model_name",
            "model_revision",
            "package_path",
            "license_marker",
            "capabilities",
            "inference_defaults",
            "critical_files",
        ]
        missing = [field for field in required if field not in item]
        if missing:
            errors.append(f"package_{index}_missing:{','.join(missing)}")
            continue

        backend = str(item["backend"])
        package_path = Path(str(item["package_path"]))
        if backend not in ALLOWED_BACKENDS:
            errors.append(f"package_{index}_invalid_backend")
        if _is_forbidden_model_identifier(str(item["package_path"])):
            errors.append(f"package_{index}_forbidden_model_identifier")
        if package_path.is_absolute():
            errors.append(f"package_{index}_unsafe_absolute_path")
        if not isinstance(item["critical_files"], list):
            errors.append(f"package_{index}_critical_files_not_list")

        packages.append(
            ModelPackageManifest(
                package_id=str(item["package_id"]),
                candidate_id=str(item["candidate_id"]),
                backend=backend,
                model_name=str(item["model_name"]),
                model_revision=str(item["model_revision"]),
                package_path=package_path,
                license_marker=str(item["license_marker"]),
                capabilities=dict(item["capabilities"]),
                inference_defaults=dict(item["inference_defaults"]),
                critical_files=tuple(dict(file_item) for file_item in item["critical_files"]),
            )
        )

    LOGGER.info(
        "model_inventory_validated",
        extra={"package_count": len(packages), "error_count": len(errors)},
    )
    return packages, errors


def _looks_like_absolute_path(value: str) -> bool:
    return PurePath(value).is_absolute() or value.startswith("~")


def _is_forbidden_model_identifier(value: str) -> bool:
    normalized = value.strip().lower()
    if normalized in FORBIDDEN_MODEL_IDENTIFIERS:
        return True
    return normalized.startswith("openai/") or normalized.startswith("systran/")
