"""Engine-independent in-memory dictionary facade for coding-term rules."""

from __future__ import annotations

from dataclasses import dataclass, field

from .coding_terms import CodingTermPolicy, CodingTermRule, PolicyValidationResult, validate_policy


@dataclass(frozen=True, repr=False)
class CodingTermDictionary:
    """Validated rule container with payload-safe diagnostics."""

    policy_id: str
    rules: tuple[CodingTermRule, ...] = field(default_factory=tuple, repr=False)
    validation: PolicyValidationResult = field(init=False, repr=False)

    def __post_init__(self) -> None:
        rules = tuple(self.rules)
        object.__setattr__(self, "rules", rules)
        object.__setattr__(self, "validation", validate_policy(self.policy_id, rules))

    @classmethod
    def from_policy(cls, policy: CodingTermPolicy) -> "CodingTermDictionary":
        return cls(policy_id=policy.policy_id, rules=policy.rules)

    @property
    def is_valid(self) -> bool:
        return self.validation.is_valid

    def require_valid(self) -> None:
        if not self.is_valid:
            raise ValueError("coding_term_dictionary_invalid")

    def __repr__(self) -> str:
        return (
            "CodingTermDictionary("
            f"policy_id={self.policy_id!r}, "
            f"rule_count={len(self.rules)}, "
            f"error_count={len(self.validation.errors)})"
        )

    def safe_log_context(self) -> dict[str, object]:
        return self.validation.safe_log_context()
