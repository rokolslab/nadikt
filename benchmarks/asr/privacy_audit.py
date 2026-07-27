"""Privacy audit helpers for benchmark artifacts."""

from __future__ import annotations

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
    "user_dictionary_entry",
)


@dataclass(frozen=True)
class PrivacyAuditResult:
    checked_artifacts: int
    canary_present: bool
    forbidden_payload_count: int

    def safe_log_context(self) -> dict[str, object]:
        return {
            "checked_artifacts": self.checked_artifacts,
            "canary_present": self.canary_present,
            "forbidden_payload_count": self.forbidden_payload_count,
        }


def audit_text_artifact(text: str, *, canary: str | None = None) -> PrivacyAuditResult:
    """Audit one text artifact without returning the canary value."""

    canary_present = bool(canary and canary in text)
    forbidden_payload_count = sum(text.count(marker) for marker in FORBIDDEN_MARKERS)
    result = PrivacyAuditResult(
        checked_artifacts=1,
        canary_present=canary_present,
        forbidden_payload_count=forbidden_payload_count,
    )
    LOGGER.info("privacy_audit_text_done", extra=result.safe_log_context())
    return result


def audit_files(paths: list[Path], *, canary: str | None = None) -> PrivacyAuditResult:
    """Audit UTF-8 text files such as stdout captures, logs and JSON reports."""

    canary_present = False
    forbidden_payload_count = 0
    checked = 0
    for path in paths:
        text = path.read_text(encoding="utf-8")
        checked += 1
        if canary and canary in text:
            canary_present = True
        forbidden_payload_count += sum(text.count(marker) for marker in FORBIDDEN_MARKERS)

    result = PrivacyAuditResult(
        checked_artifacts=checked,
        canary_present=canary_present,
        forbidden_payload_count=forbidden_payload_count,
    )
    LOGGER.info("privacy_audit_files_done", extra=result.safe_log_context())
    return result
