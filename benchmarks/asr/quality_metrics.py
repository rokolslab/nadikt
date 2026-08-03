"""Quality metrics for local ASR benchmark reports."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Mapping

TOKEN_RE = re.compile(r"[0-9A-Za-zА-Яа-яЁё_./+\-]+", re.UNICODE)
METRIC_VERSION = "quality-metrics-v2"


@dataclass(frozen=True)
class QualityMetricResult:
    metric_name: str
    value: float
    numerator: int = 0
    denominator: int = 0
    status: str = "ok"
    version: str = METRIC_VERSION

    def safe_log_context(self, sample_id: str) -> dict[str, object]:
        return {
            "sample_id": sample_id,
            "metric_name": self.metric_name,
            "numerator": self.numerator,
            "denominator": self.denominator,
            "status": self.status,
            "value": self.value,
            "version": self.version,
        }


def normalize_tokens(text: str) -> list[str]:
    normalized = unicodedata.normalize("NFKC", text).casefold()
    return [match.group(0) for match in TOKEN_RE.finditer(normalized)]


def wer(reference: str, hypothesis: str) -> QualityMetricResult:
    reference_tokens = normalize_tokens(reference)
    hypothesis_tokens = normalize_tokens(hypothesis)
    distance = _levenshtein(reference_tokens, hypothesis_tokens)
    denominator = len(reference_tokens)
    value = _rate(distance, denominator, empty_value=0.0 if not hypothesis_tokens else 1.0)
    return QualityMetricResult(metric_name="wer", value=value, numerator=distance, denominator=denominator, status=_status(denominator))


def cer(reference: str, hypothesis: str) -> QualityMetricResult:
    reference_chars = "".join(normalize_tokens(reference))
    hypothesis_chars = "".join(normalize_tokens(hypothesis))
    distance = _levenshtein(list(reference_chars), list(hypothesis_chars))
    denominator = len(reference_chars)
    value = _rate(distance, denominator, empty_value=0.0 if not hypothesis_chars else 1.0)
    return QualityMetricResult(metric_name="cer", value=value, numerator=distance, denominator=denominator, status=_status(denominator))


def english_term_accuracy(expected_terms: list[str], hypothesis: str) -> QualityMetricResult:
    if not expected_terms:
        return QualityMetricResult(metric_name="english_term_accuracy", value=0.0, status="not_applicable")
    records = [
        {"canonical": term, "accepted_variants": [term], "expected_occurrences": 1, "require_latin": False}
        for term in expected_terms
    ]
    return coding_term_accuracy(records, hypothesis, metric_name="english_term_accuracy")


def latin_preservation_rate(expected_terms: list[str], hypothesis: str) -> QualityMetricResult:
    latin_terms = [term for term in expected_terms if any("A" <= char <= "z" for char in term)]
    if not latin_terms:
        return QualityMetricResult(metric_name="latin_preservation_rate", value=0.0, status="not_applicable")
    records = [
        {"canonical": term, "accepted_variants": [term], "expected_occurrences": 1, "require_latin": True}
        for term in latin_terms
    ]
    return coding_term_accuracy(records, hypothesis, metric_name="latin_preservation_rate")


def coding_term_accuracy(term_records: list[Mapping[str, object]], hypothesis: str, *, metric_name: str = "coding_term_accuracy") -> QualityMetricResult:
    """Compute occurrence-based coding-term accuracy without substring false positives."""

    denominator = sum(_expected_occurrences(record) for record in term_records)
    if denominator == 0:
        return QualityMetricResult(metric_name=metric_name, value=0.0, status="not_applicable")
    normalized_hypothesis = _normalized_phrase(hypothesis)
    matched = 0
    for record in term_records:
        expected = _expected_occurrences(record)
        variants = record.get("accepted_variants", [])
        if not isinstance(variants, list):
            variants = []
        matched += min(expected, sum(_count_variant(normalized_hypothesis, str(variant)) for variant in variants if isinstance(variant, str)))
    return QualityMetricResult(metric_name=metric_name, value=matched / denominator, numerator=matched, denominator=denominator)


def aggregate_corpus(metric_name: str, results: list[QualityMetricResult]) -> QualityMetricResult:
    applicable = [result for result in results if result.status == "ok"]
    denominator = sum(result.denominator for result in applicable)
    numerator = sum(result.numerator for result in applicable)
    if denominator == 0:
        return QualityMetricResult(metric_name=metric_name, value=0.0, status="not_applicable")
    return QualityMetricResult(metric_name=metric_name, value=numerator / denominator, numerator=numerator, denominator=denominator)


def _rate(numerator: int, denominator: int, *, empty_value: float = 0.0) -> float:
    if denominator == 0:
        return empty_value
    return numerator / denominator


def _status(denominator: int) -> str:
    return "ok" if denominator else "not_applicable"


def _expected_occurrences(record: Mapping[str, object]) -> int:
    value = record.get("expected_occurrences", 0)
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        return 0
    return value


def _normalized_phrase(text: str) -> str:
    return " ".join(normalize_tokens(text))


def _count_variant(normalized_hypothesis: str, variant: str) -> int:
    normalized_variant = _normalized_phrase(variant)
    if not normalized_variant:
        return 0
    pattern = rf"(?<![0-9a-zа-яё_./+\-]){re.escape(normalized_variant)}(?![0-9a-zа-яё_./+\-])"
    return len(re.findall(pattern, normalized_hypothesis))


def _levenshtein(left: list[str], right: list[str]) -> int:
    previous = list(range(len(right) + 1))
    for left_index, left_value in enumerate(left, start=1):
        current = [left_index]
        for right_index, right_value in enumerate(right, start=1):
            insert_cost = current[right_index - 1] + 1
            delete_cost = previous[right_index] + 1
            replace_cost = previous[right_index - 1] + (left_value != right_value)
            current.append(min(insert_cost, delete_cost, replace_cost))
        previous = current
    return previous[-1]
