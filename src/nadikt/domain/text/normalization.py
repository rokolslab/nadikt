"""Deterministic text normalization using privacy-safe coding-term policies."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

from .coding_terms import CodingTermPolicy, CodingTermRule

_BOUNDARY = r"(?<![0-9A-Za-zА-Яа-яЁё_]){}(?![0-9A-Za-zА-Яа-яЁё_])"


@dataclass(frozen=True, repr=False)
class NormalizationResult:
    """Normalized text plus safe aggregate diagnostics."""

    text: str = field(repr=False)
    policy_id: str
    replacement_count: int
    matched_rule_count: int

    def __repr__(self) -> str:
        return (
            "NormalizationResult("
            f"policy_id={self.policy_id!r}, "
            f"replacement_count={self.replacement_count}, "
            f"matched_rule_count={self.matched_rule_count}, "
            f"text_chars={len(self.text)})"
        )

    def safe_log_context(self) -> dict[str, object]:
        return {
            "policy_id": self.policy_id,
            "replacement_count": self.replacement_count,
            "matched_rule_count": self.matched_rule_count,
            "text_chars": len(self.text),
        }


@dataclass(frozen=True)
class _Match:
    start: int
    end: int
    rule_index: int
    replacement: str


def normalize_text(text: str, policy: CodingTermPolicy) -> NormalizationResult:
    """Apply non-overlapping, longest-span replacements from a policy."""

    validation = policy.validate()
    if not validation.is_valid:
        raise ValueError("coding_term_policy_invalid")

    matches = _select_matches(text, policy.rules)
    if not matches:
        return NormalizationResult(text=text, policy_id=policy.policy_id, replacement_count=0, matched_rule_count=0)

    parts: list[str] = []
    cursor = 0
    matched_rules: set[int] = set()
    for match in matches:
        parts.append(text[cursor : match.start])
        parts.append(match.replacement)
        cursor = match.end
        matched_rules.add(match.rule_index)
    parts.append(text[cursor:])
    return NormalizationResult(
        text="".join(parts),
        policy_id=policy.policy_id,
        replacement_count=len(matches),
        matched_rule_count=len(matched_rules),
    )


def _select_matches(text: str, rules: tuple[CodingTermRule, ...]) -> tuple[_Match, ...]:
    comparable_text, start_map, end_map = _comparable_with_index_map(text)
    candidates: list[_Match] = []
    for rule_index, rule in enumerate(rules):
        for variant in sorted(rule.spoken_variants, key=len, reverse=True):
            comparable_variant = _comparable(variant)
            pattern = _BOUNDARY.format(re.escape(comparable_variant))
            for found in re.finditer(pattern, comparable_text):
                original_start = start_map[found.start()]
                original_end = end_map[found.end() - 1]
                candidates.append(_Match(original_start, original_end, rule_index, rule.canonical))

    selected: list[_Match] = []
    for candidate in sorted(candidates, key=lambda item: (-(item.end - item.start), item.start, item.rule_index)):
        if not any(_overlaps(candidate, existing) for existing in selected):
            selected.append(candidate)
    return tuple(sorted(selected, key=lambda item: item.start))


def _overlaps(left: _Match, right: _Match) -> bool:
    return left.start < right.end and right.start < left.end


def _comparable(value: str) -> str:
    return unicodedata.normalize("NFKC", value).casefold()


def _comparable_with_index_map(value: str) -> tuple[str, tuple[int, ...], tuple[int, ...]]:
    chars: list[str] = []
    start_map: list[int] = []
    end_map: list[int] = []
    index = 0
    while index < len(value):
        cluster_start = index
        index += 1
        while index < len(value) and unicodedata.combining(value[index]):
            index += 1
        cluster_end = index
        comparable = _comparable(value[cluster_start:cluster_end])
        chars.append(comparable)
        start_map.extend([cluster_start] * len(comparable))
        end_map.extend([cluster_end] * len(comparable))
    return "".join(chars), tuple(start_map), tuple(end_map)
