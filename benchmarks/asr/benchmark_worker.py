"""Spawned ASR benchmark worker.

The parent passes private paths through stdin only. This process returns bounded
JSON without transcripts, references, paths, SDK reprs or traceback text.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from nadikt.domain.ports.asr import (
    AsrBackend,
    AsrCapabilities,
    AsrEngineError,
    AsrLoadOptions,
    AsrModelMetadata,
    AsrSegmentInput,
)

from .offline_supervisor import build_unverified_worker_evidence
from .quality_metrics import cer, coding_term_accuracy, english_term_accuracy, latin_preservation_rate, wer
from .worker_protocol import WorkerPhase, WorkerRequest, WorkerResult, loads_request


def main() -> int:
    try:
        request = loads_request(sys.stdin.read())
        result = run_worker(request)
    except Exception:
        result = WorkerResult(
            nonce="invalid-request",
            package_id="unknown",
            candidate_id="unknown",
            backend="unknown",
            worker_status="protocol_error",
            phases=(WorkerPhase("protocol", "fail"),),
        )
    sys.stdout.write(result.to_worker_json())
    return 0 if result.worker_status in {"success", "not_run"} else 2


def run_worker(request: WorkerRequest) -> WorkerResult:
    phases: list[WorkerPhase] = []
    quality_metrics: dict[str, dict[str, object]] = {}
    status = "success"
    engine = _engine_from_request(request)
    try:
        started = time.monotonic()
        engine.load(AsrLoadOptions(request.package_dir, request.inference_defaults))
        phases.append(_phase("load", "success", started))
        phases.append(WorkerPhase("readiness", "success" if engine.is_ready() else "readiness_failed"))
        if request.audio_file is not None:
            segment = AsrSegmentInput(
                sample_id="worker_sample",
                segment_id=0,
                audio_path=request.audio_file,
                start_seconds=0.0,
                end_seconds=float(request.duration_seconds or 1.0),
                language_profile="ru",
                segmentation_policy_id="worker-probe-v1",
            )
            started = time.monotonic()
            engine.warm_up(segment)
            phases.append(_phase("warmup", "success", started, segment_id=0))
            started = time.monotonic()
            transcript = engine.transcribe_segment(segment)
            phases.append(_phase("transcribe_probe", "success", started, segment_id=0))
            quality_metrics = _quality_metrics(request, transcript.text)
        else:
            phases.append(WorkerPhase("warmup", "not_run"))
            phases.append(WorkerPhase("transcribe_probe", "not_run"))
    except AsrEngineError as error:
        phases.append(WorkerPhase(error.failure.phase, error.failure.code.value))
        status = "fail"
    finally:
        try:
            engine.close()
            phases.append(WorkerPhase("close", "success"))
        except AsrEngineError as error:
            phases.append(WorkerPhase("close", error.failure.code.value))
            status = "fail"

    evidence = build_unverified_worker_evidence(request.nonce)
    return WorkerResult(
        nonce=request.nonce,
        package_id=request.package_id,
        candidate_id=request.candidate_id,
        backend=request.backend,
        worker_status=status,
        phases=tuple(phases),
        quality_metrics=quality_metrics,
        offline_evidence=evidence.to_json(),
    )


def _quality_metrics(request: WorkerRequest, hypothesis: str) -> dict[str, dict[str, object]]:
    if request.reference_file is None:
        return {}
    reference = request.reference_file.read_text(encoding="utf-8")
    metrics = [
        wer(reference, hypothesis),
        cer(reference, hypothesis),
        english_term_accuracy(list(request.expected_english_terms), hypothesis),
        latin_preservation_rate(list(request.expected_english_terms), hypothesis),
        coding_term_accuracy(list(request.expected_coding_terms), hypothesis),
    ]
    return {metric.metric_name: metric.to_json() for metric in metrics}


def _engine_from_request(request: WorkerRequest) -> object:
    metadata = AsrModelMetadata(
        package_id=request.package_id,
        candidate_id=request.candidate_id,
        backend=AsrBackend(request.backend),
        model_name=request.candidate_id,
        model_revision="worker-request",
        backend_version=str(request.inference_defaults.get("backend_version") or "benchmark-lock"),
        license_marker="approved",
        capabilities=AsrCapabilities(
            languages=tuple(str(item) for item in request.capabilities.get("languages", ("ru",))),
            max_segment_seconds=float(request.capabilities.get("max_segment_seconds") or 25.0),
            punctuation=bool(request.capabilities.get("punctuation", False)),
            streaming=bool(request.capabilities.get("streaming", False)),
            word_timestamps=bool(request.capabilities.get("word_timestamps", False)),
        ),
        checksum_prefixes=request.critical_checksum_prefixes,
    )
    if request.backend == "faster-whisper":
        from nadikt.infrastructure.asr.faster_whisper import FasterWhisperAsrEngine

        return FasterWhisperAsrEngine(metadata)
    if request.backend == "gigaam":
        from nadikt.infrastructure.asr.gigaam import GigaAMAsrEngine

        return GigaAMAsrEngine(metadata)
    raise ValueError("unsupported_backend")


def _phase(phase: str, outcome: str, started: float, *, segment_id: int | None = None) -> WorkerPhase:
    return WorkerPhase(phase, outcome, (time.monotonic() - started) * 1000, segment_id=segment_id)


if __name__ == "__main__":
    raise SystemExit(main())
