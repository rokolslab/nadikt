"""Controlled-storage path and payload validation for ASR datasets."""

from __future__ import annotations

import hashlib
import stat
import wave
from dataclasses import dataclass
from pathlib import Path

from .logging_config import get_logger
from .package_integrity import is_unsafe_local_path, is_valid_sha256

LOGGER = get_logger(__name__)

MAX_REFERENCE_BYTES = 64 * 1024
SUPPORTED_SAMPLE_RATES = {16000, 48000}


@dataclass(frozen=True, repr=False)
class ControlledSamplePaths:
    sample_id: str
    audio_path: Path
    reference_path: Path

    def __repr__(self) -> str:
        return f"ControlledSamplePaths(sample_id={self.sample_id!r})"


def resolve_controlled_file(root: Path, relative_path: str) -> tuple[Path | None, str | None]:
    """Resolve a private relative path inside controlled root without leaking it."""

    if is_unsafe_local_path(relative_path):
        return None, "unsafe_path"
    root_resolved = root.resolve(strict=False)
    raw_candidate = root_resolved / relative_path
    if raw_candidate.is_symlink():
        return None, "symlink_path"
    candidate = raw_candidate.resolve(strict=False)
    if not _is_relative_to(candidate, root_resolved):
        return None, "path_escape"
    if candidate.is_symlink():
        return None, "symlink_path"
    try:
        mode = candidate.stat().st_mode
    except FileNotFoundError:
        return None, "missing_file"
    if not stat.S_ISREG(mode):
        return None, "not_regular_file"
    return candidate, None


def validate_file_digest(path: Path, expected_sha256: str) -> str | None:
    if not is_valid_sha256(expected_sha256):
        return "invalid_digest"
    if _sha256_file(path) != expected_sha256:
        return "digest_mismatch"
    return None


def validate_wav_file(path: Path, *, max_duration_seconds: float = 30.0) -> str | None:
    try:
        with wave.open(str(path), "rb") as audio:
            channels = audio.getnchannels()
            sample_width = audio.getsampwidth()
            sample_rate = audio.getframerate()
            frame_count = audio.getnframes()
    except (wave.Error, EOFError):
        return "invalid_wav"
    if channels != 1:
        return "invalid_channels"
    if sample_width != 2:
        return "invalid_sample_width"
    if sample_rate not in SUPPORTED_SAMPLE_RATES:
        return "invalid_sample_rate"
    duration = frame_count / float(sample_rate)
    if duration <= 0 or duration > max_duration_seconds:
        return "invalid_duration"
    return None


def validate_reference_file(path: Path) -> str | None:
    data = path.read_bytes()
    if len(data) > MAX_REFERENCE_BYTES:
        return "reference_too_large"
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return "reference_not_utf8"
    if "\x00" in text:
        return "reference_contains_nul"
    if not text.strip():
        return "reference_empty"
    return None


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _is_relative_to(child: Path, parent: Path) -> bool:
    try:
        child.relative_to(parent)
    except ValueError:
        return False
    return True
