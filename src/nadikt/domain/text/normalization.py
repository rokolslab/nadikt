"""Minimal deterministic text normalization for the dictation slice.

No benchmark-specific coding-term mappings, user dictionary entries or voice
commands live here. This module only shapes safe whitespace/newline boundaries
for one insertion attempt and does not log.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

LINE_SPACING_RE = re.compile(r"[ \t]*\n[ \t]*")
HORIZONTAL_SPACE_RE = re.compile(r"[ \t\f\v]+")
EXCESSIVE_NEWLINES_RE = re.compile(r"\n{3,}")


@dataclass(frozen=True, repr=False)
class TextNormalizationResult:
    """Normalization result with text redacted from repr."""

    text: str
    rule_ids: tuple[str, ...]
    input_chars: int

    @property
    def output_chars(self) -> int:
        return len(self.text)

    def __repr__(self) -> str:
        return (
            "TextNormalizationResult("
            f"rule_ids={list(self.rule_ids)!r}, input_chars={self.input_chars!r}, "
            f"output_chars={self.output_chars!r})"
        )


class DeterministicTextNormalizer:
    """Applies the minimal slice-safe whitespace rules."""

    rule_ids = (
        "strip-boundary-whitespace.v1",
        "normalize-horizontal-space.v1",
        "normalize-newline-boundaries.v1",
        "collapse-excessive-newlines.v1",
    )

    def normalize(self, text: str) -> str:
        return normalize_for_single_insertion(text).text

    def normalize_with_metadata(self, text: str) -> TextNormalizationResult:
        return normalize_for_single_insertion(text)


def normalize_for_single_insertion(text: str) -> TextNormalizationResult:
    """Shape recognized text for one safe insertion attempt."""

    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    normalized = LINE_SPACING_RE.sub("\n", normalized)
    normalized = HORIZONTAL_SPACE_RE.sub(" ", normalized)
    normalized = EXCESSIVE_NEWLINES_RE.sub("\n\n", normalized)
    normalized = normalized.strip()
    return TextNormalizationResult(
        text=normalized,
        rule_ids=DeterministicTextNormalizer.rule_ids,
        input_chars=len(text),
    )


__all__ = [
    "DeterministicTextNormalizer",
    "TextNormalizationResult",
    "normalize_for_single_insertion",
]
