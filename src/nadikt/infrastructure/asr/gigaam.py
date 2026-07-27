"""GigaAM local package probe adapter."""

from __future__ import annotations

import importlib
import time
from pathlib import Path
from typing import Any, Callable

from benchmarks.asr.manifests import ModelPackageManifest
from benchmarks.asr.probe_results import ProbeOutcome, ProbePhaseResult
from benchmarks.asr.logging_config import get_logger

LOGGER = get_logger(__name__)
MAX_GIGAAM_TRANSCRIBE_SECONDS = 25.0


class GigaAMLocalProbe:
    """Probe GigaAM using a validated package as the SDK download_root cache."""

    def __init__(self, module_loader: Callable[[], Any] | None = None) -> None:
        self._module_loader = module_loader or (lambda: importlib.import_module("gigaam"))
        self._model: Any | None = None

    def load(self, package_dir: Path, manifest: ModelPackageManifest) -> ProbePhaseResult:
        started = time.monotonic()
        LOGGER.debug("gigaam_load_start", extra={"package_id": manifest.package_id})
        try:
            module = self._module_loader()
        except ImportError:
            return _phase("backend_availability", ProbeOutcome.BACKEND_UNAVAILABLE.value, started)

        load_model = getattr(module, "load_model", None)
        if not callable(load_model):
            LOGGER.warning("gigaam_local_loading_unconfirmed", extra={"package_id": manifest.package_id})
            return _phase("load", ProbeOutcome.LOCAL_LOADING_UNCONFIRMED.value, started)

        loader_model_name = _loader_model_name(manifest)
        if not loader_model_name:
            LOGGER.warning("gigaam_local_loading_unconfirmed", extra={"package_id": manifest.package_id})
            return _phase("load", ProbeOutcome.LOCAL_LOADING_UNCONFIRMED.value, started)
        try:
            self._model = load_model(
                loader_model_name,
                download_root=str(package_dir),
                device="cpu",
                use_flash=False,
                fp16_encoder=False,
            )
        except Exception:
            LOGGER.error("gigaam_load_failed", extra={"package_id": manifest.package_id, "error_code": ProbeOutcome.LOAD_FAILED.value})
            return _phase("load", ProbeOutcome.LOAD_FAILED.value, started)
        return _phase("load", ProbeOutcome.SUCCESS.value, started)

    def is_ready(self) -> ProbePhaseResult:
        started = time.monotonic()
        return _phase("readiness", ProbeOutcome.SUCCESS.value if self._model is not None else ProbeOutcome.READINESS_FAILED.value, started)

    def warm_up(self) -> ProbePhaseResult:
        started = time.monotonic()
        return _phase("warmup", ProbeOutcome.SUCCESS.value if self._model is not None else ProbeOutcome.NOT_RUN.value, started)

    def transcribe(self, audio_file: Path | None, audio_label: str | None, duration_seconds: float | None = None) -> ProbePhaseResult:
        started = time.monotonic()
        LOGGER.debug("gigaam_transcribe_start", extra={"audio_label": audio_label or "not_provided"})
        if self._model is None or audio_file is None:
            return _phase("transcribe_probe", ProbeOutcome.NOT_RUN.value, started)
        if duration_seconds is not None and duration_seconds > MAX_GIGAAM_TRANSCRIBE_SECONDS:
            return _phase("transcribe_probe", ProbeOutcome.SEGMENT_TOO_LONG.value, started)
        try:
            self._model.transcribe(str(audio_file))
        except Exception:
            LOGGER.error("gigaam_transcribe_failed", extra={"audio_label": audio_label or "provided", "error_code": ProbeOutcome.TRANSCRIBE_FAILED.value})
            return _phase("transcribe_probe", ProbeOutcome.TRANSCRIBE_FAILED.value, started)
        return _phase("transcribe_probe", ProbeOutcome.SUCCESS.value, started)

    def close(self) -> ProbePhaseResult:
        started = time.monotonic()
        LOGGER.debug("gigaam_close_start")
        try:
            if self._model is not None and hasattr(self._model, "close"):
                self._model.close()
            self._model = None
        except Exception:
            LOGGER.error("gigaam_close_failed", extra={"error_code": ProbeOutcome.CLOSE_FAILED.value})
            return _phase("close", ProbeOutcome.CLOSE_FAILED.value, started)
        return _phase("close", ProbeOutcome.SUCCESS.value, started)


def _phase(phase: str, outcome: str, started: float) -> ProbePhaseResult:
    result = ProbePhaseResult(phase, outcome, (time.monotonic() - started) * 1000)
    LOGGER.info("gigaam_phase_done", extra={"phase": phase, "outcome": outcome})
    return result


def _loader_model_name(manifest: ModelPackageManifest) -> str | None:
    value = manifest.inference_defaults.get("gigaam_model_name")
    if isinstance(value, str) and value:
        return value
    mapping = {
        "gigaam-v3-e2e-ctc": "v3_e2e_ctc",
        "gigaam-v3-e2e-rnnt": "v3_e2e_rnnt",
        "gigaam-multilingual-220m": "multilingual_ctc",
    }
    return mapping.get(manifest.candidate_id)


__all__ = ["GigaAMLocalProbe", "MAX_GIGAAM_TRANSCRIBE_SECONDS"]
