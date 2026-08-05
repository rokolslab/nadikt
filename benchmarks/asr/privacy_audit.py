"""Privacy audit helpers for benchmark artifacts."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from .logging_config import get_logger
LOGGER = get_logger(__name__)

FORBIDDEN_MARKERS = (
    "raw_audio",
    "audio_bytes",
    "transcript_text",
    "hypothesis_text",
    "reference_text",
    "clipboard_payload",
    "backend_stderr",
    "backend_stdout",
    "dictionary_canonical",
    "exception_string",
    "normalized_text",
    "spoken_variant",
    "user_dictionary_entry",
    "private_path",
    "credential",
    "traceback",
    "NADIKT_CONTROLLED_CANARY",
)
PRIVATE_PATH_PATTERN = re.compile(r"(?:/[A-Za-z0-9_.-]+){2,}|[A-Za-z]:\\\\[^\s\"']+")
SECRET_PATTERN = re.compile(r"(?i)(?:token|password|secret|credential|api[_-]?key)\s*[:=]")


@dataclass(frozen=True)
class PrivacyAuditResult:
    checked_artifacts: int
    canary_present: bool
    forbidden_payload_count: int
    private_path_count: int = 0
    credential_marker_count: int = 0
    exception_marker_count: int = 0

    def safe_log_context(self) -> dict[str, object]:
        return {
            "checked_artifacts": self.checked_artifacts,
            "canary_present": self.canary_present,
            "forbidden_payload_count": self.forbidden_payload_count,
            "private_path_count": self.private_path_count,
            "credential_marker_count": self.credential_marker_count,
            "exception_marker_count": self.exception_marker_count,
        }

    @property
    def has_violation(self) -> bool:
        return any(
            (
                self.canary_present,
                self.forbidden_payload_count > 0,
                self.private_path_count > 0,
                self.credential_marker_count > 0,
                self.exception_marker_count > 0,
            )
        )


def audit_text_artifact(text: str, *, canary: str | None = None) -> PrivacyAuditResult:
    """Audit one text artifact without returning the canary value."""

    canary_present = bool(canary and canary in text)
    forbidden_payload_count = sum(text.count(marker) for marker in FORBIDDEN_MARKERS)
    private_path_count = len(PRIVATE_PATH_PATTERN.findall(text))
    credential_marker_count = len(SECRET_PATTERN.findall(text))
    exception_marker_count = text.count("Traceback (") + text.count("Exception:")
    result = PrivacyAuditResult(
        checked_artifacts=1,
        canary_present=canary_present,
        forbidden_payload_count=forbidden_payload_count,
        private_path_count=private_path_count,
        credential_marker_count=credential_marker_count,
        exception_marker_count=exception_marker_count,
    )
    LOGGER.info("privacy_audit_text_done", extra=result.safe_log_context())
    return result


def audit_files(paths: list[Path], *, canary: str | None = None) -> PrivacyAuditResult:
    """Audit UTF-8 text files such as stdout captures, logs and JSON reports."""

    canary_present = False
    forbidden_payload_count = 0
    private_path_count = 0
    credential_marker_count = 0
    exception_marker_count = 0
    checked = 0
    for path in paths:
        text = path.read_text(encoding="utf-8")
        checked += 1
        if canary and canary in text:
            canary_present = True
        forbidden_payload_count += sum(text.count(marker) for marker in FORBIDDEN_MARKERS)
        private_path_count += len(PRIVATE_PATH_PATTERN.findall(text))
        credential_marker_count += len(SECRET_PATTERN.findall(text))
        exception_marker_count += text.count("Traceback (") + text.count("Exception:")

    result = PrivacyAuditResult(
        checked_artifacts=checked,
        canary_present=canary_present,
        forbidden_payload_count=forbidden_payload_count,
        private_path_count=private_path_count,
        credential_marker_count=credential_marker_count,
        exception_marker_count=exception_marker_count,
    )
    LOGGER.info("privacy_audit_files_done", extra=result.safe_log_context())
    return result
