"""Controlled Windows dictation vertical-slice harness."""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from pathlib import Path

from nadikt.application.services.dictation_pipeline import DictationRunOptions
from nadikt.bootstrap import build_windows_dictation_slice
from nadikt.domain.ports.asr import AsrBackend, AsrSegmentInput
from nadikt.domain.ports.audio import AudioCaptureOptions
from nadikt.infrastructure.model_packages import validate_model_package_binding

LOGGER = logging.getLogger(__name__)
_LOG_LEVEL = os.environ.get("NADIKT_LOG_LEVEL", os.environ.get("LOG_LEVEL", "INFO")).upper()
logging.basicConfig(level=getattr(logging, _LOG_LEVEL, logging.INFO))


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    LOGGER.debug(
        "windows_dictation_slice.args",
        extra={
            "candidate_id": args.candidate_id,
            "backend": args.backend,
            "duration_seconds": args.duration_seconds,
            "sample_rate_hz": args.sample_rate_hz,
            "channel_count": args.channel_count,
            "inventory_path": "<redacted>",
            "warm_up_audio_file": "<redacted>",
        },
    )
    backend = AsrBackend(args.backend)
    try:
        binding = validate_model_package_binding(
            inventory_path=Path(args.inventory),
            package_id=args.package_id,
            candidate_id=args.candidate_id,
            backend=backend,
        )
        warm_up_segment = AsrSegmentInput(
            sample_id="warm-up-non-scored",
            segment_id=-0,
            audio_path=Path(args.warm_up_audio_file),
            start_seconds=0.0,
            end_seconds=args.warm_up_duration_seconds,
            language_profile=args.language_profile,
            segmentation_policy_id="warm-up-non-scored.v1",
        )
        components = build_windows_dictation_slice(binding, warm_up_segment)
        target = components.insertion_service.capture_target()
        if not target.success:
            _print_status("target_capture_failed", target.outcome_code, target.pending_clipboard_restore)
            components.asr_engine.close()
            return 2
        outcome = components.pipeline.run_once(
            DictationRunOptions(
                AudioCaptureOptions(
                    max_duration_seconds=args.duration_seconds,
                    sample_rate_hz=args.sample_rate_hz,
                    channel_count=args.channel_count,
                    pre_buffer_seconds=args.pre_buffer_seconds,
                    selected_device_id=args.device_id,
                    language_profile=args.language_profile,
                    segmentation_policy_id="bounded-one-shot.v1",
                )
            )
        )
        _print_status(outcome.status.value, outcome.outcome_code, components.insertion_service.has_pending_clipboard_restore)
        if components.insertion_service.has_pending_clipboard_restore:
            _settle_clipboard(components)
        components.asr_engine.close()
        return 0 if outcome.status.value == "completed" else 3
    except Exception as exc:
        LOGGER.debug("windows_dictation_slice.failed", extra={"failure_type": type(exc).__name__})
        _print_status("failed", type(exc).__name__, False)
        return 1


def _settle_clipboard(components: object) -> None:
    print(json.dumps({"status": "operator_decision_required", "pending_clipboard_restore": True}, sort_keys=True))
    decision = input("clipboard decision [restore_original/discard_original]: ").strip()
    if decision == "restore_original":
        result = components.insertion_service.restore_original()
    elif decision == "discard_original":
        result = components.insertion_service.discard_original()
    else:
        result = components.insertion_service.restore_original()
    _print_status("clipboard_settled", result.outcome_code, result.pending_clipboard_restore)


def _print_status(status: str, outcome_code: str, pending_clipboard_restore: bool) -> None:
    print(
        json.dumps(
            {
                "status": status,
                "outcome_code": outcome_code,
                "pending_clipboard_restore": pending_clipboard_restore,
            },
            sort_keys=True,
        )
    )


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run one controlled Windows dictation vertical slice.")
    parser.add_argument("--inventory", required=True)
    parser.add_argument("--package-id", required=True)
    parser.add_argument("--candidate-id", required=True)
    parser.add_argument("--backend", required=True, choices=[backend.value for backend in AsrBackend])
    parser.add_argument("--warm-up-audio-file", required=True)
    parser.add_argument("--warm-up-duration-seconds", type=float, default=1.0)
    parser.add_argument("--duration-seconds", type=float, default=8.0)
    parser.add_argument("--pre-buffer-seconds", type=float, default=0.2)
    parser.add_argument("--sample-rate-hz", type=int, default=16000)
    parser.add_argument("--channel-count", type=int, default=1)
    parser.add_argument("--device-id")
    parser.add_argument("--language-profile", default="ru-coding")
    return parser.parse_args(argv)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))


__all__ = ["main"]
