"""Benchmark-only coding term normalization policies.

These helpers are for experimental ASR scoring views only. They are not a
production user dictionary and must not log input or output text.
"""

from __future__ import annotations

from nadikt.domain.text import CodingTermPolicy, CodingTermRule, normalize_text

DEFAULT_NORMALIZATION_POLICY_ID = "coding-term-normalization-ru-pronunciation-v1"

_PUBLIC_REPLACEMENTS = {
    "пайтест": "pytest",
    "докер компоуз": "docker compose",
    "докер-компоуз": "docker compose",
    "реакт компонент": "React component",
    "фаст апи роут": "FastAPI route",
    "фастапи роут": "FastAPI route",
    "аксес токен": "access token",
    "эксес токен": "access token",
    "пул реквест": "pull request",
}
_PUBLIC_POLICY = CodingTermPolicy(
    DEFAULT_NORMALIZATION_POLICY_ID,
    tuple(
        CodingTermRule(rule_id=f"public-{index}", canonical=replacement, spoken_variants=(source,), require_latin=True)
        for index, (source, replacement) in enumerate(_PUBLIC_REPLACEMENTS.items(), start=1)
    ),
)


def normalize_coding_terms_for_scoring(text: str, *, policy_id: str = DEFAULT_NORMALIZATION_POLICY_ID) -> str:
    if policy_id != DEFAULT_NORMALIZATION_POLICY_ID:
        raise ValueError("unknown_coding_term_normalization_policy")
    return normalize_text(text, _PUBLIC_POLICY).text
