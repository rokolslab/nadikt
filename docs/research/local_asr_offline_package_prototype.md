# Local ASR offline package prototype

## Status

- Date: 2026-07-27.
- Scope: package manifest -> checksum validation -> local path gate -> optional backend probe lifecycle -> safe summary.
- Real model packages: `NOT AVAILABLE` in this workspace.
- Real ASR load/warm-up/transcribe checks: `NOT RUN`.
- Final ASR model decision: `NOT DECIDED`.

This prototype does not download model weights, does not commit model weights and does not prove ASR quality. It proves the local package safety harness and fake-backed lifecycle semantics needed before real benchmark runs.

## Implemented Evidence

| Area | Evidence | Status |
|---|---|---|
| Repository protection | Root `.gitignore` rejects local packages, Hub caches, model weight extensions, raw audio, transcripts and generated ASR run artifacts | DONE |
| Manifest validation | `model_packs/model_inventory.example.json` uses syntactically valid dummy SHA-256 values | DONE |
| Package integrity | `benchmarks/asr/package_integrity.py` validates local path safety, root containment, critical file hashes and license marker warnings | DONE |
| Dry-run integration | `benchmarks/asr/offline_check.py` and `benchmarks/asr/dry_run.py` use the integrity validator instead of a parallel checker | DONE |
| Outcome model | `benchmarks/asr/probe_results.py` serializes safe phase/package outcomes and filters unsafe details | DONE |
| faster-whisper probe | `src/nadikt/infrastructure/asr/faster_whisper.py` accepts only a verified local CTranslate2 directory, uses CPU INT8 and consumes lazy `segments` | FAKE-BACKED TESTED |
| GigaAM probe | `src/nadikt/infrastructure/asr/gigaam.py` uses verified package directory as GigaAM SDK `download_root` cache and calls `load_model` only after package validation | SOURCE-INFORMED, FAKE-BACKED TESTED |
| Single-engine runner | `benchmarks/asr/local_model_probe.py` validates one package at a time and closes the current probe before loading another | FAKE-BACKED TESTED |
| Privacy regression | Contract tests cover Hub-name rejection, corrupted packages, optional import safety and log/stdout redaction | DONE |
| Coding-term dictionary privacy | Domain text rules, benchmark adapter and privacy audit tests cover safe repr/diagnostics without transcript, normalized text or dictionary payload | DONE |

## Commands Run

Dry-run manifest and package validation:

```bash
python3 -m benchmarks.asr.dry_run --dataset benchmarks/asr/datasets/dataset.example.json --models model_packs/model_inventory.example.json
```

Observed safe outcome on 2026-07-27:

- `result`: `passed_with_expected_missing_packages`.
- `package_outcomes`: `missing_package=4`.
- `network_attempted`: `false`.
- `privacy.canary_present`: `false`.
- `privacy.forbidden_payload_count`: `0`.

Local package probe dry-run with offline marker:

```bash
python3 -m benchmarks.asr.local_model_probe --models model_packs/model_inventory.example.json --dry-run --offline-required
```

Observed safe outcome on 2026-07-27:

- `result`: `passed_with_expected_missing_packages`.
- `package_outcomes`: `missing_package=4`.
- `offline.network_block_required`: `true`.
- `offline.network_attempted`: `false`.
- backend adapters were not instantiated because packages were missing.

Automated regression command:

```bash
python3 -B -m unittest discover -s tests
```

The regression suite uses synthetic metadata and fake SDK modules only. It does not require local model packages or installed optional ASR SDKs.

## Backend Findings

### faster-whisper

Confirmed by fake-backed adapter tests:

- adapter import does not import `faster_whisper` at module import time;
- load path uses `WhisperModel(str(local_dir), device="cpu", compute_type="int8")`;
- Hub identifiers such as `small` are rejected before SDK construction;
- `segments` generator is fully consumed inside the transcribe phase;
- transcript text is not returned in JSON/log-safe DTOs;
- close hook is called when present.

Real local CTranslate2 package load is `NOT RUN` until a local package exists outside Git and license/package metadata are verified.

### GigaAM

Source review of `salute-developers/GigaAM` `gigaam/__init__.py` found that `load_model` accepts `download_root` and `_download_file` returns an existing file without network download. That gives a concrete offline package strategy: prefill the package directory with the exact files the SDK expects in its cache layout, then call `load_model(<known model name>, download_root=<validated package dir>, device="cpu", use_flash=False, fp16_encoder=False)`.

Confirmed by fake-backed adapter tests:

- adapter import does not import `gigaam` at module import time;
- the adapter calls `gigaam.load_model` only inside the validated load path;
- `download_root` is the validated package directory, not a user-provided Hub/cache string;
- default candidate mapping uses `v3_e2e_ctc`, `v3_e2e_rnnt` and `multilingual_ctc`;
- `.transcribe` rejects segments longer than 25 seconds before backend call.

Real GigaAM local package loading is still `NOT RUN` until actual `.ckpt` and tokenizer files exist outside Git and the run is executed with blocked network. The risk is reduced from unknown API to unverified cache-style offline behavior.

## Safe Failures Covered

- Missing package -> `missing_package`, no network attempt.
- Traversal, absolute and Windows absolute package paths -> `invalid_package_path`.
- Symlink/root escape -> `invalid_package_path`.
- Missing critical file -> `missing_critical_file`.
- Invalid SHA-256 format -> manifest validation error or `invalid_checksum` at package check boundary.
- Checksum mismatch -> `checksum_mismatch`.
- License marker `TO_BE_VERIFIED` -> `license_not_verified` warning, not schema failure.
- Missing optional SDK -> `backend_unavailable` when backend load is actually attempted.
- Missing or incompatible GigaAM SDK load API -> `local_loading_unconfirmed`.

## Privacy Notes

Safe artifacts may contain only package IDs, candidate IDs, backend IDs, phase IDs, outcome codes, durations, checksum prefixes, boolean offline/privacy markers and aggregate counts.

The prototype intentionally does not print:

- audio path;
- transcript or hypothesis text;
- reference text;
- user dictionary entries;
- normalized text or coding-term dictionary canonical/spoken variants;
- clipboard payload;
- absolute user paths;
- tokens or URLs.

## Next Gates

1. Prepare real model packages outside Git with license notices, critical file checksums and verified local paths.
2. Run `benchmarks.asr.local_model_probe` with externally blocked network and clean Hub caches.
3. For faster-whisper, confirm local CTranslate2 load/warm-up/close on CPU INT8 before real quality benchmark.
4. For GigaAM, build a local cache-style package containing `<gigaam_model_name>.ckpt` and required tokenizer files, then run real load/warm-up/short-transcribe under blocked network.
5. Only after package/load gates pass, run the quality/resource benchmark from `local_asr_performance_benchmark_plan.md`.
