from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from nadikt.domain.text import CodingTermPolicy, CodingTermRule, normalize_text


class TextNormalizationTest(unittest.TestCase):
    def test_replaces_public_style_variants_without_payload_repr(self) -> None:
        policy = CodingTermPolicy(
            "test-policy",
            (
                CodingTermRule("pytest", "pytest", ("пайтест",), True),
                CodingTermRule("pull-request", "pull request", ("пул реквест",), True),
            ),
        )

        result = normalize_text("запусти пайтест и создай пул реквест", policy)

        self.assertEqual("запусти pytest и создай pull request", result.text)
        self.assertEqual(2, result.replacement_count)
        self.assertNotIn("пайтест", repr(result))
        self.assertNotIn("pull request", repr(policy.rules[1]))

    def test_uses_longest_non_overlapping_match_and_is_idempotent(self) -> None:
        policy = CodingTermPolicy(
            "test-policy",
            (
                CodingTermRule("fastapi", "FastAPI", ("фаст апи",), True),
                CodingTermRule("fastapi-route", "FastAPI route", ("фаст апи роут",), True),
            ),
        )

        first = normalize_text("открой фаст апи роут", policy)
        second = normalize_text(first.text, policy)

        self.assertEqual("открой FastAPI route", first.text)
        self.assertEqual(first.text, second.text)
        self.assertEqual(0, second.replacement_count)

    def test_handles_punctuation_adjacency_and_symbol_terms(self) -> None:
        policy = CodingTermPolicy(
            "test-policy",
            (
                CodingTermRule("cpp", "C++", ("си плюс плюс",), True),
                CodingTermRule("dotnet", ".NET", ("дот нет",), True),
                CodingTermRule("node", "Node.js", ("нод джей эс",), True),
                CodingTermRule("ci-cd", "CI/CD", ("си ай си ди",), True),
            ),
        )

        result = normalize_text("си плюс плюс, дот нет/нод джей эс; си ай си ди", policy)

        self.assertEqual("C++, .NET/Node.js; CI/CD", result.text)

    def test_does_not_replace_inside_identifiers(self) -> None:
        policy = CodingTermPolicy("test-policy", (CodingTermRule("pytest", "pytest", ("пайтест",), True),))

        result = normalize_text("xпайтест пайтест_суффикс пайтест", policy)

        self.assertEqual("xпайтест пайтест_суффикс pytest", result.text)

    def test_matches_nfkc_compatible_fullwidth_latin_variant(self) -> None:
        policy = CodingTermPolicy("test-policy", (CodingTermRule("github", "GitHub", ("ＧｉｔＨｕｂ",), True),))

        result = normalize_text("открой GitHub", policy)

        self.assertEqual("открой GitHub", result.text)
        self.assertEqual(1, result.replacement_count)

    def test_matches_nfkc_composed_variant_against_decomposed_input(self) -> None:
        policy = CodingTermPolicy("test-policy", (CodingTermRule("accent", "e", ("é",), True),))

        result = normalize_text("e\u0301", policy)

        self.assertEqual("e", result.text)
        self.assertEqual(1, result.replacement_count)


if __name__ == "__main__":
    unittest.main()
