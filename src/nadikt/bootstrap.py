"""Composition helpers for early Nadikt vertical slices."""

from __future__ import annotations

import logging
import os
import time

from nadikt.domain.ports.asr import (
    AsrBackend,
    AsrEngine,
    AsrEngineError,
    AsrFailure,
    AsrFailureCode,
    AsrModelMetadata,
    AsrSegmentInput,
    safe_engine_log_context,
)
from nadikt.infrastructure.asr.faster_whisper import FasterWhisperAsrEngine
from nadikt.infrastructure.asr.gigaam import GigaAMAsrEngine
from nadikt.infrastructure.model_packages import ModelPackageBinding

LOGGER = logging.getLogger(__name__)
_LOG_LEVEL = os.environ.get("NADIKT_LOG_LEVEL", os.environ.get("LOG_LEVEL", "INFO")).upper()
logging.basicConfig(level=getattr(logging, _LOG_LEVEL, logging.INFO))


def load_local_asr_engine(binding: ModelPackageBinding, warm_up_segment: AsrSegmentInput) -> AsrEngine:
    """Instantiate, load and warm up exactly one validated local ASR candidate."""

    started = time.monotonic()
    metadata = _metadata_from_binding(binding)
    LOGGER.debug(
        "bootstrap.asr.load.start",
        extra={**safe_engine_log_context(metadata), "warm_up_segment_id": warm_up_segment.segment_id},
    )
    engine = _engine_for_backend(binding.backend, metadata)
    try:
        engine.load(binding.load_options)
        engine.warm_up(warm_up_segment)
    except Exception:
        LOGGER.debug(
            "bootstrap.asr.load.failed",
            extra={**safe_engine_log_context(metadata), "failure_code": AsrFailureCode.WARM_UP_FAILED.value},
        )
        _close_after_failed_load(engine, metadata)
        raise
    LOGGER.debug(
        "bootstrap.asr.load.complete",
        extra={
            **safe_engine_log_context(metadata),
            "duration_ms": (time.monotonic() - started) * 1000,
            "asr_status": "not_decided_single_explicit_candidate_loaded",
        },
    )
    return engine


def _metadata_from_binding(binding: ModelPackageBinding) -> AsrModelMetadata:
    return AsrModelMetadata(
        package_id=binding.package_id,
        candidate_id=binding.candidate_id,
        backend=binding.backend,
        model_name=binding.model_name,
        model_revision=binding.model_revision,
        backend_version=binding.backend_version,
        license_marker=binding.license_marker,
        capabilities=binding.capabilities,
        checksum_prefixes=binding.checksum_prefixes,
    )


def _engine_for_backend(backend: AsrBackend, metadata: AsrModelMetadata) -> AsrEngine:
    if backend == AsrBackend.GIGAAM:
        return GigaAMAsrEngine(metadata)
    if backend == AsrBackend.FASTER_WHISPER:
        return FasterWhisperAsrEngine(metadata)
    raise AsrEngineError(AsrFailure(AsrFailureCode.INCOMPATIBLE_BACKEND, "bootstrap", recoverable=True))


def _close_after_failed_load(engine: AsrEngine, metadata: AsrModelMetadata) -> None:
    try:
        engine.close()
    except Exception:
        LOGGER.debug(
            "bootstrap.asr.close_after_failed_load.failed",
            extra={**safe_engine_log_context(metadata), "failure_code": AsrFailureCode.RESOURCE_RELEASE_FAILED.value},
        )


__all__ = ["load_local_asr_engine"]
