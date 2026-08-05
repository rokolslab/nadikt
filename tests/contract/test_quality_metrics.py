from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from benchmarks.asr.quality_metrics import (
    aggregate_corpus,
    cer,
    coding_term_accuracy,
    english_term_accuracy,
    english_term_accuracy_from_records,
    latin_preservation_rate,
    latin_preservation_rate_from_records,
    metric_diagnostics,
    normalized_coding_term_metrics,
    wer,
)


class QualityMetricsTest(unittest.TestCase):
    def test_wer_and_cer_expose_numerator_denominator(self) -> None:
        word = wer("проверить сервер", "проверить")
        char = cer("abc", "ab")

        self.assertEqual("ok", word.status)
        self.assertEqual(1, word.numerator)
        self.assertEqual(2, word.denominator)
        self.assertEqual(1, char.numerator)
        self.assertEqual(3, char.denominator)

    def test_coding_terms_match_occurrences_without_substring_false_positive(self) -> None:
        records = [
            {"canonical": "pytest", "accepted_variants": ["pytest"], "expected_occurrences": 2, "require_latin": True},
            {"canonical": "C++", "accepted_variants": ["C++"], "expected_occurrences": 1, "require_latin": True},
            {"canonical": ".NET", "accepted_variants": [".NET", "dotnet"], "expected_occurrences": 1, "require_latin": True},
        ]

        result = coding_term_accuracy(records, "pytest pytester pytest C++ .NET")

        self.assertEqual(4, result.denominator)
        self.assertEqual(4, result.numerator)
        self.assertEqual(1.0, result.value)

    def test_coding_terms_require_latin_variants_when_requested(self) -> None:
        records = [
            {"canonical": "API", "accepted_variants": ["API", "апи"], "expected_occurrences": 1, "require_latin": True},
        ]

        latin = coding_term_accuracy(records, "вызови API")
        cyrillic = coding_term_accuracy(records, "вызови апи")

        self.assertEqual(1, latin.numerator)
        self.assertEqual(0, cyrillic.numerator)

    def test_coding_terms_count_multiword_identifiers_and_latin_preservation(self) -> None:
        records = [
            {"canonical": "docker compose", "accepted_variants": ["docker compose", "docker-compose"], "expected_occurrences": 1, "require_latin": True},
            {"canonical": "access token", "accepted_variants": ["access token"], "expected_occurrences": 1, "require_latin": True},
        ]

        result = coding_term_accuracy(records, "запусти docker-compose и обнови access token")

        self.assertEqual(2, result.numerator)
        self.assertEqual(2, result.denominator)

    def test_coding_terms_cover_common_coding_phrases_with_punctuation_adjacency(self) -> None:
        records = [
            {"canonical": "FastAPI route", "accepted_variants": ["FastAPI route", "Fast API route"], "expected_occurrences": 1, "require_latin": True},
            {"canonical": "React component", "accepted_variants": ["React component"], "expected_occurrences": 1, "require_latin": True},
            {"canonical": "pull request", "accepted_variants": ["pull request"], "expected_occurrences": 1, "require_latin": True},
            {"canonical": "C++", "accepted_variants": ["C++"], "expected_occurrences": 1, "require_latin": True},
            {"canonical": ".NET", "accepted_variants": [".NET", "dotnet"], "expected_occurrences": 1, "require_latin": True},
        ]

        result = coding_term_accuracy(records, "Fast API route, React component; pull request. C++/.NET")

        self.assertEqual(5, result.numerator)
        self.assertEqual(5, result.denominator)

    def test_coding_terms_do_not_overcount_colliding_accepted_variants(self) -> None:
        records = [
            {"canonical": "FastAPI route", "accepted_variants": ["FastAPI route", "fastapi route"], "expected_occurrences": 2, "require_latin": True},
        ]

        result = coding_term_accuracy(records, "FastAPI route")

        self.assertEqual(1, result.numerator)
        self.assertEqual(2, result.denominator)

    def test_english_and_latin_metrics_keep_legacy_plain_terms(self) -> None:
        english = english_term_accuracy(["docker compose", "pull request"], "docker compose")
        latin = latin_preservation_rate(["docker compose", "апи"], "docker compose апи")

        self.assertEqual("english_term_accuracy", english.metric_name)
        self.assertEqual(1, english.numerator)
        self.assertEqual(2, english.denominator)
        self.assertEqual("latin_preservation_rate", latin.metric_name)
        self.assertEqual(1, latin.numerator)
        self.assertEqual(1, latin.denominator)

    def test_english_and_latin_metrics_use_rich_records_when_available(self) -> None:
        records = [
            {"canonical": "FastAPI route", "accepted_variants": ["FastAPI route", "Fast API route"], "expected_occurrences": 2, "require_latin": True},
            {"canonical": "локальный термин", "accepted_variants": ["локальный термин"], "expected_occurrences": 1, "require_latin": False},
        ]

        english = english_term_accuracy_from_records(records, "Fast API route локальный термин")
        latin = latin_preservation_rate_from_records(records, "Fast API route локальный термин")

        self.assertEqual(2, english.numerator)
        self.assertEqual(3, english.denominator)
        self.assertEqual(1, latin.numerator)
        self.assertEqual(2, latin.denominator)

    def test_latin_metric_rejects_cyrillic_false_positive_when_latin_required(self) -> None:
        records = [
            {"canonical": "React", "accepted_variants": ["React", "реакт"], "expected_occurrences": 1, "require_latin": True},
        ]

        result = coding_term_accuracy(records, "реакт")

        self.assertEqual(0, result.numerator)
        self.assertEqual(1, result.denominator)

    def test_metric_diagnostics_are_bounded_reason_counts(self) -> None:
        missing = latin_preservation_rate_from_records(
            [{"canonical": "React", "accepted_variants": ["React"], "expected_occurrences": 2, "require_latin": True}],
            "реакт",
        )

        diagnostics = metric_diagnostics(missing)

        self.assertEqual(1, len(diagnostics))
        self.assertEqual("latin_missing", diagnostics[0].reason_code)
        self.assertEqual(2, diagnostics[0].count)
        self.assertEqual("raw", diagnostics[0].view)

    def test_normalized_coding_term_metrics_are_separate_from_raw_metrics(self) -> None:
        records = [
            {"canonical": "pytest", "accepted_variants": ["pytest"], "expected_occurrences": 1, "require_latin": True},
            {"canonical": "pull request", "accepted_variants": ["pull request"], "expected_occurrences": 1, "require_latin": True},
        ]
        raw = coding_term_accuracy(records, "пайтест и пул реквест")

        normalized = {metric.metric_name: metric for metric in normalized_coding_term_metrics(records, "пайтест и пул реквест")}

        self.assertEqual(0, raw.numerator)
        self.assertEqual(2, normalized["coding_term_accuracy_normalized"].numerator)
        self.assertEqual(2, normalized["english_term_accuracy_normalized"].numerator)
        self.assertEqual(2, normalized["latin_preservation_rate_normalized"].numerator)
        self.assertIn("coding-term-normalization-ru-pronunciation-v1", normalized["coding_term_accuracy_normalized"].version)

    def test_normalized_metrics_keep_existing_policy_names(self) -> None:
        records = [
            {"canonical": "FastAPI route", "accepted_variants": ["FastAPI route"], "expected_occurrences": 1, "require_latin": True},
        ]

        normalized = normalized_coding_term_metrics(records, "фаст апи роут")

        self.assertEqual("coding_term_accuracy_normalized", normalized[2].metric_name)
        self.assertEqual("quality-metrics-v2:coding-term-normalization-ru-pronunciation-v1", normalized[2].version)

    def test_zero_denominator_is_not_applicable(self) -> None:
        result = coding_term_accuracy([], "любой текст")

        self.assertEqual("not_applicable", result.status)
        self.assertEqual(0, result.denominator)

    def test_corpus_aggregation_sums_counts_not_percentages(self) -> None:
        first = coding_term_accuracy(
            [{"canonical": "pytest", "accepted_variants": ["pytest"], "expected_occurrences": 1, "require_latin": True}],
            "pytest",
        )
        second = coding_term_accuracy(
            [{"canonical": "React component", "accepted_variants": ["React component"], "expected_occurrences": 3, "require_latin": True}],
            "React component",
        )

        result = aggregate_corpus("coding_term_accuracy", [first, second])

        self.assertEqual(2, result.numerator)
        self.assertEqual(4, result.denominator)
        self.assertEqual(0.5, result.value)


if __name__ == "__main__":
    unittest.main()
