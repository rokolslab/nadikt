from __future__ import annotations

import hashlib
import json
import struct
import sys
import tempfile
import unittest
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from benchmarks.asr.dataset_bindings import validate_dataset_bindings
from benchmarks.asr.manifests import load_json, load_run_profile, validate_dataset_manifest, validate_run_profile_preflight


class RuCodingTermsDatasetTest(unittest.TestCase):
    def test_ru_coding_terms_profile_contains_required_terms(self) -> None:
        manifest = load_json(ROOT / "benchmarks/asr/datasets/ru_coding_terms.v1.json")

        samples, errors = validate_dataset_manifest(manifest)

        self.assertEqual([], errors)
        terms = {term["canonical"] for sample in samples for term in sample.expected_coding_terms}
        for expected in ("pytest", "docker compose", "React component", "FastAPI route", "access token", "pull request"):
            self.assertIn(expected, terms)

    def test_coding_pilot_profile_has_warmup_ru_short_and_coding_samples(self) -> None:
        manifest = load_json(ROOT / "benchmarks/asr/datasets/coding_pilot.v1.json")

        samples, errors = validate_dataset_manifest(manifest)

        self.assertEqual([], errors)
        categories = {sample.category for sample in samples}
        self.assertIn("warmup", categories)
        self.assertIn("ru_short", categories)
        self.assertIn("ru_coding_terms", categories)

    def test_coding_pilot_run_profile_requires_exact_matrix_and_durations(self) -> None:
        profile, profile_errors = load_run_profile(ROOT / "benchmarks/asr/run_profiles/coding_pilot.v1.json")
        manifest = load_json(ROOT / "benchmarks/asr/datasets/coding_pilot.v1.json")
        samples, dataset_errors = validate_dataset_manifest(manifest)

        errors = validate_run_profile_preflight(
            profile=profile,
            dataset_data=manifest,
            samples=samples,
            candidate_ids=["gigaam-multilingual-220m", "faster-whisper-small-int8"],
            repeats=3,
        )

        self.assertIsNotNone(profile)
        self.assertEqual([], profile_errors)
        self.assertEqual([], dataset_errors)
        self.assertEqual([], errors)

    def test_coding_pilot_run_profile_rejects_incomplete_matrix_and_duration_drift(self) -> None:
        profile, profile_errors = load_run_profile(ROOT / "benchmarks/asr/run_profiles/coding_pilot.v1.json")
        manifest = load_json(ROOT / "benchmarks/asr/datasets/coding_pilot.v1.json")
        manifest["samples"][1]["duration_seconds"] = 30.0
        samples, dataset_errors = validate_dataset_manifest(manifest)

        errors = validate_run_profile_preflight(
            profile=profile,
            dataset_data=manifest,
            samples=samples,
            candidate_ids=["faster-whisper-small-int8"],
            repeats=2,
        )

        self.assertEqual([], profile_errors)
        self.assertEqual([], dataset_errors)
        self.assertIn("run_profile_candidate_matrix_mismatch", errors)
        self.assertIn("run_profile_repeats_too_low", errors)
        self.assertIn("run_profile_duration_drift", errors)

    def test_valid_private_bindings_resolve_without_leaking_paths(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            public_manifest = _write_public_manifest(root)
            bindings = _write_bindings(root, public_manifest)

            result = validate_dataset_bindings(public_manifest, bindings, root)

        self.assertEqual("bindings_valid", result.outcome)
        self.assertEqual(2, result.binding_count)
        self.assertNotIn(str(root), repr(result.safe_log_context()))
        self.assertNotIn(str(root), repr(result.resolved_samples))

    def test_bindings_reject_digest_drift_and_duplicate_ids(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            public_manifest = _write_public_manifest(root)
            bindings = _write_bindings(root, public_manifest)
            data = json.loads(bindings.read_text(encoding="utf-8"))
            data["public_manifest_sha256"] = "1" * 64
            data["samples"].append(dict(data["samples"][0]))
            bindings.write_text(json.dumps(data), encoding="utf-8")

            result = validate_dataset_bindings(public_manifest, bindings, root)

        self.assertEqual("invalid_bindings", result.outcome)
        self.assertIn("public_manifest_digest_mismatch", result.errors)
        self.assertTrue(any(error.startswith("duplicate_sample_ids") for error in result.errors))

    def test_bindings_reject_unsafe_symlink_and_bad_reference(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            public_manifest = _write_public_manifest(root)
            bindings = _write_bindings(root, public_manifest)
            data = json.loads(bindings.read_text(encoding="utf-8"))
            outside = root / "outside.wav"
            _write_wav(outside)
            link = root / "audio" / "escape.wav"
            link.symlink_to(outside)
            data["samples"][0]["audio_relative_path"] = "audio/escape.wav"
            data["samples"][1]["reference_relative_path"] = "../outside.txt"
            bindings.write_text(json.dumps(data), encoding="utf-8")

            result = validate_dataset_bindings(public_manifest, bindings, root)

        self.assertIn("ru_coding_terms_001:audio_symlink_path", result.errors)
        self.assertIn("ru_short_001:reference_unsafe_path", result.errors)


def _write_public_manifest(root: Path) -> Path:
    manifest = {
        "schema_version": 1,
        "manifest_kind": "coding_pilot",
        "dataset_id": "test-coding-pilot",
        "dataset_revision": "test-v1",
        "storage_policy": "Raw audio and reference transcripts are stored outside Git in controlled storage.",
        "samples": [
            _sample("ru_coding_terms_001", "ru_coding_terms", ["pytest"]),
            _sample("ru_short_001", "ru_short", []),
        ],
    }
    path = root / "public.json"
    path.write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
    return path


def _sample(sample_id: str, category: str, terms: list[str]) -> dict[str, object]:
    return {
        "sample_id": sample_id,
        "category": category,
        "duration_seconds": 1.0,
        "language_profile": "ru_coding_terms" if category == "ru_coding_terms" else "ru",
        "audio_label": f"controlled-audio:{sample_id}",
        "reference_label": f"controlled-reference:{sample_id}",
        "expected_english_terms": terms,
        "expected_coding_terms": [
            {"term_id": term, "canonical": term, "accepted_variants": [term], "expected_occurrences": 1, "require_latin": True}
            for term in terms
        ],
        "segmentation_policy_id": "seg-25s-no-overlap-v1",
    }


def _write_bindings(root: Path, public_manifest: Path) -> Path:
    (root / "audio").mkdir()
    (root / "references").mkdir()
    samples = []
    for sample_id in ("ru_coding_terms_001", "ru_short_001"):
        audio = root / "audio" / f"{sample_id}.wav"
        reference = root / "references" / f"{sample_id}.txt"
        _write_wav(audio)
        reference.write_text("синтетическая ссылка pytest\n", encoding="utf-8")
        samples.append(
            {
                "sample_id": sample_id,
                "audio_relative_path": f"audio/{sample_id}.wav",
                "audio_sha256": _sha256(audio),
                "reference_relative_path": f"references/{sample_id}.txt",
                "reference_sha256": _sha256(reference),
                "rights_status": "approved",
                "consent_status": "synthetic",
            }
        )
    bindings = {
        "schema_version": 1,
        "bindings_id": "test-bindings",
        "public_manifest_sha256": _sha256(public_manifest),
        "samples": samples,
    }
    path = root / "bindings.json"
    path.write_text(json.dumps(bindings, ensure_ascii=False), encoding="utf-8")
    return path


def _write_wav(path: Path) -> None:
    with wave.open(str(path), "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(16000)
        frame = struct.pack("<h", 0)
        audio.writeframes(frame * 1600)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


if __name__ == "__main__":
    unittest.main()
