from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from nadikt.domain.text import CodingTermDictionary, CodingTermRule
from nadikt.domain.text.coding_terms import CodingTermValidationError


class TextDictionaryTest(unittest.TestCase):
    def test_valid_dictionary_exposes_safe_diagnostics_only(self) -> None:
        dictionary = CodingTermDictionary(
            "test-policy",
            (CodingTermRule("pytest", "pytest", ("пайтест",), True),),
        )

        self.assertTrue(dictionary.is_valid)
        self.assertEqual(1, dictionary.safe_log_context()["rule_count"])
        self.assertNotIn("пайтест", repr(dictionary))

    def test_detects_duplicate_rule_id_and_variant_conflict_without_payload(self) -> None:
        dictionary = CodingTermDictionary(
            "test-policy",
            (
                CodingTermRule("duplicate", "pytest", ("вариант",), True),
                CodingTermRule("duplicate", "FastAPI", ("вариант",), True),
            ),
        )

        self.assertFalse(dictionary.is_valid)
        self.assertIn(CodingTermValidationError.DUPLICATE_RULE_ID, dictionary.validation.errors)
        self.assertIn(CodingTermValidationError.DUPLICATE_VARIANT_CONFLICT, dictionary.validation.errors)
        self.assertNotIn("вариант", repr(dictionary.validation))

    def test_detects_empty_values_latin_requirement_and_cycles(self) -> None:
        dictionary = CodingTermDictionary(
            "test-policy",
            (
                CodingTermRule("", "термин", ("",), True),
                CodingTermRule("cycle-a", "alpha", ("beta",), True),
                CodingTermRule("cycle-b", "beta", ("alpha",), True),
            ),
        )

        errors = set(dictionary.validation.errors)

        self.assertIn(CodingTermValidationError.EMPTY_RULE_ID, errors)
        self.assertIn(CodingTermValidationError.EMPTY_VARIANT, errors)
        self.assertIn(CodingTermValidationError.LATIN_REQUIRED_CANONICAL_NOT_LATIN, errors)
        self.assertIn(CodingTermValidationError.REPLACEMENT_CYCLE, errors)
        with self.assertRaisesRegex(ValueError, "coding_term_dictionary_invalid"):
            dictionary.require_valid()


if __name__ == "__main__":
    unittest.main()
