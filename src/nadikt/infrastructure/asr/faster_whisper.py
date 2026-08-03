"""faster-whisper ASR engine backed by a verified local CTranslate2 package."""

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


class FasterWhisperAsrEngine:
    """Run faster-whisper from a local package without accepting Hub IDs."""

    def __init__(self, metadata: AsrModelMetadata, whisper_model_cls: Callable[..., Any] | None = None) -> None:
        self._metadata = metadata
        self._whisper_model_cls = whisper_model_cls
        self._model: Any | None = None
        self._inference_defaults: dict[str, object] = {}
        self._cancel_requested = False

    def metadata(self) -> AsrModelMetadata:
        return self._metadata

    def load(self, options: AsrLoadOptions) -> None:
        started = time.monotonic()
        LOGGER.debug("faster_whisper_load_start", extra=safe_engine_log_context(self._metadata))
        package_dir = options.local_package_path
        self._inference_defaults = dict(options.inference_defaults)
        if _looks_like_hub_identifier(str(package_dir)):
            raise _engine_error(AsrFailureCode.INVALID_PACKAGE_PATH, "load", recoverable=True)
        if not package_dir.is_dir():
            raise _engine_error(AsrFailureCode.MISSING_PACKAGE, "load", recoverable=True)

        try:
            model_cls = self._whisper_model_cls or importlib.import_module("faster_whisper").WhisperModel
        except (AttributeError, ImportError):
            raise _engine_error(AsrFailureCode.INCOMPATIBLE_BACKEND, "backend_availability", recoverable=True) from None

        try:
            kwargs: dict[str, object] = {"device": "cpu", "compute_type": "int8"}
            cpu_threads = self._inference_defaults.get("cpu_threads")
            if isinstance(cpu_threads, int) and cpu_threads > 0:
                kwargs["cpu_threads"] = cpu_threads
            self._model = model_cls(str(package_dir), **kwargs)
        except Exception:
            LOGGER.error("faster_whisper_load_failed", extra={**safe_engine_log_context(self._metadata), "error_code": AsrFailureCode.TRANSCRIBE_FAILED.value})
            raise _engine_error(AsrFailureCode.TRANSCRIBE_FAILED, "load", recoverable=True) from None
        _log_done("faster_whisper_load_done", self._metadata, started)

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
        LOGGER.debug("faster_whisper_transcribe_start", extra={**safe_engine_log_context(self._metadata), "segment_id": segment.segment_id})
        if self._model is None:
            raise _engine_error(AsrFailureCode.ENGINE_NOT_READY, "transcribe", recoverable=True)
        ensure_segment_within_capabilities(segment, self._metadata.capabilities)
        if self._cancel_requested:
            self._cancel_requested = False
            raise _engine_error(AsrFailureCode.CANCELLED, "transcribe", recoverable=True)
        try:
            segments, _info = self._model.transcribe(
                str(segment.audio_path),
                beam_size=int(self._inference_defaults.get("beam_size") or 5),
                language=_language_argument(segment.language_profile),
                vad_filter=bool(self._inference_defaults.get("vad_filter", False)),
            )
            texts: list[str] = []
            first_seen = False
            for sdk_segment in segments:
                if not first_seen:
                    _record(observer, "first_result", started, self._metadata.package_id, segment.segment_id)
                    first_seen = True
                texts.append(str(getattr(sdk_segment, "text", "")))
        except Exception:
            LOGGER.error("faster_whisper_transcribe_failed", extra={**safe_engine_log_context(self._metadata), "segment_id": segment.segment_id, "error_code": AsrFailureCode.TRANSCRIBE_FAILED.value})
            raise _engine_error(AsrFailureCode.TRANSCRIBE_FAILED, "transcribe", recoverable=True) from None
        _record(observer, "transcribe_done", started, self._metadata.package_id, segment.segment_id)
        return AsrSegmentTranscript(segment.segment_id, "".join(texts).strip(), segment.start_seconds, segment.end_seconds)

    def cancel(self) -> None:
        LOGGER.debug("faster_whisper_cancel_requested", extra=safe_engine_log_context(self._metadata))
        self._cancel_requested = True

    def close(self) -> None:
        started = time.monotonic()
        LOGGER.debug("faster_whisper_close_start", extra=safe_engine_log_context(self._metadata))
        model = self._model
        self._model = None
        try:
            if model is not None and hasattr(model, "close"):
                model.close()
        except Exception:
            LOGGER.error("faster_whisper_close_failed", extra={**safe_engine_log_context(self._metadata), "error_code": AsrFailureCode.RESOURCE_RELEASE_FAILED.value})
            raise _engine_error(AsrFailureCode.RESOURCE_RELEASE_FAILED, "close", recoverable=True) from None
        _log_done("faster_whisper_close_done", self._metadata, started)


def _looks_like_hub_identifier(value: str) -> bool:
    normalized = value.strip().lower()
    return normalized in {"tiny", "base", "small", "medium", "large", "large-v2", "large-v3"} or normalized.startswith(("openai/", "systran/"))


def _language_argument(language_profile: str) -> str | None:
    if language_profile.startswith("ru"):
        return "ru"
    return None


def _engine_error(code: AsrFailureCode, phase: str, *, recoverable: bool) -> AsrEngineError:
    return AsrEngineError(AsrFailure(code, phase=phase, recoverable=recoverable))


def _record(observer: AsrInferenceObserver | None, phase: str, started: float, package_id: str, segment_id: int | None) -> None:
    if observer is not None:
        observer.record(AsrTimingEvent(phase, (time.monotonic() - started) * 1000, package_id, segment_id))
    LOGGER.info("faster_whisper_phase_done", extra={"phase": phase, "outcome": "success", "package_id": package_id, "segment_id": segment_id})


def _log_done(event_name: str, metadata: AsrModelMetadata, started: float) -> None:
    LOGGER.info(event_name, extra={**safe_engine_log_context(metadata), "duration_ms": (time.monotonic() - started) * 1000, "outcome": "success"})


__all__ = ["FasterWhisperAsrEngine"]
