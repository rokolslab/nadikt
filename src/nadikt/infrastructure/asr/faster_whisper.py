"""faster-whisper local package probe adapter."""

from __future__ import annotations

import importlib
import time
from pathlib import Path
from typing import Any, Callable

from benchmarks.asr.manifests import ModelPackageManifest
from benchmarks.asr.probe_results import ProbeOutcome, ProbePhaseResult
from benchmarks.asr.logging_config import get_logger

LOGGER = get_logger(__name__)


class FasterWhisperLocalProbe:
    """Probe faster-whisper using only a verified local CTranslate2 directory."""

    def __init__(self, whisper_model_cls: Callable[..., Any] | None = None) -> None:
        self._whisper_model_cls = whisper_model_cls
        self._model: Any | None = None

    def load(self, package_dir: Path, manifest: ModelPackageManifest) -> ProbePhaseResult:
        started = time.monotonic()
        LOGGER.debug("faster_whisper_load_start", extra={"package_id": manifest.package_id})
        if _looks_like_hub_identifier(str(package_dir)):
            return _phase("load", ProbeOutcome.HUB_IDENTIFIER_REJECTED.value, started)
        if not package_dir.is_dir():
            return _phase("load", ProbeOutcome.MISSING_PACKAGE.value, started)

        try:
            model_cls = self._whisper_model_cls or importlib.import_module("faster_whisper").WhisperModel
        except (AttributeError, ImportError):
            return _phase("backend_availability", ProbeOutcome.BACKEND_UNAVAILABLE.value, started)

        try:
            self._model = model_cls(str(package_dir), device="cpu", compute_type="int8")
        except Exception:
            LOGGER.error("faster_whisper_load_failed", extra={"package_id": manifest.package_id, "error_code": ProbeOutcome.LOAD_FAILED.value})
            return _phase("load", ProbeOutcome.LOAD_FAILED.value, started)
        return _phase("load", ProbeOutcome.SUCCESS.value, started)

    def is_ready(self) -> ProbePhaseResult:
        started = time.monotonic()
        return _phase(
            "readiness",
            ProbeOutcome.SUCCESS.value if self._model is not None else ProbeOutcome.READINESS_FAILED.value,
            started,
        )

    def warm_up(self) -> ProbePhaseResult:
        started = time.monotonic()
        return _phase("warmup", ProbeOutcome.SUCCESS.value if self._model is not None else ProbeOutcome.NOT_RUN.value, started)

    def transcribe(self, audio_file: Path | None, audio_label: str | None, beam_size: int = 5) -> ProbePhaseResult:
        started = time.monotonic()
        LOGGER.debug("faster_whisper_transcribe_start", extra={"audio_label": audio_label or "not_provided"})
        if self._model is None or audio_file is None:
            return _phase("transcribe_probe", ProbeOutcome.NOT_RUN.value, started)
        try:
            segments, _info = self._model.transcribe(str(audio_file), beam_size=beam_size)
            segment_count = sum(1 for _segment in segments)
        except Exception:
            LOGGER.error("faster_whisper_transcribe_failed", extra={"audio_label": audio_label or "provided", "error_code": ProbeOutcome.TRANSCRIBE_FAILED.value})
            return _phase("transcribe_probe", ProbeOutcome.TRANSCRIBE_FAILED.value, started)
        return _phase("transcribe_probe", ProbeOutcome.SUCCESS.value, started, details={"segment_count": segment_count})

    def close(self) -> ProbePhaseResult:
        started = time.monotonic()
        LOGGER.debug("faster_whisper_close_start")
        model = self._model
        self._model = None
        try:
            if model is not None and hasattr(model, "close"):
                model.close()
        except Exception:
            LOGGER.error("faster_whisper_close_failed", extra={"error_code": ProbeOutcome.CLOSE_FAILED.value})
            return _phase("close", ProbeOutcome.CLOSE_FAILED.value, started)
        return _phase("close", ProbeOutcome.SUCCESS.value, started)


def _looks_like_hub_identifier(value: str) -> bool:
    normalized = value.strip().lower()
    return normalized in {"tiny", "base", "small", "medium", "large", "large-v2", "large-v3"} or normalized.startswith(("openai/", "systran/"))


def _phase(
    phase: str,
    outcome: str,
    started: float,
    *,
    details: dict[str, object] | None = None,
) -> ProbePhaseResult:
    result = ProbePhaseResult(phase, outcome, (time.monotonic() - started) * 1000, details=details or {})
    LOGGER.info("faster_whisper_phase_done", extra={"phase": phase, "outcome": outcome})
    return result


__all__ = ["FasterWhisperLocalProbe"]
