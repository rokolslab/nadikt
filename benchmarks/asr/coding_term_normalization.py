"""Benchmark-only coding term normalization policies.

These helpers are for experimental ASR scoring views only. They are not a
production user dictionary and must not log input or output text.
"""

from __future__ import annotations

import re

DEFAULT_NORMALIZATION_POLICY_ID = "coding-term-normalization-ru-pronunciation-v1"

_BOUNDARY = r"(?<![0-9A-Za-zА-Яа-яЁё_./+\-]){}(?![0-9A-Za-zА-Яа-яЁё_./+\-])"
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


def normalize_coding_terms_for_scoring(text: str, *, policy_id: str = DEFAULT_NORMALIZATION_POLICY_ID) -> str:
    if policy_id != DEFAULT_NORMALIZATION_POLICY_ID:
        raise ValueError("unknown_coding_term_normalization_policy")
    normalized = text
    for source, replacement in _PUBLIC_REPLACEMENTS.items():
        normalized = re.sub(_BOUNDARY.format(re.escape(source)), replacement, normalized, flags=re.IGNORECASE)
    return normalized
