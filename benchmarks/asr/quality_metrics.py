"""Quality metrics for local ASR benchmark reports."""

from __future__ import annotations

import re
from dataclasses import dataclass

TOKEN_RE = re.compile(r"[0-9A-Za-zА-Яа-яЁё]+", re.UNICODE)


@dataclass(frozen=True)
class QualityMetricResult:
    metric_name: str
    value: float
    version: str = "quality-metrics-v1"

    def safe_log_context(self, sample_id: str) -> dict[str, object]:
        return {
            "sample_id": sample_id,
            "metric_name": self.metric_name,
            "value": self.value,
            "version": self.version,
        }


def normalize_tokens(text: str) -> list[str]:
    return [match.group(0).lower() for match in TOKEN_RE.finditer(text)]


def wer(reference: str, hypothesis: str) -> QualityMetricResult:
    reference_tokens = normalize_tokens(reference)
    hypothesis_tokens = normalize_tokens(hypothesis)
    value = _error_rate(reference_tokens, hypothesis_tokens)
    return QualityMetricResult(metric_name="wer", value=value)


def cer(reference: str, hypothesis: str) -> QualityMetricResult:
    reference_chars = "".join(normalize_tokens(reference))
    hypothesis_chars = "".join(normalize_tokens(hypothesis))
    value = _error_rate(list(reference_chars), list(hypothesis_chars))
    return QualityMetricResult(metric_name="cer", value=value)


def english_term_accuracy(expected_terms: list[str], hypothesis: str) -> QualityMetricResult:
    if not expected_terms:
        return QualityMetricResult(metric_name="english_term_accuracy", value=1.0)
    normalized_hypothesis = " ".join(normalize_tokens(hypothesis))
    matched = sum(1 for term in expected_terms if term.lower() in normalized_hypothesis)
    return QualityMetricResult(metric_name="english_term_accuracy", value=matched / len(expected_terms))


def latin_preservation_rate(expected_terms: list[str], hypothesis: str) -> QualityMetricResult:
    latin_terms = [term for term in expected_terms if any("A" <= char <= "z" for char in term)]
    if not latin_terms:
        return QualityMetricResult(metric_name="latin_preservation_rate", value=1.0)
    matched = sum(1 for term in latin_terms if re.search(rf"\b{re.escape(term)}\b", hypothesis, re.IGNORECASE))
    return QualityMetricResult(metric_name="latin_preservation_rate", value=matched / len(latin_terms))


def _error_rate(reference: list[str], hypothesis: list[str]) -> float:
    if not reference:
        return 0.0 if not hypothesis else 1.0
    distance = _levenshtein(reference, hypothesis)
    return distance / len(reference)


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
