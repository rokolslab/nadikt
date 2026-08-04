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
from .quality_metrics import (
    QualityMetricResult,
    cer,
    coding_term_accuracy,
    english_term_accuracy,
    english_term_accuracy_from_records,
    latin_preservation_rate,
    latin_preservation_rate_from_records,
    metric_diagnostics,
    normalized_coding_term_metrics,
    wer,
)
from .worker_protocol import (
    WorkerMetricDiagnostic,
    WorkerMetricResult,
    WorkerPhase,
    WorkerRepeatOutcome,
    WorkerRequest,
    WorkerRequestV2,
    WorkerResult,
    WorkerResultV2,
    WorkerSampleOutcome,
    WorkerSampleRequest,
    loads_request,
    loads_request_v2,
)


def main() -> int:
    try:
        request = _loads_request(sys.stdin.read())
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


def run_worker(request: WorkerRequest | WorkerRequestV2) -> WorkerResult | WorkerResultV2:
    if isinstance(request, WorkerRequestV2):
        return _run_worker_v2(request)
    return _run_worker_v1(request)


def _run_worker_v1(request: WorkerRequest) -> WorkerResult:
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


def _run_worker_v2(request: WorkerRequestV2) -> WorkerResultV2:
    phases: list[WorkerPhase] = []
    samples: list[WorkerSampleOutcome] = []
    status = "success"
    engine = _engine_from_request(request)
    try:
        started = time.monotonic()
        engine.load(AsrLoadOptions(request.package_dir, request.inference_defaults))
        phases.append(_phase("load", "success", started))
        ready = engine.is_ready()
        phases.append(WorkerPhase("readiness", "success" if ready else "readiness_failed"))
        if ready:
            samples.append(_run_sample(engine, request.repeat.warmup_sample, phase_name="warmup"))
            for sample in request.repeat.scored_samples:
                samples.append(_run_sample(engine, sample, phase_name="transcribe"))
        else:
            status = "fail"
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
    if any(sample.outcome != "success" for sample in samples):
        status = "fail"
    return WorkerResultV2(
        nonce=request.nonce,
        package_id=request.package_id,
        candidate_id=request.candidate_id,
        backend=request.backend,
        worker_status=status,
        repeat=WorkerRepeatOutcome(
            repeat_index=request.repeat.repeat_index,
            outcome="success" if status == "success" else "fail",
            phases=tuple(phases),
            samples=tuple(samples),
        ),
    )


def _run_sample(engine: object, sample: WorkerSampleRequest, *, phase_name: str) -> WorkerSampleOutcome:
    segment = AsrSegmentInput(
        sample_id=sample.sample_id,
        segment_id=0,
        audio_path=sample.audio_file,
        start_seconds=0.0,
        end_seconds=float(sample.duration_seconds),
        language_profile="ru",
        segmentation_policy_id="worker-repeat-v2",
    )
    try:
        started = time.monotonic()
        if sample.scored:
            transcript = engine.transcribe_segment(segment)
            phases = (_phase(phase_name, "success", started, segment_id=0),)
            metric_results = _quality_metric_results(sample, transcript.text)
            metrics = _worker_metrics(metric_results)
            diagnostics = _worker_metric_diagnostics(sample, metric_results)
        else:
            engine.warm_up(segment)
            phases = (_phase(phase_name, "success", started, segment_id=0),)
            metrics = ()
            diagnostics = ()
        return WorkerSampleOutcome(sample.sample_id, sample.category, sample.scored, "success", phases, metrics, diagnostics)
    except AsrEngineError as error:
        return WorkerSampleOutcome(sample.sample_id, sample.category, sample.scored, "fail", (WorkerPhase(error.failure.phase, error.failure.code.value),), ())


def _quality_metrics(request: WorkerRequest, hypothesis: str) -> dict[str, dict[str, object]]:
    if request.reference_file is None:
        return {}
    reference = request.reference_file.read_text(encoding="utf-8")
    expected_coding_terms = list(request.expected_coding_terms)
    expected_english_terms = list(request.expected_english_terms)
    metrics = [
        wer(reference, hypothesis),
        cer(reference, hypothesis),
        _english_metric(expected_coding_terms, expected_english_terms, hypothesis),
        _latin_metric(expected_coding_terms, expected_english_terms, hypothesis),
        coding_term_accuracy(expected_coding_terms, hypothesis),
    ]
    if expected_coding_terms:
        metrics.extend(normalized_coding_term_metrics(expected_coding_terms, hypothesis))
    return {metric.metric_name: metric.to_json() for metric in metrics}


def _sample_metrics(sample: WorkerSampleRequest, hypothesis: str) -> tuple[WorkerMetricResult, ...]:
    return _worker_metrics(_quality_metric_results(sample, hypothesis))


def _quality_metric_results(sample: WorkerSampleRequest, hypothesis: str) -> list[QualityMetricResult]:
    if sample.reference_file is None:
        return []
    reference = sample.reference_file.read_text(encoding="utf-8")
    expected_coding_terms = list(sample.expected_coding_terms)
    expected_english_terms = list(sample.expected_english_terms)
    metrics = [
        wer(reference, hypothesis),
        cer(reference, hypothesis),
        _english_metric(expected_coding_terms, expected_english_terms, hypothesis),
        _latin_metric(expected_coding_terms, expected_english_terms, hypothesis),
        coding_term_accuracy(expected_coding_terms, hypothesis),
    ]
    if expected_coding_terms:
        metrics.extend(normalized_coding_term_metrics(expected_coding_terms, hypothesis))
    return metrics


def _worker_metrics(metrics: list[QualityMetricResult]) -> tuple[WorkerMetricResult, ...]:
    return tuple(WorkerMetricResult(metric.metric_name, metric.version, metric.value, metric.numerator, metric.denominator, metric.status) for metric in metrics)


def _worker_metric_diagnostics(sample: WorkerSampleRequest, metrics: list[QualityMetricResult]) -> tuple[WorkerMetricDiagnostic, ...]:
    diagnostics: list[WorkerMetricDiagnostic] = []
    for metric in metrics:
        if _term_metric_view(metric.metric_name) is None:
            continue
        view = _term_metric_view(metric.metric_name) or "raw"
        for diagnostic in metric_diagnostics(metric, view=view):
            diagnostics.append(
                WorkerMetricDiagnostic(
                    sample_id=sample.sample_id,
                    category=sample.category,
                    metric_name=diagnostic.metric_name,
                    view=diagnostic.view,
                    status=diagnostic.status,
                    numerator=diagnostic.numerator,
                    denominator=diagnostic.denominator,
                    reason_code=diagnostic.reason_code,
                    count=diagnostic.count,
                )
            )
    return tuple(diagnostics)


def _term_metric_view(metric_name: str) -> str | None:
    raw_names = {"coding_term_accuracy", "english_term_accuracy", "latin_preservation_rate"}
    normalized_names = {f"{name}_normalized" for name in raw_names}
    if metric_name in raw_names:
        return "raw"
    if metric_name in normalized_names:
        return "normalized"
    return None


def _english_metric(expected_coding_terms: list[object], expected_english_terms: list[str], hypothesis: str) -> QualityMetricResult:
    if expected_coding_terms:
        return english_term_accuracy_from_records(expected_coding_terms, hypothesis)
    return english_term_accuracy(expected_english_terms, hypothesis)


def _latin_metric(expected_coding_terms: list[object], expected_english_terms: list[str], hypothesis: str) -> QualityMetricResult:
    if expected_coding_terms:
        return latin_preservation_rate_from_records(expected_coding_terms, hypothesis)
    return latin_preservation_rate(expected_english_terms, hypothesis)


def _engine_from_request(request: WorkerRequest | WorkerRequestV2) -> object:
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


def _loads_request(text: str) -> WorkerRequest | WorkerRequestV2:
    try:
        return loads_request_v2(text)
    except ValueError as error:
        if str(error) != "invalid_worker_protocol_version":
            raise
    return loads_request(text)


def _phase(phase: str, outcome: str, started: float, *, segment_id: int | None = None) -> WorkerPhase:
    return WorkerPhase(phase, outcome, (time.monotonic() - started) * 1000, segment_id=segment_id)


if __name__ == "__main__":
    raise SystemExit(main())
