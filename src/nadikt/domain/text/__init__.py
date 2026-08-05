"""Pure text-domain primitives for Nadikt normalization and dictionaries."""

from .coding_terms import (
    CodingTermPolicy,
    CodingTermRule,
    CodingTermValidationError,
    PolicyValidationResult,
)
from .dictionary import CodingTermDictionary
from .normalization import NormalizationResult, normalize_text

__all__ = [
    "CodingTermDictionary",
    "CodingTermPolicy",
    "CodingTermRule",
    "CodingTermValidationError",
    "NormalizationResult",
    "PolicyValidationResult",
    "normalize_text",
]
