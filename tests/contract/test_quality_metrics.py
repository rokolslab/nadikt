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

from benchmarks.asr.quality_metrics import aggregate_corpus, cer, coding_term_accuracy, wer


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
