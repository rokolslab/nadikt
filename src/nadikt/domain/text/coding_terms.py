"""Privacy-safe coding-term rule objects for text normalization.

The domain owns generic rule mechanics only. Benchmark-specific public mappings
stay in benchmark modules and are adapted into these value objects when needed.
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass, field
from enum import Enum


class CodingTermValidationError(str, Enum):
    """Bounded validation reason codes without rule payload."""

    DUPLICATE_RULE_ID = "duplicate_rule_id"
    DUPLICATE_VARIANT_CONFLICT = "duplicate_variant_conflict"
    EMPTY_CANONICAL = "empty_canonical"
    EMPTY_RULE_ID = "empty_rule_id"
    EMPTY_VARIANT = "empty_variant"
    LATIN_REQUIRED_CANONICAL_NOT_LATIN = "latin_required_canonical_not_latin"
    REPLACEMENT_CYCLE = "replacement_cycle"


@dataclass(frozen=True, repr=False)
class CodingTermRule:
    """One generic replacement rule without payload-bearing repr output."""

    rule_id: str
    canonical: str = field(repr=False)
    spoken_variants: tuple[str, ...] = field(repr=False)
    require_latin: bool = True

    def __post_init__(self) -> None:
        object.__setattr__(self, "rule_id", self.rule_id.strip())
        object.__setattr__(self, "canonical", self.canonical.strip())
        object.__setattr__(self, "spoken_variants", tuple(variant.strip() for variant in self.spoken_variants))

    def __repr__(self) -> str:
        return (
            "CodingTermRule("
            f"rule_id={self.rule_id!r}, "
            f"variant_count={len(self.spoken_variants)}, "
            f"require_latin={self.require_latin!r})"
        )

    def safe_log_context(self) -> dict[str, object]:
        return {
            "rule_id": self.rule_id,
            "variant_count": len(self.spoken_variants),
            "require_latin": self.require_latin,
        }


@dataclass(frozen=True, repr=False)
class PolicyValidationResult:
    """Validation summary with reason counts only."""

    policy_id: str
    rule_count: int
    errors: tuple[CodingTermValidationError, ...] = field(default_factory=tuple)

    @property
    def is_valid(self) -> bool:
        return not self.errors

    def __repr__(self) -> str:
        return (
            "PolicyValidationResult("
            f"policy_id={self.policy_id!r}, "
            f"rule_count={self.rule_count}, "
            f"error_count={len(self.errors)})"
        )

    def safe_log_context(self) -> dict[str, object]:
        return {
            "policy_id": self.policy_id,
            "rule_count": self.rule_count,
            "error_count": len(self.errors),
            "reason_codes": tuple(error.value for error in self.errors),
        }


@dataclass(frozen=True, repr=False)
class CodingTermPolicy:
    """A deterministic, engine-independent set of coding-term rules."""

    policy_id: str
    rules: tuple[CodingTermRule, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "policy_id", self.policy_id.strip())
        object.__setattr__(self, "rules", tuple(self.rules))

    def __repr__(self) -> str:
        return f"CodingTermPolicy(policy_id={self.policy_id!r}, rule_count={len(self.rules)})"

    def validate(self) -> PolicyValidationResult:
        return validate_policy(self.policy_id, self.rules)

    def safe_log_context(self) -> dict[str, object]:
        result = self.validate()
        return result.safe_log_context()


def validate_policy(policy_id: str, rules: tuple[CodingTermRule, ...]) -> PolicyValidationResult:
    errors: list[CodingTermValidationError] = []
    seen_rule_ids: set[str] = set()
    variant_to_canonical: dict[str, str] = {}
    canonical_keys = {_key(rule.canonical) for rule in rules if rule.canonical}

    for rule in rules:
        if not rule.rule_id:
            errors.append(CodingTermValidationError.EMPTY_RULE_ID)
        elif rule.rule_id in seen_rule_ids:
            errors.append(CodingTermValidationError.DUPLICATE_RULE_ID)
        seen_rule_ids.add(rule.rule_id)

        if not rule.canonical:
            errors.append(CodingTermValidationError.EMPTY_CANONICAL)
        if rule.require_latin and not _has_latin(rule.canonical):
            errors.append(CodingTermValidationError.LATIN_REQUIRED_CANONICAL_NOT_LATIN)

        for variant in rule.spoken_variants:
            if not variant:
                errors.append(CodingTermValidationError.EMPTY_VARIANT)
                continue
            variant_key = _key(variant)
            canonical_key = _key(rule.canonical)
            existing = variant_to_canonical.get(variant_key)
            if existing is not None and existing != canonical_key:
                errors.append(CodingTermValidationError.DUPLICATE_VARIANT_CONFLICT)
            variant_to_canonical[variant_key] = canonical_key
            if variant_key in canonical_keys and variant_key != canonical_key:
                errors.append(CodingTermValidationError.REPLACEMENT_CYCLE)

    return PolicyValidationResult(policy_id=policy_id, rule_count=len(rules), errors=tuple(errors))


def normalized_key(value: str) -> str:
    """Return the comparison key used for conflict checks and matching."""

    return _key(value)


def _key(value: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", value).casefold().split())


def _has_latin(value: str) -> bool:
    return any(("A" <= char <= "Z") or ("a" <= char <= "z") for char in value)
