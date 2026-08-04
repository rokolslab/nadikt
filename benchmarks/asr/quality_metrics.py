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

    def to_json(self) -> dict[str, object]:
        return {
            "metric_name": self.metric_name,
            "value": round(self.value, 6),
            "numerator": self.numerator,
            "denominator": self.denominator,
            "status": self.status,
            "version": self.version,
        }


@dataclass(frozen=True)
class MetricDiagnostic:
    metric_name: str
    status: str
    numerator: int
    denominator: int
    reason_code: str
    count: int
    view: str = "raw"

    def to_json(self) -> dict[str, object]:
        return {
            "metric_name": self.metric_name,
            "view": self.view,
            "status": self.status,
            "numerator": self.numerator,
            "denominator": self.denominator,
            "reason_code": self.reason_code,
            "count": self.count,
        }

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
    normalized = unicodedata.normalize("NFKC", text).casefold().replace("/", " ")
    tokens: list[str] = []
    for match in TOKEN_RE.finditer(normalized):
        token = match.group(0)
        if len(token) > 1:
            token = token.rstrip(".")
        if token:
            tokens.append(token)
    return tokens


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
    return english_term_accuracy_from_records(records, hypothesis)


def english_term_accuracy_from_records(term_records: list[Mapping[str, object]], hypothesis: str) -> QualityMetricResult:
    records = [_with_latin_requirement(record, require_latin=False) for record in term_records]
    return coding_term_accuracy(records, hypothesis, metric_name="english_term_accuracy")


def latin_preservation_rate(expected_terms: list[str], hypothesis: str) -> QualityMetricResult:
    latin_terms = [term for term in expected_terms if any("A" <= char <= "z" for char in term)]
    if not latin_terms:
        return QualityMetricResult(metric_name="latin_preservation_rate", value=0.0, status="not_applicable")
    records = [
        {"canonical": term, "accepted_variants": [term], "expected_occurrences": 1, "require_latin": True}
        for term in latin_terms
    ]
    return latin_preservation_rate_from_records(records, hypothesis)


def latin_preservation_rate_from_records(term_records: list[Mapping[str, object]], hypothesis: str) -> QualityMetricResult:
    records = [_with_latin_requirement(record, require_latin=True) for record in term_records if bool(record.get("require_latin", False))]
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
        require_latin = bool(record.get("require_latin", False))
        variants = record.get("accepted_variants", [])
        if not isinstance(variants, list):
            variants = []
        matched += min(expected, _count_record_matches(normalized_hypothesis, variants, require_latin=require_latin))
    return QualityMetricResult(metric_name=metric_name, value=matched / denominator, numerator=matched, denominator=denominator)


def aggregate_corpus(metric_name: str, results: list[QualityMetricResult]) -> QualityMetricResult:
    applicable = [result for result in results if result.status == "ok"]
    denominator = sum(result.denominator for result in applicable)
    numerator = sum(result.numerator for result in applicable)
    if denominator == 0:
        return QualityMetricResult(metric_name=metric_name, value=0.0, status="not_applicable")
    return QualityMetricResult(metric_name=metric_name, value=numerator / denominator, numerator=numerator, denominator=denominator)


def metric_diagnostics(result: QualityMetricResult, *, view: str = "raw") -> tuple[MetricDiagnostic, ...]:
    if result.status == "not_applicable" or result.denominator == 0:
        return (_diagnostic(result, "not_applicable", max(1, result.denominator), view=view),)
    if result.numerator >= result.denominator:
        return (_diagnostic(result, "exact_latin_match", result.denominator, view=view),)
    if result.metric_name == "latin_preservation_rate" and result.numerator == 0:
        return (_diagnostic(result, "latin_missing", result.denominator, view=view),)
    if result.numerator == 0:
        return (_diagnostic(result, "variant_missing", result.denominator, view=view),)
    return (
        _diagnostic(result, "accepted_variant_match", result.numerator, view=view),
        _diagnostic(result, "occurrence_shortfall", result.denominator - result.numerator, view=view),
    )


def _rate(numerator: int, denominator: int, *, empty_value: float = 0.0) -> float:
    if denominator == 0:
        return empty_value
    return numerator / denominator


def _diagnostic(result: QualityMetricResult, reason_code: str, count: int, *, view: str) -> MetricDiagnostic:
    return MetricDiagnostic(
        metric_name=result.metric_name,
        view=view,
        status=result.status,
        numerator=result.numerator,
        denominator=result.denominator,
        reason_code=reason_code,
        count=max(0, count),
    )


def _status(denominator: int) -> str:
    return "ok" if denominator else "not_applicable"


def _expected_occurrences(record: Mapping[str, object]) -> int:
    value = record.get("expected_occurrences", 0)
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        return 0
    return value


def _with_latin_requirement(record: Mapping[str, object], *, require_latin: bool) -> dict[str, object]:
    updated = dict(record)
    updated["require_latin"] = require_latin
    return updated


def _normalized_phrase(text: str) -> str:
    return " ".join(normalize_tokens(text))


def _count_variant(normalized_hypothesis: str, variant: str) -> int:
    return len(_variant_spans(normalized_hypothesis, variant))


def _count_record_matches(normalized_hypothesis: str, variants: list[object], *, require_latin: bool) -> int:
    spans: list[tuple[int, int]] = []
    for variant in variants:
        if isinstance(variant, str) and (not require_latin or _has_latin(variant)):
            spans.extend(_variant_spans(normalized_hypothesis, variant))
    selected: list[tuple[int, int]] = []
    for span in sorted(set(spans), key=lambda item: (item[0], -(item[1] - item[0]))):
        if not any(_spans_overlap(span, existing) for existing in selected):
            selected.append(span)
    return len(selected)


def _variant_spans(normalized_hypothesis: str, variant: str) -> list[tuple[int, int]]:
    normalized_variant = _normalized_phrase(variant)
    if not normalized_variant:
        return []
    pattern = rf"(?<![0-9a-zа-яё_./+\-]){re.escape(normalized_variant)}(?![0-9a-zа-яё_./+\-])"
    return [(match.start(), match.end()) for match in re.finditer(pattern, normalized_hypothesis)]


def _spans_overlap(left: tuple[int, int], right: tuple[int, int]) -> bool:
    return left[0] < right[1] and right[0] < left[1]


def _has_latin(text: str) -> bool:
    return any(("a" <= char <= "z") or ("A" <= char <= "Z") for char in text)


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
