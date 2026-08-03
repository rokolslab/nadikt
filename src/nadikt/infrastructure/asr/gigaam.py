"""GigaAM ASR engine backed by a verified local package/cache layout."""

from __future__ import annotations

import importlib
import logging
import time
from pathlib import Path
from typing import Any, Callable

from nadikt.domain.ports.asr import (
    AsrEngineError,
    AsrFailure,
    AsrFailureCode,
    AsrInferenceObserver,
    AsrLoadOptions,
    AsrModelMetadata,
    AsrSegmentInput,
    AsrSegmentTranscript,
    AsrTimingEvent,
    ensure_segment_within_capabilities,
    safe_engine_log_context,
)

LOGGER = logging.getLogger(__name__)
MAX_GIGAAM_TRANSCRIBE_SECONDS = 25.0
ALLOWED_GIGAAM_MODEL_NAMES = {"v3_e2e_ctc", "v3_e2e_rnnt", "multilingual_ctc"}
REQUIRED_GIGAAM_CACHE_FILES = {
    "v3_e2e_ctc": {"v3_e2e_ctc.ckpt", "v3_e2e_ctc_tokenizer.model"},
    "v3_e2e_rnnt": {"v3_e2e_rnnt.ckpt", "v3_e2e_rnnt_tokenizer.model"},
    "multilingual_ctc": {"multilingual_ctc.ckpt"},
}


class GigaAMAsrEngine:
    """Run GigaAM on short Nadikt-managed segments from a local cache package."""

    def __init__(self, metadata: AsrModelMetadata, module_loader: Callable[[], Any] | None = None) -> None:
        self._metadata = metadata
        self._module_loader = module_loader or (lambda: importlib.import_module("gigaam"))
        self._model: Any | None = None
        self._loader_model_name: str | None = None
        self._cancel_requested = False

    def metadata(self) -> AsrModelMetadata:
        return self._metadata

    def load(self, options: AsrLoadOptions) -> None:
        started = time.monotonic()
        LOGGER.debug("gigaam_load_start", extra=safe_engine_log_context(self._metadata))
        package_dir = options.local_package_path
        if not package_dir.is_dir():
            raise _engine_error(AsrFailureCode.MISSING_PACKAGE, "load", recoverable=True)
        loader_model_name = _loader_model_name(self._metadata.candidate_id, options.inference_defaults)
        if not loader_model_name:
            LOGGER.warning("gigaam_local_loading_unconfirmed", extra=safe_engine_log_context(self._metadata))
            raise _engine_error(AsrFailureCode.INCOMPATIBLE_BACKEND, "load", recoverable=True)
        missing_files = _missing_required_cache_files(loader_model_name, package_dir)
        if missing_files:
            raise _engine_error(AsrFailureCode.MISSING_CRITICAL_FILE, "load", recoverable=True)
        try:
            module = self._module_loader()
        except ImportError:
            raise _engine_error(AsrFailureCode.INCOMPATIBLE_BACKEND, "backend_availability", recoverable=True) from None

        load_model = getattr(module, "load_model", None)
        if not callable(load_model):
            LOGGER.warning("gigaam_local_loading_unconfirmed", extra=safe_engine_log_context(self._metadata))
            raise _engine_error(AsrFailureCode.INCOMPATIBLE_BACKEND, "load", recoverable=True)

        try:
            self._model = load_model(
                loader_model_name,
                download_root=str(package_dir),
                device="cpu",
                use_flash=False,
                fp16_encoder=False,
            )
            self._loader_model_name = loader_model_name
        except Exception:
            LOGGER.error("gigaam_load_failed", extra={**safe_engine_log_context(self._metadata), "error_code": AsrFailureCode.TRANSCRIBE_FAILED.value})
            raise _engine_error(AsrFailureCode.TRANSCRIBE_FAILED, "load", recoverable=True) from None
        _log_done("gigaam_load_done", self._metadata, started)

    def is_ready(self) -> bool:
        return self._model is not None

    def warm_up(self, segment: AsrSegmentInput, observer: AsrInferenceObserver | None = None) -> None:
        started = time.monotonic()
        try:
            self.transcribe_segment(segment, observer=None)
        except AsrEngineError as error:
            raise AsrEngineError(AsrFailure(AsrFailureCode.WARM_UP_FAILED, "warm_up", recoverable=error.failure.recoverable)) from None
        _record(observer, "warm_up_done", started, self._metadata.package_id, segment.segment_id)

    def transcribe_segment(
        self,
        segment: AsrSegmentInput,
        observer: AsrInferenceObserver | None = None,
    ) -> AsrSegmentTranscript:
        started = time.monotonic()
        LOGGER.debug("gigaam_transcribe_start", extra={**safe_engine_log_context(self._metadata), "segment_id": segment.segment_id})
        if self._model is None:
            raise _engine_error(AsrFailureCode.ENGINE_NOT_READY, "transcribe", recoverable=True)
        ensure_segment_within_capabilities(segment, self._metadata.capabilities)
        if segment.duration_seconds > MAX_GIGAAM_TRANSCRIBE_SECONDS:
            raise _engine_error(AsrFailureCode.SEGMENT_TOO_LONG, "transcribe", recoverable=True)
        if self._cancel_requested:
            self._cancel_requested = False
            raise _engine_error(AsrFailureCode.CANCELLED, "transcribe", recoverable=True)
        try:
            text = self._model.transcribe(str(segment.audio_path))
        except Exception:
            LOGGER.error("gigaam_transcribe_failed", extra={**safe_engine_log_context(self._metadata), "segment_id": segment.segment_id, "error_code": AsrFailureCode.TRANSCRIBE_FAILED.value})
            raise _engine_error(AsrFailureCode.TRANSCRIBE_FAILED, "transcribe", recoverable=True) from None
        _record(observer, "first_result", started, self._metadata.package_id, segment.segment_id)
        _record(observer, "transcribe_done", started, self._metadata.package_id, segment.segment_id)
        return AsrSegmentTranscript(segment.segment_id, str(text).strip(), segment.start_seconds, segment.end_seconds)

    def cancel(self) -> None:
        LOGGER.debug("gigaam_cancel_requested", extra=safe_engine_log_context(self._metadata))
        self._cancel_requested = True

    def close(self) -> None:
        started = time.monotonic()
        LOGGER.debug("gigaam_close_start", extra=safe_engine_log_context(self._metadata))
        model = self._model
        self._model = None
        try:
            if model is not None and hasattr(model, "close"):
                model.close()
        except Exception:
            LOGGER.error("gigaam_close_failed", extra={**safe_engine_log_context(self._metadata), "error_code": AsrFailureCode.RESOURCE_RELEASE_FAILED.value})
            raise _engine_error(AsrFailureCode.RESOURCE_RELEASE_FAILED, "close", recoverable=True) from None
        _log_done("gigaam_close_done", self._metadata, started)


def _loader_model_name(candidate_id: str, inference_defaults: object) -> str | None:
    defaults = inference_defaults if isinstance(inference_defaults, dict) else {}
    value = defaults.get("gigaam_model_name")
    if isinstance(value, str) and value in ALLOWED_GIGAAM_MODEL_NAMES:
        return value
    mapping = {
        "gigaam-v3-e2e-ctc": "v3_e2e_ctc",
        "gigaam-v3-e2e-rnnt": "v3_e2e_rnnt",
        "gigaam-multilingual-220m": "multilingual_ctc",
    }
    return mapping.get(candidate_id)


def _missing_required_cache_files(loader_model_name: str, package_dir: Path) -> tuple[str, ...]:
    required = REQUIRED_GIGAAM_CACHE_FILES.get(loader_model_name)
    if not required:
        return ("unknown-layout",)
    return tuple(sorted(relative_path for relative_path in required if not (package_dir / relative_path).is_file()))


def _engine_error(code: AsrFailureCode, phase: str, *, recoverable: bool) -> AsrEngineError:
    return AsrEngineError(AsrFailure(code, phase=phase, recoverable=recoverable))


def _record(observer: AsrInferenceObserver | None, phase: str, started: float, package_id: str, segment_id: int | None) -> None:
    if observer is not None:
        observer.record(AsrTimingEvent(phase, (time.monotonic() - started) * 1000, package_id, segment_id))
    LOGGER.info("gigaam_phase_done", extra={"phase": phase, "outcome": "success", "package_id": package_id, "segment_id": segment_id})


def _log_done(event_name: str, metadata: AsrModelMetadata, started: float) -> None:
    LOGGER.info(event_name, extra={**safe_engine_log_context(metadata), "duration_ms": (time.monotonic() - started) * 1000, "outcome": "success"})


__all__ = ["GigaAMAsrEngine", "MAX_GIGAAM_TRANSCRIBE_SECONDS"]
