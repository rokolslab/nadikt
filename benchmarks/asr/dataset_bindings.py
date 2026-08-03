"""Private dataset bindings validation for ASR benchmark runs."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from .dataset_storage import ControlledSamplePaths, resolve_controlled_file, validate_file_digest, validate_reference_file, validate_wav_file
from .logging_config import get_logger
from .manifests import SampleManifest, load_json, validate_dataset_manifest
from .package_integrity import is_valid_sha256

LOGGER = get_logger(__name__)

ALLOWED_RIGHTS_STATUSES = {"approved", "review_required", "prohibited"}
ALLOWED_CONSENT_STATUSES = {"synthetic", "anonymized", "approved_recording", "review_required"}


@dataclass(frozen=True)
class DatasetBindingResult:
    outcome: str
    binding_count: int
    errors: tuple[str, ...]
    resolved_samples: tuple[ControlledSamplePaths, ...] = ()

    def safe_log_context(self) -> dict[str, object]:
        return {"outcome": self.outcome, "binding_count": self.binding_count, "error_count": len(self.errors), "errors": list(self.errors)}


def validate_dataset_bindings(public_manifest_path: Path, bindings_path: Path, controlled_root: Path) -> DatasetBindingResult:
    """Validate private sample bindings without returning transcript/audio payload."""

    LOGGER.info("dataset_bindings_validation_start", extra={"manifest_label": public_manifest_path.name, "bindings_label": bindings_path.name})
    public_data = load_json(public_manifest_path)
    samples, manifest_errors = validate_dataset_manifest(public_data)
    bindings_data = load_json(bindings_path)
    errors = list(manifest_errors)
    errors.extend(_validate_bindings_shape(bindings_data))
    if errors:
        return _finish(DatasetBindingResult("invalid_bindings", 0, tuple(errors)))

    expected_digest = str(bindings_data["public_manifest_sha256"]).lower()
    if _sha256_file(public_manifest_path) != expected_digest:
        errors.append("public_manifest_digest_mismatch")

    sample_ids = {sample.sample_id for sample in samples}
    binding_items = bindings_data["samples"]
    binding_ids = [str(item["sample_id"]) for item in binding_items]
    duplicate_ids = sorted({sample_id for sample_id in binding_ids if binding_ids.count(sample_id) > 1})
    if duplicate_ids:
        errors.append("duplicate_sample_ids:" + ",".join(duplicate_ids))
    missing_ids = sample_ids.difference(binding_ids)
    extra_ids = set(binding_ids).difference(sample_ids)
    if missing_ids:
        errors.append("missing_sample_ids:" + ",".join(sorted(missing_ids)))
    if extra_ids:
        errors.append("extra_sample_ids:" + ",".join(sorted(extra_ids)))

    samples_by_id = {sample.sample_id: sample for sample in samples}
    resolved: list[ControlledSamplePaths] = []
    for item in binding_items:
        sample_id = str(item["sample_id"])
        public_sample = samples_by_id.get(sample_id)
        sample_errors, paths = _validate_one_binding(item, controlled_root, public_sample)
        errors.extend(f"{sample_id}:{error}" for error in sample_errors)
        if paths is not None:
            resolved.append(paths)

    if errors:
        return _finish(DatasetBindingResult("invalid_bindings", len(binding_items), tuple(errors)))
    return _finish(DatasetBindingResult("bindings_valid", len(binding_items), (), tuple(resolved)))


def _validate_bindings_shape(data: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    if data.get("schema_version") != 1:
        errors.append("invalid_schema_version")
    if not isinstance(data.get("bindings_id"), str) or not data.get("bindings_id"):
        errors.append("bindings_id_required")
    if not is_valid_sha256(str(data.get("public_manifest_sha256", ""))):
        errors.append("invalid_public_manifest_sha256")
    samples = data.get("samples")
    if not isinstance(samples, list) or not samples:
        return errors + ["samples_required"]
    for index, item in enumerate(samples):
        if not isinstance(item, Mapping):
            errors.append(f"sample_{index}_not_object")
            continue
        required = ["sample_id", "audio_relative_path", "audio_sha256", "reference_relative_path", "reference_sha256", "rights_status", "consent_status"]
        missing = [field for field in required if field not in item]
        if missing:
            errors.append(f"sample_{index}_missing:{','.join(missing)}")
        if item.get("rights_status") not in ALLOWED_RIGHTS_STATUSES:
            errors.append(f"sample_{index}_invalid_rights_status")
        if item.get("consent_status") not in ALLOWED_CONSENT_STATUSES:
            errors.append(f"sample_{index}_invalid_consent_status")
    return errors


def _validate_one_binding(item: Mapping[str, Any], root: Path, public_sample: SampleManifest | None) -> tuple[list[str], ControlledSamplePaths | None]:
    errors: list[str] = []
    if public_sample is None:
        return ["unknown_public_sample"], None
    if item["rights_status"] != "approved":
        errors.append("rights_not_approved")
    if item["consent_status"] == "review_required":
        errors.append("consent_review_required")

    audio_path, audio_error = resolve_controlled_file(root, str(item["audio_relative_path"]))
    reference_path, reference_error = resolve_controlled_file(root, str(item["reference_relative_path"]))
    if audio_error:
        errors.append("audio_" + audio_error)
    if reference_error:
        errors.append("reference_" + reference_error)
    if audio_path is not None:
        digest_error = validate_file_digest(audio_path, str(item["audio_sha256"]).lower())
        wav_error = validate_wav_file(audio_path, max_duration_seconds=max(public_sample.duration_seconds + 1.0, 1.0))
        if digest_error:
            errors.append("audio_" + digest_error)
        if wav_error:
            errors.append("audio_" + wav_error)
    if reference_path is not None:
        digest_error = validate_file_digest(reference_path, str(item["reference_sha256"]).lower())
        reference_error = validate_reference_file(reference_path)
        if digest_error:
            errors.append("reference_" + digest_error)
        if reference_error:
            errors.append(reference_error)
    if errors:
        return errors, None
    return [], ControlledSamplePaths(str(item["sample_id"]), audio_path, reference_path)  # type: ignore[arg-type]


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _finish(result: DatasetBindingResult) -> DatasetBindingResult:
    LOGGER.info("dataset_bindings_validation_done", extra=result.safe_log_context())
    return result
