# Results template: local ASR performance benchmark

## Статус

- Дата шаблона: 2026-07-27.
- Фактические model runs: `NOT RUN`.
- Решение о модели: `NOT DECIDED`.

Этот документ предназначен для публикации результатов после запуска protocol из `docs/research/local_asr_performance_benchmark_plan.md`. Не выбирайте модель на основании пустого шаблона или dry-run без реальных packages.

## Coding Pilot Results — run_kind=coding_pilot

Status: `BLOCKED / NOT PUBLISHED`.

Required frozen pair: `gigaam-multilingual-220m` and `faster-whisper-small-int8` with at least three repeats each, separate non-scored warm-up, scored `ru_short` and `ru_coding_terms`, schema v2 aggregate, complete quality denominators and qualified offline evidence.

No publishable coding-pilot result is currently present. Historical file `benchmarks/asr/results/pilot-ru-coding-20260803T121525Z.json` was removed from the publishable results directory because it was schema-invalid legacy evidence: one candidate only, schema v1, `offline_evidence.status=NOT VERIFIED`, and no complete v2 metric matrix. It must not be used for ASR model choice or roadmap completion.

## Environment

| Поле | Значение |
|---|---|
| Run ID | TBD |
| Dataset revision | TBD |
| Nadikt revision | TBD |
| OS / environment | TBD |
| WSL kernel, если применимо | TBD |
| CPU | TBD |
| RAM | TBD |
| GPU | None / TBD |
| Power plan | TBD |
| Background load profile | TBD |
| Python version | TBD |
| Offline network policy | TBD |
| Measurement backend | TBD |

## Dataset Summary

| Category | Samples | Total duration | Notes |
|---|---:|---:|---|
| `ru_short` | TBD | TBD | TBD |
| `ru_en_terms` | TBD | TBD | TBD |
| `names_abbrev_numbers` | TBD | TBD | TBD |
| `pauses_noise` | TBD | TBD | TBD |
| `long_10m` | TBD | TBD | TBD |
| `boundary_cases` | TBD | TBD | TBD |

Reference transcripts and audio remain in controlled storage. This public report contains only aggregate metrics and anonymous sample IDs.

## Candidate Matrix

| Candidate | Backend | Package revision | License status | Offline load | Packaging notes |
|---|---|---|---|---|---|
| GigaAM v3 e2e CTC | GigaAM | TBD | TBD | NOT RUN | Verify local loading API |
| GigaAM v3 e2e RNN-T | GigaAM | TBD | TBD | NOT RUN | Verify local loading API |
| GigaAM Multilingual 220M | GigaAM | TBD | TBD | NOT RUN | Verify RU+English quality |
| Whisper small INT8 | faster-whisper / CTranslate2 | TBD | TBD | NOT RUN | Must use local CTranslate2 path |
| T-one optional | TBD | TBD | TBD | NOT RUN | Include only if offline package is proven |

## Performance Results

| Candidate | Cold load s | Warm-up s | First result s | RTF median | RTF p95 | Stop-to-text 60s | Stop-to-text 10m | Peak RSS MiB | CPU avg % | CPU max % |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| GigaAM v3 e2e CTC | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD |
| GigaAM v3 e2e RNN-T | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD |
| GigaAM Multilingual 220M | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD |
| Whisper small INT8 | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD |
| T-one optional | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD |

## Quality Results

| Candidate | WER ru | CER ru | English term accuracy | Latin preservation | Boundary pass rate | Long dictation outcome | Notes |
|---|---:|---:|---:|---:|---:|---|---|
| GigaAM v3 e2e CTC | TBD | TBD | TBD | TBD | TBD | NOT RUN | TBD |
| GigaAM v3 e2e RNN-T | TBD | TBD | TBD | TBD | TBD | NOT RUN | TBD |
| GigaAM Multilingual 220M | TBD | TBD | TBD | TBD | TBD | NOT RUN | TBD |
| Whisper small INT8 | TBD | TBD | TBD | TBD | TBD | NOT RUN | TBD |
| T-one optional | TBD | TBD | TBD | TBD | TBD | NOT RUN | TBD |

## Offline And Privacy Gates

| Gate | GigaAM CTC | GigaAM RNN-T | GigaAM 220M | Whisper small INT8 | T-one optional |
|---|---|---|---|---|---|
| Local package path only | NOT RUN | NOT RUN | NOT RUN | NOT RUN | NOT RUN |
| Missing package does not download | NOT RUN | NOT RUN | NOT RUN | NOT RUN | NOT RUN |
| Corrupted checksum rejected | NOT RUN | NOT RUN | NOT RUN | NOT RUN | NOT RUN |
| Network blocked run passes | NOT RUN | NOT RUN | NOT RUN | NOT RUN | NOT RUN |
| One model loaded at a time | NOT RUN | NOT RUN | NOT RUN | NOT RUN | NOT RUN |
| Logs contain no audio/transcript payload | NOT RUN | NOT RUN | NOT RUN | NOT RUN | NOT RUN |
| Result artifacts contain aggregates only | NOT RUN | NOT RUN | NOT RUN | NOT RUN | NOT RUN |

## Offline Package Prototype Snapshot

| Check | Result | Evidence |
|---|---|---|
| Example inventory schema/checksum format | PASS | `model_packs/model_inventory.example.json` validates with dummy SHA-256 values |
| Missing package dry-run | PASS | `missing_package=4`, `network_attempted=false` |
| Local probe dry-run with offline marker | PASS | `passed_with_expected_missing_packages`, `offline.network_block_required=true` |
| Corrupted synthetic package | PASS | Contract tests cover `checksum_mismatch` before backend factory creation |
| faster-whisper lifecycle | FAKE-BACKED PASS | CPU INT8 constructor, Hub reject and lazy segment consumption verified with fake SDK |
| GigaAM local loading | SOURCE-INFORMED / REAL RUN NOT RUN | Source review shows `download_root` cache-style loading can be probed; fake-backed tests verify adapter call shape |
| Real model load/warm-up/transcribe | NOT RUN | No local real packages in repository/workspace |

Details: `docs/research/local_asr_offline_package_prototype.md`.

## Decision Inputs

### Russian Mode

- Candidate selected: `TBD`.
- Required evidence: quality on `ru_short`, `names_abbrev_numbers`, `pauses_noise`, `long_10m`, resource fit on CPU-only machine, local package validation, license review.
- Current decision: `NOT DECIDED`.

### Russian + English Mode

- Candidate selected: `TBD`.
- Required evidence: English term accuracy, latin preservation, RU quality regression check, resource fit on CPU-only machine, local package validation, license review.
- Current decision: `NOT DECIDED`.

### Optional T-one

- Include in MVP: `TBD`.
- Required evidence: local package lifecycle, license review, resource and quality comparison.
- Current decision: `NOT DECIDED`.

## Limitations

- WSL2 Ubuntu measurements do not replace Windows 10/11 acceptance measurements.
- i3 12th generation development results do not redefine the MVP hardware baseline from ТЗ.
- Dry-run validates manifests and safe failure behavior only; it does not measure ASR quality.
- Offline package prototype validates lifecycle gates and fake-backed adapter behavior only; it does not prove real SDK package loading or ASR quality.
- Reference transcripts and raw audio are controlled data and are not published in this report.

## Recommendation

Do not fill this section until all required candidates have completed offline acceptance, quality metrics, resource measurements and privacy audit.

- Recommended Russian candidate: `TBD`.
- Recommended Russian + English candidate: `TBD`.
- Deferred risks: `TBD`.
- Follow-up Windows verification: `TBD`.
