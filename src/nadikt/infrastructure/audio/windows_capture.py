"""Opt-in Windows bounded microphone capture adapter.

The adapter lazy-loads the optional ``sounddevice`` package only when audio is
actually enumerated or captured. It is intentionally not a committed runtime
dependency yet; missing SDK/platform capability fails closed through the audio
port's typed failure envelope.
"""

from __future__ import annotations

import hashlib
import importlib
import logging
import os
import platform
import tempfile
import time
import uuid
import wave
from pathlib import Path
from typing import Any

from nadikt.domain.ports.asr import AsrSegmentInput
from nadikt.domain.ports.audio import (
    AudioCaptureError,
    AudioCaptureFailure,
    AudioCaptureFailureCode,
    AudioCaptureOptions,
    AudioCapturePort,
    AudioCaptureResult,
    AudioDeviceDescriptor,
    AudioLevelStatus,
    safe_audio_capture_log_context,
)

LOGGER = logging.getLogger(__name__)
_LOG_LEVEL = os.environ.get("NADIKT_LOG_LEVEL", os.environ.get("LOG_LEVEL", "INFO")).upper()
logging.basicConfig(level=getattr(logging, _LOG_LEVEL, logging.INFO))


class WindowsAudioCaptureAdapter(AudioCapturePort):
    """One-shot microphone capture for a controlled Windows host."""

    def __init__(self, *, temp_dir: Path | None = None) -> None:
        self._temp_dir = temp_dir
        self._cancel_requested = False

    def list_input_devices(self) -> tuple[AudioDeviceDescriptor, ...]:
        LOGGER.debug("audio.list_input_devices.start", extra={"adapter": "windows_sounddevice"})
        sounddevice = self._load_sounddevice()
        raw_devices = sounddevice.query_devices()
        descriptors: list[AudioDeviceDescriptor] = []
        for index, raw_device in enumerate(raw_devices):
            max_input_channels = int(raw_device.get("max_input_channels", 0))
            if max_input_channels <= 0:
                continue
            capability_category = self._capability_category(max_input_channels)
            descriptors.append(
                AudioDeviceDescriptor(
                    device_id=self._opaque_device_id(index, raw_device),
                    capability_category=capability_category,
                    is_default=False,
                )
            )
        LOGGER.debug(
            "audio.list_input_devices.complete",
            extra={"adapter": "windows_sounddevice", "device_count": len(descriptors)},
        )
        return tuple(descriptors)

    def capture_once(self, options: AudioCaptureOptions) -> AudioCaptureResult:
        LOGGER.debug(
            "audio.capture_once.start",
            extra={
                "adapter": "windows_sounddevice",
                "max_duration_seconds": options.max_duration_seconds,
                "sample_rate_hz": options.sample_rate_hz,
                "channel_count": options.channel_count,
                "pre_buffer_seconds": options.pre_buffer_seconds,
                "segmentation_policy_id": options.segmentation_policy_id,
            },
        )
        self._ensure_windows()
        sounddevice = self._load_sounddevice()
        device_index, descriptor = self._resolve_device(sounddevice, options.selected_device_id)
        temp_path: Path | None = None
        start = time.monotonic()
        try:
            frames = int((options.max_duration_seconds + options.pre_buffer_seconds) * options.sample_rate_hz)
            if frames <= 0:
                raise ValueError("capture frame count must be positive")
            self._cancel_requested = False
            recording = sounddevice.rec(
                frames,
                samplerate=options.sample_rate_hz,
                channels=options.channel_count,
                dtype="int16",
                device=device_index,
            )
            sounddevice.wait()
            if self._cancel_requested:
                raise AudioCaptureError(
                    AudioCaptureFailure(AudioCaptureFailureCode.CANCELLED, "record", True, retryable=True)
                )
            duration_seconds = time.monotonic() - start
            level_status = self._level_status(recording)
            temp_path = self._write_wav(recording, options.sample_rate_hz, options.channel_count)
            segment = AsrSegmentInput(
                sample_id=uuid.uuid4().hex,
                segment_id=0,
                audio_path=temp_path,
                start_seconds=0.0,
                end_seconds=duration_seconds,
                language_profile=options.language_profile,
                segmentation_policy_id=options.segmentation_policy_id,
            )
            result = AudioCaptureResult(
                segment=segment,
                device=descriptor,
                level_status=level_status,
                duration_seconds=duration_seconds,
                sample_rate_hz=options.sample_rate_hz,
                channel_count=options.channel_count,
            )
            LOGGER.debug("audio.capture_once.complete", extra=safe_audio_capture_log_context(result))
            return result
        except AudioCaptureError:
            self._cleanup_temp_path(temp_path)
            raise
        except Exception as exc:  # pragma: no cover - exercised by Windows host smoke.
            self._cleanup_temp_path(temp_path)
            LOGGER.debug(
                "audio.capture_once.failed",
                extra={"adapter": "windows_sounddevice", "failure_code": AudioCaptureFailureCode.CAPTURE_FAILED.value},
            )
            raise AudioCaptureError(
                AudioCaptureFailure(AudioCaptureFailureCode.CAPTURE_FAILED, "record", True, retryable=True)
            ) from exc

    def cancel(self) -> None:
        LOGGER.debug("audio.cancel.start", extra={"adapter": "windows_sounddevice"})
        self._cancel_requested = True
        try:
            self._load_sounddevice().stop()
        except AudioCaptureError:
            raise
        except Exception as exc:  # pragma: no cover - depends on optional SDK state.
            raise AudioCaptureError(
                AudioCaptureFailure(AudioCaptureFailureCode.CAPTURE_FAILED, "cancel", True, retryable=True)
            ) from exc
        LOGGER.debug("audio.cancel.complete", extra={"adapter": "windows_sounddevice", "outcome": "requested"})

    def cleanup(self, result: AudioCaptureResult) -> None:
        LOGGER.debug(
            "audio.cleanup.start",
            extra={"sample_id": result.segment.sample_id, "segment_id": result.segment.segment_id},
        )
        try:
            result.segment.audio_path.unlink(missing_ok=True)
        except OSError as exc:
            LOGGER.debug(
                "audio.cleanup.failed",
                extra={"failure_code": AudioCaptureFailureCode.TEMP_CLEANUP_FAILED.value},
            )
            raise AudioCaptureError(
                AudioCaptureFailure(AudioCaptureFailureCode.TEMP_CLEANUP_FAILED, "cleanup", True, retryable=True)
            ) from exc
        LOGGER.debug(
            "audio.cleanup.complete",
            extra={"sample_id": result.segment.sample_id, "segment_id": result.segment.segment_id},
        )

    def _ensure_windows(self) -> None:
        if platform.system() == "Windows":
            return
        raise AudioCaptureError(
            AudioCaptureFailure(AudioCaptureFailureCode.DEVICE_UNAVAILABLE, "platform", False, retryable=False)
        )

    def _load_sounddevice(self) -> Any:
        try:
            return importlib.import_module("sounddevice")
        except ImportError as exc:
            raise AudioCaptureError(
                AudioCaptureFailure(AudioCaptureFailureCode.DEVICE_UNAVAILABLE, "optional_import", False)
            ) from exc

    def _resolve_device(self, sounddevice: Any, selected_device_id: str | None) -> tuple[int | None, AudioDeviceDescriptor]:
        raw_devices = sounddevice.query_devices()
        if selected_device_id is None:
            default_input = sounddevice.default.device[0]
            if default_input is None or int(default_input) < 0:
                raise AudioCaptureError(
                    AudioCaptureFailure(AudioCaptureFailureCode.DEVICE_UNAVAILABLE, "device_selection", True)
                )
            raw_device = raw_devices[int(default_input)]
            max_input_channels = int(raw_device.get("max_input_channels", 0))
            if max_input_channels <= 0:
                raise AudioCaptureError(
                    AudioCaptureFailure(AudioCaptureFailureCode.INVALID_DEVICE, "device_selection", True)
                )
            return int(default_input), AudioDeviceDescriptor(
                device_id=self._opaque_device_id(int(default_input), raw_device),
                capability_category=self._capability_category(max_input_channels),
                is_default=True,
            )

        for index, raw_device in enumerate(raw_devices):
            if self._opaque_device_id(index, raw_device) != selected_device_id:
                continue
            max_input_channels = int(raw_device.get("max_input_channels", 0))
            if max_input_channels <= 0:
                break
            return index, AudioDeviceDescriptor(
                device_id=selected_device_id,
                capability_category=self._capability_category(max_input_channels),
                is_default=False,
            )

        raise AudioCaptureError(AudioCaptureFailure(AudioCaptureFailureCode.INVALID_DEVICE, "device_selection", True))

    def _write_wav(self, recording: Any, sample_rate_hz: int, channel_count: int) -> Path:
        temp_file = tempfile.NamedTemporaryFile(
            prefix="nadikt-capture-",
            suffix=".wav",
            dir=self._temp_dir,
            delete=False,
        )
        temp_path = Path(temp_file.name)
        temp_file.close()
        with wave.open(str(temp_path), "wb") as wav_file:
            wav_file.setnchannels(channel_count)
            wav_file.setsampwidth(2)
            wav_file.setframerate(sample_rate_hz)
            wav_file.writeframes(recording.tobytes())
        return temp_path

    def _cleanup_temp_path(self, temp_path: Path | None) -> None:
        if temp_path is None:
            return
        try:
            temp_path.unlink(missing_ok=True)
        except OSError:
            LOGGER.debug(
                "audio.cleanup_after_failure.failed",
                extra={"failure_code": AudioCaptureFailureCode.TEMP_CLEANUP_FAILED.value},
            )

    def _level_status(self, recording: Any) -> AudioLevelStatus:
        try:
            peak = max(abs(int(sample)) for sample in recording.flatten())
        except Exception:
            return AudioLevelStatus.UNKNOWN
        if peak == 0:
            return AudioLevelStatus.SILENCE
        if peak < 512:
            return AudioLevelStatus.LOW
        if peak >= 32760:
            return AudioLevelStatus.CLIPPED
        return AudioLevelStatus.NORMAL

    def _opaque_device_id(self, index: int, raw_device: dict[str, object]) -> str:
        material = f"{index}:{raw_device.get('hostapi')}:{raw_device.get('max_input_channels')}".encode("utf-8")
        return hashlib.sha256(material).hexdigest()[:16]

    def _capability_category(self, max_input_channels: int) -> str:
        if max_input_channels == 1:
            return "mono-input"
        return "multi-channel-input"


__all__ = ["WindowsAudioCaptureAdapter"]
