"""Dry-run CLI for ASR benchmark manifests without loading real models."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .manifests import load_json, validate_dataset_manifest, validate_model_inventory
from .offline_check import validate_local_package
from .privacy_audit import audit_text_artifact
from .resource_measurement import measure_phase


def run_dry_run(dataset_path: Path, models_path: Path) -> dict[str, Any]:
    """Validate manifests and produce a privacy-safe dry-run summary."""

    with measure_phase("dry_run_manifest_validation") as validation_snapshots:
        dataset_data = load_json(dataset_path)
        model_data = load_json(models_path)
        samples, dataset_errors = validate_dataset_manifest(dataset_data)
        packages, model_errors = validate_model_inventory(model_data)

    outcomes: Counter[str] = Counter()
    warnings: Counter[str] = Counter()
    with measure_phase("dry_run_package_checks") as package_snapshots:
        for package in packages:
            result = validate_local_package(
                package.package_id,
                package.package_path,
                models_path.parent,
                package.critical_files,
                package.license_marker,
            )
            outcomes[result.outcome] += 1
            warnings.update(result.warnings)

    created_at = datetime.now(UTC)
    summary = {
        "run_id": "dry-run-" + created_at.strftime("%Y%m%dT%H%M%SZ"),
        "created_at": created_at.isoformat(),
        "dataset": {
            "dataset_id": dataset_data.get("dataset_id"),
            "dataset_revision": dataset_data.get("dataset_revision"),
            "sample_count": len(samples),
            "categories": sorted({sample.category for sample in samples}),
            "validation_errors": dataset_errors,
        },
        "models": {
            "inventory_id": model_data.get("inventory_id"),
            "package_count": len(packages),
            "validation_errors": model_errors,
            "package_outcomes": dict(sorted(outcomes.items())),
            "package_warnings": dict(sorted(warnings.items())),
        },
        "offline": {
            "network_attempted": False,
            "network_block_verification": "external_environment_required",
        },
        "resources": [
            *(snapshot.safe_log_context() for snapshot in validation_snapshots),
            *(snapshot.safe_log_context() for snapshot in package_snapshots),
        ],
    }
    privacy = audit_text_artifact(json.dumps(summary, ensure_ascii=False), canary="NADIKT_CONTROLLED_CANARY")
    summary["privacy"] = privacy.safe_log_context()
    summary["result"] = _classify_summary(dataset_errors, model_errors, outcomes)
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate ASR benchmark manifests without loading models.")
    parser.add_argument("--dataset", required=True, type=Path, help="Path to dataset manifest JSON")
    parser.add_argument("--models", required=True, type=Path, help="Path to model package inventory JSON")
    args = parser.parse_args(argv)

    summary = run_dry_run(args.dataset, args.models)
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if summary["result"] != "invalid_manifests" else 2


def _classify_summary(
    dataset_errors: list[str],
    model_errors: list[str],
    outcomes: Counter[str],
) -> str:
    if dataset_errors or model_errors:
        return "invalid_manifests"
    if outcomes and set(outcomes) == {"missing_package"}:
        return "passed_with_expected_missing_packages"
    if not outcomes:
        return "passed_without_packages"
    return "passed"


if __name__ == "__main__":
    raise SystemExit(main())
